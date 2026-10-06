from __future__ import annotations

import copy
import hashlib
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json
from test_evaluation_plan import plan_input, supplement
from test_evaluation_reference import reference_input

from research_project.inspect_sr.records import evidence_id, source_version_id
from research_project.medical_review.evaluation import freeze_evaluation_plan, load_evaluation_plan
from research_project.medical_review.evaluation_packets import (
    load_source_packets,
    prepare_source_packets,
)
from research_project.medical_review.evaluation_reference import freeze_reference_ledger


def reference_run(workspace, *, with_supplement=False):
    repo, bundle_path, _, bundle, _ = workspace
    if with_supplement:
        doc = supplement(workspace)
        # These are private study annotations, never model packet instructions.
        bundle["planned_checks"][0]["rationale"] = "PRIVATE-SUPPLEMENT-DERIVED-CONTEXT"
        ev = copy.deepcopy(bundle["evidence"][0])
        ev.update(
            source_version_id=doc["source_version_id"],
            raw_value="Synthetic supplemental footnote.",
            parsed_path=doc["path"],
            parsed_sha256=doc["sha256"],
        )
        ev["evidence_id"] = evidence_id(
            ev["source_version_id"],
            ev["locator"],
            ev["raw_value"],
            ev["parser"]["id"],
            ev["parser"]["version"],
        )
        bundle["evidence"].append(ev)
        bundle["context_fields"] = {
            "synthetic": {
                "assignment": {
                    "reported": {
                        "status": "known",
                        "value": ev["raw_value"],
                        "evidence_ids": [ev["evidence_id"]],
                    }
                }
            }
        }
        write_json(bundle_path, bundle)
    plan_path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    parent = freeze_evaluation_plan(repo, plan_path)
    plan = load_evaluation_plan(repo, parent)
    data = reference_input(plan)
    data["case_reviews"][0]["adjudication"]["issues"][0]["rationale"] += " PRIVATE-REFERENCE-ANSWER"
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/reference.json", data
    )
    return freeze_reference_ledger(repo, parent, path), plan


def packet_root(run, row):
    return run / row["workspace_reference"]


