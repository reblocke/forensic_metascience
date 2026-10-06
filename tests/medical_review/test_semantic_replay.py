"""Synthetic supplied-response orchestration; not model reasoning or medical qualification."""

from __future__ import annotations

import copy
import hashlib

import pytest
from support.medical_review_fixtures import write_json

from research_project.inspect_sr.records import evidence_id, source_version_id
from research_project.medical_review.audit import load_dossier, verify_review
from research_project.medical_review.bundle import chronology_relation
from research_project.medical_review.reporting import build_report_model, render_review
from research_project.medical_review.runner import run_review

CASES = [
    {
        "name": "time_zero",
        "profile": "observational_rwd",
        "check": "observational.time_zero",
        "field": "time_zero",
        "problem": (
            "Follow-up begins on day 0; exposed participants are those who survive "
            "to start treatment during days 1 to 30."
        ),
        "control": (
            "Eligibility, treatment initiation or noninitiation, and follow-up "
            "begin on the same day 0 for both strategies."
        ),
        "concern": (
            "Post-baseline exposure classification requires survival until initiation, "
            "creating guaranteed survival time for that classification."
        ),
        "repair": (
            "Align eligibility, strategy assignment and follow-up at a justified time zero; "
            "inspect the actual design rather than presume a bias direction."
        ),
        "safeguard": "specific mechanism",
    },
    {
        "name": "subgroups",
        "profile": "clinical_trial",
        "check": "inference.subgroups",
        "field": "effect_scale",
        "problem": (
            "Risk ratios are 0.75 (95% CI 0.55 to 1.02) and 0.80 (0.65 to 0.98). "
            "Benefit differs by subgroup solely because one interval crosses 1; "
            "no interaction evidence is supplied."
        ),
        "control": (
            "Risk ratios are 0.75 (95% CI 0.55 to 1.02) and 0.80 (0.65 to 0.98). "
            "Different null crossings do not establish a subgroup difference; "
            "no interaction claim is made."
        ),
        "concern": (
            "Different null crossings do not establish effect heterogeneity "
            "without appropriate interaction and scale evidence."
        ),
        "repair": (
            "Remove the unsupported subgroup-difference claim or supply a justified "
            "interaction analysis; do not infer it from separate significance tests."
        ),
        "safeguard": "Different null crossings",
    },
    {
        "name": "precise_nonsignificance",
        "profile": "clinical_trial",
        "check": "inference.effects",
        "field": "effect_scale",
        "problem": (
            "Risk difference is 0.001 (95% CI -0.002 to 0.004); "
            "nonsignificance proves exact equality."
        ),
        "control": (
            "Risk difference is 0.001 (95% CI -0.002 to 0.004). The precise estimate "
            "is reported without claiming exact equality, clinical equivalence "
            "or automatic lack of information."
        ),
        "concern": "Nonsignificance alone does not prove exact equality or equivalence.",
        "repair": (
            "Interpret the effect and interval without demanding post-hoc power "
            "or automatically calling this precise result underpowered."
        ),
        "safeguard": "may be informative when precise",
    },
    {
        "name": "development_model",
        "profile": "prediction_model",
        "check": "prediction.benefit",
        "field": "development_validation_setting",
        "problem": (
            "This development model has internally validated AUROC 0.90, "
            "which alone proves improved patient outcomes from routine deployment."
        ),
        "control": (
            "This exploratory development model has internally validated AUROC 0.90. "
            "It makes no deployment-benefit claim and identifies future utility "
            "evaluation as separate work."
        ),
        "concern": (
            "Internal discrimination alone does not establish deployment benefit "
            "or clinical utility."
        ),
        "repair": (
            "Limit the clinical-benefit claim to the development evidence; "
            "a deployment trial is not compulsory for the stated development aim."
        ),
        "safeguard": "development study need not",
    },
    {
        "name": "harms",
        "profile": "clinical_trial",
        "check": "harms.ascertainment",
        "field": "outcome_measurement",
        "problem": (
            "Two recorded adverse events occurred in each group. Follow-up harms "
            "interviews were missing for 58% of participants; "
            "equal recorded counts establish safety."
        ),
        "control": (
            "Two recorded adverse events occurred in each group. Follow-up harms "
            "interviews were missing for 58% of participants; "
            "these counts cannot establish safety."
        ),
        "concern": (
            "Limited harms ascertainment prevents reassurance from similar recorded event counts."
        ),
        "repair": (
            "Report ascertainment and missingness, and qualify the safety interpretation; "
            "missing interviews are not negative events."
        ),
        "safeguard": "limited ascertainment",
    },
]


