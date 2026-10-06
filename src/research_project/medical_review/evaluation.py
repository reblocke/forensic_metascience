"""Offline, source-bound evaluation planning; qualification and live execution remain pending."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.bundle import load_bundle
from research_project.medical_review.context import build_study_context
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    UPSTREAM_COMMIT,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.medical_review.routing import build_review_plan
from research_project.run_manifest import create_run, update_run

CONDITIONS = ("strong_single_reviewer", "original_reviewer", "medical_adaptation")
PROFILES = {"clinical_trial", "observational_rwd", "diagnostic_accuracy", "prediction_model"}
PLAN_FIELDS = {
    "schema_version",
    "evaluation_id",
    "revision",
    "seed",
    "conditions",
    "cases",
    "thresholds",
}
CASE_FIELDS = {
    "case_id",
    "bundle_reference",
    "partition",
    "previously_analyzed",
    "synthetic",
    "dependency_group",
    "profile_ids",
    "common_source_version_id",
    "upstream_full_bundle_source_version_ids",
}


def _exact(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"Unsupported evaluation {label} contract fields.")


def _identifier(value: Any, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError(f"Evaluation {label} requires an explicit bounded local identity.")


def _public_file(repo: Path, reference: str) -> dict[str, str]:
    relative = Path(reference)
    path = repo / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe evaluation comparator source path.")
    if any(p.is_symlink() for p in (path, *path.parents) if p != repo):
        raise ValueError("Evaluation comparator source symlinks are refused.")
    return {"reference": reference, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _conditions(repo: Path, rows: Any) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(rows, list) or len(rows) != len(CONDITIONS):
        raise ValueError("Evaluation requires all three predeclared comparison conditions.")
    conditions = []
    seen = set()
    for row in rows:
        _exact(row, {"condition_id", "runtime"}, "condition")
        name = row["condition_id"]
        if name not in CONDITIONS or name in seen:
            raise ValueError("Unknown or duplicate evaluation comparison condition.")
        seen.add(name)
        runtime = row["runtime"]
        if runtime is not None:
            _exact(runtime, {"provider", "backend", "model", "tools", "limits"}, "planned runtime")
            for field in ("provider", "backend", "model"):
                if not isinstance(runtime[field], str) or not runtime[field].strip():
                    raise ValueError("Planned runtime identity must be explicit.")
            if (
                not isinstance(runtime["tools"], list)
                or any(tool not in {"source_read", "web_search"} for tool in runtime["tools"])
                or len(set(runtime["tools"])) != len(runtime["tools"])
            ):
                raise ValueError("Planned evaluation tools require explicit supported scope.")
            _exact(runtime["limits"], {"max_sessions", "max_duration_seconds"}, "runtime limits")
            if any(type(v) is not int or v < 1 for v in runtime["limits"].values()):
                raise ValueError("Planned evaluation resource limits must be positive integers.")
        conditions.append(copy.deepcopy(row))
    runtimes = [row["runtime"] for row in conditions]
    comparison = (
        "unknown_planned_runtime"
        if any(r is None for r in runtimes)
        else (
            "same_planned_runtime"
            if all(r == runtimes[0] for r in runtimes)
            else "workflow_plus_runtime"
        )
    )
    return sorted(conditions, key=lambda r: CONDITIONS.index(r["condition_id"])), comparison


def _source_records(repo: Path) -> dict[str, Any]:
    upstream = read_json(repo / "config/medical_review/upstream/provenance.json")
    if upstream.get("commit") != UPSTREAM_COMMIT or upstream.get("license") != "MIT":
        raise ValueError("Evaluation original Reviewer provenance is not the pinned comparator.")
    for row in upstream["files"]:
        reference = "config/medical_review/upstream/" + row["local_path"]
        if _public_file(repo, reference)["sha256"] != row["sha256"]:
            raise ValueError("Pinned upstream comparator source hash changed.")
    return {
        "strong_single_reviewer": _public_file(
            repo, "prompts/medical_review/strong_single_reviewer.txt"
        ),
        "original_reviewer": {
            "repository": upstream["repository"],
            "commit": UPSTREAM_COMMIT,
            "workflow_modifications": "none",
            "provenance": _public_file(repo, "config/medical_review/upstream/provenance.json"),
        },
        "medical_adaptation": _public_file(repo, "config/medical_review/check_catalogue.json"),
        "upstream_multi_document_adapter": "unavailable_not_assumed",
    }


def _code_sources() -> dict[str, Path]:
    package = Path(__file__).parent
    return {
        **{
            name: package / name
            for name in (
                "evaluation.py",
                "records.py",
                "bundle.py",
                "context.py",
                "routing.py",
                "audit.py",
            )
        },
        "run_manifest.py": package.parent / "run_manifest.py",
        "inspect_sr_records.py": package.parent / "inspect_sr/records.py",
    }


def prepare_evaluation_plan(repo_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Validate a proposed paired plan without writes, source retrieval or model calls."""
    repo = repo_root.resolve()
    _exact(data, PLAN_FIELDS, "plan")
    if data["schema_version"] != "medical_evaluation_plan_input_v1":
        raise ValueError("Unsupported evaluation plan schema.")
    _identifier(data["evaluation_id"], "evaluation_id")
    if type(data["revision"]) is not int or data["revision"] < 1:
        raise ValueError("Evaluation plan revision must be positive.")
    if type(data["seed"]) is not int or not 0 <= data["seed"] < 2**31:
        raise ValueError("Evaluation blinding seed must be an explicit nonnegative 31-bit integer.")
    if data["thresholds"] is not None:
        raise ValueError(
            "Threshold approval/adoption is not implemented in this planning increment."
        )
    conditions, runtime_comparison = _conditions(repo, data["conditions"])
    if not isinstance(data["cases"], list) or not 1 <= len(data["cases"]) <= 256:
        raise ValueError("Evaluation plan requires 1..256 bounded case records.")
    cases, comparisons, tokens, seen = [], [], [], set()
    for row in data["cases"]:
        _exact(row, CASE_FIELDS, "case")
        for key in ("case_id", "dependency_group"):
            _identifier(row[key], key)
        if row["case_id"] in seen:
            raise ValueError("Duplicate evaluation case identity.")
        seen.add(row["case_id"])
        if row["partition"] not in {"development", "held_out"} or any(
            type(row[k]) is not bool for k in ("previously_analyzed", "synthetic")
        ):
            raise ValueError("Evaluation case partition/history must be explicit.")
        if row["partition"] == "held_out" and (row["previously_analyzed"] or row["synthetic"]):
            raise ValueError(
                "Previously analyzed or synthetic cases cannot count as held-out evidence."
            )
        profiles = row["profile_ids"]
        if not isinstance(profiles, list) or not profiles or not set(profiles) <= PROFILES:
            raise ValueError("Evaluation case needs supported initial medical profiles.")
        reference = row["bundle_reference"]
        if (
            not isinstance(reference, str)
            or Path(reference).is_absolute()
            or ".." in Path(reference).parts
        ):
            raise ValueError("Evaluation bundle references must be contained repo-relative paths.")
        bundle, digest = load_bundle(repo, Path(reference))
        context = build_study_context(bundle, bundle.get("context_fields"))
        review_plan = build_review_plan(bundle, context, profiles, repo)
        documents = [d for d in bundle["documents"] if d["availability"] == "supplied"]
        versions = {d["source_version_id"] for d in documents}
        main = row["common_source_version_id"]
        if main not in {d["source_version_id"] for d in documents if d["role"] == "manuscript"}:
            raise ValueError("Common-input track needs one supplied exact manuscript version.")
        upstream_versions = row["upstream_full_bundle_source_version_ids"]
        if not isinstance(upstream_versions, list) or upstream_versions != [main]:
            raise ValueError("Unverified upstream multi-document adapter/source access is refused.")
        case = {
            **copy.deepcopy(row),
            "bundle_sha256": digest,
            "bundle": bundle,
            "context_sha256": content_hash(context),
            "review_plan": review_plan,
            "source_fidelity_verified": False,
        }
        cases.append(case)
        token = {"group:" + row["dependency_group"]}
        token.update("study:" + r["study_id"] for r in bundle["studies"])
        token.update("report:" + r["report_id"] for r in bundle["reports"])
        token.update("source:" + d["sha256"] for d in documents)
        tokens.append(token)
        for track in ("common_input", "full_bundle"):
            for condition in CONDITIONS:
                source_ids = (
                    [main]
                    if track == "common_input" or condition == "original_reviewer"
                    else sorted(versions)
                )
                comparisons.append(
                    {
                        "case_id": row["case_id"],
                        "track": track,
                        "condition_id": condition,
                        "source_version_ids": source_ids,
                        "input_equivalence": "unmatched"
                        if track == "full_bundle" and set(source_ids) != versions
                        else "matched",
                        "equivalence_scope": (
                            "planned_exact_source_access_not_executed_or_fidelity_verified"
                        ),
                        "execution": "not_requested",
                    }
                )
        if len(json.dumps(cases, ensure_ascii=False).encode()) > MAX_JSON_BYTES:
            raise ValueError("Evaluation plan source metadata exceeds 20 MiB; split explicitly.")
    # Connected components bind declared study families plus independently checked
    # study/report identities and exact content, including aliases and versions.
    groups = [set([i]) for i in range(len(cases))]
    for i, left in enumerate(tokens):
        for j in range(i):
            if left & tokens[j]:
                union = groups[i] | groups[j]
                for k in union:
                    groups[k] = union
    for group in {tuple(sorted(g)) for g in groups}:
        if len({cases[i]["partition"] for i in group}) != 1:
            raise ValueError(
                "Dependent study/report/source versions span development and held-out partitions."
            )
        unit = identity("evaluationstudy", sorted(cases[i]["case_id"] for i in group))
        for i in group:
            cases[i]["analysis_unit_id"] = unit
    assets = {
        "prompts/medical_review/strong_single_reviewer.txt",
        "config/medical_review/upstream/provenance.json",
        "config/medical_review/check_catalogue.json",
        "config/medical_review/guidance_registry.json",
    }
    upstream = read_json(repo / "config/medical_review/upstream/provenance.json")
    assets.update("config/medical_review/upstream/" + r["local_path"] for r in upstream["files"])
    assets.update(r["path"] for case in cases for r in case["review_plan"]["prompt_sources"])
    plan = {
        "schema_version": "medical_evaluation_plan_v1",
        "evaluation_id": data["evaluation_id"],
        "revision": data["revision"],
        "seed": data["seed"],
        "input": copy.deepcopy(data),
        "conditions": conditions,
        "comparator_sources": _source_records(repo),
        "public_assets": [_public_file(repo, reference) for reference in sorted(assets)],
        "runtime_comparison": runtime_comparison,
        "cases": cases,
        "comparisons": comparisons,
        "dependence_scope": (
            "declared_groups_canonical_study_report_ids_and_content_hashes_not_proof_of_novelty"
        ),
        "execution_permissions": {"allow_llm": False, "allow_web_search": False},
        "qualification": {
            "status": "pending",
            "medical_performance_validated": False,
            "feature_default_enabled": False,
            "remaining": [
                "source_and_runtime_approval",
                "operational_smoke_test",
                "source_adjudicated_reference_ledger",
                "blinded_adjudication",
                "approved_preunblinding_thresholds",
                "sufficient_heldout_evaluation",
            ],
        },
    }
    if len(json.dumps(plan, ensure_ascii=False, indent=2).encode()) > MAX_JSON_BYTES:
        raise ValueError("Evaluation plan exceeds 20 MiB; explicit bounded splitting required.")
    return {**plan, "plan_id": identity("medicalevaluationplan", plan)}


