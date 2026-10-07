from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json
from test_evaluation_packets import reference_run

from research_project.medical_review.evaluation_candidates import (
    freeze_candidates,
    load_candidates,
)
from research_project.medical_review.evaluation_packets import (
    load_source_packets,
    prepare_source_packets,
)


def inputs(workspace):
    repo, _, _, bundle, upstream = workspace
    reference, _ = reference_run(workspace, with_supplement=True)
    packets_run = prepare_source_packets(repo, reference)
    packets = load_source_packets(repo, packets_run)["packets"]
    base = repo / "data/private/medical_reviews/evaluation-synthetic/evaluation"
    attempts = []
    for i, packet in enumerate(packets["packets"]):
        payload = copy.deepcopy(upstream)
        payload["paper_id"] = packet["packet_id"]
        main = next(
            a
            for a in packet["source_aliases"]
            if a["source_version_id"] == bundle["documents"][0]["source_version_id"]
        )
        payload["findings"][0]["source_objects"][0]["path"] = main["local_file"]
        # A real, exact annotation for an unselected supplement cannot resolve in common input.
        footnote = copy.deepcopy(payload["findings"][0])
        footnote["id"] = "supplement-finding"
        obj = footnote["source_objects"][0]
        obj["path"] = next(
            (a["local_file"] for a in packet["source_aliases"] if a != main),
            "sources/unselected-supplement.txt",
        )
        obj["text_quote"] = "Synthetic supplemental footnote."
        obj["id"] = "source-supplement"
        footnote["claim_evidence_links"][0]["source_object_ids"] = [obj["id"]]
        payload["findings"].append(footnote)
        path = write_json(base / f"output-{i}.json", payload)
        attempts.append(
            {
                "attempt_id": f"attempt-{i}",
                "packet_id": packet["packet_id"],
                "status": "completed",
                "stop_reason": None,
                "origin": "offline_supplied",
                "runtime": None,
                "upstream_revision": None,
                "usage": {
                    "elapsed_seconds": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "cost_amount": None,
                    "cost_currency": None,
                },
                "outputs": [
                    {
                        "output_id": "methods",
                        "stage": "reviewer",
                        "output_reference": str(path.relative_to(repo)),
                    }
                ],
            }
        )
    return (
        packets_run,
        packets,
        {
            "schema_version": "medical_evaluation_candidate_input_v1",
            "packets_record_id": packets["record_id"],
            "attempts": attempts,
        },
        base / "candidates.json",
    )


def test_candidates_retain_attempts_raw_bytes_stages_scoped_citations_and_unknown_usage(workspace):
    repo, *_ = workspace
    parent, packets, data, path = inputs(workspace)
    failed = copy.deepcopy(data["attempts"][0])
    failed.update(
        attempt_id="failed-attempt",
        status="failed",
        stop_reason="Supplied quota failure.",
        outputs=[],
    )
    failed["usage"].update(cost_amount=0.25, cost_currency="USD")
    failed["usage"].update(input_tokens=0, output_tokens=0, total_tokens=0)
    data["attempts"].append(failed)
    source = data["attempts"][0]["outputs"][0]
    data["attempts"][0]["outputs"].append({**source, "output_id": "editor", "stage": "synthesis"})
    write_json(path, data)
    run = freeze_candidates(repo, parent, path)
    loaded = load_candidates(repo, run)
    record = loaded["candidates"]
    assert record["original"] == data
    assert record["medical_performance_validated"] is False
    assert record["runtime_evidence"] == "operator_reported_not_verified"
    assert record["review_coverage_available"] is False
    assert record["official_assessment"] is None
    assert len(record["attempts"]) == 7
    assert len(record["candidates"]) == 14
    assert record["attempts"][-1]["usage"]["cost_amount"] == 0.25
    assert record["attempts"][-1]["usage"]["total_tokens"] == 0
    assert record["attempts"][0]["usage"]["total_tokens"] is None
    assert {r["stage"] for r in record["candidates"]} == {"reviewer", "synthesis"}
    packet_map = {p["packet_id"]: p for p in packets["packets"]}
    for attempt in record["attempts"]:
        for output in attempt["outputs"]:
            assert (run / output["raw_reference"]).read_bytes() == (
                repo / output["output_reference"]
            ).read_bytes()
    for candidate in record["candidates"]:
        assert candidate["human_status"] == "pending"
        assert candidate["qualified_result_ids"] == []
        assert candidate["official_assessment"] is None
        packet = packet_map[candidate["packet_id"]]
        link = candidate["source_links"][0]
        if candidate["original_finding_id"] == "finding-1":
            assert link["resolution"] == "exact"
        elif packet["track"] == "full_bundle" and packet["condition_id"] != "original_reviewer":
            assert link["resolution"] == "exact"
        else:
            assert link["resolution"] == "unresolved"
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.parametrize("change", ["packet", "duplicate", "authority", "usage", "traversal"])
def test_candidate_input_rejects_identity_authority_and_scope_before_a_run(workspace, change):
    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    if change == "packet":
        data["attempts"][0]["packet_id"] = "unknown-packet"
    elif change == "duplicate":
        data["attempts"].append(copy.deepcopy(data["attempts"][0]))
    elif change == "authority":
        data["attempts"][0]["human_verified"] = True
    elif change == "usage":
        data["attempts"][0]["usage"]["cost_amount"] = -1
    else:
        data["attempts"][0]["outputs"][0]["output_reference"] = "../secret.json"
    write_json(path, data)
    before = set(repo.rglob("run_manifest.json"))
    with pytest.raises(ValueError):
        freeze_candidates(repo, parent, path)
    assert set(repo.rglob("run_manifest.json")) == before


