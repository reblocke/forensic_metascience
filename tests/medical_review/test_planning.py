from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.bundle import chronology_relation, load_bundle
from research_project.medical_review.context import build_study_context
from research_project.medical_review.preflight import structural_preflight
from research_project.medical_review.routing import build_review_plan

ROOT = Path(__file__).resolve().parents[2]


def test_context_keeps_reported_facts_interpretations_and_unknowns_separate(workspace):
    _, _, _, bundle, _ = workspace
    evidence = bundle["evidence"][0]["evidence_id"]
    supplied = {
        "synthetic": {
            "assignment": {
                "reported": {
                    "status": "known",
                    "value": "medical record number parity",
                    "evidence_ids": [evidence],
                },
                "interpretations": [
                    {
                        "value": "quasi-random assignment",
                        "evidence_ids": [evidence],
                        "rationale": "Deterministic allocation; inspect the source.",
                    }
                ],
                "preferred_design": {
                    "value": "concealed random allocation",
                    "rationale": "Reviewer proposal, not a reported fact.",
                },
            }
        }
    }
    context = build_study_context(bundle, supplied)
    field = context["studies"][0]["fields"]["assignment"]
    assert field["reported"]["value"] == "medical record number parity"
    assert field["interpretations"][0]["value"] == "quasi-random assignment"
    assert field["preferred_design"]["value"] == "concealed random allocation"
    assert context["studies"][0]["fields"]["estimand"]["reported"]["status"] == "unknown"
    assert build_study_context(bundle, supplied) == context
    assert "human_verified" not in json.dumps(context)


def test_asserted_context_requires_known_evidence(workspace):
    _, _, _, bundle, _ = workspace
    supplied = {
        "synthetic": {
            "estimand": {"reported": {"status": "known", "value": "ATE", "evidence_ids": []}}
        }
    }
    with pytest.raises(ValueError, match="evidence"):
        build_study_context(bundle, supplied)
    supplied["synthetic"]["estimand"]["reported"]["evidence_ids"] = ["fabricated"]
    with pytest.raises(ValueError, match="evidence"):
        build_study_context(bundle, supplied)


def test_mixed_aims_select_union_and_preserve_unsupported_component(workspace):
    _, _, _, bundle, _ = workspace
    context = build_study_context(bundle)
    plan = build_review_plan(
        bundle,
        context,
        ["clinical_trial", "prediction_model", "systematic_review_meta_analysis"],
        ROOT,
    )
    ids = {row["check_id"] for row in plan["checks"]}
    assert {"trial.assignment", "prediction.leakage", "core.claim_evidence"} <= ids
    assert "systematic_review_meta_analysis" in plan["unsupported_profiles"]
    assert plan["full_coverage"] is False
    assert len(plan["checks"]) == len(
        {(r["check_id"], r["study_id"], r["comparison_id"]) for r in plan["checks"]}
    )
    assert all(row["execution"] == "not_requested" for row in plan["checks"])
    assert plan["model_calls"] == 0


def test_unknown_classification_is_unresolved_and_does_not_skip_profiles(workspace):
    _, _, _, bundle, _ = workspace
    plan = build_review_plan(bundle, build_study_context(bundle), None, ROOT)
    assert plan["routing_status"] == "unresolved"
    assert set(plan["selected_profiles"]) == {
        "clinical_trial",
        "observational_rwd",
        "diagnostic_accuracy",
        "prediction_model",
    }
    assert {
        "trial.assignment",
        "observational.time_zero",
        "diagnosis.reference_standard",
        "prediction.leakage",
    } <= {c["check_id"] for c in plan["checks"]}
    assert not any(c["applicability"] == "not_applicable" for c in plan["checks"])


