"""Offline minimum-content source packets; no backend or blinding qualification."""

from __future__ import annotations

import hashlib
import json
import random
import stat
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation_reference import (
    _code_sources as reference_code_sources,
)
from research_project.medical_review.evaluation_reference import load_reference_ledger
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

DEFAULT_PACKET_BYTES = 64 * 1024 * 1024
DEFAULT_TOTAL_BYTES = 512 * 1024 * 1024
MAX_PACKETS = 1024
MAX_FILES = 16384
WORKSPACES = "generated/medical_evaluation/reviewer_workspaces"
PROTECTED_DIRECTORIES = {
    "authorizations",
    "human_dispositions",
    "numeric_input_reviews",
    "evaluation",
}
PRIVATE_SCHEMA_PREFIXES = (
    "medical_evaluation_",
    "medical_execution_",
    "medical_human_",
    "medical_numeric_input_review_",
    "medical_numeric_check_",
    "medical_arithmetic_",
    "medical_source_authorization_",
    "medical_review_",
    "medical_reviewer_",
    "medical_study_context_",
    "medical_verification_",
    "medical_method_handoff_",
    "medical_import_",
    "medical_parser_preflight_",
    "medical_manual_adoption_",
    "inspect_sr_",
    "forensics_run_",
)


def _source_path(repo: Path, case: dict[str, Any], doc: dict[str, Any]) -> Path:
    scope = PRIVATE_SOURCES / case["bundle"]["study_id"]
    source = private_path(repo, Path(doc["path"]), scope)
    if source.relative_to(repo / scope).parts[0] in PROTECTED_DIRECTORIES:
        raise ValueError(
            "Protected private record locations cannot become reviewer source documents."
        )
    with source.open("rb") as stream:
        start = stream.read(256)
        if source.suffix.lower() == ".json" or start.lstrip().startswith((b"{", b"[")):
            stream.seek(0)
            try:
                data = parse_json(stream.read(MAX_JSON_BYTES + 1))
            except (ValueError, RecursionError) as error:
                raise ValueError(
                    "Cannot establish source JSON's private-record boundary."
                ) from error
            pending = [data]
            while pending:
                item = pending.pop()
                if isinstance(item, dict):
                    schema = item.get("schema_version")
                    if isinstance(schema, str) and schema.startswith(PRIVATE_SCHEMA_PREFIXES):
                        raise ValueError(
                            "Private review/evaluation records cannot be staged "
                            "as source documents."
                        )
                    pending.extend(item.values())
                elif isinstance(item, list):
                    pending.extend(item)
    return source


