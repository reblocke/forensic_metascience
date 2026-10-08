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
    PROBE_MODES,
    PROBE_SCHEMA,
    PROMPT,
    audit_evidence,
)
from research_project.medical_review.codex_backend import (
    INSTRUCTIONS,
    MODEL,
    clean_environment,
    codex_command,
    execution_policy,
    runtime_identity,
)
from research_project.medical_review.codex_process import bounded_process
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


def _probe_command(executable: str, root: Path, port: int, mode: str) -> list[str]:
    command = codex_command(
        executable,
        root / "workspace",
        root / "instructions.txt",
        root / "schema.json",
        root / "final.json",
        provider_url=f"http://127.0.0.1:{port}/v1",
    )
    if mode in {"stderr_limit", "invalid_config"}:
        command[-1:-1] = ["-c", "qualification_canary_unsupported=true"]
    # Contain the entire controller's probe egress, including telemetry/auth refresh.
    seatbelt = (
        "(version 1)(allow default)(deny network*)"
        f'(allow network-outbound (remote tcp "localhost:{port}"))'
    )
    return ["/usr/bin/sandbox-exec", "-p", seatbelt, *command]


def _probe_cli(executable: str, catalogue: Path, root: Path, mode: str) -> dict[str, Any]:
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
            body = (
                _response(json.dumps({"ok": "x" * 4096 if mode == "final_limit" else "synthetic"}))
                if mode in {"success", "event_limit", "final_limit"}
                else b'{"error":{"message":"maximum context length exceeded",'
                b'"type":"invalid_request_error","code":"context_length_exceeded"}}'
                if mode == "context"
                else b'{"error":{"message":"synthetic failure"}}'
            )
            self.send_response(
                200
                if mode in {"success", "event_limit", "final_limit"}
                else 400
                if mode == "context"
                else 503
            )
            self.send_header(
                "Content-Type",
                "text/event-stream"
                if mode in {"success", "event_limit", "final_limit"}
                else "application/json",
            )
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
    command = _probe_command(executable, root, port, mode)
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


def qualify_codex(repo: Path, *, catalogue: Path, probe_executable: Path | None = None) -> Path:
    """Write immutable evidence. Explicit executable probes can never authorize live use."""
    output = private_path(repo, QUALIFICATIONS / uuid4().hex, QUALIFICATIONS)
    output.mkdir(parents=True)
    evidence, errors, runtime = {"sandbox": {}, "probes": {}}, [], None
    try:
        runtime = runtime_identity(catalogue, probe_executable=probe_executable)
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
                evidence["probes"][mode] = _probe_cli(executable, catalogue, destination, mode)
                retained = output / mode
                shutil.copytree(destination / "streams", retained / "streams")
                shutil.copytree(destination / "requests", retained / "requests")
                if (destination / "final.json").is_file():
                    shutil.copyfile(destination / "final.json", retained / "final.json")
    except (Exception, KeyboardInterrupt) as error:
        errors.append(type(error).__name__ + ": " + str(error))
    checks, audit_errors = audit_evidence(evidence)
    write_json(output / "evidence.json", evidence)
    passing = all(checks.values())
    receipt = {
        "schema_version": "medical_codex_qualification_v2",
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


def _validate_evidence_files(root: Path, evidence: dict, runtime: dict) -> None:
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
            != _probe_command(runtime["executable_path"], temporary, probe["provider_port"], mode)
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
        if probe["final"] != (json.loads(final.read_bytes()) if final.is_file() else None):
            raise ValueError("Codex qualification final bytes changed.")
        stderr = (retained / "streams/stderr.txt").read_bytes()
        unknown = b"qualification_canary_unsupported" in stderr and b"unknown" in stderr.lower()
        if unknown != probe["unknown_config_error"]:
            raise ValueError("Codex qualification configuration evidence changed.")


def validate_qualification(repo: Path, path: Path) -> dict[str, Any]:
    """Recompute acceptance; old, assessment-only, relabeled or changed receipts fail."""
    path = private_path(repo, path, QUALIFICATIONS)
    receipt = read_json(path)
    if (
        receipt.get("schema_version") != "medical_codex_qualification_v2"
        or receipt.get("assessment_only") is not False
        or receipt.get("receipt_sha256")
        != content_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        or receipt.get("qualified") is not True
        or receipt.get("all_checks_passed") is not True
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
    if receipt["runtime"] != runtime_identity(path.parent / "catalogue.json"):
        raise ValueError("Codex runtime/code/catalogue/policy changed; requalification required.")
    try:
        evidence = read_json(path.parent / "evidence.json")
        _validate_evidence_files(path.parent, evidence, receipt["runtime"])
        checks, _ = audit_evidence(evidence)
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise ValueError("Codex qualification raw evidence is invalid.") from error
    if checks != receipt["checks"] or not all(checks.values()):
        raise ValueError("Codex qualification tools/context/sandbox evidence does not pass.")
    return receipt
