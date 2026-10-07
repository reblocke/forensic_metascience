from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import create_workspace, write_json
from test_evaluation_assessment import assessment_input
from test_evaluation_candidates import inputs

from research_project.medical_review import evaluation_synthesis as synthesis_module
from research_project.medical_review.evaluation_assessment import (
    load_assessment_packets,
    prepare_assessment_packets,
    record_assessment,
)
from research_project.medical_review.evaluation_candidates import freeze_candidates
from research_project.medical_review.evaluation_synthesis import (
    load_synthesis,
    load_synthesis_packets,
    prepare_synthesis_packets,
    record_synthesis,
    validate_synthesis,
)


def prepared(workspace, *, empty_synthesis=False):
    repo, *_ = workspace
    packets, packet_record, data, path = inputs(workspace)
    conditions = {p["packet_id"]: p["condition_id"] for p in packet_record["packets"]}
    changed = False
    for i, attempt in enumerate(data["attempts"]):
        attempt["runtime"] = {
            "provider": "PRIVATE-CONDITION-PROVIDER",
            "backend": "PRIVATE-CONDITION-BACKEND",
            "model": "PRIVATE-CONDITION-MODEL",
            "tools": [],
        }
        reviewer_path = repo / attempt["outputs"][0]["output_reference"]
        payload = json.loads(reviewer_path.read_text())
        payload["notes"] = ["GLOBAL-NUMERIC-CAVEAT"]
        write_json(reviewer_path, payload)
        if conditions[attempt["packet_id"]] == "strong_single_reviewer":
            continue
        payload["findings"] = payload["findings"][:1]
        if not changed:
            payload["findings"][0]["numeric_check"]["recomputation_notes"] = (
                "All arithmetic confirmed."
            )
            changed = True
        if empty_synthesis:
            payload["findings"] = []
        output = write_json(path.parent / f"synthesis-{i}.json", payload)
        attempt["outputs"].append(
            {
                "output_id": "final-editor",
                "stage": "synthesis",
                "output_reference": str(output.relative_to(repo)),
            }
        )
    write_json(path, data)
    candidate_run = freeze_candidates(repo, packets, path)
    blind = prepare_assessment_packets(repo, candidate_run)
    assessment_path = write_json(
        path.parent / "candidate-assessment.json",
        assessment_input(load_assessment_packets(repo, blind)),
    )
    assessment = record_assessment(repo, blind, assessment_path)
    run = prepare_synthesis_packets(repo, assessment)
    return repo, run, load_synthesis_packets(repo, run), path.parent


@pytest.fixture(scope="module")
def ready(tmp_path_factory):
    # Reuse an immutable real pipeline for read-only/pure contract cases.
    workspace = create_workspace(
        tmp_path_factory.mktemp("synthesis"), Path(__file__).resolve().parents[2]
    )
    return prepared(workspace)


def synthesis_input(loaded):
    record = loaded["packets"]
    case = loaded["assessment"]["packets"]["candidates"]["packets"]["reference"]["plan"]["cases"][0]
    evidence = case["bundle"]["evidence"][0]
    groups, judgments = [], []
    for index, view in enumerate(record["views"]):
        items = [i for i in record["items"] if i["view_id"] == view["view_id"]]
        reviewers = [i["item_id"] for i in items if i["stage"] == "reviewer"]
        outputs = [i["item_id"] for i in items if i["stage"] == "synthesis"]
        group_id = f"group-{index}" if outputs else None
        if outputs:
            groups.append(
                {
                    "group_id": group_id,
                    "reviewer_item_ids": reviewers,
                    "synthesis_item_ids": outputs,
                    "conflicting_interpretations": ["Synthetic interpretations differ."],
                    "rationale": (
                        "Explicit synthetic membership; not semantic deduplication by code."
                    ),
                }
            )
        packet = json.loads(
            (loaded["run_root"] / view["workspace_reference"] / "synthesis_packet.json").read_text()
        )
        output_text = json.dumps(
            [i for i in packet["items"] if i["stage_role"] == "synthesis_output"]
        )
        caveat_lost = bool(outputs) and "Not executed." not in output_text
        for item in items:
            reviewer = item["stage"] == "reviewer"
            judgments.append(
                {
                    "item_id": item["item_id"],
                    "group_id": group_id,
                    "disposition": ("grouped" if reviewer else "mapped")
                    if outputs
                    else "unavailable",
                    "distorted": caveat_lost if outputs else None,
                    "error_stage": "report_synthesis" if caveat_lost else "unknown",
                    "evidence": [
                        {
                            "source_version_id": evidence["source_version_id"],
                            "locator": evidence["locator"],
                            "raw_value": evidence["raw_value"],
                        }
                    ]
                    if outputs
                    else [],
                    "critical_caveats": [
                        {
                            "input_quote": "Not executed.",
                            "output_quote": None if caveat_lost else "Not executed.",
                            "status": "lost" if caveat_lost else "preserved",
                            "rationale": "Synthetic source-linked qualifier review.",
                        }
                    ]
                    if reviewer and outputs
                    else [],
                    "rationale": (
                        "Synthetic source-based accounting; not actual medical validation."
                    ),
                }
            )
    common = {
        "domain_qualifications": "Synthetic fixture only.",
        "date": "2026-10-06T16:00:00-06:00",
        "blinded_to_condition": True,
        "source_bytes_reviewed": True,
        "reviewed_source_version_ids": sorted(
            {s for v in record["views"] for s in v["source_version_ids"]}
        ),
        "reviewed_view_ids": [v["view_id"] for v in record["views"]],
        "view_timings": [
            {"view_id": v["view_id"], "verification_seconds": None, "revision_seconds": None}
            for v in record["views"]
        ],
        "groups": groups,
        "judgments": judgments,
    }
    adjudication = {
        **copy.deepcopy(common),
        "human_identity": "synthesis-adjudicator",
        "date": "2026-10-06T16:05:00-06:00",
    }
    for row in adjudication["judgments"]:
        row.update(assessor_ids=["reader-1", "reader-2"], assessor_shortfall_reason=None)
    return {
        "schema_version": "medical_evaluation_synthesis_input_v1",
        "synthesis_packets_id": record["record_id"],
        "supersedes_run_reference": None,
        "assessors": [
            {
                **copy.deepcopy(common),
                "assessor_id": f"reader-{i}",
                "human_identity": f"synthesis-human-{i}",
            }
            for i in (1, 2)
        ],
        "adjudication": adjudication,
    }


