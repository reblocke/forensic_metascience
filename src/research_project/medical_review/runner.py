"""Auditable offline replay and explicit refusal of unqualified live execution.

No live backend is registered. Prompt instructions and staging directories are
not claimed to enforce provider filesystem, tool or network restrictions.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.bundle import load_bundle
from research_project.medical_review.context import build_study_context
from research_project.medical_review.importer import _adapter_hash, _coverage
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    private_path,
    read_json,
    write_json,
)
from research_project.medical_review.routing import build_review_plan
from research_project.run_manifest import create_run, update_run

DEFAULT_LIMITS = {
    "max_duration_seconds": 120,
    "max_sessions": 1,
    "max_retries": 0,
    "max_source_bytes": 64 * 1024 * 1024,
}


def validate_authorization(
    record: dict[str, Any],
    bundle: dict[str, Any],
    *,
    backend: str,
    provider: str | None,
    model: str | None,
    allow_web_search: bool,
) -> None:
    """Validate source approval separately from backend qualification."""
    fields = {
        "schema_version",
        "bundle_sha256",
        "sources",
        "provider",
        "backend",
        "model",
        "purposes",
        "tools",
        "allow_web_search",
        "valid_from",
        "valid_until",
        "approver",
        "rationale",
    }
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("Authorization requires the exact source-specific contract.")
    if record["schema_version"] != "medical_source_authorization_v1":
        raise ValueError("Unsupported authorization schema.")
    expected = [
        {
            "source_version_id": d["source_version_id"],
            "sha256": d["sha256"],
            "classification": d.get("permissions", {}).get("classification"),
        }
        for d in bundle["documents"]
        if d["availability"] == "supplied"
    ]
    sources = record["sources"]
    if (
        not isinstance(sources, list)
        or any(not isinstance(s, dict) for s in sources)
        or any(not s["classification"] for s in expected)
        or sorted(content_hash(s) for s in sources) != sorted(content_hash(s) for s in expected)
        or record["bundle_sha256"] != content_hash(bundle)
    ):
        raise ValueError(
            "Authorization does not match exact bundle/source versions and classifications."
        )
    if (
        not provider
        or not model
        or record["backend"] != backend
        or record["provider"] != provider
        or record["model"] != model
    ):
        raise ValueError("Authorization does not match the requested provider/backend/model.")
    if (
        not isinstance(record["purposes"], list)
        or "medical_review" not in record["purposes"]
        or not isinstance(record["tools"], list)
        or not set(record["tools"]) <= {"source_read", "web_search"}
        or type(record["allow_web_search"]) is not bool
    ):
        raise ValueError("Authorization purpose/tools are unsupported.")
    if allow_web_search and (
        record["allow_web_search"] is not True or "web_search" not in record["tools"]
    ):
        raise ValueError("Authorization does not permit manuscript-derived search.")
    for field in ("approver", "rationale"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ValueError("Authorization requires a private human approver and rationale.")
    try:
        start, end = [datetime.fromisoformat(record[k]) for k in ("valid_from", "valid_until")]
    except (ValueError, TypeError) as error:
        raise ValueError("Authorization validity dates are invalid.") from error
    if start.tzinfo is None or end.tzinfo is None or not start <= datetime.now(UTC) < end:
        raise ValueError("Authorization is expired, premature or lacks timezone precision.")


def _limits(supplied: dict[str, Any] | None) -> dict[str, Any]:
    if supplied is not None and (
        not isinstance(supplied, dict) or not set(supplied) <= set(DEFAULT_LIMITS)
    ):
        raise ValueError("Unsupported execution limit.")
    result = {**DEFAULT_LIMITS, **(supplied or {})}
    for field in ("max_source_bytes", "max_sessions", "max_retries"):
        if type(result[field]) is not int or result[field] < (0 if field == "max_retries" else 1):
            raise ValueError("Execution limits require positive integers; retries may be zero.")
    duration = result["max_duration_seconds"]
    if type(duration) not in {int, float} or not 0 < duration <= 3600:
        raise ValueError("Execution duration limit must be positive and at most 3600 seconds.")
    if result["max_retries"] != 0 or result["max_sessions"] != 1:
        raise ValueError("Only one local replay session and zero automatic retries are supported.")
    return result


def _code_hash() -> str:
    package = Path(__file__).resolve().parent
    return content_hash(
        {
            "adapter": _adapter_hash(),
            **{
                name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                for name in ("runner.py", "replay_worker.py")
            },
        }
    )


def _validate_resume(repo: Path, path: Path, dependencies: str) -> dict[str, Any]:
    run = private_path(repo, path, PRIVATE_RUNS)
    manifest = read_json(private_path(repo, run / "run_manifest.json", PRIVATE_RUNS))
    request = read_json(
        private_path(repo, run / "generated/medical_review/attempt_requested.json", PRIVATE_RUNS)
    )
    if (
        manifest.get("schema_version") != "forensics_run_v3"
        or manifest.get("run_id") != run.name
        or request.get("schema_version") != "medical_execution_request_v1"
        or request.get("dependencies_sha256") != dependencies
        or content_hash(request.get("dependencies")) != dependencies
        or request.get("request_id")
        != identity("medicalrequest", {k: v for k, v in request.items() if k != "request_id"})
    ):
        raise ValueError("Resume dependencies changed; reuse refused.")
    required = {"generated/medical_review/attempt_requested.json"}
    if manifest.get("status") in {"completed", "failed"}:
        required |= {
            "generated/medical_review/attempt_result.json",
            "processed/medical_review/coverage.json",
        }
    if not required <= {row.get("path") for row in manifest.get("artifacts", [])}:
        raise ValueError("Resume artifact receipts are incomplete.")
    for row in manifest.get("artifacts", []):
        reference = Path(row["path"])
        if reference.is_absolute() or ".." in reference.parts:
            raise ValueError("Unsafe resume artifact reference.")
        artifact = private_path(repo, run / reference, PRIVATE_RUNS)
        if (
            run not in artifact.parents
            or hashlib.sha256(artifact.read_bytes()).hexdigest() != row["sha256"]
        ):
            raise ValueError("Resume artifact changed; reuse refused.")
    return request


def _replay_environment() -> dict[str, str]:
    """Only the trusted local importer is started, without inherited provider credentials."""
    return {
        "PATH": os.defpath,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "en_US.UTF-8",
    }


def _execute_replay(
    repo: Path,
    bundle: Path,
    snapshot: Path,
    profiles: list[str] | None,
    timeout: float,
    recover_incomplete: bool = False,
) -> Path:
    command = [
        sys.executable,
        "-B",
        "-m",
        "research_project.medical_review.replay_worker",
        "--repo-root",
        str(repo),
        "--bundle",
        str(bundle),
        "--input",
        str(snapshot),
    ]
    for profile in profiles or []:
        command.extend(["--profile", profile])
    if recover_incomplete:
        command.append("--recover-incomplete")
    result = subprocess.run(
        command,
        cwd=repo,
        env=_replay_environment(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        # Worker emits controlled validator errors only. Preserve them privately, without env dumps.
        raise ValueError("Offline replay failed: " + result.stderr.strip()[:4096])
    return private_path(repo, Path(result.stdout.strip()), PRIVATE_RUNS)


def run_review(
    repo_root: Path,
    bundle_path: Path,
    *,
    backend: str,
    input_path: Path | None = None,
    offline: bool = True,
    allow_llm: bool = False,
    allow_web_search: bool = False,
    authorization_path: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    limits: dict[str, Any] | None = None,
    resume_run: Path | None = None,
    output_root: Path | None = None,
    profiles: list[str] | None = None,
) -> Path:
    """Create an immutable attempt; replay local output or record a blocked live request.

    A completed replay is a completed import, never completed medical coverage.
    Live operational restrictions remain unsupported, so no model process starts.
    """
    started = time.monotonic()
    repo = repo_root.resolve()
    limits = _limits(limits)
    bundle_path = private_path(repo, bundle_path, PRIVATE_SOURCES)
    bundle, bundle_hash = load_bundle(repo, bundle_path)
    context = build_study_context(bundle, bundle.get("context_fields"))
    profiles = profiles or bundle.get("profile_ids")
    plan = build_review_plan(bundle, context, profiles, repo)
    output = private_path(repo, output_root or PRIVATE_RUNS, PRIVATE_RUNS)
    authorization_record = None
    if authorization_path is not None:
        authorization_path = private_path(
            repo, authorization_path, PRIVATE_SOURCES / bundle["study_id"] / "authorizations"
        )
        authorization_record = read_json(authorization_path)
    raw = None
    if input_path is not None:
        input_path = private_path(repo, input_path, PRIVATE_SOURCES / bundle["study_id"])
        with input_path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise ValueError("Replay input exceeds the explicit JSON limit.")
    dependencies = {
        "bundle_sha256": bundle_hash,
        "context_sha256": content_hash(context),
        "plan_sha256": content_hash(plan),
        "code_sha256": _code_hash(),
        "backend": backend,
        "provider": provider,
        "requested_model": model,
        "offline": offline,
        "allow_llm": allow_llm,
        "allow_web_search": allow_web_search,
        "authorization_sha256": content_hash(authorization_record)
        if authorization_record
        else None,
        "raw_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "limits": limits,
    }
    dependencies_hash = content_hash(dependencies)
    if resume_run is not None:
        _validate_resume(repo, resume_run, dependencies_hash)
    source_paths = {
        repo / d["path"] for d in bundle["documents"] if d["availability"] == "supplied"
    }
    source_paths.update(repo / e["parsed_path"] for e in bundle["evidence"])
    inputs = [
        *sorted(source_paths),
        *([input_path] if input_path else []),
        *([authorization_path] if authorization_path else []),
        repo / "config/medical_review/check_catalogue.json",
        repo / "config/medical_review/guidance_registry.json",
        *[repo / p["path"] for p in plan["prompt_sources"]],
    ]
    run, manifest = create_run(
        repo_root=repo,
        output_root=output,
        study_id=bundle["study_id"],
        categories=["medical_review"],
        config_path=bundle_path,
        input_paths=inputs,
        settings={
            **dependencies,
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
            "dependencies_sha256": dependencies_hash,
            "execution_mode": "offline_replay" if backend == "replay" else "blocked_live",
        },
    )
    request = {
        "schema_version": "medical_execution_request_v1",
        "run_id": run.name,
        "created_at": datetime.now(UTC).isoformat(),
        "dependencies_sha256": dependencies_hash,
        "dependencies": dependencies,
        "resume_run_reference": str(private_path(repo, resume_run, PRIVATE_RUNS).relative_to(repo))
        if resume_run
        else None,
    }
    request = {**request, "request_id": identity("medicalrequest", request)}
    generated = run / "generated/medical_review"
    request_path = generated / "attempt_requested.json"
    write_json(request_path, request)
    update_run(manifest, artifact=str(request_path))
    status, reason, imported = "blocked", None, None
    try:
        for name, value in [("bundle", bundle), ("study_context", context), ("review_plan", plan)]:
            path = run / f"processed/medical_review/{name}.json"
            write_json(path, value)
            update_run(manifest, artifact=str(path))
        if raw is not None:
            raw_path = generated / "raw/replay_input.json"
            raw_path.parent.mkdir(parents=True)
            with raw_path.open("xb") as stream:
                stream.write(raw)
            update_run(manifest, artifact=str(raw_path))
        if sum(p.stat().st_size for p in source_paths) > limits["max_source_bytes"]:
            reason = "Declared source-byte limit exceeded; execution deferred."
        elif backend != "replay":
            if offline:
                reason = "Application offline mode forbids model transmission and search."
            elif not allow_llm:
                reason = "Live execution requires explicit allow-llm permission."
            elif authorization_record is None:
                reason = "Source-specific provider authorization is absent."
            else:
                try:
                    validate_authorization(
                        authorization_record,
                        bundle,
                        backend=backend,
                        provider=provider,
                        model=model,
                        allow_web_search=allow_web_search,
                    )
                except ValueError as error:
                    reason = str(error)
                else:
                    reason = (
                        "Live backend restrictions are not qualified; "
                        "filesystem/tools/egress enforcement unavailable."
                    )
        elif raw is None:
            reason = "Offline replay requires an existing local reviewer output."
        else:
            snapshot = private_path(
                repo,
                PRIVATE_SOURCES
                / bundle["study_id"]
                / "replay_inputs"
                / (dependencies["raw_sha256"] + ".json"),
                PRIVATE_SOURCES,
            )
            if snapshot.exists():
                if snapshot.read_bytes() != raw:
                    raise ValueError("Immutable replay snapshot was changed.")
            else:
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                with snapshot.open("xb") as stream:
                    stream.write(raw)
                snapshot.chmod(0o444)
            timeout = limits["max_duration_seconds"] - (time.monotonic() - started)
            if timeout <= 0:
                raise TimeoutError("Replay duration budget exhausted before worker launch.")
            imported = _execute_replay(
                repo,
                bundle_path,
                snapshot,
                profiles,
                timeout,
                recover_incomplete=resume_run is not None,
            )
            imported_manifest = read_json(imported / "run_manifest.json")
            if imported_manifest["effective_settings"]["raw_sha256"] != dependencies["raw_sha256"]:
                raise ValueError("Replay raw dependency changed.")
            _, current_hash = load_bundle(repo, bundle_path)
            if (
                current_hash != bundle_hash
                or _code_hash() != dependencies["code_sha256"]
                or build_review_plan(bundle, context, profiles, repo) != plan
            ):
                raise ValueError(
                    "Replay source/code/plan dependencies changed; no reuse qualified."
                )
            status = "completed"
            reason = "Local output replayed; substantive check coverage remains unavailable."
    except (Exception, KeyboardInterrupt) as error:
        status = "failed"
        reason = (
            "Replay timeout; partial outputs retained; no automatic retry."
            if isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
            else "Replay interrupted; partial outputs retained."
            if isinstance(error, KeyboardInterrupt)
            else str(error)
        )
        imported = None
    coverage = _coverage(bundle, plan)
    if status != "completed":
        for row in coverage:
            row["execution"] = status
            row["stop_reason"] = reason
    coverage_path = run / "processed/medical_review/coverage.json"
    write_json(coverage_path, coverage)
    update_run(manifest, artifact=str(coverage_path))
    result = {
        "schema_version": "medical_execution_attempt_v1",
        "run_id": run.name,
        "request_id": request["request_id"],
        "dependencies_sha256": dependencies_hash,
        "status": status,
        "reason": reason,
        "effective_model": None,
        "effective_permissions": {"allow_llm": False, "allow_web_search": False},
        "authorization_sha256": dependencies["authorization_sha256"],
        "model_calls": 0,
        "search_activity": [],
        "token_usage": None,
        "cost_estimate": None,
        "duration_seconds": time.monotonic() - started,
        "limits": limits,
        "coverage_available": False,
        "provider_fallbacks": [],
        "live_isolation_status": "unsupported_no_backend_started",
        "import_run_id": imported.name if imported else None,
        "import_run_reference": str(imported.relative_to(repo)) if imported else None,
    }
    result_path = generated / "attempt_result.json"
    write_json(result_path, {**result, "attempt_id": identity("medicalattempt", result)})
    update_run(manifest, artifact=str(result_path))
    update_run(manifest, stage="medical-execution", status=status)
    update_run(
        manifest,
        status="completed" if status == "completed" else "failed",
        error=reason if status != "completed" else None,
    )
    return run
