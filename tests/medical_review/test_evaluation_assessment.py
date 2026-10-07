from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json
from test_evaluation_candidates import inputs
from test_evaluation_reference import reference_input

from research_project.medical_review import evaluation_assessment as assessment_module
from research_project.medical_review.evaluation import freeze_evaluation_plan, load_evaluation_plan
from research_project.medical_review.evaluation_assessment import (
    load_assessment,
    load_assessment_packets,
    prepare_assessment_packets,
    record_assessment,
    validate_assessment,
)
from research_project.medical_review.evaluation_candidates import freeze_candidates
from research_project.medical_review.evaluation_packets import (
    load_source_packets,
    prepare_source_packets,
)
from research_project.medical_review.evaluation_reference import freeze_reference_ledger


def prepared(workspace, *, two_cases=False, empty=False):
    repo, *_ = workspace
    packets, original_packets, data, path = inputs(workspace)
    if two_cases:
        plan_data = json.loads((path.parent / "plan.json").read_text())
        case = copy.deepcopy(plan_data["cases"][0])
        case["case_id"] = "second-case"
        plan_data["cases"].append(case)
        plan_path = write_json(path.parent / "two-case-plan.json", plan_data)
        plan_run = freeze_evaluation_plan(repo, plan_path)
        plan = load_evaluation_plan(repo, plan_run)
        reference = reference_input(plan)
        second = copy.deepcopy(reference["case_reviews"][0])
        second["case_id"] = "second-case"
        reference["case_reviews"].append(second)
        reference_path = write_json(path.parent / "two-case-reference.json", reference)
        reference_run = freeze_reference_ledger(repo, plan_run, reference_path)
        packets = prepare_source_packets(repo, reference_run)
        new_packets = load_source_packets(repo, packets)["packets"]
        attempts = []
        for i, packet in enumerate(new_packets["packets"]):
            original = next(
                p
                for p in original_packets["packets"]
                if (p["condition_id"], p["track"]) == (packet["condition_id"], packet["track"])
            )
            attempt = copy.deepcopy(
                next(a for a in data["attempts"] if a["packet_id"] == original["packet_id"])
            )
            output = attempt["outputs"][0]
            payload = json.loads((repo / output["output_reference"]).read_text())
            payload["paper_id"] = packet["packet_id"]
            output_path = write_json(path.parent / f"two-case-output-{i}.json", payload)
            output["output_reference"] = str(output_path.relative_to(repo))
            attempt.update(attempt_id=f"attempt-{i}", packet_id=packet["packet_id"])
            attempts.append(attempt)
        data.update(packets_record_id=new_packets["record_id"], attempts=attempts)
    if empty:
        for attempt in data["attempts"]:
            output_path = repo / attempt["outputs"][0]["output_reference"]
            payload = json.loads(output_path.read_text())
            payload["findings"] = []
            write_json(output_path, payload)
    # Explicit metadata sentinels must never become assessor inputs.
    data["attempts"][0]["runtime"] = {
        "provider": "PRIVATE-CONDITION-PROVIDER",
        "backend": "PRIVATE-CONDITION-BACKEND",
        "model": "PRIVATE-CONDITION-MODEL",
        "tools": ["source_read"],
    }
    write_json(path, data)
    candidate_run = freeze_candidates(repo, packets, path)
    blind_run = prepare_assessment_packets(repo, candidate_run)
    return blind_run, load_assessment_packets(repo, blind_run), path.parent / "assessment.json"


def assessment_input(loaded):
    views = loaded["packets"]["views"]
    versions = sorted({v for view in views for v in view["source_version_ids"]})
    view_ids = [v["view_id"] for v in views]
    items = loaded["packets"]["items"]
    case = loaded["candidates"]["packets"]["reference"]["plan"]["cases"][0]
    evidence = case["bundle"]["evidence"][0]
    judgment = {
        "disposition": "confirmed_concern",
        "issue_type": "assignment",
        "important": True,
        "serious_false_allegation": False,
        "source_attribution": "correct",
        "evidence": [
            {
                "source_version_id": evidence["source_version_id"],
                "locator": evidence["locator"],
                "raw_value": evidence["raw_value"],
            }
        ],
        "rationale": "Synthetic source-based judgment; not actual clinical adjudication.",
    }
    common = {
        "domain_qualifications": "Synthetic assessor fixture, not a real credential.",
        "date": "2026-10-06T15:00:00-06:00",
        "blinded_to_condition": True,
        "source_bytes_reviewed": True,
        "reviewed_source_version_ids": versions,
        "reviewed_view_ids": view_ids,
        "view_timings": [
            {"view_id": v, "verification_seconds": None, "revision_seconds": None} for v in view_ids
        ],
    }
    assessors = [
        {
            **copy.deepcopy(common),
            "assessor_id": f"reader-{i}",
            "human_identity": f"private-human-{i}",
            "judgments": [
                {**copy.deepcopy(judgment), "item_id": item["item_id"]} for item in items
            ],
        }
        for i in (1, 2)
    ]
    reference = loaded["candidates"]["packets"]["reference"]["ledger"]["reference_issues"][0]
    return {
        "schema_version": "medical_evaluation_assessment_input_v1",
        "assessment_packets_id": loaded["packets"]["record_id"],
        "supersedes_run_reference": None,
        "assessors": assessors,
        "adjudication": {
            **copy.deepcopy(common),
            "date": "2026-10-06T15:05:00-06:00",
            "human_identity": "private-human-adjudicator",
            "judgments": [
                {
                    **copy.deepcopy(judgment),
                    "item_id": item["item_id"],
                    "reference_ids": [reference["reference_id"]],
                    "assessor_ids": ["reader-1", "reader-2"],
                    "assessor_shortfall_reason": None,
                }
                for item in items
            ],
        },
    }