def test_paired_packets_preserve_stage_context_caveats_without_condition_metadata(ready):
    _, run, loaded, _ = ready
    assert loaded["packets"]["blinding_verified"] is False
    for view in loaded["packets"]["views"]:
        root = run / view["workspace_reference"]
        payload = json.loads((root / "synthesis_packet.json").read_text())
        assert "GLOBAL-NUMERIC-CAVEAT" in json.dumps(payload)
        text = "\n".join(p.read_text() for p in root.rglob("*") if p.is_file())
        for secret in (
            "PRIVATE-CONDITION-",
            "PRIVATE-REFERENCE-ANSWER",
            "human_identity",
            "final-editor",
        ):
            assert secret not in text
        assert payload["review_coverage_available"] is False


def test_explicit_memberships_caveat_loss_unknowns_and_immutable_supersession(ready):
    repo, parent, loaded, base = ready
    data = synthesis_input(loaded)
    path = write_json(base / "synthesis-assessment.json", data)
    run = record_synthesis(repo, parent, path)
    record = load_synthesis(repo, run)["synthesis"]
    assert record["original"] == data
    assert len(record["judgments"]) == 16
    assert len(record["groups"]) == 4
    assert all(len(g["reviewer_item_ids"]) == 2 for g in record["groups"])
    assert any(
        r["critical_caveats"] and r["critical_caveats"][0]["status"] == "lost"
        for r in record["judgments"]
    )
    assert any(
        r["disposition"] == "unavailable" and r["distorted"] is None for r in record["judgments"]
    )
    assert record["medical_performance_validated"] is False
    assert record["official_assessment"] is None
    old = (run / "processed/medical_evaluation/synthesis.json").read_bytes()
    data["supersedes_run_reference"] = str(run.relative_to(repo))
    data["adjudication"]["date"] = "2026-10-06T16:10:00-06:00"
    revised = record_synthesis(repo, parent, write_json(path, data))
    assert load_synthesis(repo, revised)["synthesis"]["supersedes_record_id"] == record["record_id"]
    assert (run / "processed/medical_evaluation/synthesis.json").read_bytes() == old


def test_missing_memberships_forged_caveats_cross_scopes_and_authority_reject(ready):
    _, _, loaded, _ = ready
    baseline = synthesis_input(loaded)
    paired = next(
        r
        for r in baseline["adjudication"]["judgments"]
        if r["critical_caveats"] and r["critical_caveats"][0]["status"] == "lost"
    )
    changes = [
        lambda x: x["adjudication"]["judgments"].pop(),
        lambda x: x["adjudication"]["groups"][0]["reviewer_item_ids"].pop(),
        lambda x: x["adjudication"]["groups"][0].update(
            synthesis_item_ids=[x["adjudication"]["groups"][1]["synthesis_item_ids"][0]]
        ),
        lambda x: x["adjudication"].update(official_assessment="pass"),
        lambda x: x["assessors"][0].update(blinded_to_condition=False),
        lambda x: x["adjudication"]["judgments"][0].update(error_stage="invented"),
    ]
    for change in changes:
        data = copy.deepcopy(baseline)
        change(data)
        with pytest.raises(ValueError):
            validate_synthesis(loaded, data)
    data = copy.deepcopy(baseline)
    row = next(r for r in data["adjudication"]["judgments"] if r["item_id"] == paired["item_id"])
    row["critical_caveats"][0].update(status="preserved", output_quote="Not executed.")
    with pytest.raises(ValueError, match="quote"):
        validate_synthesis(loaded, data)
    data = copy.deepcopy(baseline)
    unavailable = next(
        r for r in data["adjudication"]["judgments"] if r["disposition"] == "unavailable"
    )
    unavailable.update(
        disposition="lost", distorted=False, evidence=copy.deepcopy(paired["evidence"])
    )
    with pytest.raises(ValueError, match="completed stage pair"):
        validate_synthesis(loaded, data)