def freeze_evaluation_plan(repo_root: Path, input_path: Path) -> Path:
    """Freeze an explicit local plan into a fresh canonical immutable run."""
    repo = repo_root.resolve()
    path = private_path(repo, input_path, PRIVATE_SOURCES)
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    data = parse_json(raw)
    plan = prepare_evaluation_plan(repo, data)
    private_path(repo, path, PRIVATE_SOURCES / data["evaluation_id"] / "evaluation")
    code_sources = _code_sources()
    code = {name: path.read_bytes() for name, path in code_sources.items()}
    assets = {r["reference"]: (repo / r["reference"]).read_bytes() for r in plan["public_assets"]}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=data["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=path,
        input_paths=[repo / c["bundle_reference"] for c in data["cases"]],
        settings={
            "medical_evaluation_plan_sha256": content_hash(plan),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        raw_path = run / "generated/medical_evaluation/raw/plan_input.json"
        raw_path.parent.mkdir(parents=True)
        with raw_path.open("xb") as stream:
            stream.write(raw)
        update_run(manifest, artifact=str(raw_path))
        for name, contents in code.items():
            target = run / "generated/medical_evaluation/code" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(contents)
            update_run(manifest, artifact=str(target))
        for reference, contents in assets.items():
            target = run / "generated/medical_evaluation/sources" / reference
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(contents)
            update_run(manifest, artifact=str(target))
        if (
            path.read_bytes() != raw
            or prepare_evaluation_plan(repo, data) != plan
            or any(code_sources[name].read_bytes() != contents for name, contents in code.items())
            or any((repo / ref).read_bytes() != contents for ref, contents in assets.items())
        ):
            raise ValueError("Evaluation plan/source/prompt/code changed while freezing.")
        artifact = run / "processed/medical_evaluation/plan.json"
        write_json(artifact, plan)
        update_run(manifest, artifact=str(artifact))
        update_run(manifest, stage="evaluation-plan", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_evaluation_plan(repo_root: Path, run_path: Path) -> dict[str, Any]:
    """Load only an explicit completed source/prompt-bound plan for dependent reuse."""
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if manifest["status"] != "completed" or not settings.get("medical_evaluation_plan_sha256"):
        raise ValueError("Evaluation plan run is not successfully frozen.")
    path = recorded_artifact(repo, run, manifest, "processed/medical_evaluation/plan.json")
    plan = read_json(path)
    raw_path = recorded_artifact(
        repo, run, manifest, "generated/medical_evaluation/raw/plan_input.json"
    )
    raw = raw_path.read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(plan) != settings["medical_evaluation_plan_sha256"]
    ):
        raise ValueError("Evaluation plan raw/source binding changed.")
    archived_code = {
        name: hashlib.sha256(
            recorded_artifact(
                repo, run, manifest, "generated/medical_evaluation/code/" + name
            ).read_bytes()
        ).hexdigest()
        for name in _code_sources()
    }
    if content_hash(archived_code) != settings["code_sha256"]:
        raise ValueError("Evaluation archived code binding changed.")
    for asset in plan["public_assets"]:
        path = recorded_artifact(
            repo, run, manifest, "generated/medical_evaluation/sources/" + asset["reference"]
        )
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError("Evaluation archived prompt/config source binding changed.")
    if prepare_evaluation_plan(repo, parse_json(raw)) != plan:
        raise ValueError("Frozen evaluation plan dependency/authority changed; prepare a new plan.")
    return plan