def add_source(repo, bundle, name, text, *, role="manuscript", date=None, source_id=None):
    """Stage a new immutable synthetic source before any review is created."""
    path = repo / f"data/private/medical_reviews/synthetic/sources/{name}.txt"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    doc = copy.deepcopy(bundle["documents"][0])
    doc.update(
        source_id=source_id or name,
        role=role,
        path=str(path.relative_to(repo)),
        sha256=digest,
        upstream_paths=[f"inputs/{name}.txt"],
        date=date,
        date_precision="day" if date else "unknown",
    )
    doc["source_version_id"] = source_version_id(doc["source_id"], digest)
    locator = f"section={name};paragraph=1"
    parser = doc["parser"]
    ev = {
        "evidence_id": evidence_id(
            doc["source_version_id"], locator, text, parser["id"], parser["version"]
        ),
        "source_version_id": doc["source_version_id"],
        "locator": locator,
        "raw_value": text,
        "parser": parser,
        "parsed_path": doc["path"],
        "parsed_sha256": digest,
        "page_index": None,
        "upstream_page": None,
        "page_label": None,
        "section": name,
        "visual_inspected": False,
    }
    bundle["documents"].append(doc)
    bundle["evidence"].append(ev)
    return doc, ev


def finding_for(upstream, doc, ev, concern, repair):
    finding = copy.deepcopy(upstream["findings"][0])
    finding.update(
        finding_summary=concern,
        claim_text=ev["raw_value"],
        suggested_fix=repair,
        evidence_summary=ev["raw_value"],
    )
    finding["location"].update(
        page=None, page_label=None, section=ev["section"], text_quote=ev["raw_value"]
    )
    finding["source_objects"][0].update(
        path=doc["upstream_paths"][0],
        page=None,
        page_label=None,
        section=ev["section"],
        text_quote=ev["raw_value"],
    )
    finding["claim_evidence_links"][0].update(claim_text=ev["raw_value"])
    finding["claim_evidence_links"][0]["note"] = (
        "Synthetic supplied-response link; not independently verified."
    )
    finding["numeric_check"] = None
    return finding


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
@pytest.mark.parametrize("variant", ["problem", "control"])
def test_paired_supplied_responses_retain_scope_and_do_not_invent_control_concerns(
    workspace, case, variant
):
    repo, bundle_path, incoming, bundle, upstream = workspace
    doc, ev = add_source(repo, bundle, case["name"], case[variant])
    bundle["planned_checks"] = []
    bundle["profile_ids"] = [case["profile"]]
    bundle["context_fields"] = {
        "synthetic": {
            case["field"]: {
                "reported": {
                    "status": "known",
                    "value": case[variant],
                    "evidence_ids": [ev["evidence_id"]],
                }
            }
        }
    }
    finding = finding_for(upstream, doc, ev, case["concern"], case["repair"])
    upstream["findings"] = [finding] if variant == "problem" else []
    upstream["summary"] = "Synthetic supplied-response replay; no model reasoning evaluated."
    write_json(bundle_path, bundle)
    write_json(incoming, upstream)
    attempt = run_review(repo, bundle_path, backend="replay", input_path=incoming)
    dossier = load_dossier(repo, attempt)
    model = build_report_model(repo, dossier)
    check = next(c for c in model["review_plan"]["checks"] if c["check_id"] == case["check"])
    assert case["safeguard"] in check["safeguard"]
    field = model["study_context"]["studies"][0]["fields"][case["field"]]
    assert field["reported"]["value"] == case[variant]
    assert len(model["proposals"]) == (1 if variant == "problem" else 0)
    if variant == "problem":
        proposal = model["proposals"][0]
        assert proposal["original"] == finding
        assert proposal["evidence_links"][0]["evidence_id"] == ev["evidence_id"]
        assert proposal["bias_direction"] == "unknown"
        assert model["proposal_statuses"][0]["human_status"] == "pending"
    assert model["review_complete"] is False and model["review_coverage_available"] is False
    assert model["official_assessment"] is None and model["synthesis_disposition"] is None
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.parametrize("available", [False, True], ids=["missing-amendment", "dated-amendment"])
def test_dated_amendment_and_footnote_demote_supplied_criticism_without_erasing_history(
    workspace, available
):
    repo, bundle_path, incoming, bundle, upstream = workspace
    bundle["planned_checks"] = []
    bundle["profile_ids"] = ["clinical_trial"]
    doc, ev = add_source(
        repo, bundle, "endpoint-report", "The primary endpoint was day-90 mortality."
    )
    old, old_ev = add_source(
        repo,
        bundle,
        "sap-original",
        "The original primary endpoint was day-30 mortality.",
        role="sap",
        date="2025-01-01",
        source_id="sap",
    )
    enrollment, _ = add_source(
        repo,
        bundle,
        "enrollment-history",
        "The first participant enrolled on 2025-03-01.",
        role="registry_history",
        date="2025-03-01",
    )
    counter_ids = []
    if available:
        amended, amended_ev = add_source(
            repo,
            bundle,
            "sap-amended",
            "The 2025-02-01 amendment changed the primary endpoint "
            "to day-90 mortality before enrollment.",
            role="sap",
            date="2025-02-01",
            source_id="sap",
        )
        amended["supersedes_source_version_id"] = old["source_version_id"]
        _, footnote = add_source(
            repo,
            bundle,
            "endpoint-footnote",
            "Supplement footnote: the reported day-90 endpoint follows "
            "the dated pre-enrollment SAP amendment.",
            role="supplement",
        )
        counter_ids = [amended_ev["evidence_id"], footnote["evidence_id"]]
        assert chronology_relation(old, amended) == "before"
        assert chronology_relation(amended, enrollment) == "before"
    else:
        missing = copy.deepcopy(old)
        missing.update(
            source_id="missing-amendment",
            source_version_id=None,
            availability="referenced_but_missing",
            path=None,
            sha256=None,
            date=None,
            date_precision="unknown",
            upstream_paths=[],
        )
        bundle["documents"].append(missing)
    finding = finding_for(
        upstream,
        doc,
        ev,
        "Apparent primary-endpoint change requires the dated amendment and footnote to interpret.",
        "Check the dated SAP versions and supplement before alleging selective reporting.",
    )
    upstream["findings"] = [finding]
    write_json(bundle_path, bundle)
    write_json(incoming, upstream)
    source = run_review(repo, bundle_path, backend="replay", input_path=incoming)
    dossier = load_dossier(repo, source)
    proposal = dossier["proposals"][0]
    frozen = (source / "run_manifest.json").read_bytes()
    path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/amendment.json",
        {
            "schema_version": "medical_verification_input_v1",
            "numeric_requests": [],
            "counterevidence": [
                {
                    "proposal_id": proposal["proposal_id"],
                    "disposition": "already_addressed" if available else "unresolved",
                    "reviewed_claim": proposal["claim"],
                    "strongest_alternative": (
                        "A pre-enrollment SAP amendment and "
                        "supplemental footnote explain the change."
                    )
                    if available
                    else "A dated amendment may explain the change, but it is unavailable.",
                    "rationale": (
                        "Synthetic supplied counterevidence; "
                        "source-semantic adjudication is not automated."
                    ),
                    "supporting_evidence_ids": [],
                    "contradicting_evidence_ids": counter_ids,
                    "missing_materials": [] if available else ["missing-amendment"],
                    "change_summary": "Demote the criticism while preserving both source versions."
                    if available
                    else (
                        "Keep unresolved; missing evidence is not a selective-reporting allegation."
                    ),
                    "model": "synthetic-supplied-response",
                    "backend": "offline-fixture",
                    "prompt_sha256": hashlib.sha256(
                        (repo / "prompts/medical_review/counterevidence.txt").read_bytes()
                    ).hexdigest(),
                }
            ],
        },
    )
    verified = verify_review(repo, source, path)
    report = render_review(repo, verified)
    model = build_report_model(repo, load_dossier(repo, report))
    assert model["proposals"][0] == proposal
    assert model["bundle"]["documents"] == bundle["documents"]
    assert (source / "run_manifest.json").read_bytes() == frozen
    status = model["proposal_statuses"][0]
    assert status["model_disposition"] == ("already_addressed" if available else "unresolved")
    assert status["human_status"] == "pending"
    assert model["verification"][0]["independently_human_confirmed"] is False
    if available:
        assert status["presentation"] == "demoted_unverified_proposal"
        assert old_ev in model["bundle"]["evidence"] and amended_ev in model["bundle"]["evidence"]
    else:
        assert model["verification"][0]["missing_materials"] == ["missing-amendment"]
        assert "missing-amendment" in model["rendered_markdown"]
    assert model["review_complete"] is False and model["official_assessment"] is None
    assert not (repo / "data/private/inspect_sr").exists()