def test_blind_packets_preserve_source_access_claims_caveats_without_admin_metadata(workspace):
    repo, *_ = workspace
    run, loaded, _ = prepared(workspace)
    assert loaded["packets"]["blinding_verified"] is False
    assert len(loaded["packets"]["items"]) == 12
    for view in loaded["packets"]["views"]:
        root = run / view["workspace_reference"]
        data = json.loads((root / "assessment_packet.json").read_text())
        assert len(data["sources"]) == 2  # Full source truth for human assessment.
        assert data["review_coverage_available"] is False
        assert data["official_assessment"] is None
        text = "\n".join(p.read_text() for p in root.rglob("*") if p.is_file())
        for secret in [
            "PRIVATE-CONDITION-",
            "PRIVATE-REFERENCE-ANSWER",
            "human_identity",
            "original_reviewer",
            "strong_single_reviewer",
            "medical_adaptation",
        ]:
            assert secret not in text
        assert "Assignment unclear." in text
        assert "Not executed." in text  # Numerical proposal qualification retained.
        assert not (root / "instructions").exists()


def test_assessments_preserve_independent_disagreement_source_evidence_and_private_history(
    workspace,
):
    repo, *_ = workspace
    parent, loaded, path = prepared(workspace)
    data = assessment_input(loaded)
    data["assessors"][0]["view_timings"][0].update(verification_seconds=25.5, revision_seconds=0)
    data["assessors"][1]["judgments"][0].update(
        disposition="unresolved", source_attribution="unresolved"
    )
    write_json(path, data)
    run = record_assessment(repo, parent, path)
    record = load_assessment(repo, run)["assessment"]
    assert record["original"] == data
    assert record["record_type"] == "operator_attested_candidate_assessment"
    assert record["medical_performance_validated"] is False
    assert record["official_assessment"] is None
    assert record["judgments"][0]["evidence"][0]["evidence_id"]
    assert record["assessors"][1]["judgments"][0]["disposition"] == "unresolved"
    assert record["assessors"][0]["view_timings"][0]["verification_seconds"] == 25.5
    assert record["assessors"][0]["view_timings"][0]["revision_seconds"] == 0
    assert record["assessors"][1]["view_timings"][0]["revision_seconds"] is None
    assert not (repo / "data/private/inspect_sr").exists()
    before = (run / "processed/medical_evaluation/assessment.json").read_bytes()
    data["supersedes_run_reference"] = str(run.relative_to(repo))
    data["adjudication"]["date"] = "2026-10-06T15:10:00-06:00"
    data["adjudication"]["judgments"][0].update(
        disposition="optional_improvement", reference_ids=[]
    )
    write_json(path, data)
    revised = record_assessment(repo, parent, path)
    assert revised != run
    assert (
        load_assessment(repo, revised)["assessment"]["supersedes_record_id"] == record["record_id"]
    )
    assert (run / "processed/medical_evaluation/assessment.json").read_bytes() == before


def test_assessment_validation_rejects_missing_accounting_evidence_authority_and_blinding(
    workspace,
):
    _, loaded, _ = prepared(workspace)
    baseline = assessment_input(loaded)
    changes = [
        lambda x: x["adjudication"]["judgments"].pop(),
        lambda x: x["assessors"][0]["judgments"].pop(),
        lambda x: x["assessors"][0].update(blinded_to_condition=False),
        lambda x: x["adjudication"]["judgments"][0].update(reference_ids=["other-case-reference"]),
        lambda x: x["adjudication"]["judgments"][0].update(evidence=[]),
        lambda x: x["adjudication"].update(official_assessment="pass"),
        lambda x: x["assessors"][1].update(human_identity=x["assessors"][0]["human_identity"]),
        lambda x: x["assessors"][0]["view_timings"].pop(),
        lambda x: x["assessors"][0]["view_timings"][0].update(verification_seconds=-1),
        lambda x: x["assessors"][0]["view_timings"][0].update(revision_seconds=True),
        lambda x: x["assessors"][0]["view_timings"][0].update(revision_seconds=float("inf")),
    ]
    for change in changes:
        data = copy.deepcopy(baseline)
        change(data)
        with pytest.raises(ValueError):
            validate_assessment(loaded, data)


