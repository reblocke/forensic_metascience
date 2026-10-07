"""Offline candidate ingestion bound to source packets, never live-run qualification."""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.bundle import resolve_source_object
from research_project.medical_review.evaluation import _exact, _identifier
from research_project.medical_review.evaluation_packets import _code_sources as packet_code_sources
from research_project.medical_review.evaluation_packets import _json_bytes, load_source_packets
from research_project.medical_review.importer import validate_upstream
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    UPSTREAM_COMMIT,
    UPSTREAM_SCHEMA_HASH,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

MAX_ATTEMPTS = 1024
MAX_OUTPUTS = 4096
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
ATTEMPT_FIELDS = {
    "attempt_id",
    "packet_id",
    "status",
    "stop_reason",
    "origin",
    "runtime",
    "upstream_revision",
    "usage",
    "outputs",
}
USAGE_FIELDS = {
    "elapsed_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_amount",
    "cost_currency",
}


def _usage(row: Any) -> None:
    _exact(row, USAGE_FIELDS, "candidate usage")
    for key in USAGE_FIELDS - {"cost_currency"}:
        value = row[key]
        if value is not None and (
            type(value) not in {int, float}
            or (type(value) is float and not math.isfinite(value))
            or value < 0
            or (key.endswith("tokens") and type(value) is not int)
        ):
            raise ValueError("Observed candidate usage must be nonnegative numbers or null.")
    currency = row["cost_currency"]
    if currency is not None and (
        not isinstance(currency, str)
        or len(currency) != 3
        or not currency.isascii()
        or not currency.isalpha()
        or not currency.isupper()
    ):
        raise ValueError("Candidate cost currency needs an explicit three-letter code or null.")
    if row["cost_amount"] is not None and currency is None:
        raise ValueError("Observed candidate cost requires its currency.")