def test_explicit_whole_finding_loss_preserves_disagreement_and_source_members(ready):
    _, _, loaded, _ = ready
    data = synthesis_input(loaded)
    group = data["adjudication"]["groups"][0]
    lost = group["reviewer_item_ids"].pop()
    for row in data["adjudication"]["judgments"]:
        if row["item_id"] == lost:
            row.update(group_id=None, disposition="lost", distorted=False, critical_caveats=[])
        elif row["item_id"] == group["reviewer_item_ids"][0]:
            row["disposition"] = "displayed"
    record = validate_synthesis(loaded, data)
    assert next(r for r in record["judgments"] if r["item_id"] == lost)["disposition"] == "lost"
    assert (
        next(r for r in record["assessors"][0]["judgments"] if r["item_id"] == lost)["disposition"]
        == "grouped"
    )


def test_synthesis_cli_uses_explicit_parent_and_no_live_flags(ready):
    repo, parent, loaded, base = ready
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    path = write_json(base / "cli-synthesis.json", synthesis_input(loaded))
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/medical_review.py"),
            "evaluation-synthesis",
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
        load_synthesis(repo, Path(result.stdout.strip()))["manifest"]["effective_settings"][
            "allow_llm"
        ]
        is False
    )


def test_empty_supplied_synthesis_can_have_explicit_loss_but_never_clean_coverage(workspace):
    _, _, loaded, _ = prepared(workspace, empty_synthesis=True)
    data = synthesis_input(loaded)
    evidence = loaded["assessment"]["packets"]["candidates"]["packets"]["reference"]["plan"][
        "cases"
    ][0]["bundle"]["evidence"][0]
    items = {i["item_id"]: i for i in loaded["packets"]["items"]}
    for person in [*data["assessors"], data["adjudication"]]:
        for row in person["judgments"]:
            if items[row["item_id"]]["declared_pair_complete"]:
                row.update(
                    disposition="lost",
                    distorted=False,
                    evidence=[
                        {
                            "source_version_id": evidence["source_version_id"],
                            "locator": evidence["locator"],
                            "raw_value": evidence["raw_value"],
                        }
                    ],
                )
    record = validate_synthesis(loaded, data)
    assert sum(r["disposition"] == "lost" for r in record["judgments"]) == 8
    assert sum(r["disposition"] == "unavailable" for r in record["judgments"]) == 4
    assert record["review_coverage_available"] is False
    assert record["medical_performance_validated"] is False


def test_workspace_inventory_drift_refuses_reuse_and_restoration_recovers(ready):
    repo, parent, loaded, _ = ready
    root = parent / loaded["packets"]["views"][0]["workspace_reference"]
    extra = root / "unexpected.json"
    try:
        root.chmod(0o755)
        extra.write_text('{"condition":"must_not_be_supplied"}')
        root.chmod(0o555)
        with pytest.raises(ValueError, match="inventory|artifact"):
            load_synthesis_packets(repo, parent)
    finally:
        root.chmod(0o755)
        extra.unlink(missing_ok=True)
        root.chmod(0o555)
    assert (
        load_synthesis_packets(repo, parent)["packets"]["record_id"]
        == loaded["packets"]["record_id"]
    )


def test_input_drift_retains_failed_raw_attempt_without_publishing(ready, monkeypatch):
    repo, parent, loaded, base = ready
    path = write_json(base / "synthesis-input-drift.json", synthesis_input(loaded))
    original = path.read_bytes()
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    original_write = synthesis_module._write

    def drift(run, manifest, reference, raw):
        original_write(run, manifest, reference, raw)
        if reference.endswith("raw/synthesis_input.json"):
            path.write_bytes(original + b" ")

    monkeypatch.setattr(synthesis_module, "_write", drift)
    with pytest.raises(ValueError, match="changed while recording"):
        record_synthesis(repo, parent, path)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    manifest = new.pop()
    assert json.loads(manifest.read_text())["status"] == "failed"
    assert not (manifest.parent / "processed/medical_evaluation/synthesis.json").exists()
    assert (
        manifest.parent / "generated/medical_evaluation/raw/synthesis_input.json"
    ).read_bytes() == original


def test_unresolved_item_cannot_turn_missing_stage_into_observed_caveat_loss(ready):
    _, _, loaded, _ = ready
    data = synthesis_input(loaded)
    row = next(r for r in data["adjudication"]["judgments"] if r["disposition"] == "unavailable")
    row.update(
        disposition="unresolved",
        critical_caveats=[
            {
                "input_quote": "Not executed.",
                "output_quote": None,
                "status": "lost",
                "rationale": "Synthetic missing-stage regression.",
            }
        ],
    )
    with pytest.raises(ValueError, match="completed stage pair"):
        validate_synthesis(loaded, data)
