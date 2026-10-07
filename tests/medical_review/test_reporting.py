from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.audit import (
    load_dossier,
    verify_review,
)
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.reporting import build_report_model, render_review


def _set_reconstruction_scopes(workspace):
    _, bundle_path, _, bundle, _ = workspace
    bundle["studies"].append({"study_id": "second-study", "trial_id": None})
    bundle["reports"][0]["study_ids"].append("second-study")
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
        {
            "comparison_id": "followup-effect",
            "study_id": "second-study",
            "profile_ids": ["observational_rwd"],
        },
    ]
    scopes = [
        ("Study: synthetic", "Study one population", "Study one estimand"),
        ("Study: second-study", "Study two population", "Study two estimand"),
        (
            "Comparison: trial-effect (study: synthetic)",
            "Trial comparison population",
            "Trial comparison estimand",
        ),
        (
            "Comparison: risk-model (study: synthetic)",
            "Prediction comparison population",
            "Prediction comparison estimand",
        ),
        (
            "Comparison: followup-effect (study: second-study)",
            "Followup comparison population",
            "Followup comparison estimand",
        ),
    ]

    def fields(population, estimand):
        return {
            field: {
                "reported": {
                    "status": "known",
                    "value": value,
                    "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
                }
            }
            for field, value in (("target_population", population), ("estimand", estimand))
        }

    bundle["context_fields"] = {
        row["study_id"]: fields(*scope[1:])
        for row, scope in zip(bundle["studies"], scopes[:2], strict=True)
    }
    bundle["comparison_context_fields"] = {
        row["comparison_id"]: fields(*scope[1:])
        for row, scope in zip(bundle["comparisons"], scopes[2:], strict=True)
    }
    write_json(bundle_path, bundle)
    return scopes


def _assert_reconstruction_scopes(text, scopes):
    section = " ".join(text.split()).rsplit("Study reconstruction and unresolved gaps", 1)[1]
    section = section.split("Upstream qualifications", 1)[0]
    positions = [section.index(label) for label, _, _ in scopes]
    assert positions == sorted(positions)
    for index, (_, population, estimand) in enumerate(scopes):
        end = positions[index + 1] if index + 1 < len(scopes) else len(section)
        block = section[positions[index] : end]
        assert population in block and estimand in block
        assert "Unknown or not reconstructed" in block
        for other, (_, other_population, other_estimand) in enumerate(scopes):
            if other != index:
                assert other_population not in block and other_estimand not in block