@pytest.mark.parametrize(
    ("profiles", "required", "excluded"),
    [
        (
            None,
            {
                "trial.assignment",
                "observational.time_zero",
                "diagnosis.reference_standard",
                "prediction.leakage",
            },
            set(),
        ),
        (
            ["clinical_trial"],
            {"trial.assignment"},
            {"observational.time_zero", "diagnosis.reference_standard", "prediction.leakage"},
        ),
        (
            ["clinical_trial", "prediction_model"],
            {"trial.assignment", "prediction.leakage"},
            {"observational.time_zero", "diagnosis.reference_standard"},
        ),
        (
            ["other"],
            {
                "trial.assignment",
                "observational.time_zero",
                "diagnosis.reference_standard",
                "prediction.leakage",
            },
            set(),
        ),
    ],
)
def test_empty_comparison_profiles_inherit_the_same_scope_as_omitted_profiles(
    workspace, profiles, required, excluded
):
    _, _, _, bundle, _ = workspace
    bundle["planned_checks"] = []
    bundle["comparisons"] = [{"comparison_id": "unresolved-aim", "study_id": "synthetic"}]
    omitted = build_review_plan(bundle, build_study_context(bundle), profiles, ROOT)
    bundle["comparisons"][0]["profile_ids"] = []
    empty = build_review_plan(bundle, build_study_context(bundle), profiles, ROOT)
    assert empty["checks"] == omitted["checks"]
    assert empty["selected_profiles"] == omitted["selected_profiles"]
    assert empty["unsupported_profiles"] == omitted["unsupported_profiles"]
    ids = {row["check_id"] for row in empty["checks"]}
    assert required <= ids and not excluded.intersection(ids)
    assert all(row["comparison_id"] == "unresolved-aim" for row in empty["checks"])
    assert all(row["applicability"] == "unknown" for row in empty["checks"])


def test_empty_profile_fallback_does_not_broaden_an_explicit_neighbor(workspace):
    _, _, _, bundle, _ = workspace
    bundle["comparisons"] = [
        {
            "comparison_id": "trial-effect",
            "study_id": "synthetic",
            "profile_ids": ["clinical_trial"],
        },
        {"comparison_id": "unspecified-aim", "study_id": "synthetic", "profile_ids": []},
    ]
    plan = build_review_plan(
        bundle, build_study_context(bundle), ["clinical_trial", "prediction_model"], ROOT
    )
    trial = {r["check_id"] for r in plan["checks"] if r["comparison_id"] == "trial-effect"}
    unspecified = {r["check_id"] for r in plan["checks"] if r["comparison_id"] == "unspecified-aim"}
    assert "trial.assignment" in trial and "prediction.leakage" not in trial
    assert {"trial.assignment", "prediction.leakage"} <= unspecified
    assert not {"observational.time_zero", "diagnosis.reference_standard"}.intersection(unspecified)


def test_missing_sap_prevents_prespecification_verification(workspace):
    _, _, _, bundle, _ = workspace
    plan = build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], ROOT)
    check = next(c for c in plan["checks"] if c["check_id"] == "trial.prespecification")
    assert check["required_source_gaps"]
    assert check["verification_available"] is False
    assert check["assessment"] == "cannot_verify"
    assert check["execution"] == "not_requested"


def test_guideline_assertions_remain_disabled_without_approved_pack(workspace):
    _, _, _, bundle, _ = workspace
    plan = build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], ROOT)
    assert plan["guidance_status"] == "unavailable"
    assert plan["enabled_guideline_claims"] == []
    assert all(not c["guideline_claims_enabled"] for c in plan["checks"])


def test_date_precision_cannot_establish_unsupported_chronology():
    assert (
        chronology_relation(
            {"date": "2020", "date_precision": "year"},
            {"date": "2020-03-10", "date_precision": "day"},
        )
        == "overlapping_precision"
    )
    assert (
        chronology_relation(
            {"date": "2019", "date_precision": "year"},
            {"date": "2020-03", "date_precision": "month"},
        )
        == "before"
    )
    assert (
        chronology_relation(
            {"date": None, "date_precision": "unknown"},
            {"date": "2020-03", "date_precision": "month"},
        )
        == "unknown"
    )
    with pytest.raises(ValueError, match="date|precision"):
        chronology_relation(
            {"date": "2020-03-10", "date_precision": "year"},
            {"date": None, "date_precision": "unknown"},
        )


