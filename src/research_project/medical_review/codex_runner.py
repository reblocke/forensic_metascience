"""Opt-in Codex attempt lifecycle and registered generation-to-import lineage."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.bundle import load_bundle
from research_project.medical_review.codex_backend import (
    INSTRUCTIONS,
    MODEL,
    clean_environment,
    codex_command,
    execution_policy,
)
from research_project.medical_review.codex_generation import (
    derived_payload,
    observed_metadata,
    output_schema,
    reading_proposals,
    validate_generation,
)
from research_project.medical_review.codex_packet import validate_packet
from research_project.medical_review.codex_process import bounded_process, session_lock
from research_project.medical_review.codex_qualification import validate_qualification
from research_project.medical_review.context import build_study_context
from research_project.medical_review.importer import _coverage, import_reviewer
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.medical_review.routing import build_review_plan
from research_project.medical_review.runner import _limits, validate_authorization
from research_project.run_manifest import create_run, update_run


def load_reading_layer(repo, run, manifest, result, dossier):
    """Reconstruct the scoped layer from registered raw output and immutable parent import."""

    def artifact(relative):
        return recorded_artifact(repo, run, manifest, relative)

    request = read_json(artifact("generated/medical_review/attempt_requested.json"))
    if (
        request.get("schema_version") != "medical_execution_request_v2"
        or request.get("request_id")
        != identity("medicalrequest", {k: v for k, v in request.items() if k != "request_id"})
        or request.get("dependencies_sha256") != content_hash(request.get("dependencies"))
        or result.get("request_id") != request["request_id"]
        or result.get("dependencies_sha256") != request["dependencies_sha256"]
        or result.get("status") != "completed"
        or result.get("coverage_available") is not False
    ):
        raise ValueError("Codex reading attempt binding changed.")
    lineage = read_json(artifact("generated/medical_review/reading_lineage.json"))
    raw = artifact("generated/medical_review/raw/generation.json").read_bytes()
    envelope = parse_json(raw)
    bundle = dossier["bundle"]
    packet = lineage["packet"]
    packet_bytes = artifact("generated/medical_review/streams/stdin.txt").read_bytes()
    if (
        lineage.get("schema_version") != "medical_codex_lineage_v1"
        or lineage.get("original_reviewer_executed") is not False
        or lineage["generation_sha256"] != hashlib.sha256(raw).hexdigest()
        or lineage["import_manifest_sha256"] != content_hash(dossier["manifest"])
        or lineage["packet_sha256"] != hashlib.sha256(packet_bytes).hexdigest()
        or lineage["packet_sha256"] != bundle["codex_packet"]["packet_sha256"]
        or parse_json(packet_bytes) != packet
        or any(
            lineage["runtime_observed"].get(k) != result.get(k) for k in lineage["runtime_observed"]
        )
    ):
        raise ValueError("Codex reading generation/import provenance changed.")
    validate_generation(repo, envelope, bundle, packet)
    imported_raw = (dossier["run_root"] / "generated/medical_review/raw/reviewer.json").read_bytes()
    if (
        derived_payload(envelope) != parse_json(imported_raw)
        or hashlib.sha256(imported_raw).hexdigest() != lineage["derived_payload_sha256"]
    ):
        raise ValueError("Codex derived import transformation changed.")
    expected = reading_proposals(
        dossier["proposals"],
        envelope,
        bundle,
        packet,
        envelope_sha256=lineage["generation_sha256"],
        packet_sha256=lineage["packet_sha256"],
        runtime=lineage["runtime_observed"],
    )
    if read_json(artifact("processed/medical_review/proposals.json")) != expected:
        raise ValueError("Codex scoped proposal layer changed.")
    return {
        **dossier,
        "proposals": expected,
        "proposal_run_root": run,
        "reading_execution": {
            k: lineage[k]
            for k in (
                "requested",
                "runtime_observed",
                "generation_sha256",
                "derived_payload_sha256",
                "packet_sha256",
                "original_reviewer_executed",
            )
        },
    }


def _limits_codex(supplied: dict[str, Any] | None) -> dict[str, Any]:
    limits = _limits({"max_duration_seconds": 600, **(supplied or {})})
    policy = execution_policy()
    if (
        limits["max_duration_seconds"] > 600
        or limits["max_source_bytes"] > policy["max_source_bytes"]
    ):
        raise ValueError("Codex limits cannot exceed the fixed execution policy.")
    return limits


def _launch(
    packet: bytes,
    catalogue: Path,
    generated: Path,
    schema: dict[str, Any],
    limits: dict[str, Any],
    lock_fd: int,
    *,
    executable: str,
) -> None:
    """Only the trusted controller handles authentication; reviewer workspace has no credentials."""
    auth_home = Path.home() / ".codex"
    # Do not inherit an alternate CODEX_HOME or API-key based provider from the environment.
    auth_file = auth_home / "auth.json"
    if auth_file.is_symlink():
        raise ValueError("Codex authentication symlink refused.")
    auth = read_json(auth_file)
    if (
        auth.get("auth_mode") != "chatgpt"
        or auth.get("OPENAI_API_KEY") is not None
        or not isinstance(auth.get("tokens"), dict)
    ):
        raise ValueError(
            "Codex backend requires file-backed ChatGPT authentication; API fallback refused."
        )
    status = subprocess.run(
        [executable, "login", "status"], capture_output=True, text=True, timeout=10, check=False
    )
    if status.returncode != 0 or "Logged in using ChatGPT" not in status.stdout + status.stderr:
        raise ValueError("Codex ChatGPT authentication is unavailable.")
    with tempfile.TemporaryDirectory(prefix="medical-codex-session-") as directory:
        root = Path(directory)
        home, workspace = root / "runtime", root / "sources"
        home.mkdir()
        workspace.mkdir()
        write_json(home / "auth.json", auth)
        (home / "auth.json").chmod(0o600)
        shutil.copyfile(catalogue, home / "models_cache.json")
        instructions, schema_path = root / "instructions.txt", root / "schema.json"
        instructions.write_text(INSTRUCTIONS, encoding="utf-8")
        write_json(schema_path, schema)
        source = workspace / "packet.json"
        with source.open("xb") as stream:
            stream.write(packet)
        source.chmod(0o444)
        workspace.chmod(0o555)
        final = generated / "raw/generation.json"
        final.parent.mkdir(parents=True, exist_ok=True)
        command = codex_command(executable, workspace, instructions, schema_path, final)
        try:
            code = bounded_process(
                command,
                cwd=workspace,
                env=clean_environment(home),
                prompt=packet,
                output=generated / "streams",
                final=final,
                duration=limits["max_duration_seconds"],
                event_bytes=execution_policy()["max_event_bytes"],
                stderr_bytes=execution_policy()["max_stderr_bytes"],
                final_bytes=execution_policy()["max_final_bytes"],
                lock_fd=lock_fd,
                cleanup_directory=root,
            )
            if code != 0:
                raise ValueError(
                    "Codex generation failed; private streams retained, no retry or fallback."
                )
        finally:
            workspace.chmod(0o700)


def run_codex_review(
    repo_root: Path,
    bundle_path: Path,
    *,
    offline: bool,
    allow_llm: bool,
    allow_web_search: bool,
    authorization_path: Path | None,
    provider: str | None,
    model: str | None,
    limits: dict[str, Any] | None,
    resume_run: Path | None,
    output_root: Path | None,
    profiles: list[str] | None,
    qualification_path: Path | None,
    input_path: Path | None,
) -> Path:
    started = time.monotonic()
    repo = repo_root.resolve()
    limits = _limits_codex(limits)
    bundle, digest = load_bundle(repo, bundle_path)
    context = build_study_context(bundle, bundle.get("context_fields"))
    plan = build_review_plan(bundle, context, profiles or bundle.get("profile_ids"), repo)
    auth = (
        read_json(
            private_path(
                repo, authorization_path, PRIVATE_SOURCES / bundle["study_id"] / "authorizations"
            )
        )
        if authorization_path
        else None
    )
    reason, preparation, qualification = None, None, None
    try:
        if offline:
            raise ValueError(
                "Application offline mode forbids Codex model transmission and search."
            )
        if not allow_llm:
            raise ValueError("Codex execution requires explicit allow-llm permission.")
        if allow_web_search:
            raise ValueError("Codex backend does not support web search.")
        if provider != "openai" or model != MODEL or input_path is not None:
            raise ValueError(
                "Codex requires provider openai, model gpt-6-astra and a prepared packet. "
                "Replay input is unsupported."
            )
        preparation = validate_packet(repo, bundle_path)
        if qualification_path is None:
            raise ValueError("Codex runtime qualification is absent.")
        qualification = validate_qualification(repo, qualification_path)
        if bundle["codex_packet"]["qualification_sha256"] != qualification["receipt_sha256"]:
            raise ValueError("Prepared packet qualification changed.")
        if auth is None:
            raise ValueError("Source-specific provider authorization is absent.")
        validate_authorization(
            auth,
            bundle,
            backend="codex_cli",
            provider=provider,
            model=model,
            allow_web_search=False,
            packet_sha256=bundle["codex_packet"]["packet_sha256"],
            execution_policy_sha256=content_hash(execution_policy()),
        )
        prepared_plan = build_review_plan(bundle, context, bundle.get("profile_ids"), repo)
        if plan != prepared_plan:
            raise ValueError("Requested profiles differ from the prepared packet plan.")
        paths = {repo / d["path"] for d in bundle["documents"] if d["availability"] == "supplied"}
        if sum(p.stat().st_size for p in paths) > limits["max_source_bytes"]:
            raise ValueError("Declared Codex source-byte limit exceeded.")
    except ValueError as error:
        reason = str(error)
    dependencies = {
        "bundle_sha256": digest,
        "context_sha256": content_hash(context),
        "plan_sha256": content_hash(plan),
        "code_sha256": content_hash(
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(Path(__file__).parent.glob("*.py"))
            }
        ),
        "packet_sha256": bundle.get("codex_packet", {}).get("packet_sha256"),
        "policy_sha256": content_hash(execution_policy()),
        "qualification_sha256": qualification["receipt_sha256"] if qualification else None,
        "authorization_sha256": content_hash(auth) if auth else None,
        "backend": "codex_cli",
        "provider": provider,
        "requested_model": model,
        "offline": offline,
        "allow_llm": allow_llm,
        "allow_web_search": allow_web_search,
        "limits": limits,
    }
    if resume_run is not None:
        manifest = validate_run_artifacts(repo, resume_run)
        request = read_json(
            recorded_artifact(
                repo, resume_run, manifest, "generated/medical_review/attempt_requested.json"
            )
        )
        result = read_json(
            recorded_artifact(
                repo, resume_run, manifest, "generated/medical_review/attempt_result.json"
            )
        )
        if (
            reason
            or request.get("dependencies") != dependencies
            or result.get("status") != "completed"
        ):
            raise ValueError(
                "Codex resume requires validated success with matching dependencies; "
                "start a new explicit attempt."
            )
        from research_project.medical_review.audit import load_dossier

        load_dossier(repo, resume_run)
        return private_path(repo, resume_run, PRIVATE_RUNS)
    run, manifest = create_run(
        repo_root=repo,
        output_root=private_path(repo, output_root or PRIVATE_RUNS, PRIVATE_RUNS),
        study_id=bundle["study_id"],
        categories=["medical_review"],
        config_path=bundle_path,
        input_paths=[
            *([authorization_path] if authorization_path else []),
            *([qualification_path] if qualification_path else []),
        ],
        settings={
            **dependencies,
            "execution_mode": "codex_reading",
            "offline": bool(reason),
            "allow_llm": reason is None,
            "allow_web_search": False,
            "dependencies_sha256": content_hash(dependencies),
        },
    )
    generated = run / "generated/medical_review"
    request = {
        "schema_version": "medical_execution_request_v2",
        "run_id": run.name,
        "created_at": datetime.now(UTC).isoformat(),
        "dependencies": dependencies,
        "dependencies_sha256": content_hash(dependencies),
    }
    write_json(
        generated / "attempt_requested.json",
        {**request, "request_id": identity("medicalrequest", request)},
    )
    status, imported, runtime = (
        "blocked",
        None,
        {
            "effective_model": None,
            "model_calls": 0,
            "token_usage": None,
            "cost_estimate": None,
            "search_activity": [],
            "provider_fallbacks": [],
        },
    )
    try:
        for name, value in [("bundle", bundle), ("study_context", context), ("review_plan", plan)]:
            write_json(run / f"processed/medical_review/{name}.json", value)
        if reason is None:
            with session_lock(
                private_path(repo, PRIVATE_SOURCES / "codex_session.lock", PRIVATE_SOURCES)
            ) as lock_fd:
                # Recheck inside the lock, before handling credentials or launching.
                qualification = validate_qualification(repo, qualification_path)
                validate_packet(repo, bundle_path)
                validate_authorization(
                    auth,
                    bundle,
                    backend="codex_cli",
                    provider=provider,
                    model=model,
                    allow_web_search=False,
                    packet_sha256=dependencies["packet_sha256"],
                    execution_policy_sha256=dependencies["policy_sha256"],
                )
                write_json(generated / "qualification.json", qualification)
                write_json(generated / "output_schema.json", output_schema(repo))
                runtime = {**runtime, "model_calls": None}
                _launch(
                    preparation["raw"],
                    private_path(repo, qualification_path, PRIVATE_SOURCES).parent
                    / "catalogue.json",
                    generated,
                    output_schema(repo),
                    limits,
                    lock_fd,
                    executable=qualification["runtime"]["executable_path"],
                )
                runtime = observed_metadata(generated / "streams/events.jsonl")
                if (generated / "raw/generation.json").stat().st_size > execution_policy()[
                    "max_final_bytes"
                ]:
                    raise ValueError("Codex generation exceeds its final JSON byte limit.")
                envelope_bytes = (generated / "raw/generation.json").read_bytes()
                envelope = parse_json(envelope_bytes)
                validate_generation(repo, envelope, bundle, preparation["packet"])
                if load_bundle(repo, bundle_path)[1] != digest:
                    raise ValueError("Codex source bundle changed during generation.")
                validate_packet(repo, bundle_path)
                validate_qualification(repo, qualification_path)
                payload = derived_payload(envelope)
                incoming = private_path(
                    repo,
                    PRIVATE_SOURCES
                    / bundle["study_id"]
                    / "codex_outputs"
                    / (content_hash(payload) + ".json"),
                    PRIVATE_SOURCES,
                )
                if incoming.exists():
                    if read_json(incoming) != payload:
                        raise ValueError("Immutable Codex derived output changed.")
                else:
                    write_json(incoming, payload)
                imported = import_reviewer(repo, bundle_path, incoming, profiles=profiles)
                originals = read_json(imported / "processed/medical_review/proposals.json")
                write_json(
                    run / "processed/medical_review/proposals.json",
                    reading_proposals(
                        originals,
                        envelope,
                        bundle,
                        preparation["packet"],
                        envelope_sha256=hashlib.sha256(envelope_bytes).hexdigest(),
                        packet_sha256=dependencies["packet_sha256"],
                        runtime=runtime,
                    ),
                )
                write_json(
                    generated / "reading_lineage.json",
                    {
                        "schema_version": "medical_codex_lineage_v1",
                        "generation_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
                        "derived_payload_sha256": hashlib.sha256(
                            (imported / "generated/medical_review/raw/reviewer.json").read_bytes()
                        ).hexdigest(),
                        "import_manifest_sha256": content_hash(
                            read_json(imported / "run_manifest.json")
                        ),
                        "packet": preparation["packet"],
                        "packet_sha256": dependencies["packet_sha256"],
                        "runtime_observed": runtime,
                        "requested": {
                            "provider": "openai",
                            "backend": "codex_cli",
                            "model": MODEL,
                            "reasoning": "max",
                        },
                        "original_reviewer_executed": False,
                    },
                )
                status, reason = (
                    "completed",
                    "Codex reading imported; findings unverified and check coverage incomplete.",
                )
    except (Exception, KeyboardInterrupt) as error:
        status, imported = "failed", None
        reason = (
            "Codex interrupted; partial outputs retained, no retry."
            if isinstance(error, KeyboardInterrupt)
            else str(error)
        )
    coverage = _coverage(bundle, plan)
    if status != "completed":
        for row in coverage:
            row.update(execution=status, stop_reason=reason)
    write_json(run / "processed/medical_review/coverage.json", coverage)
    result = {
        "schema_version": "medical_execution_attempt_v2",
        "run_id": run.name,
        "request_id": identity("medicalrequest", request),
        "dependencies_sha256": content_hash(dependencies),
        "status": status,
        "reason": reason,
        **runtime,
        "effective_permissions": {
            "allow_llm": runtime["model_calls"] is None,
            "allow_web_search": False,
        },
        "authorization_sha256": dependencies["authorization_sha256"],
        "duration_seconds": time.monotonic() - started,
        "limits": limits,
        "coverage_available": False,
        "live_isolation_status": "qualified" if qualification else "unqualified_no_backend_started",
        "import_run_id": imported.name if imported else None,
        "import_run_reference": imported.relative_to(repo).as_posix() if imported else None,
    }
    write_json(
        generated / "attempt_result.json",
        {**result, "attempt_id": identity("medicalattempt", result)},
    )
    for artifact in sorted(run.rglob("*")):
        if artifact.is_file() and artifact.name != "run_manifest.json":
            update_run(manifest, artifact=str(artifact))
    update_run(manifest, stage="medical-execution", status=status)
    update_run(
        manifest,
        status="completed" if status == "completed" else "failed",
        error=reason if status != "completed" else None,
    )
    return run
