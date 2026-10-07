from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from support.medical_review_fixtures import create_workspace, write_json
from test_evaluation_synthesis import prepared, synthesis_input

from research_project.medical_review import evaluation_governance as governance
from research_project.medical_review.evaluation_governance import (
    freeze_thresholds,
    load_thresholds,
    load_unblinding,
    record_unblinding,
    validate_thresholds,
    validate_unblinding,
)
from research_project.medical_review.evaluation_synthesis import record_synthesis


def threshold_input(reference, *, approved=True):
    criteria = [
        {
            "criterion_id": domain,
            "domain": domain,
            "metric_definition": "Synthetic measurement only; not an approved clinical metric.",
            "unit": "synthetic units",
            "denominator": "Explicit synthetic fixture denominator.",
            "aggregation": "Explicit synthetic fixture aggregation; no inference by code.",
            "scope_description": "Synthetic development comparisons only.",
            "direction": "at_most" if domain == "serious_false_allegations" else "at_least",
            "threshold_value": 0
            if domain == "serious_false_allegations"
            else (0.5 if approved else None),
            "rationale": "Synthetic contract fixture; not a recommended medical cutoff.",
        }
        for domain in governance.DOMAINS
    ]
    return {
        "schema_version": "medical_evaluation_threshold_input_v1",
        "reference_record_id": reference["ledger"]["ledger_id"],
        "criteria": criteria,
        "approval": {
            "decision": "approved",
            "human_identity": "synthetic-threshold-approver",
            "domain_qualifications": "Synthetic fixture, not an actual credential.",
            "date": "2026-10-06T16:15:00-06:00",
            "conditions_not_previously_unblinded": True,
            "rationale": "Synthetic approval only; no actual scientific approval.",
        }
        if approved
        else None,
    }


def ready_workspace(workspace):
    repo, packets, loaded, base = prepared(workspace)
    synthesis = record_synthesis(
        repo, packets, write_json(base / "governance-synthesis.json", synthesis_input(loaded))
    )
    reference = loaded["assessment"]["packets"]["candidates"]["packets"]["reference"]
    path = write_json(base / "approved-thresholds.json", threshold_input(reference))
    thresholds = freeze_thresholds(repo, reference["run_root"], path)
    return repo, reference, synthesis, thresholds, base


@pytest.fixture(scope="module")
def ready(tmp_path_factory):
    return ready_workspace(
        create_workspace(tmp_path_factory.mktemp("governance"), Path(__file__).resolve().parents[2])
    )


def unblind_input(thresholds, synthesis_id):
    return {
        "schema_version": "medical_evaluation_unblinding_input_v1",
        "threshold_record_id": thresholds["thresholds"]["record_id"],
        "synthesis_record_id": synthesis_id,
        "operator": {
            "human_identity": "synthetic-unblinding-operator",
            "domain_qualifications": "Synthetic fixture only.",
            "date": "2026-10-06T16:30:00-06:00",
            "conditions_not_previously_unblinded": True,
            "rationale": "Synthetic declared release, not actual medical evaluation.",
        },
    }


def inputs(ready):
    repo, _, synthesis, threshold_run, base = ready
    thresholds = load_thresholds(repo, threshold_run)
    source = governance.load_synthesis(repo, synthesis)
    return (
        thresholds,
        source,
        write_json(
            base / "unblinding.json", unblind_input(thresholds, source["synthesis"]["record_id"])
        ),
    )


def test_pending_thresholds_keep_nulls_and_zero_without_allowing_unblinding(ready):
    repo, reference, synthesis, _, base = ready
    data = threshold_input(reference, approved=False)
    path = write_json(base / "pending-thresholds.json", data)
    run = freeze_thresholds(repo, reference["run_root"], path)
    record = load_thresholds(repo, run)["thresholds"]
    assert record["approval_status"] == "pending"
    assert any(c["threshold_value"] is None for c in record["criteria"])
    assert any(c["threshold_value"] == 0 for c in record["criteria"])
    assert record["medical_performance_validated"] is False
    loaded = load_thresholds(repo, run)
    source = governance.load_synthesis(repo, synthesis)
    request = unblind_input(loaded, source["synthesis"]["record_id"])
    with pytest.raises(ValueError, match="approved"):
        record_unblinding(repo, run, synthesis, write_json(base / "pending-unblind.json", request))