def test_reconstruction_keeps_each_study_and_comparison_labeled(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    scopes = _set_reconstruction_scopes(workspace)
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    original = copy.deepcopy(dossier["study_context"])
    model = build_report_model(repo, dossier)
    _assert_reconstruction_scopes(model["rendered_markdown"], scopes)
    assert model["study_context"] == original == dossier["study_context"]


@pytest.mark.parametrize("kind", ["study", "comparison"])
@pytest.mark.parametrize("scope_id", ["scope-" + "a" * 58, "scope_<script>{{"])
def test_scope_labels_escape_and_wrap_ids_without_changing_context(workspace, kind, scope_id):
    repo, bundle_path, incoming, bundle, _ = workspace
    _set_reconstruction_scopes(workspace)
    if kind == "study":
        bundle["studies"][1]["study_id"] = scope_id
        bundle["reports"][0]["study_ids"][1] = scope_id
        bundle["comparisons"][2]["study_id"] = scope_id
        fields = bundle["context_fields"]
        fields[scope_id] = fields.pop("second-study")
    else:
        bundle["comparisons"][1]["comparison_id"] = scope_id
        fields = bundle["comparison_context_fields"]
        fields[scope_id] = fields.pop("risk-model")
    write_json(bundle_path, bundle)
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    original = copy.deepcopy(dossier["study_context"])
    model = build_report_model(repo, dossier)
    section = model["rendered_markdown"].split("## Study reconstruction and unresolved gaps", 1)[1]
    section = section.split("## Upstream qualifications", 1)[0]
    if "<script>" in scope_id:
        assert "<script>" not in section and "{{" not in section
        assert "&#60;script&#62;" in section and "&#123;&#123;" in section
    else:
        assert f"scope-{'a' * 26} {'a' * 32}" in section
        assert scope_id not in section
    assert scope_id in json.dumps(model["study_context"])
    assert model["study_context"] == original == dossier["study_context"]


def test_same_observation_groups_all_provenance_but_same_quote_different_issue_survives(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    first = import_reviewer(repo, bundle_path, incoming)
    dossier = load_dossier(repo, first)
    duplicate = copy.deepcopy(dossier["proposals"][0])
    duplicate["proposal_id"] = "synthetic-second-agent"
    duplicate["reviewer_role"] = "clinical"
    duplicate["origin"]["backend"] = "synthetic"
    duplicate["evidence_links"][0]["source_object_id"] = "second-agent-source-object"
    distinct = copy.deepcopy(duplicate)
    distinct["proposal_id"] = "synthetic-distinct-issue"
    distinct["normalized_concern"] = "A different outcome-definition question."
    dossier["proposals"].extend([duplicate, distinct])
    model = build_report_model(repo, dossier)
    groups = model["groups"]
    assert len(groups) == 2
    assert sorted(len(g["proposal_ids"]) for g in groups) == [1, 2]
    assert set(model["accounted_proposal_ids"]) == {p["proposal_id"] for p in dossier["proposals"]}
    assert model["agent_agreement_is_independent_evidence"] is False
    assert model["official_assessment"] is None and model["synthesis_disposition"] is None


def test_unverified_major_concern_and_caveat_survive_model_and_markdown(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    upstream["findings"][0]["finding_summary"] = "Major concern: allocation mechanism is unclear."
    upstream["findings"][0]["suggested_fix"] = (
        "Clarify allocation; MRN parity does not establish concealed random allocation."
    )
    upstream["notes"] = ["Critical caveat: a dated amendment may explain the apparent change."]
    write_json(incoming, upstream)
    source = import_reviewer(repo, bundle_path, incoming)
    model = build_report_model(repo, load_dossier(repo, source))
    markdown = model["rendered_markdown"]
    assert "Major concern" in markdown and "Critical caveat" in markdown
    assert "concealed random allocation" in markdown
    assert "unknown" in markdown.lower() or "unavailable" in markdown.lower()
    assert "pending" in markdown
    output = render_review(repo, source)
    stored = json.loads((output / "processed/medical_review/report_model.json").read_text())
    assert stored["proposals"] == model["proposals"]
    assert (output / "reports/medical_review/review.md").read_text() == stored["rendered_markdown"]
    assert not (output / "reports/medical_review/review.html").exists()
    assert not (repo / "data/private/inspect_sr").exists()


def test_report_demotes_counterevidence_without_erasing_original_and_never_finalizes_inspect(
    workspace,
):
    repo, bundle_path, incoming, bundle, _ = workspace
    source = import_reviewer(repo, bundle_path, incoming)
    proposal = load_dossier(repo, source)["proposals"][0]
    data = {
        "schema_version": "medical_verification_input_v1",
        "numeric_requests": [],
        "counterevidence": [
            {
                "proposal_id": proposal["proposal_id"],
                "disposition": "already_addressed",
                "reviewed_claim": proposal["claim"],
                "strongest_alternative": "Supplement provides the answer.",
                "rationale": "Read the cited footnote.",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [bundle["evidence"][0]["evidence_id"]],
                "missing_materials": [],
                "change_summary": "Demote criticism; retain historical original.",
                "model": None,
                "backend": None,
                "prompt_sha256": None,
            }
        ],
    }
    path = write_json(repo / "data/private/medical_reviews/synthetic/verification/pass.json", data)
    verified = verify_review(repo, source, path)
    model = build_report_model(repo, load_dossier(repo, verified))
    item = model["proposal_statuses"][0]
    assert item["model_disposition"] == "already_addressed"
    assert item["presentation"] == "demoted_unverified_proposal"
    assert item["human_status"] == "pending"
    assert model["proposals"][0] == proposal
    assert model["official_assessment"] is None and model["synthesis_disposition"] is None
    assert "Supplement provides the answer" in model["rendered_markdown"]


def test_empty_findings_does_not_render_reassuring_coverage(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    upstream["findings"] = []
    write_json(incoming, upstream)
    source = import_reviewer(repo, bundle_path, incoming)
    model = build_report_model(repo, load_dossier(repo, source))
    assert model["review_complete"] is False
    assert model["review_coverage_available"] is False
    assert "coverage remains unavailable" in model["rendered_markdown"].lower()
    assert model["coverage"] and all(c["inspected_units"] is None for c in model["coverage"])


def test_private_report_root_and_untrusted_active_content_are_constrained(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    upstream["notes"] = [
        '<script>alert(1)</script> {{< include /private/secret >}} `r system("evil")`'
    ]
    write_json(incoming, upstream)
    source = import_reviewer(repo, bundle_path, incoming)
    with pytest.raises(ValueError, match="private"):
        render_review(repo, source, output_root=repo / "reports")
    model = build_report_model(repo, load_dossier(repo, source))
    assert "<script>" not in model["rendered_markdown"]
    assert "{{<" not in model["rendered_markdown"]
    assert "`r system" not in model["rendered_markdown"]
    assert model["proposals"][0]["original"] == upstream["findings"][0]


def test_report_validator_refuses_caveat_removal_and_missing_group_members(workspace):
    from research_project.medical_review.reporting import validate_report_model

    repo, bundle_path, incoming, _, upstream = workspace
    upstream["notes"] = ["Critical caveat must remain visible."]
    write_json(incoming, upstream)
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    tampered = copy.deepcopy(model)
    tampered["upstream_metadata"]["notes"] = []
    with pytest.raises(ValueError, match="traceability"):
        validate_report_model(tampered, dossier)
    tampered = copy.deepcopy(model)
    tampered["groups"] = []
    with pytest.raises(ValueError, match="every|Every|group"):
        validate_report_model(tampered, dossier)
    for field in ("arithmetic_result_ids", "method_handoff_ids", "numeric_input_review_ids"):
        tampered = copy.deepcopy(model)
        del tampered["manual_adoption_packet"][field]
        with pytest.raises(ValueError, match="numerical traceability"):
            validate_report_model(tampered, dossier)
    validate_report_model(json.loads(json.dumps(model, sort_keys=True)), dossier)


def test_explicit_reporting_omission_and_optional_improvement_have_separate_sections(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    omission = upstream["findings"][0]
    omission["category"] = "reporting_gap"
    omission["finding_summary"] = "Synthetic reporting omission: allocation details unavailable."
    optional = copy.deepcopy(omission)
    optional.update(
        id="optional-2",
        issue_type="copyedit_issue",
        category="copyediting",
        finding_summary="Synthetic optional improvement: shorten a sentence.",
    )
    upstream["findings"].append(optional)
    write_json(incoming, upstream)
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    markdown = model["rendered_markdown"]
    omissions = markdown.split("## Reporting omissions\n")[1].split("## Optional improvements\n")[0]
    optional_section = markdown.split("## Optional improvements\n")[1].split(
        "## Numerical checks\n"
    )[0]
    assert "allocation details unavailable" in omissions
    assert "shorten a sentence" not in omissions
    assert "shorten a sentence" in optional_section
    assert model["proposals"][0]["original"] == omission
    assert all(s["human_status"] == "pending" for s in model["proposal_statuses"])
    assert model["official_assessment"] is None


def test_source_and_proposal_hashes_wrap_for_display_without_changing_machine_values(workspace):
    repo, bundle_path, incoming, bundle, _ = workspace
    dossier = load_dossier(repo, import_reviewer(repo, bundle_path, incoming))
    model = build_report_model(repo, dossier)
    original_hash = model["proposals"][0]["original_sha256"]
    assert len(original_hash) == 64
    assert original_hash not in model["rendered_markdown"]
    assert (original_hash[:32] + " " + original_hash[32:]) in model["rendered_markdown"]
    assert model["proposals"] == dossier["proposals"]
    assert model["bundle"] == bundle
    source_label_lines = [
        line for line in model["rendered_markdown"].splitlines() if "/ source version id:**" in line
    ]
    assert source_label_lines and all(line.endswith(":**") for line in source_label_lines)


def test_real_cli_verification_decision_and_private_markdown_lineage(workspace):
    import subprocess
    import sys

    from research_project.medical_review.audit import HUMAN_FIELDS

    repo, bundle_path, incoming, bundle, _ = workspace
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src/research_project", repo / "src/research_project")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")

    def invoke(operation, *arguments):
        result = subprocess.run(
            [sys.executable, str(repo / "scripts/medical_review.py"), operation, *arguments],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return Path(result.stdout.strip())

    run = invoke("import-reviewer", "--bundle", str(bundle_path), "--input", str(incoming))
    proposal = json.loads((run / "processed/medical_review/proposals.json").read_text())[0]
    verification = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/empty.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [],
        },
    )
    derived = invoke("verify", "--run", str(run), "--input", str(verification))
    e = bundle["evidence"][0]
    data = dict(
        schema_version="medical_human_disposition_input_v1",
        proposal_id=proposal["proposal_id"],
        disposition="unresolved",
        human_identity="synthetic-cli-reviewer",
        date="2026-10-06T12:00:00-06:00",
        rationale="Synthetic independent source review.",
        source_bytes_reviewed=True,
        locators_reviewed=True,
        supersedes=None,
        reviewed_evidence=[
            {
                "evidence_id": e["evidence_id"],
                "source_sha256": bundle["documents"][0]["sha256"],
                "locator": e["locator"],
                "raw_value": e["raw_value"],
            }
        ],
    )
    assert set(data) == HUMAN_FIELDS
    decision = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/human.json", data
    )
    human = invoke("decide", "--run", str(derived), "--input", str(decision))
    report = invoke("render", "--run", str(derived))
    model = json.loads((report / "processed/medical_review/report_model.json").read_text())
    assert model["proposal_statuses"][0]["human_status"] == "unresolved"
    assert model["human_history"][0]["disposition_id"] == human.stem
    assert model["manual_adoption_packet"]["automatic_adoption"] is False
    assert not (repo / "data/private/inspect_sr").exists()


def test_real_two_review_import_consolidation_keeps_provenance_and_human_origin(workspace):
    from research_project.medical_review.audit import consolidate_reviews, record_human_disposition

    repo, bundle_path, incoming, bundle, upstream = workspace
    first = import_reviewer(repo, bundle_path, incoming)
    upstream["reviewer"] = "clinical"
    upstream["findings"][0]["source_objects"][0]["id"] = "clinical-source"
    upstream["findings"][0]["claim_evidence_links"][0]["source_object_ids"] = ["clinical-source"]
    second_input = write_json(incoming.with_name("clinical.json"), upstream)
    second = import_reviewer(repo, bundle_path, second_input)
    frozen = [(p / "run_manifest.json").read_bytes() for p in (first, second)]
    combined = consolidate_reviews(repo, [first, second])
    dossier = load_dossier(repo, combined)
    model = build_report_model(repo, dossier)
    assert len(model["groups"]) == 1 and len(model["groups"][0]["proposal_ids"]) == 2
    assert len(model["proposals"]) == 2
    assert [(p / "run_manifest.json").read_bytes() for p in (first, second)] == frozen
    proposal = dossier["proposals"][1]
    e = bundle["evidence"][0]
    data = dict(
        schema_version="medical_human_disposition_input_v1",
        proposal_id=proposal["proposal_id"],
        disposition="unresolved",
        human_identity="synthetic-combined-reviewer",
        date="2026-10-06T12:00:00-06:00",
        rationale="Review the second original source-bound proposal.",
        source_bytes_reviewed=True,
        locators_reviewed=True,
        supersedes=None,
        reviewed_evidence=[
            {
                "evidence_id": e["evidence_id"],
                "source_sha256": bundle["documents"][0]["sha256"],
                "locator": e["locator"],
                "raw_value": e["raw_value"],
            }
        ],
    )
    path = record_human_disposition(repo, combined, data)
    record = json.loads(path.read_text())
    assert record["original_proposal_run_reference"] == str(second.relative_to(repo))
    assert record["original_run_id"] == second.name
    rendered = render_review(repo, combined)
    assert load_dossier(repo, rendered)["proposals"] == dossier["proposals"]
    with pytest.raises(ValueError, match="Nested consolidation"):
        consolidate_reviews(repo, [combined, first])
    with pytest.raises(ValueError, match="2–16"):
        consolidate_reviews(repo, [first] * 17)


def test_consolidation_refuses_duplicate_and_changed_bundle_context(workspace):
    from research_project.medical_review.audit import consolidate_reviews

    repo, bundle_path, incoming, bundle, _ = workspace
    first = import_reviewer(repo, bundle_path, incoming)
    with pytest.raises(ValueError, match="Duplicate"):
        consolidate_reviews(repo, [first, first])
    bundle["revision"] += 1
    write_json(bundle_path, bundle)
    changed = import_reviewer(repo, bundle_path, incoming)
    with pytest.raises(ValueError, match="identical bundle"):
        consolidate_reviews(repo, [first, changed])


@pytest.mark.report_integration
def test_medical_current_model_renders_major_concern_and_caveat_html_pdf(
    workspace, preserve_synthetic_artifact
):
    if not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Quarto is required for the medical report acceptance lane.")
        pytest.skip("Quarto unavailable; medical report acceptance remains open.")
    repo, bundle_path, incoming, bundle, upstream = workspace
    scopes = _set_reconstruction_scopes(workspace)
    (repo / "notebooks").mkdir()
    template = Path(__file__).resolve().parents[2] / "notebooks/medical_manuscript_review.qmd"
    shutil.copy(template, repo / "notebooks/medical_manuscript_review.qmd")
    upstream["findings"][0]["finding_summary"] = "Major concern: allocation mechanism is unclear."
    upstream["notes"] = [
        "Critical caveat: a dated amendment may explain the apparent change.",
        "<script>synthetic_active_canary()</script> {{< include /private/secret >}}",
    ]
    write_json(incoming, upstream)
    source = import_reviewer(repo, bundle_path, incoming)
    frozen_parent = (source / "run_manifest.json").read_bytes()
    from research_project.medical_review.records import content_hash

    proposal = load_dossier(repo, source)["proposals"][0]
    arithmetic_input = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/report-numbers.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [
                {
                    "schema_version": "medical_numeric_check_request_v1",
                    "run_id": proposal["run_id"],
                    "proposal_id": proposal["proposal_id"],
                    "study_id": "synthetic",
                    "comparison_id": None,
                    "bundle_sha256": content_hash(bundle),
                    "kind": "percentage",
                    "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
                    "population": "synthetic-unverified-transcription",
                    "horizon": "day-30",
                    "orientation": "event-risk",
                    "inputs": {"numerator": 1, "denominator": 2},
                    "reported_comparison": None,
                }
            ],
        },
    )
    verified = verify_review(repo, source, arithmetic_input)
    output = render_review(repo, verified, html=True, pdf=True)
    assert (source / "run_manifest.json").read_bytes() == frozen_parent
    # Historical report reads are explicit and do not mutate the original import.
    assert load_dossier(repo, output)["proposals"] == load_dossier(repo, source)["proposals"]
    html = (output / "reports/medical_review/review.html").read_text()
    from pypdf import PdfReader

    pdf_path = output / "reports/medical_review/review.pdf"
    pdf = " ".join(
        " ".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages).split()
    )
    import re
    from html import unescape

    _assert_reconstruction_scopes(unescape(re.sub(r"<[^>]+>", " ", html)), scopes)
    _assert_reconstruction_scopes(pdf, scopes)
    for text in ("Major concern", "Critical caveat", "pending", "coverage remains unavailable"):
        assert text in html and text in pdf
    for text in ("proposed_transcription", "qualified method result", "false"):
        assert text in html and text in pdf
    stored = json.loads((output / "processed/medical_review/report_model.json").read_text())
    href = stored["source_navigation"]["documents"][0]["href"]
    assert f'href="{href}"' in html
    source_targets = [
        str(annotation.get_object().get("/A", {}).get("/URI", ""))
        for page in PdfReader(pdf_path).pages
        for annotation in page.get("/Annots", [])
    ]
    assert href in source_targets
    assert "Open original source" in pdf
    assert stored["arithmetic_results"][0]["qualified_method_result"] is False
    assert stored["manual_adoption_packet"]["arithmetic_result_ids"] == [
        stored["arithmetic_results"][0]["result_id"]
    ]
    assert "<script>synthetic_active_canary()" not in html
    assert not (repo / "data/private/inspect_sr").exists()
    for fmt in ("md", "html", "pdf"):
        preserve_synthetic_artifact(
            f"medical-review.{fmt}", output / f"reports/medical_review/review.{fmt}"
        )
    preserve_synthetic_artifact(
        "medical-report-model.json", output / "processed/medical_review/report_model.json"
    )