def test_single_assessor_shortfall_stays_explicit(workspace):
    _, loaded, _ = prepared(workspace)
    data = assessment_input(loaded)
    data["assessors"] = data["assessors"][:1]
    for judgment in data["adjudication"]["judgments"]:
        judgment.update(
            assessor_ids=["reader-1"],
            assessor_shortfall_reason="Synthetic unavailable second reader.",
        )
    record = validate_assessment(loaded, data)
    assert all(r["assessor_count"] == 1 for r in record["judgments"])
    assert record["medical_performance_validated"] is False


def test_reference_ids_are_case_local_without_shadowing(workspace):
    _, loaded, _ = prepared(workspace, two_cases=True)
    record = validate_assessment(loaded, assessment_input(loaded))
    assert len(record["judgments"]) == 24
    assert len({r["case_id"] for r in record["judgments"]}) == 2
    assert all(r["reference_ids"] == ["reference-assignment"] for r in record["judgments"])


def test_empty_candidates_never_establish_completed_reassuring_coverage(workspace):
    _, loaded, _ = prepared(workspace, empty=True)
    record = validate_assessment(loaded, assessment_input(loaded))
    assert record["judgments"] == []
    assert len(record["empty_views"]) == 6
    assert record["review_coverage_available"] is False
    assert record["medical_performance_validated"] is False


def test_blind_workspace_drift_cannot_be_reused(workspace):
    repo, *_ = workspace
    run, loaded, _ = prepared(workspace)
    root = run / loaded["packets"]["views"][0]["workspace_reference"]
    root.chmod(0o755)
    (root / "unexpected-admin.json").write_text('{"condition":"hidden"}')
    root.chmod(0o555)
    with pytest.raises(ValueError, match="inventory|artifact"):
        load_assessment_packets(repo, run)


def test_source_drift_preserves_failed_packet_attempt_without_publishing(workspace, monkeypatch):
    repo, *_ = workspace
    _, loaded, _ = prepared(workspace)
    candidates = loaded["candidates"]["run_root"]
    source = (
        repo
        / loaded["candidates"]["packets"]["reference"]["plan"]["cases"][0]["bundle"]["documents"][
            0
        ]["path"]
    )
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    original_write = assessment_module._write

    def drift(run, manifest, reference, raw):
        original_write(run, manifest, reference, raw)
        if reference.endswith("assessment_packet.json"):
            source.write_bytes(source.read_bytes() + b" changed source")

    monkeypatch.setattr(assessment_module, "_write", drift)
    with pytest.raises(ValueError):
        prepare_assessment_packets(repo, candidates)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    manifest = new.pop()
    assert json.loads(manifest.read_text())["status"] == "failed"
    assert not (manifest.parent / "processed/medical_evaluation/assessment_packets.json").exists()
    assert (manifest.parent / "generated/medical_evaluation/code/evaluation_assessment.py").exists()


def test_input_drift_preserves_raw_assessment_without_publishing(workspace, monkeypatch):
    repo, *_ = workspace
    parent, loaded, path = prepared(workspace)
    write_json(path, assessment_input(loaded))
    original = path.read_bytes()
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    original_write = assessment_module._write

    def drift(run, manifest, reference, raw):
        original_write(run, manifest, reference, raw)
        if reference.endswith("raw/assessment_input.json"):
            path.write_bytes(original + b" ")

    monkeypatch.setattr(assessment_module, "_write", drift)
    with pytest.raises(ValueError, match="changed while recording"):
        record_assessment(repo, parent, path)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    manifest = new.pop()
    assert json.loads(manifest.read_text())["status"] == "failed"
    assert not (manifest.parent / "processed/medical_evaluation/assessment.json").exists()
    assert (
        manifest.parent / "generated/medical_evaluation/raw/assessment_input.json"
    ).read_bytes() == original


def test_assessment_cli_has_no_live_or_official_judgment_flags(workspace):
    repo, *_ = workspace
    parent, loaded, path = prepared(workspace)
    write_json(path, assessment_input(loaded))
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/medical_review.py"),
            "evaluation-assess",
            "--packets-run",
            str(parent),
            "--input",
            str(path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        load_assessment(repo, Path(result.stdout.strip()))["manifest"]["effective_settings"][
            "allow_llm"
        ]
        is False
    )