def _json_bytes(value: Any) -> bytes:
    raw = (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Source packet JSON exceeds 20 MiB; explicit bounded splitting required.")
    return raw


def _limits(repetitions: int, packet_bytes: int, total_bytes: int) -> dict[str, int]:
    if type(repetitions) is not int or not 1 <= repetitions <= 64:
        raise ValueError("Source packet repetitions require an explicit integer in 1..64.")
    if any(type(v) is not int or v < 1 for v in (packet_bytes, total_bytes)):
        raise ValueError("Source packet byte limits must be positive integers.")
    return {
        "repetitions": repetitions,
        "max_packet_bytes": packet_bytes,
        "max_total_bytes": total_bytes,
    }


def _instruction_files(repo: Path, case: dict[str, Any], condition: str) -> dict[str, bytes]:
    upstream = repo / "config/medical_review/upstream"
    if condition == "original_reviewer":
        # These retained originals are not the complete executable workflow.
        return {
            "instructions/upstream/" + row["local_path"]: (
                upstream / row["local_path"]
            ).read_bytes()
            for row in read_json(upstream / "provenance.json")["files"]
        }
    catalogue = read_json(repo / "config/medical_review/check_catalogue.json")
    profiles = case["review_plan"]["selected_profiles"]
    checks = [
        r
        for r in catalogue["checks"]
        if r["module"] == "core" or set(r["profiles"]).intersection(profiles)
    ]
    # Only public rule text is copied. Bundle overrides, context fields, evidence
    # annotations and source-reference decisions cannot enter this reconstruction.
    scope = {
        "schema_version": "medical_evaluation_reviewer_scope_v1",
        "profile_ids": profiles,
        "shared_reconstruction": "withheld_reconstruct_from_staged_sources",
        "applicability": "reconstruct_from_staged_sources_profiles_are_routing_hints",
        "guidance_status": "unavailable_no_guideline_specific_claims",
        "output_schema": "instructions/upstream/reviewer_output.schema.json",
        "checks": [
            {
                key: r[key]
                for key in (
                    "check_id",
                    "module",
                    "reviewer",
                    "question",
                    "safeguard",
                    "required_source_role_groups",
                )
            }
            for r in checks
        ],
        "execution_permissions": {"allow_llm": False, "allow_web_search": False},
        "limitations": [
            "Generic responsibilities are not inspected coverage or session-spawning instructions.",
            "Source fidelity is unverified; reconstruct actual applicability from supplied bytes.",
            "Workspace staging is not process isolation or source transmission authorization.",
        ],
    }
    names = {"shared_evidence", *{r["module"] for r in checks}}
    if condition == "strong_single_reviewer":
        names.add("strong_single_reviewer")
    else:
        names.update({"counterevidence", "editor"})
    return {
        "review_scope.json": _json_bytes(scope),
        **{
            "instructions/" + name + ".txt": (
                repo / "prompts/medical_review" / (name + ".txt")
            ).read_bytes()
            for name in sorted(names)
        },
        **{
            "instructions/upstream/" + name: (upstream / name).read_bytes()
            for name in ("LICENSE.md", "reviewer_output.schema.json")
        },
    }


def _specifications(
    repo: Path, reference: dict[str, Any], limits: dict[str, int]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    plan, ledger = reference["plan"], reference["ledger"]
    if len(plan["comparisons"]) * limits["repetitions"] > MAX_PACKETS:
        raise ValueError(
            "Source packet count exceeds 1024 limit; split explicitly, preserving study dependence."
        )
    cases = {r["case_id"]: r for r in plan["cases"]}
    source_paths = {
        (case["case_id"], d["source_version_id"]): _source_path(repo, case, d)
        for case in cases.values()
        for d in case["bundle"]["documents"]
        if d["availability"] == "supplied"
    }
    packets, contents, total, file_count = [], {}, 0, 0
    for comparison in plan["comparisons"]:
        case = cases[comparison["case_id"]]
        docs = {
            d["source_version_id"]: d
            for d in case["bundle"]["documents"]
            if d["availability"] == "supplied"
        }
        for repetition in range(1, limits["repetitions"] + 1):
            packet_id = identity(
                "packet",
                {
                    "plan_id": plan["plan_id"],
                    "ledger_id": ledger["ledger_id"],
                    "seed": plan["seed"],
                    "comparison": comparison,
                    "repetition": repetition,
                },
            )
            literals = _instruction_files(repo, case, comparison["condition_id"])
            sources, aliases, paths = [], [], {}
            for index, version in enumerate(comparison["source_version_ids"], 1):
                doc = docs[version]
                source = source_paths[(case["case_id"], version)]
                suffix = source.suffix.lower()
                if suffix not in {".pdf", ".txt", ".csv", ".tsv", ".json"}:
                    suffix = ".bin"
                local = f"sources/source-{index:03d}{suffix}"
                sources.append(
                    {
                        "source_version_id": version,
                        "sha256": doc["sha256"],
                        "role": doc["role"],
                        "local_file": local,
                    }
                )
                aliases.append(
                    {
                        "local_file": local,
                        "source_version_id": version,
                        "original_reference": doc["path"],
                        "upstream_paths": doc.get("upstream_paths", []),
                    }
                )
                paths[local] = source
            literals["source_index.json"] = _json_bytes(
                {
                    "schema_version": "medical_evaluation_source_index_v1",
                    "packet_id": packet_id,
                    "sources": sources,
                    "source_fidelity_verified": False,
                }
            )
            receipts = [
                {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}
                for name, raw in sorted(literals.items())
            ]
            receipts.extend(
                {
                    "path": r["local_file"],
                    "sha256": r["sha256"],
                    "byte_count": paths[r["local_file"]].stat().st_size,
                }
                for r in sources
            )
            size = sum(r["byte_count"] for r in receipts)
            total += size
            file_count += len(receipts)
            if size > limits["max_packet_bytes"] or total > limits["max_total_bytes"]:
                raise ValueError("Source packet byte limit exceeded before staging; no truncation.")
            if file_count > MAX_FILES:
                raise ValueError("Source packet file count exceeds 16384 limit; split explicitly.")
            packets.append(
                {
                    "packet_id": packet_id,
                    "case_id": case["case_id"],
                    "analysis_unit_id": case["analysis_unit_id"],
                    "partition": case["partition"],
                    "synthetic": case["synthetic"],
                    "track": comparison["track"],
                    "condition_id": comparison["condition_id"],
                    "repetition": repetition,
                    "source_version_ids": comparison["source_version_ids"],
                    "input_equivalence": comparison["input_equivalence"],
                    "workspace_reference": WORKSPACES + "/" + packet_id,
                    "files": sorted(receipts, key=lambda r: r["path"]),
                    "workspace_bytes": size,
                    "source_aliases": aliases,
                    "comparator_execution": "blocked_unmodified_workflow_not_staged_or_executed"
                    if comparison["condition_id"] == "original_reviewer"
                    else "not_requested",
                }
            )
            contents[packet_id] = {"literals": literals, "sources": paths}
    random.Random(plan["seed"]).shuffle(packets)
    record = {
        "schema_version": "medical_evaluation_source_packets_v1",
        "plan_id": plan["plan_id"],
        "ledger_id": ledger["ledger_id"],
        "limits": limits,
        "packets": packets,
        "total_workspace_bytes": total,
        "runtime_comparison": plan["runtime_comparison"],
        "planned_conditions": plan["conditions"],
        "equivalence_scope": "staged_exact_source_bytes_not_executed_or_fidelity_verified",
        "execution": "not_requested",
        "backend_isolation_qualified": False,
        "medical_performance_validated": False,
        "execution_permissions": {"allow_llm": False, "allow_web_search": False},
        "blinding_scope": (
            "opaque_packet_ids_private_condition_mapping_not_candidate_assessor_blinding"
        ),
    }
    record["record_id"] = identity("medicalevaluationpackets", record)
    _json_bytes(record)
    return record, contents


def _code_sources() -> dict[str, Path]:
    return {**reference_code_sources(), "evaluation_packets.py": Path(__file__)}


def _freeze_directory(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
    root.chmod(0o555)


def _validate_workspaces(
    repo: Path, run: Path, manifest: dict[str, Any], record: dict[str, Any]
) -> None:
    parent = private_path(repo, run / WORKSPACES, PRIVATE_RUNS)
    if {p.name for p in parent.iterdir()} != {r["packet_id"] for r in record["packets"]}:
        raise ValueError("Source packet workspace inventory changed.")
    if stat.S_IMODE(parent.stat().st_mode) != 0o555:
        raise ValueError("Source packet directory must remain read-only.")
    for row in record["packets"]:
        root = private_path(repo, run / row["workspace_reference"], PRIVATE_RUNS)
        paths = {str(p.relative_to(root)): p for p in root.rglob("*")}
        expected_files = {r["path"] for r in row["files"]}
        expected_dirs = {
            str(p) for name in expected_files for p in Path(name).parents if str(p) != "."
        }
        if set(paths) != expected_files | expected_dirs:
            raise ValueError("Source packet file/directory inventory changed.")
        for path in (root, *paths.values()):
            private_path(repo, path, PRIVATE_RUNS)
            expected_mode = 0o555 if path.is_dir() else 0o444
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != expected_mode:
                raise ValueError(
                    "Source packet permissions require read-only, non-executable files."
                )
        for item in row["files"]:
            path = recorded_artifact(
                repo, run, manifest, row["workspace_reference"] + "/" + item["path"]
            )
            if path.stat().st_size != item["byte_count"] or sha256_file(path) != item["sha256"]:
                raise ValueError("Source packet bytes/hash changed.")


def prepare_source_packets(
    repo_root: Path,
    reference_run: Path,
    *,
    repetitions: int = 1,
    max_packet_bytes: int = DEFAULT_PACKET_BYTES,
    max_total_bytes: int = DEFAULT_TOTAL_BYTES,
) -> Path:
    """Stage only explicit local sources/public instructions; never start a reviewer."""
    repo = repo_root.resolve()
    limits = _limits(repetitions, max_packet_bytes, max_total_bytes)
    parent = private_path(repo, reference_run, PRIVATE_RUNS)
    parent_hash = sha256_file(parent / "run_manifest.json")
    reference = load_reference_ledger(repo, parent)
    record, contents = _specifications(repo, reference, limits)
    code_sources = _code_sources()
    code = {name: path.read_bytes() for name, path in code_sources.items()}
    request = {
        "schema_version": "medical_evaluation_packet_request_v1",
        "reference_run": str(parent.relative_to(repo)),
        "reference_manifest_sha256": parent_hash,
        "limits": limits,
    }
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=reference["plan"]["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=parent / "processed/medical_evaluation/reference_ledger.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_packets_sha256": content_hash(record),
            "request": request,
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        raw = run / "generated/medical_evaluation/raw/source_packet_request.json"
        write_json(raw, request)
        update_run(manifest, artifact=str(raw))
        for name, value in code.items():
            target = run / "generated/medical_evaluation/code" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(value)
            update_run(manifest, artifact=str(target))
        actual_total = 0
        for row in record["packets"]:
            root = private_path(repo, run / row["workspace_reference"], PRIVATE_RUNS)
            actual_packet = 0
            values = contents[row["packet_id"]]
            for item in row["files"]:
                target = root / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                if item["path"] in values["literals"]:
                    with target.open("xb") as stream:
                        stream.write(values["literals"][item["path"]])
                    count = target.stat().st_size
                    actual_packet += count
                    actual_total += count
                else:
                    source = private_path(repo, values["sources"][item["path"]], PRIVATE_SOURCES)
                    with source.open("rb") as incoming, target.open("xb") as outgoing:
                        for chunk in iter(lambda: incoming.read(128 * 1024), b""):
                            actual_packet += len(chunk)
                            actual_total += len(chunk)
                            if (
                                actual_packet > limits["max_packet_bytes"]
                                or actual_total > limits["max_total_bytes"]
                            ):
                                raise ValueError(
                                    "Source packet byte limit changed/exceeded while copying."
                                )
                            outgoing.write(chunk)
                if (
                    actual_packet > limits["max_packet_bytes"]
                    or actual_total > limits["max_total_bytes"]
                ):
                    raise ValueError(
                        "Source packet byte limit exceeded while staging instructions."
                    )
                if (
                    target.stat().st_size != item["byte_count"]
                    or sha256_file(target) != item["sha256"]
                ):
                    raise ValueError("Source packet source/prompt hash changed while copying.")
                target.chmod(0o444)
                update_run(manifest, artifact=str(target))
            _freeze_directory(root)
        _freeze_directory(run / WORKSPACES)
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or _specifications(repo, load_reference_ledger(repo, parent), limits)[0] != record
            or any(code_sources[k].read_bytes() != value for k, value in code.items())
        ):
            raise ValueError("Source packet parent/source/prompt/code changed while staging.")
        _validate_workspaces(repo, run, read_json(manifest), record)
        path = run / "processed/medical_evaluation/source_packets.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="evaluation-packets", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_source_packets(repo_root: Path, run_path: Path) -> dict[str, Any]:
    """Validate exact inventory/bytes/modes and source/reference lineage for reuse."""
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if manifest["status"] != "completed" or not settings.get("medical_evaluation_packets_sha256"):
        raise ValueError("Source packet run is not successfully completed.")
    request = read_json(
        recorded_artifact(
            repo, run, manifest, "generated/medical_evaluation/raw/source_packet_request.json"
        )
    )
    if (
        request != settings["request"]
        or request["schema_version"] != "medical_evaluation_packet_request_v1"
    ):
        raise ValueError("Source packet request binding changed.")
    limits = request["limits"]
    if (
        _limits(limits["repetitions"], limits["max_packet_bytes"], limits["max_total_bytes"])
        != limits
    ):
        raise ValueError("Source packet limit contract changed.")
    parent = private_path(repo, Path(request["reference_run"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != request["reference_manifest_sha256"]:
        raise ValueError("Source packet reference manifest changed.")
    reference = load_reference_ledger(repo, parent)
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/source_packets.json")
    )
    archived = {
        name: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + name)
        )
        for name in _code_sources()
    }
    if (
        content_hash(archived) != settings["code_sha256"]
        or content_hash(record) != settings["medical_evaluation_packets_sha256"]
        or _specifications(repo, reference, limits)[0] != record
    ):
        raise ValueError("Source packet code/semantic/reference binding changed.")
    _validate_workspaces(repo, run, manifest, record)
    return {"run_root": run, "manifest": manifest, "reference": reference, "packets": record}