@pytest.mark.report_integration
def test_actual_native_qualifications_and_blocked_coverage_survive_html_pdf(
    workspace, preserve_synthetic_artifact
):
    import csv
    import re

    from pypdf import PdfReader
    from support.medical_review_native import prepare_native_review

    rscript = shutil.which("Rscript")
    if not rscript or not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Actual R and Quarto are required for numerical handoff report acceptance.")
        pytest.skip("R/Quarto unavailable; native handoff rendering remains unverified.")
    repo, *_ = workspace
    source, numeric, output, root = prepare_native_review(workspace, rscript)
    (repo / "notebooks").mkdir()
    shutil.copy(root / "notebooks/medical_manuscript_review.qmd", repo / "notebooks")
    dossier = load_dossier(repo, source)
    with (output / "numeric_standardized_results_v2.csv").open() as stream:
        results = list(csv.DictReader(stream))
    requests = [
        {
            "schema_version": "medical_method_handoff_request_v1",
            "proposal_id": dossier["proposals"][0]["proposal_id"],
            "numeric_run_reference": str(numeric.relative_to(repo)),
            "receipt_artifact": "reports/numeric/numeric_method_receipts.csv",
            "result_artifact": "reports/numeric/numeric_standardized_results_v2.csv",
            "method_id": method,
            "result_ids": [r["result_id"] for r in results if r["method_id"] == method],
            "rationale": "Synthetic actual-R qualification rendering check.",
        }
        for method in ("scrutiny_grim_map", "statcheck", "scrutiny_rounding_bias")
    ]
    frozen = (output / "numeric_method_receipts.csv").read_bytes()
    input_path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/report-methods.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [],
            "method_handoffs": requests,
        },
    )
    verified = verify_review(repo, source, input_path)
    report = render_review(repo, verified, html=True, pdf=True)
    assert (output / "numeric_method_receipts.csv").read_bytes() == frozen
    model = json.loads((report / "processed/medical_review/report_model.json").read_text())
    assert load_dossier(repo, report)["method_handoffs"] == model["method_handoffs"]
    html = (report / "reports/medical_review/review.html").read_text()
    raw_pdf = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(report / "reports/medical_review/review.pdf").pages
    )
    # TeX may hyphenate long status values at a line boundary; exact JSON stays unchanged.
    pdf = " ".join(re.sub(r"(?<=\w)-\n(?=\w)", "", raw_pdf).split())
    for status in (
        "qualified_existing_result_reference",
        "unqualified_existing_result_reference",
        "captured_at_handoff",
        "blocked",
        "review reassurance",
        "pending",
    ):
        assert status in html and status in pdf
    assert model["method_handoffs"][-1]["receipt"]["n_evaluated"] == 0
    assert model["method_handoffs"][-1]["results"] == []
    assert all(h["review_reassurance"] is False for h in model["method_handoffs"])
    assert not (repo / "data/private/inspect_sr").exists()
    for fmt in ("html", "pdf"):
        preserve_synthetic_artifact(
            f"medical-native-review.{fmt}", report / f"reports/medical_review/review.{fmt}"
        )
    preserve_synthetic_artifact(
        "medical-native-report-model.json", report / "processed/medical_review/report_model.json"
    )