def _input(loaded: dict[str, Any], data: Any) -> None:
    _exact(data, {"schema_version", "packets_record_id", "attempts"}, "candidate input")
    if data["schema_version"] != "medical_evaluation_candidate_input_v1":
        raise ValueError("Unsupported candidate input schema.")
    if data["packets_record_id"] != loaded["packets"]["record_id"]:
        raise ValueError("Candidate source-packet record identity mismatch.")
    rows = data["attempts"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ATTEMPTS:
        raise ValueError("Candidate input requires 1..1024 explicit attempts.")
    packets = {p["packet_id"]: p for p in loaded["packets"]["packets"]}
    seen, count = set(), 0
    for row in rows:
        _exact(row, ATTEMPT_FIELDS, "candidate attempt")
        _identifier(row["attempt_id"], "attempt_id")
        if (
            row["attempt_id"] in seen
            or not isinstance(row["packet_id"], str)
            or row["packet_id"] not in packets
        ):
            raise ValueError("Duplicate attempt or unknown candidate packet identity.")
        seen.add(row["attempt_id"])
        if row["status"] not in {"completed", "partial", "failed", "blocked", "not_started"}:
            raise ValueError("Unsupported declared candidate attempt status.")
        if row["status"] != "completed" and (
            not isinstance(row["stop_reason"], str) or not row["stop_reason"].strip()
        ):
            raise ValueError("Incomplete candidate attempt requires an explicit stop reason.")
        if row["status"] == "completed" and row["stop_reason"] is not None:
            raise ValueError("Completed candidate attempt cannot have a stop reason.")
        if row["origin"] != "offline_supplied":
            raise ValueError("Candidate ingestion supports offline supplied outputs only.")
        runtime = row["runtime"]
        if runtime is not None:
            _exact(runtime, {"provider", "backend", "model", "tools"}, "reported runtime")
            if any(
                not isinstance(runtime[k], str) or not runtime[k].strip()
                for k in ("provider", "backend", "model")
            ):
                raise ValueError("Reported runtime identities must be explicit.")
            tools = runtime["tools"]
            if (
                not isinstance(tools, list)
                or any(t not in {"source_read", "web_search"} for t in tools)
                or len(set(tools)) != len(tools)
            ):
                raise ValueError("Reported tools require explicit supported declarations.")
        revision = row["upstream_revision"]
        if revision is not None and (
            revision != UPSTREAM_COMMIT
            or packets[row["packet_id"]]["condition_id"] != "original_reviewer"
        ):
            raise ValueError("Unsupported candidate upstream revision/condition declaration.")
        _usage(row["usage"])
        outputs = row["outputs"]
        if not isinstance(outputs, list):
            raise ValueError("Candidate outputs require an explicit list.")
        if (row["status"] == "completed" and not outputs) or (
            row["status"] in {"not_started", "blocked"} and outputs
        ):
            raise ValueError("Candidate output presence conflicts with declared attempt status.")
        output_ids = set()
        for output in outputs:
            _exact(output, {"output_id", "stage", "output_reference"}, "candidate output")
            _identifier(output["output_id"], "output_id")
            if output["output_id"] in output_ids or output["stage"] not in {
                "reviewer",
                "synthesis",
            }:
                raise ValueError("Duplicate output identity or unsupported candidate stage.")
            output_ids.add(output["output_id"])
            reference = output["output_reference"]
            if (
                not isinstance(reference, str)
                or Path(reference).is_absolute()
                or ".." in Path(reference).parts
            ):
                raise ValueError("Candidate output references require contained relative paths.")
            count += 1
        if count > MAX_OUTPUTS:
            raise ValueError("Candidate output count exceeds 4096; split explicitly.")


def _raw_reference(attempt: str, output: str) -> str:
    return f"generated/medical_evaluation/raw/outputs/{attempt}/{output}.json"


def _prepare(
    repo: Path, loaded: dict[str, Any], data: Any, snapshots: dict[str, bytes]
) -> dict[str, Any]:
    _input(loaded, data)
    packets = {p["packet_id"]: p for p in loaded["packets"]["packets"]}
    cases = {c["case_id"]: c for c in loaded["reference"]["plan"]["cases"]}
    attempts, candidates = [], []
    for row in data["attempts"]:
        packet = packets[row["packet_id"]]
        case = cases[packet["case_id"]]
        bundle = copy.deepcopy(case["bundle"])
        selected = set(packet["source_version_ids"])
        aliases = {a["source_version_id"]: a["local_file"] for a in packet["source_aliases"]}
        bundle["documents"] = [d for d in bundle["documents"] if d["source_version_id"] in selected]
        bundle["evidence"] = [e for e in bundle["evidence"] if e["source_version_id"] in selected]
        for doc in bundle["documents"]:
            doc["upstream_paths"] = [aliases[doc["source_version_id"]]]
        outputs = []
        for output in row["outputs"]:
            raw_ref = _raw_reference(row["attempt_id"], output["output_id"])
            raw = snapshots[raw_ref]
            payload = parse_json(raw)
            validate_upstream(payload, repo, UPSTREAM_SCHEMA_HASH)
            if payload["paper_id"] not in {
                packet["packet_id"],
                case["bundle"]["upstream_paper_id"],
            }:
                raise ValueError("Candidate paper identity does not map to its explicit packet.")
            if row["status"] == "completed" and payload["run_status"] not in {
                "ok",
                "cannot_verify",
            }:
                raise ValueError("Completed attempt conflicts with supplied output status.")
            outputs.append(
                {
                    **output,
                    "raw_reference": raw_ref,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "reported_run_status": payload["run_status"],
                    "original_summary": payload["summary"],
                    "original_notes": payload["notes"],
                }
            )
            for finding in payload["findings"]:
                candidate = {
                    "packet_id": row["packet_id"],
                    "attempt_id": row["attempt_id"],
                    "output_id": output["output_id"],
                    "stage": output["stage"],
                    "original_finding_id": finding["id"],
                    "original_sha256": content_hash(finding),
                    "original": copy.deepcopy(finding),
                    "raw_reference": raw_ref,
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_links": [
                        resolve_source_object(bundle, obj) for obj in finding["source_objects"]
                    ],
                    "human_status": "pending",
                    "qualified_result_ids": [],
                    "official_assessment": None,
                }
                candidate["candidate_id"] = identity(
                    "evaluationcandidate",
                    {
                        "packet_id": row["packet_id"],
                        "attempt_id": row["attempt_id"],
                        "output_id": output["output_id"],
                        "finding_id": finding["id"],
                        "original_sha256": candidate["original_sha256"],
                    },
                )
                candidates.append(candidate)
        attempts.append(
            {**copy.deepcopy(row), "outputs": outputs, "upstream_workflow_verified": False}
        )
    record = {
        "schema_version": "medical_evaluation_candidates_v1",
        "original": copy.deepcopy(data),
        "packets_record_id": loaded["packets"]["record_id"],
        "attempts": attempts,
        "candidates": candidates,
        "unreported_packet_ids": sorted(set(packets) - {r["packet_id"] for r in attempts}),
        "runtime_evidence": "operator_reported_not_verified",
        "review_coverage_available": False,
        "review_coverage_reason": "Supplied upstream-shaped outputs have no per-check coverage.",
        "medical_performance_validated": False,
        "official_assessment": None,
        "synthesis_membership": "not_provided_not_inferred",
    }
    record["record_id"] = identity("evaluationcandidates", record)
    _json_bytes(record)
    return record


