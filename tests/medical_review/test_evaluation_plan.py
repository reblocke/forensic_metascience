from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json

from research_project.inspect_sr.records import evidence_id, source_version_id, stable_report_id
from research_project.medical_review.evaluation import (
    freeze_evaluation_plan,
    load_evaluation_plan,
    prepare_evaluation_plan,
)


def plan_input(workspace):
    repo, bundle_path, _, bundle, _ = workspace
    return {
        "schema_version": "medical_evaluation_plan_input_v1",
        "evaluation_id": "evaluation-synthetic",
        "revision": 1,
        "seed": 601,
        "conditions": [
            {"condition_id": name, "runtime": None}
            for name in ("strong_single_reviewer", "original_reviewer", "medical_adaptation")
        ],
        "cases": [
            {
                "case_id": "synthetic-trial",
                "bundle_reference": str(bundle_path.relative_to(repo)),
                "partition": "development",
                "previously_analyzed": False,
                "synthetic": True,
                "dependency_group": "synthetic-study",
                "profile_ids": ["clinical_trial"],
                "common_source_version_id": bundle["documents"][0]["source_version_id"],
                "upstream_full_bundle_source_version_ids": [
                    bundle["documents"][0]["source_version_id"]
                ],
            }
        ],
        "thresholds": None,
    }


def supplement(workspace):
    repo, bundle_path, _, bundle, _ = workspace
    source = bundle_path.parent / "sources/supplement.txt"
    source.write_text("Synthetic supplemental footnote.\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    document = copy.deepcopy(bundle["documents"][0])
    document.update(
        source_id="supplement",
        source_version_id=source_version_id("supplement", digest),
        role="supplement",
        path=str(source.relative_to(repo)),
        sha256=digest,
        upstream_paths=["inputs/supplement.txt"],
    )
    bundle["documents"].append(document)
    write_json(bundle_path, bundle)
    return document


def test_plan_distinguishes_equivalent_inputs_from_unmatched_upstream_access(workspace):
    repo, *_ = workspace
    supplement(workspace)
    data = plan_input(workspace)
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    plan = prepare_evaluation_plan(repo, data)
    assert {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()} == before
    common = [r for r in plan["comparisons"] if r["track"] == "common_input"]
    full = [r for r in plan["comparisons"] if r["track"] == "full_bundle"]
    assert len(common) == len(full) == 3
    assert len({tuple(r["source_version_ids"]) for r in common}) == 1
    assert all(r["input_equivalence"] == "matched" for r in common)
    assert (
        next(r for r in full if r["condition_id"] == "original_reviewer")["input_equivalence"]
        == "unmatched"
    )
    assert (
        len(
            {
                tuple(r["source_version_ids"])
                for r in full
                if r["condition_id"] != "original_reviewer"
            }
        )
        == 1
    )
    assert plan["runtime_comparison"] == "unknown_planned_runtime"
    assert plan["qualification"]["status"] == "pending"
    assert plan["qualification"]["medical_performance_validated"] is False
    assert plan["execution_permissions"] == {"allow_llm": False, "allow_web_search": False}


def test_plan_limit_includes_saved_identity_and_newline(workspace, monkeypatch):
    from research_project.medical_review import evaluation as module

    repo, *_ = workspace
    data = plan_input(workspace)
    plan = prepare_evaluation_plan(repo, data)
    saved_size = len(json.dumps(plan, sort_keys=True, ensure_ascii=False, indent=2).encode()) + 1
    monkeypatch.setattr(module, "MAX_JSON_BYTES", saved_size - 1)
    with pytest.raises(ValueError, match="exceeds"):
        prepare_evaluation_plan(repo, data)


@pytest.mark.parametrize("change", ["previous", "synthetic", "shared_study", "shared_group"])
def test_heldout_cannot_relabel_development_or_dependent_sources(workspace, change):
    repo, *_ = workspace
    data = plan_input(workspace)
    heldout = copy.deepcopy(data["cases"][0])
    heldout.update(case_id="heldout", partition="held_out", synthetic=False)
    if change == "previous":
        data["cases"] = [heldout]
        heldout["previously_analyzed"] = True
    elif change == "synthetic":
        data["cases"] = [heldout]
        heldout["synthetic"] = True
    elif change == "shared_study":
        heldout["dependency_group"] = "declared-independent-but-same-study"
        data["cases"].append(heldout)
    else:
        data["cases"].append(heldout)
    with pytest.raises(ValueError, match="held.out|development|dependen|synthetic"):
        prepare_evaluation_plan(repo, data)


@pytest.mark.parametrize("change", ["extra", "condition", "source", "profile", "threshold"])
def test_plan_rejects_fabricated_contract_and_unsupported_comparison_claims(workspace, change):
    repo, *_ = workspace
    data = plan_input(workspace)
    if change == "extra":
        data["human_verified"] = True
    elif change == "condition":
        data["conditions"].pop()
    elif change == "source":
        data["cases"][0]["upstream_full_bundle_source_version_ids"] = ["invented"]
    elif change == "profile":
        data["cases"][0]["profile_ids"] = ["systematic_review_meta_analysis"]
    else:
        data["thresholds"] = {"automatically_approved": True}
    with pytest.raises(ValueError):
        prepare_evaluation_plan(repo, data)


def test_full_bundle_upstream_adapter_cannot_be_assumed_from_declared_source_list(workspace):
    repo, *_ = workspace
    doc = supplement(workspace)
    data = plan_input(workspace)
    data["cases"][0]["upstream_full_bundle_source_version_ids"].append(doc["source_version_id"])
    with pytest.raises(ValueError, match="adapter|upstream"):
        prepare_evaluation_plan(repo, data)


def test_freeze_uses_canonical_run_and_preserves_raw_plan_and_code(workspace):
    repo, *_ = workspace
    data = plan_input(workspace)
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json", data
    )
    raw = path.read_bytes()
    run = freeze_evaluation_plan(repo, path)
    plan = load_evaluation_plan(repo, run)
    manifest = json.loads((run / "run_manifest.json").read_text())
    assert manifest["schema_version"] == "forensics_run_v3"
    assert manifest["status"] == "completed"
    assert manifest["effective_settings"]["allow_llm"] is False
    assert (run / "generated/medical_evaluation/raw/plan_input.json").read_bytes() == raw
    assert (run / "generated/medical_evaluation/code/evaluation.py").is_file()
    assert (
        run
        / "generated/medical_evaluation/sources/prompts/medical_review/strong_single_reviewer.txt"
    ).read_bytes() == (repo / "prompts/medical_review/strong_single_reviewer.txt").read_bytes()
    assert plan["qualification"]["feature_default_enabled"] is False
    second = freeze_evaluation_plan(repo, path)
    assert second != run
    assert load_evaluation_plan(repo, second)["plan_id"] == plan["plan_id"]
    assert (run / "generated/medical_evaluation/raw/plan_input.json").read_bytes() == raw