def test_source_correction_retains_two_versions_and_unresolved_alias(workspace):
    import hashlib

    from research_project.inspect_sr.records import source_version_id

    repo, bundle_path, _, bundle, _ = workspace
    old = bundle["documents"][0]
    corrected = copy.deepcopy(old)
    path = (repo / old["path"]).with_name("main-corrected.txt")
    path.write_text("Corrected allocation description.", encoding="utf-8")
    corrected["path"] = str(path.relative_to(repo))
    corrected["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    corrected["source_version_id"] = source_version_id(corrected["source_id"], corrected["sha256"])
    corrected["role"] = "correction"
    corrected["supersedes_source_version_id"] = old["source_version_id"]
    bundle["documents"].append(corrected)
    bundle["revision"] = 2
    write_json(bundle_path, bundle)
    loaded, _ = load_bundle(repo, bundle_path)
    assert len(loaded["documents"]) == 2
    assert (repo / old["path"]).read_text().startswith("Random assignment")


def test_text_preflight_records_checked_and_unsupported_properties(workspace):
    repo, _, _, bundle, _ = workspace
    result = structural_preflight(repo, bundle)
    source = result["sources"][0]
    assert source["source_version_id"] == bundle["documents"][0]["source_version_id"]
    assert source["extraction_status"] == "completed"
    assert source["pages"][0]["text"].startswith("Random assignment")
    assert source["visual_inspection"] == "not_performed"
    assert source["properties"]["table_structure"] == "unsupported"
    assert source["properties"]["signs_units_formulas"] == "unverified"
    assert source["source_fidelity_verified"] is False


def test_empty_pdf_is_extraction_shortfall_not_a_manuscript_defect(workspace):
    import hashlib

    from pypdf import PdfWriter

    from research_project.inspect_sr.records import source_version_id

    repo, _, _, bundle, _ = workspace
    path = repo / "data/private/medical_reviews/synthetic/sources/blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    with path.open("wb") as stream:
        writer.write(stream)
    doc = copy.deepcopy(bundle["documents"][0])
    doc["path"] = str(path.relative_to(repo))
    doc["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    doc["source_version_id"] = source_version_id(doc["source_id"], doc["sha256"])
    bundle["documents"] = [doc]
    bundle["evidence"] = []
    result = structural_preflight(repo, bundle)
    source = result["sources"][0]
    assert source["extraction_status"] == "partial"
    assert source["page_count"] == 1 and source["pages_with_text"] == 0
    assert source["manuscript_defect"] is None
    assert source["source_fidelity_verified"] is False


def test_comparison_scopes_are_not_collapsed(workspace):
    _, _, _, bundle, _ = workspace
    bundle["comparisons"] = [
        {"comparison_id": "trial-effect", "study_id": "synthetic"},
        {"comparison_id": "prognostic-model", "study_id": "synthetic"},
    ]
    plan = build_review_plan(
        bundle, build_study_context(bundle), ["clinical_trial", "prediction_model"], ROOT
    )
    scopes = {row["comparison_id"] for row in plan["checks"]}
    assert scopes == {"trial-effect", "prognostic-model"}


def test_context_rejects_known_fact_with_unreviewed_study_mapping(workspace):
    _, _, _, bundle, _ = workspace
    bundle["studies"].append({"study_id": "second", "trial_id": None})
    bundle["reports"][0]["study_ids"] = ["synthetic", "second"]
    bundle["reports"][0]["mapping_reviewed"] = False
    supplied = {
        "synthetic": {
            "assignment": {
                "reported": {
                    "status": "known",
                    "value": "randomized",
                    "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
                }
            }
        }
    }
    with pytest.raises(ValueError, match="scope|mapping"):
        build_study_context(bundle, supplied)


def test_protocol_planning_explicitly_limits_results_questions(workspace):
    _, _, _, bundle, _ = workspace
    plan = build_review_plan(
        bundle, build_study_context(bundle), ["protocol", "clinical_trial"], ROOT
    )
    assert all(row["review_stage"] == "protocol" for row in plan["checks"])
    assert all("observed results" in row["stage_scope_reason"] for row in plan["checks"])


def test_comparisons_have_independent_reconstruction_and_profile_routes(workspace):
    _, _, _, bundle, _ = workspace
    bundle["comparisons"] = [
        {
            "comparison_id": "trial-effect",
            "study_id": "synthetic",
            "profile_ids": ["clinical_trial"],
        },
        {
            "comparison_id": "risk-model",
            "study_id": "synthetic",
            "profile_ids": ["prediction_model"],
        },
    ]
    context = build_study_context(bundle)
    assert {r["comparison_id"] for r in context["comparisons"]} == {"trial-effect", "risk-model"}
    assert all(
        r["fields"]["estimand"]["reported"]["status"] == "unknown" for r in context["comparisons"]
    )
    plan = build_review_plan(bundle, context, ["clinical_trial", "prediction_model"], ROOT)
    assert not any(
        c["check_id"] == "trial.assignment" and c["comparison_id"] == "risk-model"
        for c in plan["checks"]
    )
    assert not any(
        c["check_id"] == "prediction.leakage" and c["comparison_id"] == "trial-effect"
        for c in plan["checks"]
    )


def test_changed_prompt_hash_refuses_planning(workspace):
    repo, _, _, bundle, _ = workspace
    prompt = repo / "prompts/medical_review/shared_evidence.txt"
    prompt.write_text("tampered prompt", encoding="utf-8")
    with pytest.raises(ValueError, match="prompt|hash"):
        build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)


def test_unapproved_guidance_flags_cannot_enable_guideline_claims(workspace):
    repo, _, _, bundle, _ = workspace
    path = repo / "config/medical_review/guidance_registry.json"
    guidance = json.loads(path.read_text())
    guidance["packs"][0]["approved"] = True
    guidance["packs"][0]["available"] = True
    write_json(path, guidance)
    with pytest.raises(ValueError, match="verified sources"):
        build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)