def test_rejected_model_authority_retains_failed_raw_attempt_without_publishing_candidates(
    workspace,
):
    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    source = repo / data["attempts"][0]["outputs"][0]["output_reference"]
    payload = json.loads(source.read_text())
    payload["human_verified"] = True
    write_json(source, payload)
    write_json(path, data)
    with pytest.raises(ValueError, match="fields"):
        freeze_candidates(repo, parent, path)
    roots = repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic"
    failed = [
        p.parent
        for p in roots.glob("*/run_manifest.json")
        if json.loads(p.read_text())["status"] == "failed"
    ]
    assert len(failed) == 1
    assert source.read_bytes() in [
        p.read_bytes()
        for p in (failed[0] / "generated/medical_evaluation/raw/outputs").rglob("*.json")
    ]
    assert not (failed[0] / "processed/medical_evaluation/candidates.json").exists()


def test_candidate_loader_rejects_changed_registered_output(workspace):
    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    write_json(path, data)
    run = freeze_candidates(repo, parent, path)
    output = load_candidates(repo, run)["candidates"]["attempts"][0]["outputs"][0]
    raw = run / output["raw_reference"]
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash|artifact"):
        load_candidates(repo, run)


def test_candidate_cli_import_is_offline_and_uses_an_explicit_packet_parent(workspace):
    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    write_json(path, data)
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/medical_review.py"),
            "evaluation-candidates",
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
    loaded = load_candidates(repo, Path(result.stdout.strip()))
    assert loaded["manifest"]["effective_settings"]["allow_llm"] is False
    assert len(loaded["candidates"]["candidates"]) == 12


@pytest.mark.parametrize("change", ["input", "output"])
def test_candidate_freeze_drift_preserves_raw_failed_attempt(workspace, monkeypatch, change):
    from research_project.medical_review import evaluation_candidates as module

    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    write_json(path, data)
    source = (
        path if change == "input" else repo / data["attempts"][0]["outputs"][0]["output_reference"]
    )
    original = source.read_bytes()
    actual_update = module.update_run
    changed = False

    def mutate(manifest, **kwargs):
        nonlocal changed
        result = actual_update(manifest, **kwargs)
        if not changed and "/raw/" in kwargs.get("artifact", ""):
            source.write_bytes(original + b" ")
            changed = True
        return result

    monkeypatch.setattr(module, "update_run", mutate)
    with pytest.raises(ValueError, match="changed"):
        freeze_candidates(repo, parent, path)
    roots = repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic"
    failed = [
        p.parent
        for p in roots.glob("*/run_manifest.json")
        if json.loads(p.read_text())["status"] == "failed"
    ]
    assert len(failed) == 1
    assert original in [
        p.read_bytes() for p in (failed[0] / "generated/medical_evaluation/raw").rglob("*.json")
    ]
    assert not (failed[0] / "processed/medical_evaluation/candidates.json").exists()


def test_empty_candidates_and_repeat_imports_never_establish_coverage_or_independence(workspace):
    repo, *_ = workspace
    parent, _, data, path = inputs(workspace)
    data["attempts"] = data["attempts"][:1]
    output = repo / data["attempts"][0]["outputs"][0]["output_reference"]
    payload = json.loads(output.read_text())
    payload["findings"] = []
    write_json(output, payload)
    write_json(path, data)
    first = freeze_candidates(repo, parent, path)
    second = freeze_candidates(repo, parent, path)
    a = load_candidates(repo, first)["candidates"]
    assert first != second
    assert a == load_candidates(repo, second)["candidates"]
    assert a["candidates"] == []
    assert a["review_coverage_available"] is False
    assert len(a["unreported_packet_ids"]) == 5
    assert a["medical_performance_validated"] is False