def test_frozen_plan_refuses_source_and_artifact_drift(workspace):
    repo, bundle_path, *_ = workspace
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    run = freeze_evaluation_plan(repo, path)
    source = bundle_path.parent / "sources/main.txt"
    before = source.read_bytes()
    source.write_bytes(before + b"Changed source.\n")
    with pytest.raises(ValueError, match="hash|source"):
        load_evaluation_plan(repo, run)
    source.write_bytes(before)
    artifact = run / "processed/medical_evaluation/plan.json"
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="artifact|hash"):
        load_evaluation_plan(repo, run)


def test_frozen_plan_rejects_resealed_code_without_its_recorded_code_binding(workspace):
    repo, *_ = workspace
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    run = freeze_evaluation_plan(repo, path)
    code = run / "generated/medical_evaluation/code/evaluation.py"
    code.write_bytes(code.read_bytes() + b"\n# Changed archived code.\n")
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    row = next(r for r in manifest["artifacts"] if r["path"] == str(code.relative_to(run)))
    row["sha256"] = hashlib.sha256(code.read_bytes()).hexdigest()
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="code"):
        load_evaluation_plan(repo, run)


@pytest.mark.parametrize("different", [False, True])
def test_declared_runtime_comparison_never_grants_execution(workspace, different):
    repo, *_ = workspace
    data = plan_input(workspace)
    runtime = {
        "provider": "synthetic-provider",
        "backend": "synthetic-backend",
        "model": "synthetic-model",
        "tools": ["source_read"],
        "limits": {"max_sessions": 1, "max_duration_seconds": 60},
    }
    for row in data["conditions"]:
        row["runtime"] = copy.deepcopy(runtime)
    if different:
        data["conditions"][0]["runtime"]["model"] = "different-synthetic-model"
    plan = prepare_evaluation_plan(repo, data)
    assert plan["runtime_comparison"] == (
        "workflow_plus_runtime" if different else "same_planned_runtime"
    )
    assert plan["qualification"]["status"] == "pending"
    assert plan["execution_permissions"]["allow_llm"] is False