def test_unresolved_comparison_uses_profile_union(workspace):
    _, _, _, bundle, _ = workspace
    bundle["comparisons"] = [
        {"comparison_id": "unclear-aim", "study_id": "synthetic", "profile_ids": ["other"]}
    ]
    plan = build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], ROOT)
    assert {"trial.assignment", "prediction.leakage", "diagnosis.reference_standard"} <= {
        c["check_id"] for c in plan["checks"]
    }
    assert all(c["applicability"] == "unknown" for c in plan["checks"])


def test_comparison_cannot_borrow_required_source_from_other_report(workspace):
    repo, _, _, bundle, _ = workspace
    first = bundle["reports"][0]["report_id"]
    bundle["reports"].append({"report_id": "other-report", "study_ids": ["synthetic"]})
    supplement = copy.deepcopy(bundle["documents"][0])
    supplement["role"] = "sap"
    supplement["report_ids"] = ["other-report"]
    bundle["documents"].append(supplement)
    bundle["comparisons"] = [
        {
            "comparison_id": "trial-effect",
            "study_id": "synthetic",
            "report_ids": [first],
            "profile_ids": ["clinical_trial"],
        }
    ]
    plan = build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)
    check = next(c for c in plan["checks"] if c["check_id"] == "trial.prespecification")
    assert check["required_source_gaps"]
    assert check["verification_available"] is False


def test_planned_override_cannot_silently_disappear(workspace):
    repo, _, _, bundle, _ = workspace
    bundle["planned_checks"].append(
        {
            "check_id": "invented.check",
            "study_id": "synthetic",
            "comparison_id": None,
            "applicability": "applicable",
            "rationale": "Operator requested this check.",
        }
    )
    with pytest.raises(ValueError, match="planned|catalogue|scope"):
        build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)


def test_text_source_has_no_invented_page_count(workspace):
    repo, _, _, bundle, _ = workspace
    source = structural_preflight(repo, bundle)["sources"][0]
    assert source["page_count"] is None
    assert source["pages_with_text"] is None
    assert source["extracted_units"] == 1


def test_specialist_interpretation_cannot_cite_another_study(workspace):
    _, _, _, bundle, _ = workspace
    bundle["studies"].append({"study_id": "unrelated"})
    fields = {
        "unrelated": {
            "assignment": {
                "interpretations": [
                    {
                        "value": "random assignment",
                        "rationale": "Proposed interpretation.",
                        "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
                    }
                ]
            }
        }
    }
    with pytest.raises(ValueError, match="scope|mapping"):
        build_study_context(bundle, fields)