def test_approved_release_has_exact_lineage_is_idempotent_and_locks_later_approval(ready):
    repo, reference, synthesis, threshold_run, base = ready
    thresholds, source, path = inputs(ready)
    run = record_unblinding(repo, threshold_run, synthesis, path)
    loaded = load_unblinding(repo, run)
    record = loaded["unblinding"]
    assert record["threshold_record_id"] == thresholds["thresholds"]["record_id"]
    assert len(record["condition_map"]) == 6
    assert len(record["item_map"]) == 16
    assert record["medical_performance_validated"] is False
    assert record["official_assessment"] is None
    before = (run / "processed/medical_evaluation/unblinding.json").read_bytes()
    assert record_unblinding(repo, threshold_run, synthesis, path) == run
    assert (run / "processed/medical_evaluation/unblinding.json").read_bytes() == before
    changed = threshold_input(reference)
    changed["criteria"][0]["threshold_value"] = 0.6
    with pytest.raises(ValueError, match="already.*unblind|after.*unblind"):
        freeze_thresholds(
            repo, reference["run_root"], write_json(base / "posthoc-thresholds.json", changed)
        )


def test_approval_definitions_scopes_dates_and_model_authority_are_strict(ready):
    _, reference, _, _, _ = ready
    baseline = threshold_input(reference)
    changes = [
        lambda x: x["criteria"].pop(),
        lambda x: x["criteria"][0].update(aggregation=""),
        lambda x: x["criteria"][0].update(threshold_value=None),
        lambda x: x["criteria"][0].update(threshold_value=True),
        lambda x: x["criteria"][0].update(threshold_value=float("inf")),
        lambda x: x["approval"].update(conditions_not_previously_unblinded=False),
        lambda x: x["approval"].update(date="2026-10-06"),
        lambda x: x.update(official_assessment="pass"),
        lambda x: x.update(reference_record_id="unrelated"),
    ]
    for change in changes:
        data = copy.deepcopy(baseline)
        change(data)
        with pytest.raises(ValueError):
            validate_thresholds(reference, data)
    thresholds, synthesis, path = inputs(ready)
    request = json.loads(path.read_text())
    request["operator"]["date"] = "2026-10-06T16:00:00-06:00"
    with pytest.raises(ValueError, match="precede"):
        validate_unblinding(thresholds, synthesis, request)


def test_release_failure_recovers_same_immutable_receipt_without_changing_thresholds(
    workspace, monkeypatch
):
    ready = ready_workspace(workspace)
    repo, _, synthesis, threshold_run, _ = ready
    _, _, path = inputs(ready)
    original_write = governance._write
    before = set((repo / "data/processed").rglob("run_manifest.json"))

    def fail(run, manifest, reference, raw):
        if reference == "processed/medical_evaluation/unblinding.json":
            raise RuntimeError("Synthetic post-publication failure")
        original_write(run, manifest, reference, raw)

    with monkeypatch.context() as patch:
        patch.setattr(governance, "_write", fail)
        with pytest.raises(RuntimeError, match="post-publication"):
            record_unblinding(repo, threshold_run, synthesis, path)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    failed = new.pop()
    assert json.loads(failed.read_text())["status"] == "failed"
    recovered = record_unblinding(repo, threshold_run, synthesis, path)
    assert recovered != failed.parent
    assert load_unblinding(repo, recovered)["manifest"]["effective_settings"][
        "recovery_of_run_reference"
    ] == str(failed.parent.relative_to(repo))
    assert json.loads(failed.read_text())["status"] == "failed"
    assert record_unblinding(repo, threshold_run, synthesis, path) == recovered


def test_existing_release_refuses_a_different_request(ready):
    repo, _, synthesis, threshold_run, _ = ready
    _, _, path = inputs(ready)
    record_unblinding(repo, threshold_run, synthesis, path)
    request = json.loads(path.read_text())
    request["operator"]["rationale"] += " altered request"
    changed = write_json(path.parent / "different-release.json", request)
    with pytest.raises(ValueError, match="different|immutable"):
        record_unblinding(repo, threshold_run, synthesis, changed)