def _code_sources() -> dict[str, Path]:
    package = Path(__file__).parent
    return {
        **packet_code_sources(),
        "evaluation_candidates.py": Path(__file__),
        "importer.py": package / "importer.py",
    }


def _snapshot(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Candidate JSON exceeds 20 MiB; split explicitly.")
    return raw


def freeze_candidates(repo_root: Path, packets_run: Path, input_path: Path) -> Path:
    """Retain exact offline outputs and reject invalid findings in an auditable failed attempt."""
    repo = repo_root.resolve()
    parent = private_path(repo, packets_run, PRIVATE_RUNS)
    parent_hash = sha256_file(parent / "run_manifest.json")
    loaded = load_source_packets(repo, parent)
    scope = PRIVATE_SOURCES / loaded["reference"]["plan"]["evaluation_id"] / "evaluation"
    source = private_path(repo, input_path, scope)
    raw_input = _snapshot(source)
    data = parse_json(raw_input)
    _input(loaded, data)
    snapshots, originals, total = {}, {}, 0
    for attempt in data["attempts"]:
        for output in attempt["outputs"]:
            path = private_path(repo, Path(output["output_reference"]), scope)
            raw = _snapshot(path)
            total += len(raw)
            if len(raw) > MAX_JSON_BYTES or total > MAX_OUTPUT_BYTES:
                raise ValueError("Candidate raw output byte limits exceeded; split explicitly.")
            key = _raw_reference(attempt["attempt_id"], output["output_id"])
            snapshots[key], originals[key] = raw, path
    code_sources = _code_sources()
    code = {k: p.read_bytes() for k, p in code_sources.items()}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=loaded["reference"]["plan"]["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=source,
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_candidate_import": True,
            "packets_run_reference": str(parent.relative_to(repo)),
            "packets_manifest_sha256": parent_hash,
            "raw_sha256": hashlib.sha256(raw_input).hexdigest(),
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        archived = {
            "generated/medical_evaluation/raw/candidate_input.json": raw_input,
            **snapshots,
            **{"generated/medical_evaluation/code/" + k: v for k, v in code.items()},
        }
        for reference, raw in archived.items():
            path = run / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
            update_run(manifest, artifact=str(path))
        record = _prepare(repo, loaded, data, snapshots)
        if (
            sha256_file(source) != hashlib.sha256(raw_input).hexdigest()
            or sha256_file(parent / "run_manifest.json") != parent_hash
            or any(
                sha256_file(p) != hashlib.sha256(snapshots[k]).hexdigest()
                for k, p in originals.items()
            )
            or any(code_sources[k].read_bytes() != v for k, v in code.items())
            or _prepare(repo, load_source_packets(repo, parent), data, snapshots) != record
        ):
            raise ValueError("Candidate input/source/parent/code changed while freezing.")
        path = run / "processed/medical_evaluation/candidates.json"
        write_json(path, record)
        update_run(manifest, artifact=str(path))
        update_run(manifest, stage="evaluation-candidates", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_candidates(repo_root: Path, run_path: Path) -> dict[str, Any]:
    """Validate archived outputs, exact parent lineage and source-scoped semantic reconstruction."""
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_candidate_import") is not True
    ):
        raise ValueError("Candidate import is not successfully completed.")
    parent = private_path(repo, Path(settings["packets_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["packets_manifest_sha256"]:
        raise ValueError("Candidate source-packet manifest changed.")
    loaded = load_source_packets(repo, parent)
    raw = _snapshot(
        recorded_artifact(
            repo, run, manifest, "generated/medical_evaluation/raw/candidate_input.json"
        )
    )
    data = parse_json(raw)
    _input(loaded, data)
    snapshots = {
        _raw_reference(a["attempt_id"], o["output_id"]): _snapshot(
            recorded_artifact(repo, run, manifest, _raw_reference(a["attempt_id"], o["output_id"]))
        )
        for a in data["attempts"]
        for o in a["outputs"]
    }
    archived = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources()
    }
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/candidates.json")
    )
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(archived) != settings["code_sha256"]
        or _prepare(repo, loaded, data, snapshots) != record
    ):
        raise ValueError("Candidate raw/code/source/semantic binding changed.")
    return {"run_root": run, "manifest": manifest, "packets": loaded, "candidates": record}
