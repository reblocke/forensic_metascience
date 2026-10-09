"""Offline, actual-CLI qualification with synthetic sources and a loopback provider.

No credentials are read. A failed capability audit is a failed qualification,
even when individual command sandbox checks pass.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_project.medical_review.codex_audit import (
    CHECKS,
    NATIVE_PROBES,
    PROBE_MODES,
    PROBE_SCHEMA,
    PROMPT,
    TOOL_DENIAL_MARKER,
    audit_evidence,
)
from research_project.medical_review.codex_backend import (
    ADOPTED_RUNTIME,
    INSTRUCTIONS,
    MODEL,
    clean_environment,
    codex_command,
    execution_policy,
    runtime_identity,
)
from research_project.medical_review.codex_process import bounded_process
from research_project.medical_review.codex_source_build import validate_build_manifest
from research_project.medical_review.records import (
    PRIVATE_SOURCES,
    content_hash,
    private_path,
    read_json,
    write_json,
)

QUALIFICATIONS = PRIVATE_SOURCES / "runtime_qualifications"


def _synthetic_auth(path: Path) -> None:
    claims = {
        "exp": 4102444800,
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "synthetic-account",
            "chatgpt_plan_type": "pro",
        },
    }
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    write_json(
        path / "auth.json",
        {
            "auth_mode": "chatgpt",
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": "e30." + encoded + ".synthetic",
                "access_token": "synthetic-only",
                "refresh_token": "synthetic-only",
                "account_id": "synthetic-account",
            },
            "last_refresh": datetime.now(UTC).isoformat(),
        },
    )


def _response(final: str) -> bytes:
    message = {
        "type": "message",
        "id": "msg_synthetic",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": final}],
    }
    response = {
        "id": "resp_synthetic",
        "object": "response",
        "model": MODEL,
        "status": "completed",
        "output": [message],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }
    items = [
        {
            "type": "response.created",
            "response": {**response, "status": "in_progress", "output": []},
        },
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**message, "content": []},
        },
        {
            "type": "response.output_text.delta",
            "item_id": message["id"],
            "output_index": 0,
            "content_index": 0,
            "delta": final,
        },
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        {"type": "response.completed", "response": response},
    ]
    return "".join("data: " + json.dumps(row) + "\n\n" for row in items).encode()


def _native_response(mode: str) -> bytes:
    """Force valid unsolicited calls, even though the request advertises no tools."""
    custom = mode in {"tool_freeform", "tool_exec", "tool_patch", "tool_nested", "tool_after_final"}
    names = {
        "tool_direct": (None, "exec_command"),
        "tool_namespaced": ("connector", "read"),
        "tool_freeform": (None, "apply_patch"),
        "tool_exec": ("functions", "exec"),
        "tool_wait": ("functions", "wait"),
        "tool_patch": ("functions", "apply_patch"),
        "tool_user_input": ("functions", "request_user_input_async"),
        "tool_nested": ("functions", "exec"),
        "tool_after_final": ("functions", "exec"),
    }
    namespace, name = names.get(mode, (None, "tool_search"))
    call = {
        "type": "custom_tool_call" if custom else "function_call",
        "id": "ctc_synthetic" if custom else "fc_synthetic",
        "call_id": "synthetic-call",
        "name": name,
    }
    if namespace is not None:
        call["namespace"] = namespace
    if custom:
        call["input"] = (
            'await tools.apply_patch("*** Begin Patch\n*** End Patch");'
            if mode == "tool_nested"
            else 'text("TOOL_EXECUTION_SENTINEL")'
            if name == "exec"
            else "*** Begin Patch\n*** End Patch"
        )
    else:
        arguments = (
            {"cell_id": "synthetic"}
            if mode == "tool_wait"
            else {"questions": [{"title": "Synthetic only"}]}
            if mode == "tool_user_input"
            else {"source": "synthetic"}
            if mode == "tool_namespaced"
            else {"cmd": "echo TOOL_EXECUTION_SENTINEL"}
        )
        call["arguments"] = json.dumps(arguments)
    if mode == "tool_search_malformed":
        call = {
            "type": "tool_search_call",
            "id": "ts_synthetic",
            "call_id": "synthetic-call",
            "execution": "client",
            "arguments": {"unexpected": True},
        }
    elif mode == "tool_hosted_search":
        call = {
            "type": "web_search_call",
            "id": "ws_synthetic",
            "status": "completed",
            "action": {"type": "search", "query": "synthetic only"},
        }
    elif mode == "tool_hosted_image":
        call = {
            "type": "image_generation_call",
            "id": "ig_synthetic",
            "status": "completed",
            "result": "synthetic only",
        }
    output = [call]
    if mode == "tool_after_final":
        output.insert(
            0,
            {
                "type": "message",
                "id": "msg_synthetic",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": '{"ok":"synthetic"}'}],
            },
        )
    response = {
        "id": "resp_synthetic",
        "object": "response",
        "model": MODEL,
        "status": "completed",
        "output": output,
    }
    events = [
        {
            "type": "response.created",
            "response": {**response, "status": "in_progress", "output": []},
        }
    ]
    for index, item in enumerate(output):
        events.extend(
            [
                {"type": "response.output_item.added", "output_index": index, "item": item},
                {"type": "response.output_item.done", "output_index": index, "item": item},
            ]
        )
    events.append({"type": "response.completed", "response": response})
    return "".join("data: " + json.dumps(row) + "\n\n" for row in events).encode()


def _provider_response(mode: str, index: int) -> tuple[int, str, bytes]:
    if mode in NATIVE_PROBES and index == 0:
        return 200, "text/event-stream", _native_response(mode)
    if mode in {"success", "event_limit", "final_limit"}:
        return (
            200,
            "text/event-stream",
            _response(json.dumps({"ok": "x" * 4096 if mode == "final_limit" else "synthetic"})),
        )
    if mode == "context":
        return (
            400,
            "application/json",
            (
                b'{"error":{"message":"maximum context length exceeded",'
                b'"type":"invalid_request_error","code":"context_length_exceeded"}}'
            ),
        )
    return 503, "application/json", b'{"error":{"message":"synthetic failure"}}'


def _probe_command(
    executable: str, root: Path, port: int, mode: str, *, disable_tools: bool = False
) -> list[str]:
    command = codex_command(
        executable,
        root / "workspace",
        root / "instructions.txt",
        root / "schema.json",
        root / "final.json",
        provider_url=f"http://127.0.0.1:{port}/v1",
        disable_tools=disable_tools,
    )
    if mode in {"stderr_limit", "invalid_config"}:
        command[-1:-1] = ["-c", "qualification_canary_unsupported=true"]
    # Contain the entire controller's probe egress, including telemetry/auth refresh.
    seatbelt = (
        "(version 1)(allow default)(deny network*)"
        f'(allow network-outbound (remote tcp "localhost:{port}"))'
    )
    return ["/usr/bin/sandbox-exec", "-p", seatbelt, *command]


def _probe_cli(
    executable: str, catalogue: Path, root: Path, mode: str, *, disable_tools: bool = False
) -> dict[str, Any]:
    home, workspace = root / "runtime", root / "workspace"
    home.mkdir()
    workspace.mkdir()
    _synthetic_auth(home)
    shutil.copyfile(catalogue, home / "models_cache.json")
    # Deliberately offered context must not enter the wire request.
    (workspace / "AGENTS.md").write_text("PRIVATE_CONTEXT_SENTINEL", encoding="utf-8")
    (home / "config.toml").write_text('developer_instructions="PRIVATE_CONFIG_SENTINEL"\n')
    instructions = root / "instructions.txt"
    instructions.write_text(INSTRUCTIONS, encoding="utf-8")
    schema = root / "schema.json"
    write_json(schema, PROBE_SCHEMA)
    requests: list[dict[str, Any]] = []
    authentication: list[bool] = []
    request_errors: list[str] = []
    wire = root / "requests"
    wire.mkdir()
    responses = root / "responses"
    responses.mkdir()
    cancel = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            if length > 1024 * 1024:
                request_errors.append("Outgoing request exceeds capture limit.")
                self.send_error(413)
                return
            raw = self.rfile.read(length)
            index = len(authentication)
            (wire / f"{index:03d}.json").write_bytes(raw)
            write_json(wire / f"{index:03d}.headers.json", dict(self.headers.items()))
            try:
                requests.append(json.loads(raw))
            except (ValueError, UnicodeError) as exc:
                request_errors.append(str(exc))
            authentication.append(self.headers.get("Authorization") == "Bearer synthetic-only")
            if mode == "cancel":
                cancel.wait(5)
            status, content_type, body = _provider_response(mode, index)
            (responses / f"{index:03d}.body").write_bytes(body)
            write_json(
                responses / f"{index:03d}.json", {"status": status, "content_type": content_type}
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    final = root / "final.json"
    command = _probe_command(executable, root, port, mode, disable_tools=disable_tools)
    error, code = None, None
    try:
        code = bounded_process(
            command,
            cwd=workspace,
            env=clean_environment(home),
            prompt=PROMPT.encode(),
            output=root / "streams",
            final=final,
            duration=1.5 if mode == "cancel" else 30,
            event_bytes=64 if mode == "event_limit" else 8 * 1024 * 1024,
            stderr_bytes=16 if mode == "stderr_limit" else 1024 * 1024,
            final_bytes=1024 if mode == "final_limit" else 2 * 1024 * 1024,
        )
    except (Exception, KeyboardInterrupt) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        cancel.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    final_value = None
    if final.is_file():
        try:
            final_value = json.loads(final.read_bytes())
        except (ValueError, UnicodeError):
            pass  # Malformed bytes remain retained, never accepted.
    shell = Path(executable).resolve().parents[1] / "codex-resources/zsh/bin/zsh"
    streams = root / "streams"
    stderr = (streams / "stderr.txt").read_bytes()
    return {
        "requests": requests,
        "authentication": authentication,
        "request_errors": request_errors,
        "exit_code": code,
        "error": error,
        "final": final_value,
        "prompt": PROMPT,
        "command": command,
        "workspace": str(workspace),
        "runtime_home": str(home),
        "resource_shell": str(shell) if shell.is_file() else None,
        "provider_port": port,
        "event_bytes": (streams / "events.jsonl").stat().st_size,
        "stderr_bytes": len(stderr),
        "final_bytes": final.stat().st_size if final.is_file() else 0,
        "tool_denial_error": TOOL_DENIAL_MARKER in stderr
        or TOOL_DENIAL_MARKER in (streams / "events.jsonl").read_bytes(),
        "unknown_config_error": b"qualification_canary_unsupported" in stderr
        and b"unknown" in stderr.lower(),
    }


def _sandbox_checks(executable: str, root: Path) -> dict[str, Any]:
    workspace = root / "sandbox"
    workspace.mkdir()
    home = root / "sandbox-runtime"
    home.mkdir()
    allowed, outside = workspace / "source.txt", root / "outside.txt"
    allowed.write_text("ALLOWED_SENTINEL")
    outside.write_text("PRIVATE_SENTINEL")
    (workspace / "escape").symlink_to(outside)
    settings = [
        "-P",
        "medical_reading",
        "-C",
        str(workspace),
        "-c",
        'permissions.medical_reading={filesystem={":root"="deny",":minimal"="read",'
        '":workspace_roots"={"."="read"}},network={enabled=false}}',
    ]
    commands = {
        "allowed_read": ["/bin/cat", str(allowed)],
        "outside_denied": ["/bin/cat", str(outside)],
        "symlink_denied": ["/bin/cat", str(workspace / "escape")],
        "source_write_denied": ["/usr/bin/touch", str(allowed)],
        "workspace_write_denied": ["/usr/bin/touch", str(workspace / "new")],
    }
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        # A reachable positive control; refusal alone is not denial evidence.
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            connection, _ = listener.accept()
            connection.close()
        commands["network_denied"] = [
            "/usr/bin/curl",
            "--max-time",
            "1",
            f"http://127.0.0.1:{port}",
        ]
        results = {}
        for name, args in commands.items():
            result = subprocess.run(
                [executable, "sandbox", *settings, "--", *args],
                capture_output=True,
                timeout=10,
                env=clean_environment(home),
            )
            results[name] = {
                "command": [executable, "sandbox", *settings, "--", *args],
                "returncode": result.returncode,
                "stdout": base64.b64encode(result.stdout).decode(),
                "stderr": base64.b64encode(result.stderr).decode(),
            }
        accepted = False
        listener.settimeout(0.05)
        try:
            connection, _ = listener.accept()
            connection.close()
            accepted = True
        except TimeoutError:
            pass
    return {"results": results, "network_positive": True, "network_accepted": accepted}


def qualify_codex(
    repo: Path,
    *,
    catalogue: Path,
    probe_executable: Path | None = None,
    probe_build_manifest: Path | None = None,
    runtime_executable: Path | None = None,
    runtime_build_manifest: Path | None = None,
) -> Path:
    """Write fresh evidence; assessment and operational selection remain distinct."""
    if (runtime_executable is None) != (runtime_build_manifest is None):
        raise ValueError("Operational executable and build manifest must be supplied together.")
    if runtime_executable is not None and (
        probe_executable is not None or probe_build_manifest is not None
    ):
        raise ValueError("Operational and assessment runtime arguments are exclusive.")
    if probe_build_manifest is not None and probe_executable is None:
        raise ValueError("A source build manifest requires an assessment-only probe executable.")
    output = private_path(repo, QUALIFICATIONS / uuid4().hex, QUALIFICATIONS)
    output.mkdir(parents=True)
    evidence, errors, runtime = {"sandbox": {}, "probes": {}}, [], None
    manifest_path = probe_build_manifest if probe_executable is not None else runtime_build_manifest
    try:
        runtime = runtime_identity(
            catalogue, probe_executable=probe_executable, runtime_executable=runtime_executable
        )
        if probe_executable is None and manifest_path is None:
            raise ValueError(
                "Operational qualification requires an explicit retained build manifest."
            )
        if manifest_path is not None:
            manifest_path = private_path(
                repo, manifest_path, PRIVATE_SOURCES / "runtime_candidates"
            )
            build = validate_build_manifest(manifest_path, Path(runtime["executable_path"]))
            if probe_executable is None:
                _validate_adopted_build(build)
            retained_build = output / "source-build"
            retained_build.mkdir()
            shutil.copyfile(manifest_path, retained_build / "build-manifest.json")
            for artifact in build["artifacts"].values():
                destination = retained_build / artifact["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(manifest_path.parent / artifact["path"], destination)
        shutil.copyfile(catalogue, output / "catalogue.json")
        if probe_executable is not None:
            provenance = Path(runtime["executable_path"]).parent.parent / "distribution.json"
            if provenance.is_file():
                shutil.copyfile(provenance, output / "distribution.json")
        with tempfile.TemporaryDirectory(prefix="medical-codex-qualification-") as directory:
            root = Path(directory)
            executable = runtime["executable_path"]
            evidence["sandbox"] = _sandbox_checks(executable, root)
            for mode in PROBE_MODES:
                destination = root / mode
                destination.mkdir()
                evidence["probes"][mode] = _probe_cli(
                    executable,
                    catalogue,
                    destination,
                    mode,
                    disable_tools=manifest_path is not None,
                )
                retained = output / mode
                shutil.copytree(destination / "streams", retained / "streams")
                shutil.copytree(destination / "requests", retained / "requests")
                shutil.copytree(destination / "responses", retained / "responses")
                if (destination / "final.json").is_file():
                    shutil.copyfile(destination / "final.json", retained / "final.json")
    except (Exception, KeyboardInterrupt) as error:
        errors.append(type(error).__name__ + ": " + str(error))
    checks, audit_errors = audit_evidence(evidence)
    write_json(output / "evidence.json", evidence)
    passing = all(checks.values()) and not errors and not audit_errors
    receipt = {
        "schema_version": "medical_codex_qualification_v4",
        "runtime_adoption": ADOPTED_RUNTIME.copy() if probe_executable is None else None,
        "source_build_manifest": "source-build/build-manifest.json"
        if manifest_path is not None
        else None,
        "assessment_only": probe_executable is not None,
        "all_checks_passed": passing,
        "runtime": runtime,
        "policy": execution_policy(),
        "checks": checks,
        "qualified": passing and probe_executable is None,
        "errors": errors + audit_errors,
        "created_at": datetime.now(UTC).isoformat(),
        "artifacts": {
            p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    receipt["receipt_sha256"] = content_hash(receipt)
    write_json(output / "qualification.json", receipt)
    return output / "qualification.json"


def _validate_adopted_build(build: dict) -> None:
    if (
        build.get("source", {}).get("commit") != ADOPTED_RUNTIME["source_commit"]
        or build.get("target") != ADOPTED_RUNTIME["target"]
        or build.get("executable_sha256") != ADOPTED_RUNTIME["executable_sha256"]
        or build.get("artifacts", {}).get("native_patch", {}).get("sha256")
        != ADOPTED_RUNTIME["native_patch_sha256"]
    ):
        raise ValueError("Codex build does not match the adopted runtime provenance.")


def _validate_evidence_files(
    root: Path, evidence: dict, runtime: dict, *, disable_tools: bool = False
) -> None:
    """Bind derived observations back to preserved raw bytes, including failed probes."""
    if set(evidence.get("probes", {})) != set(PROBE_MODES):
        raise ValueError("Codex qualification lacks complete probe evidence.")
    for mode, probe in evidence["probes"].items():
        retained = root / mode
        temporary = Path(probe["runtime_home"]).parent
        if (
            not temporary.is_absolute()
            or ".." in temporary.parts
            or probe["workspace"] != str(temporary / "workspace")
            or probe["runtime_home"] != str(temporary / "runtime")
        ):
            raise ValueError("Codex qualification workspace metadata changed.")
        shell = Path(runtime["executable_path"]).parents[1] / "codex-resources/zsh/bin/zsh"
        if probe["resource_shell"] != (
            str(shell) if runtime["resource_shell_sha256"] is not None else None
        ):
            raise ValueError("Codex qualification runtime resource metadata changed.")
        if (
            type(probe["provider_port"]) is not int
            or not 0 < probe["provider_port"] < 65536
            or probe["command"]
            != _probe_command(
                runtime["executable_path"],
                temporary,
                probe["provider_port"],
                mode,
                disable_tools=disable_tools,
            )
        ):
            raise ValueError("Codex qualification effective configuration changed.")
        if (retained / "streams/stdin.txt").read_bytes() != PROMPT.encode() or probe[
            "prompt"
        ] != PROMPT:
            raise ValueError("Codex qualification source context changed.")
        requests = [
            json.loads(p.read_bytes())
            for p in sorted((retained / "requests").glob("[0-9][0-9][0-9].json"))
        ]
        headers = [read_json(p) for p in sorted((retained / "requests").glob("*.headers.json"))]
        if (
            len(headers) != len(requests)
            or [
                {k.lower(): v for k, v in h.items()}.get("authorization") == "Bearer synthetic-only"
                for h in headers
            ]
            != probe["authentication"]
        ):
            raise ValueError("Codex qualification raw authentication evidence changed.")
        response_files = sorted((retained / "responses").glob("*.body"))
        metadata_files = sorted((retained / "responses").glob("*.json"))
        if len(response_files) != len(requests) or len(metadata_files) != len(requests):
            raise ValueError("Codex qualification lacks issued provider responses.")
        for index, (body_file, metadata_file) in enumerate(
            zip(response_files, metadata_files, strict=True)
        ):
            status, content_type, body = _provider_response(mode, index)
            if (
                body_file.name != f"{index:03d}.body"
                or metadata_file.name != f"{index:03d}.json"
                or body_file.read_bytes() != body
                or read_json(metadata_file) != {"status": status, "content_type": content_type}
            ):
                raise ValueError("Codex qualification issued response evidence changed.")
        if requests != probe["requests"]:
            raise ValueError("Codex qualification raw wire evidence changed.")
        for field, relative in (
            ("event_bytes", "streams/events.jsonl"),
            ("stderr_bytes", "streams/stderr.txt"),
            ("final_bytes", "final.json"),
        ):
            artifact = retained / relative
            if probe[field] != (artifact.stat().st_size if artifact.is_file() else 0):
                raise ValueError("Codex qualification raw stream sizes changed.")
        final = retained / "final.json"
        final_value = None
        if final.is_file():
            try:
                final_value = json.loads(final.read_bytes())
            except (ValueError, UnicodeError):
                pass  # Preserve invalid failed output; it cannot satisfy the success check.
        if probe["final"] != final_value:
            raise ValueError("Codex qualification final bytes changed.")
        stderr = (retained / "streams/stderr.txt").read_bytes()
        unknown = b"qualification_canary_unsupported" in stderr and b"unknown" in stderr.lower()
        denial = (
            TOOL_DENIAL_MARKER in stderr
            or TOOL_DENIAL_MARKER in (retained / "streams/events.jsonl").read_bytes()
        )
        if denial != probe.get("tool_denial_error", False):
            raise ValueError("Codex qualification dispatch rejection evidence changed.")
        if unknown != probe["unknown_config_error"]:
            raise ValueError("Codex qualification configuration evidence changed.")


def _validate_receipt(repo: Path, path: Path, *, assessment: bool) -> dict[str, Any]:
    """Recompute acceptance; old, assessment-only, relabeled or changed receipts fail."""
    path = private_path(repo, path, QUALIFICATIONS)
    receipt = read_json(path)
    if (
        "source_build_manifest" not in receipt
        or receipt.get("schema_version") != "medical_codex_qualification_v4"
        or "runtime_adoption" not in receipt
        or receipt["runtime_adoption"] != (None if assessment else ADOPTED_RUNTIME)
        or receipt.get("assessment_only") is not assessment
        or receipt.get("receipt_sha256")
        != content_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        or receipt.get("qualified") is not (not assessment)
        or receipt.get("all_checks_passed") is not True
        or receipt.get("errors") != []
        or set(receipt.get("checks", {})) != CHECKS
        or any(value is not True for value in receipt["checks"].values())
        or receipt.get("policy") != execution_policy()
    ):
        raise ValueError(
            "Codex runtime qualification failed, is assessment-only, or is unsupported."
        )
    artifacts = receipt.get("artifacts", {})
    required = {"catalogue.json", "evidence.json"} | {
        f"{mode}/streams/{name}"
        for mode in PROBE_MODES
        for name in ("stdin.txt", "events.jsonl", "stderr.txt")
    }
    present = {
        p.relative_to(path.parent).as_posix()
        for p in path.parent.rglob("*")
        if p.is_file() and p != path
    }
    if not required <= artifacts.keys() or set(artifacts) != present:
        raise ValueError("Codex qualification lacks complete raw artifacts.")
    for relative, digest in artifacts.items():
        artifact = private_path(repo, path.parent / relative, QUALIFICATIONS)
        if (
            path.parent not in artifact.parents
            or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Codex qualification artifacts changed.")
    manifest = receipt.get("source_build_manifest")
    if (
        manifest not in (None, "source-build/build-manifest.json")
        or not assessment
        and manifest is None
    ):
        raise ValueError("Codex operational qualification requires adopted build provenance.")
    if manifest is not None:
        build = validate_build_manifest(
            path.parent / manifest, Path(receipt["runtime"]["executable_path"])
        )
        if not assessment:
            _validate_adopted_build(build)
    current = runtime_identity(
        path.parent / "catalogue.json",
        **{
            "probe_executable" if assessment else "runtime_executable": Path(
                receipt["runtime"]["executable_path"]
            )
        },
    )
    if receipt["runtime"] != current:
        raise ValueError("Codex runtime/code/catalogue/policy changed; requalification required.")
    try:
        evidence = read_json(path.parent / "evidence.json")
        _validate_evidence_files(
            path.parent, evidence, receipt["runtime"], disable_tools=manifest is not None
        )
        checks, _ = audit_evidence(evidence)
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise ValueError("Codex qualification raw evidence is invalid.") from error
    if checks != receipt["checks"] or not all(checks.values()):
        raise ValueError("Codex qualification tools/context/sandbox evidence does not pass.")
    return receipt


def validate_qualification(repo: Path, path: Path) -> dict[str, Any]:
    """Only current supported operational receipts may authorize source preparation."""
    return _validate_receipt(repo, path, assessment=False)


def validate_assessment(repo: Path, path: Path) -> dict[str, Any]:
    """Reaudit a passing candidate without granting preparation/execution eligibility."""
    return _validate_receipt(repo, path, assessment=True)