def test_threshold_freeze_preserves_failed_input_drift(ready, monkeypatch):
    repo, reference, _, _, base = ready
    data = threshold_input(reference, approved=False)
    path = write_json(base / "drifting-thresholds.json", data)
    original_write = governance._write
    before = set((repo / "data/processed").rglob("run_manifest.json"))

    def drift(run, manifest, artifact, raw):
        original_write(run, manifest, artifact, raw)
        if artifact == governance.RAW:
            changed = copy.deepcopy(data)
            changed["criteria"][0]["rationale"] = "Changed after raw archival."
            write_json(path, changed)

    with monkeypatch.context() as patch:
        patch.setattr(governance, "_write", drift)
        with pytest.raises(ValueError, match="changed"):
            freeze_thresholds(repo, reference["run_root"], path)
    failed = (set((repo / "data/processed").rglob("run_manifest.json")) - before).pop()
    assert json.loads(failed.read_text())["status"] == "failed"
    assert not (failed.parent / "processed/medical_evaluation/thresholds.json").exists()
    assert json.loads((failed.parent / governance.RAW).read_text()) == data


def test_supplied_signed_cutoffs_and_foreign_reference_remain_explicit(ready):
    _, reference, _, _, _ = ready
    data = threshold_input(reference)
    data["criteria"][0]["threshold_value"] = -0.25
    assert validate_thresholds(reference, data)["criteria"][0]["threshold_value"] == -0.25
    thresholds, synthesis, path = inputs(ready)
    foreign = copy.deepcopy(synthesis)
    governance._reference(foreign)["ledger"]["ledger_id"] = "unrelated-reference"
    with pytest.raises(ValueError, match="lineage"):
        validate_unblinding(thresholds, foreign, json.loads(path.read_text()))


def test_governance_cli_uses_explicit_parents_and_offline_boundaries(ready):
    repo, reference, synthesis, thresholds, base = ready
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    script = repo / "scripts/medical_review.py"
    shutil.copy(root / "scripts/medical_review.py", script)
    pending = write_json(base / "cli-thresholds.json", threshold_input(reference, approved=False))
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "evaluation-thresholds",
            "--reference-run",
            str(reference["run_root"]),
            "--input",
            str(pending),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        load_thresholds(repo, Path(result.stdout.strip()))["thresholds"]["approval_status"]
        == "pending"
    )
    _, _, path = inputs(ready)
    command = [
        sys.executable,
        str(script),
        "evaluation-unblind",
        "--thresholds-run",
        str(thresholds),
        "--synthesis-run",
        str(synthesis),
        "--input",
        str(path),
    ]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (
        load_unblinding(repo, Path(result.stdout.strip()))["manifest"]["effective_settings"][
            "allow_llm"
        ]
        is False
    )
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    refused = subprocess.run(command + ["--allow-llm"], cwd=repo, capture_output=True, text=True)
    assert refused.returncode == 2
    assert set((repo / "data/processed").rglob("run_manifest.json")) == before


def test_finite_integer_cutoff_is_preserved_without_float_conversion():
    reference = {
        "ledger": {"ledger_id": "synthetic-ledger"},
        "plan": {"plan_id": "synthetic-plan", "evaluation_id": "synthetic"},
    }
    data = threshold_input(reference)
    data["criteria"][0]["threshold_value"] = 10**400
    record = validate_thresholds(reference, data)
    assert record["criteria"][0]["threshold_value"] == 10**400


def test_receipt_publication_is_complete_exclusive_and_read_only(tmp_path):
    receipt = tmp_path / "receipts/plan.json"
    governance._publish(receipt, b'{"release":"first"}\n')
    assert receipt.read_bytes() == b'{"release":"first"}\n'
    assert receipt.stat().st_mode & 0o777 == 0o444
    with pytest.raises(FileExistsError):
        governance._publish(receipt, b'{"release":"replacement"}\n')
    assert receipt.read_bytes() == b'{"release":"first"}\n'
    assert sorted(p.name for p in receipt.parent.iterdir()) == ["plan.json"]


def test_plan_lock_serializes_approval_and_release(workspace):
    repo, *_ = workspace
    record = {"evaluation_id": "synthetic", "plan_id": "synthetic-lock-test"}
    entered, acquired = Event(), Event()

    def competing_transaction():
        entered.set()
        with governance._plan_lock(repo, record):
            acquired.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with governance._plan_lock(repo, record):
            future = pool.submit(competing_transaction)
            assert entered.wait(2)
            assert not acquired.wait(0.05)
        future.result(timeout=2)
    assert acquired.is_set()