def test_real_cli_plan_is_output_free_and_freeze_is_explicit(workspace):
    repo, *_ = workspace
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src/research_project", repo / "src/research_project")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    command = [
        sys.executable,
        str(repo / "scripts/medical_review.py"),
        "evaluation-plan",
        "--input",
        str(path),
    ]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["qualification"]["status"] == "pending"
    assert {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()} == before
    result = subprocess.run([*command, "--freeze"], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert load_evaluation_plan(repo, Path(result.stdout.strip()))["plan_id"] == plan["plan_id"]


def test_copied_source_cannot_be_held_out_by_renaming_all_declared_identities(workspace):
    repo, bundle_path, _, original, _ = workspace
    data = plan_input(workspace)
    alias = copy.deepcopy(original)
    alias["study_id"] = "synthetic-alias"
    alias["studies"] = [{"study_id": "synthetic-alias", "trial_id": None}]
    report = stable_report_id("", local_key="synthetic-alias-report")
    alias["reports"] = [
        {"report_id": report, "study_ids": ["synthetic-alias"], "mapping_reviewed": True}
    ]
    target = repo / "data/private/medical_reviews/synthetic-alias/sources/main.txt"
    target.parent.mkdir(parents=True)
    target.write_bytes((bundle_path.parent / "sources/main.txt").read_bytes())
    doc = alias["documents"][0]
    doc.update(
        source_id="aliased-main",
        report_ids=[report],
        path=str(target.relative_to(repo)),
        source_version_id=source_version_id("aliased-main", doc["sha256"]),
    )
    ev = alias["evidence"][0]
    ev.update(source_version_id=doc["source_version_id"], parsed_path=str(target.relative_to(repo)))
    ev["evidence_id"] = evidence_id(
        ev["source_version_id"],
        ev["locator"],
        ev["raw_value"],
        ev["parser"]["id"],
        ev["parser"]["version"],
    )
    alias["planned_checks"][0]["study_id"] = "synthetic-alias"
    alias_path = write_json(target.parent.parent / "bundle.json", alias)
    heldout = copy.deepcopy(data["cases"][0])
    heldout.update(
        case_id="renamed-heldout",
        partition="held_out",
        synthetic=False,
        dependency_group="declared-independent",
        bundle_reference=str(alias_path.relative_to(repo)),
        common_source_version_id=doc["source_version_id"],
        upstream_full_bundle_source_version_ids=[doc["source_version_id"]],
    )
    data["cases"].append(heldout)
    with pytest.raises(ValueError, match="Dependent|held.out"):
        prepare_evaluation_plan(repo, data)


def test_midfreeze_source_drift_preserves_failed_attempt_and_raw_input(workspace, monkeypatch):
    import research_project.medical_review.evaluation as evaluation

    repo, bundle_path, *_ = workspace
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    raw = path.read_bytes()
    original_create = evaluation.create_run

    def drifting_create(**kwargs):
        result = original_create(**kwargs)
        source = bundle_path.parent / "sources/main.txt"
        source.write_bytes(source.read_bytes() + b"External source drift.\n")
        return result

    monkeypatch.setattr(evaluation, "create_run", drifting_create)
    with pytest.raises(ValueError, match="hash|changed"):
        freeze_evaluation_plan(repo, path)
    runs = list(
        (repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic").iterdir()
    )
    assert len(runs) == 1
    assert json.loads((runs[0] / "run_manifest.json").read_text())["status"] == "failed"
    assert (runs[0] / "generated/medical_evaluation/raw/plan_input.json").read_bytes() == raw
    assert not (runs[0] / "processed/medical_evaluation/plan.json").exists()


def test_changed_comparator_requires_new_plan_but_retains_frozen_original(workspace):
    repo, *_ = workspace
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    run = freeze_evaluation_plan(repo, path)
    prompt = repo / "prompts/medical_review/strong_single_reviewer.txt"
    original = prompt.read_bytes()
    prompt.write_bytes(original + b"\nChanged comparator.\n")
    with pytest.raises(ValueError, match="dependency"):
        load_evaluation_plan(repo, run)
    archived = (
        run
        / "generated/medical_evaluation/sources/prompts/medical_review/strong_single_reviewer.txt"
    )
    assert archived.read_bytes() == original