def test_source_packets_preserve_tracks_exact_sources_repetitions_and_metadata_boundary(workspace):
    repo, *_ = workspace
    parent, plan = reference_run(workspace, with_supplement=True)
    run = prepare_source_packets(repo, parent, repetitions=2)
    loaded = load_source_packets(repo, run)
    record = loaded["packets"]
    assert len(record["packets"]) == 12
    assert record["execution"] == "not_requested"
    assert record["backend_isolation_qualified"] is False
    assert record["medical_performance_validated"] is False
    assert record["plan_id"] == plan["plan_id"]
    assert loaded["reference"]["ledger"]["contains_synthetic_cases"] is True
    for row in record["packets"]:
        root = packet_root(run, row)
        assert row["condition_id"] not in root.name
        index = json.loads((root / "source_index.json").read_text())
        assert set(index) == {"schema_version", "packet_id", "sources", "source_fidelity_verified"}
        assert index["source_fidelity_verified"] is False
        assert "evidence" not in index  # Benchmark annotations are not reviewer inputs.
        expected = [plan["cases"][0]["common_source_version_id"]]
        if row["track"] == "full_bundle" and row["condition_id"] != "original_reviewer":
            expected = sorted(
                d["source_version_id"] for d in plan["cases"][0]["bundle"]["documents"]
            )
        assert row["source_version_ids"] == expected
        assert [s["source_version_id"] for s in index["sources"]] == expected
        for source in index["sources"]:
            path = root / source["local_file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
            assert stat.S_IMODE(path.stat().st_mode) == 0o444
        text = "\n".join(p.read_text() for p in root.rglob("*") if p.is_file())
        for private in (
            "PRIVATE-SUPPLEMENT-DERIVED-CONTEXT",
            "PRIVATE-REFERENCE-ANSWER",
            "private-synthetic-human",
            "human_identity",
            "assessor_issue_refs",
            "data/private/",
        ):
            assert private not in text
        if row["track"] == "common_input" or row["condition_id"] == "original_reviewer":
            assert "Synthetic supplemental footnote" not in text
        if row["condition_id"] != "original_reviewer":
            scope = json.loads((root / "review_scope.json").read_text())
            assert scope["shared_reconstruction"] == "withheld_reconstruct_from_staged_sources"
            assert scope["execution_permissions"] == {"allow_llm": False, "allow_web_search": False}
        else:
            assert (
                row["comparator_execution"] == "blocked_unmodified_workflow_not_staged_or_executed"
            )
            assert not (root / "review_scope.json").exists()
    pairs = [
        r
        for r in record["packets"]
        if r["track"] == "full_bundle"
        and r["repetition"] == 1
        and r["condition_id"] != "original_reviewer"
    ]
    assert pairs[0]["source_version_ids"] == pairs[1]["source_version_ids"]


def test_same_declared_seed_and_dependencies_create_stable_packet_identity_without_overwrite(
    workspace,
):
    repo, *_ = workspace
    parent, _ = reference_run(workspace)
    first = prepare_source_packets(repo, parent)
    second = prepare_source_packets(repo, parent)
    assert first != second
    assert (
        load_source_packets(repo, first)["packets"] == load_source_packets(repo, second)["packets"]
    )


@pytest.mark.parametrize("change", ["zero", "bool", "bytes", "total", "many"])
def test_packet_limits_refuse_before_staging_and_never_truncate(workspace, change):
    repo, *_ = workspace
    parent, _ = reference_run(workspace)
    options = {
        "zero": {"repetitions": 0},
        "bool": {"repetitions": True},
        "bytes": {"max_packet_bytes": 1},
        "total": {"max_total_bytes": 1},
        "many": {"repetitions": 10000},
    }[change]
    before = {p for p in repo.rglob("run_manifest.json")}
    with pytest.raises(ValueError, match="limit|bound|byte|packet|repetition"):
        prepare_source_packets(repo, parent, **options)
    assert {p for p in repo.rglob("run_manifest.json")} == before


@pytest.mark.parametrize("change", ["new_file", "write_mode", "source_bytes", "symlink"])
def test_packet_reuse_requires_exact_inventory_permissions_and_registered_bytes(workspace, change):
    repo, *_ = workspace
    parent, _ = reference_run(workspace)
    run = prepare_source_packets(repo, parent)
    record = load_source_packets(repo, run)["packets"]
    root = packet_root(run, record["packets"][0])
    path = root / "source_index.json"
    root.chmod(0o755)
    if change == "new_file":
        (root / "unregistered.txt").write_text("Unexpected input.")
    elif change == "write_mode":
        path.chmod(0o644)
    elif change == "source_bytes":
        path.chmod(0o644)
        path.write_bytes(path.read_bytes() + b" ")
        path.chmod(0o444)
    else:
        path.unlink()
        path.symlink_to(parent / "processed/medical_evaluation/reference_ledger.json")
    root.chmod(0o555)
    with pytest.raises(ValueError, match="inventory|permission|read.only|artifact|hash|symlink"):
        load_source_packets(repo, run)


def test_staging_source_drift_preserves_failed_attempt_without_publishing_packets(
    workspace, monkeypatch
):
    from research_project.medical_review import evaluation_packets as module

    repo, _, _, bundle, _ = workspace
    parent, _ = reference_run(workspace)
    source = repo / bundle["documents"][0]["path"]
    real_update = module.update_run
    changed = False

    def change_source(manifest, **kwargs):
        nonlocal changed
        result = real_update(manifest, **kwargs)
        if not changed and "/reviewer_workspaces/" in kwargs.get("artifact", ""):
            source.write_bytes(source.read_bytes() + b"\nChanged source.")
            changed = True
        return result

    monkeypatch.setattr(module, "update_run", change_source)
    with pytest.raises(ValueError, match="hash|changed"):
        prepare_source_packets(repo, parent)
    attempts = list(
        (repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic").glob(
            "*/run_manifest.json"
        )
    )
    failed = [p for p in attempts if json.loads(p.read_text())["status"] == "failed"]
    assert len(failed) == 1
    assert not (failed[0].parent / "processed/medical_evaluation/source_packets.json").exists()
    assert list(
        (failed[0].parent / "generated/medical_evaluation/reviewer_workspaces").rglob(
            "source-001.txt"
        )
    )


def test_original_comparator_retains_pinned_bytes_without_substituting_medical_prompts(workspace):
    repo, *_ = workspace
    parent, _ = reference_run(workspace)
    run = prepare_source_packets(repo, parent)
    record = load_source_packets(repo, run)["packets"]
    row = next(r for r in record["packets"] if r["condition_id"] == "original_reviewer")
    root = packet_root(run, row)
    upstream = json.loads((repo / "config/medical_review/upstream/provenance.json").read_text())
    for asset in upstream["files"]:
        assert (root / "instructions/upstream" / asset["local_path"]).read_bytes() == (
            repo / "config/medical_review/upstream" / asset["local_path"]
        ).read_bytes()
    assert not (root / "instructions/strong_single_reviewer.txt").exists()
    assert not (root / "instructions/shared_evidence.txt").exists()


def test_packet_cli_has_no_live_options_and_freezes_an_explicit_parent(workspace):
    repo, *_ = workspace
    parent, _ = reference_run(workspace)
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    command = [
        sys.executable,
        str(repo / "scripts/medical_review.py"),
        "evaluation-packets",
        "--reference-run",
        str(parent),
        "--repetitions",
        "2",
    ]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    loaded = load_source_packets(repo, Path(result.stdout.strip()))
    assert len(loaded["packets"]["packets"]) == 12
    assert loaded["manifest"]["effective_settings"]["allow_llm"] is False
    assert not (repo / "data/private/inspect_sr").exists()
    forbidden = subprocess.run([*command, "--allow-llm"], cwd=repo, capture_output=True, text=True)
    assert forbidden.returncode == 2


def test_packets_retain_declared_mixed_aim_profile_union_without_private_context(workspace):
    repo, bundle_path, _, bundle, _ = workspace
    report_ids = bundle["documents"][0]["report_ids"]
    bundle["planned_checks"] = []
    bundle["comparisons"] = [
        {
            "comparison_id": f"aim-{name}",
            "study_id": "synthetic",
            "report_ids": report_ids,
            "profile_ids": [name],
        }
        for name in ("clinical_trial", "prediction_model")
    ]
    write_json(bundle_path, bundle)
    parent, _ = reference_run(workspace)
    run = prepare_source_packets(repo, parent)
    rows = load_source_packets(repo, run)["packets"]["packets"]
    for row in rows:
        if row["condition_id"] == "original_reviewer":
            continue
        root = packet_root(run, row)
        scope = json.loads((root / "review_scope.json").read_text())
        assert scope["profile_ids"] == ["clinical_trial", "prediction_model"]
        assert {r["module"] for r in scope["checks"]} >= {"trial", "prediction"}
        assert (root / "instructions/prediction.txt").is_file()


@pytest.mark.parametrize("limit", ["packet", "total"])
def test_streaming_caps_stop_source_growth_and_preserve_bounded_failed_attempt(
    workspace, monkeypatch, limit
):
    from research_project.medical_review import evaluation_packets as module

    repo, _, _, bundle, _ = workspace
    parent, _ = reference_run(workspace)
    valid = prepare_source_packets(repo, parent)
    record = load_source_packets(repo, valid)["packets"]
    largest = max(r["workspace_bytes"] for r in record["packets"])
    total = record["total_workspace_bytes"]
    source = repo / bundle["documents"][0]["path"]
    actual_update = module.update_run
    changed = False

    def grow_source(manifest, **kwargs):
        nonlocal changed
        result = actual_update(manifest, **kwargs)
        if not changed and "/reviewer_workspaces/" in kwargs.get("artifact", ""):
            source.write_bytes(b"Synthetic growing source.\n" * (total // 10 + 100))
            changed = True
        return result

    monkeypatch.setattr(module, "update_run", grow_source)
    packet_cap = largest + 1 if limit == "packet" else total * 4
    total_cap = total * 4 if limit == "packet" else total + 1
    with pytest.raises(ValueError, match="byte limit changed/exceeded while copying"):
        prepare_source_packets(repo, parent, max_packet_bytes=packet_cap, max_total_bytes=total_cap)
    roots = repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic"
    failed = [
        p.parent
        for p in roots.glob("*/run_manifest.json")
        if json.loads(p.read_text())["status"] == "failed"
    ]
    assert len(failed) == 1
    assert not (failed[0] / "processed/medical_evaluation/source_packets.json").exists()
    staged_bytes = sum(
        p.stat().st_size for p in (failed[0] / module.WORKSPACES).rglob("*") if p.is_file()
    )
    assert staged_bytes <= total_cap
    assert staged_bytes <= packet_cap  # Failure occurs in the first packet.


@pytest.mark.parametrize("location", ["evaluation", "sources", "nested", "execution"])
def test_private_reference_record_cannot_be_mislabelled_as_analysis_output(workspace, location):
    repo, bundle_path, _, bundle, _ = workspace
    private = {
        "schema_version": "medical_execution_attempt_v1"
        if location == "execution"
        else "medical_evaluation_reference_input_v1",
        "private_reference_answer": "PRIVATE-ANSWER-NEVER-A-REVIEWER-INPUT",
    }
    source = write_json(
        bundle_path.parent
        / ("sources" if location in {"nested", "execution"} else location)
        / "mislabelled.json",
        {"analysis": [private]} if location == "nested" else private,
    )
    doc = copy.deepcopy(bundle["documents"][0])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    doc.update(
        source_id="private-record",
        source_version_id=source_version_id("private-record", digest),
        role="analysis_output",
        path=str(source.relative_to(repo)),
        sha256=digest,
        upstream_paths=["inputs/mislabelled.json"],
    )
    bundle["documents"].append(doc)
    write_json(bundle_path, bundle)
    parent, _ = reference_run(workspace)
    before = set(repo.rglob("run_manifest.json"))
    with pytest.raises(ValueError, match="private|protected|record"):
        prepare_source_packets(repo, parent)
    assert set(repo.rglob("run_manifest.json")) == before


def test_ordinary_analysis_json_remains_an_exact_full_bundle_source(workspace):
    repo, bundle_path, _, bundle, _ = workspace
    source = write_json(
        bundle_path.parent / "sources" / "analysis.json",
        {"schema_version": "synthetic_analysis_v1", "events": 2, "participants": 10},
    )
    doc = copy.deepcopy(bundle["documents"][0])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    version = source_version_id("analysis", digest)
    doc.update(
        source_id="analysis",
        source_version_id=version,
        role="analysis_output",
        path=str(source.relative_to(repo)),
        sha256=digest,
        upstream_paths=["inputs/analysis.json"],
    )
    bundle["documents"].append(doc)
    write_json(bundle_path, bundle)
    parent, _ = reference_run(workspace)
    run = prepare_source_packets(repo, parent)
    record = load_source_packets(repo, run)["packets"]
    included = 0
    for row in record["packets"]:
        index = json.loads((packet_root(run, row) / "source_index.json").read_text())
        for entry in index["sources"]:
            if entry["source_version_id"] == version:
                assert row["track"] == "full_bundle"
                assert row["condition_id"] != "original_reviewer"
                assert (
                    packet_root(run, row) / entry["local_file"]
                ).read_bytes() == source.read_bytes()
                included += 1
    assert included == 2
    assert record["medical_performance_validated"] is False
