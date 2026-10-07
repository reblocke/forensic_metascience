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

from research_project.medical_review.codex_backend import (
    INSTRUCTIONS,
    MODEL,
    clean_environment,
    codex_command,
    execution_policy,
    runtime_identity,
    validate_request,
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
CHECKS = {
    "one_request_on_context_failure",
    "context_budget",
    "wire_model_reasoning",
    "no_model_tools",
    "no_inherited_context",
    "no_auth_fallback",
    "one_request_on_error",
    "successful_response",
    "allowed_read",
    "outside_denied",
    "symlink_denied",
    "source_write_denied",
    "workspace_write_denied",
    "network_denied",
    "cancellation",
}


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
    write_json(
        schema,
        {
            "type": "object",
            "properties": {"ok": {"type": "string"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    )
    requests: list[dict[str, Any]] = []
    authentication: list[bool] = []
    cancel = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            requests.append(json.loads(raw))
            authentication.append(self.headers.get("Authorization") == "Bearer synthetic-only")
            if mode == "cancel":
                cancel.wait(5)
            body = (
                _response('{"ok":"synthetic"}')
                if mode == "success"
                else b'{"error":{"message":"maximum context length exceeded",'
                b'"type":"invalid_request_error","code":"context_length_exceeded"}}'
                if mode == "context"
                else b'{"error":{"message":"synthetic failure"}}'
            )
            self.send_response(200 if mode == "success" else 400 if mode == "context" else 503)
            self.send_header(
                "Content-Type", "text/event-stream" if mode == "success" else "application/json"
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
    command = codex_command(
        executable,
        workspace,
        instructions,
        schema,
        final,
        provider_url=f"http://127.0.0.1:{port}/v1",
    )
    # Contain the entire controller's probe egress, including telemetry/auth refresh.
    seatbelt = (
        "(version 1)(allow default)(deny network*)"
        f'(allow network-outbound (remote tcp "localhost:{port}"))'
    )
    command = ["/usr/bin/sandbox-exec", "-p", seatbelt, *command]
    error, code = None, None
    try:
        code = bounded_process(
            command,
            cwd=workspace,
            env=clean_environment(home),
            prompt=b"SYNTHETIC_SOURCE_ONLY",
            output=root / "streams",
            final=final,
            duration=1.5 if mode == "cancel" else 30,
            event_bytes=8 * 1024 * 1024,
            stderr_bytes=1024 * 1024,
            final_bytes=2 * 1024 * 1024,
        )
    except (Exception, KeyboardInterrupt) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        cancel.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return {
        "requests": requests,
        "authentication": authentication,
        "exit_code": code,
        "error": error,
        "final": json.loads(final.read_text()) if final.is_file() else None,
    }


def _sandbox_checks(executable: str, root: Path) -> dict[str, bool]:
    workspace = root / "sandbox"
    workspace.mkdir()
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
                env={"PATH": "/usr/bin:/bin"},
            )
            results[name] = (
                result.returncode == 0 and result.stdout == b"ALLOWED_SENTINEL"
                if name == "allowed_read"
                else result.returncode == 7
                if name == "network_denied"
                else result.returncode == 1 and b"Operation not permitted" in result.stderr
            )
        listener.settimeout(0.05)
        try:
            connection, _ = listener.accept()
            connection.close()
            results["network_denied"] = False
        except TimeoutError:
            pass
    return results


def qualify_codex(repo: Path, *, catalogue: Path) -> Path:
    """Write one immutable private receipt, preserving negative qualification evidence."""
    output = private_path(repo, QUALIFICATIONS / uuid4().hex, QUALIFICATIONS)
    output.mkdir(parents=True)
    checks, probes, errors, runtime = {}, {}, [], None
    try:
        runtime = runtime_identity(catalogue)
        shutil.copyfile(catalogue, output / "catalogue.json")
        with tempfile.TemporaryDirectory(prefix="medical-codex-qualification-") as directory:
            root = Path(directory)
            executable = shutil.which("codex")
            checks.update(_sandbox_checks(executable, root))
            for mode in ("success", "error", "context", "cancel"):
                destination = root / mode
                destination.mkdir()
                probes[mode] = _probe_cli(executable, catalogue, destination, mode)
                shutil.copytree(destination / "streams", output / mode)
            requests = probes["success"]["requests"]
            checks["successful_response"] = (
                probes["success"]["exit_code"] == 0
                and probes["success"]["final"] == {"ok": "synthetic"}
                and len(requests) == 1
            )
            checks["wire_model_reasoning"] = bool(requests) and all(
                r.get("model") == MODEL and r.get("reasoning", {}).get("effort") == "max"
                for r in requests
            )
            checks["no_model_tools"] = bool(requests)
            for request in requests:
                try:
                    validate_request(request)
                except ValueError as error:
                    checks["no_model_tools"] = False
                    errors.append(str(error))
            context = json.dumps([r.get("input") for r in requests])
            checks["context_budget"] = (
                bool(requests)
                and len(context.encode()) <= execution_policy()["max_runtime_context_bytes"]
            )
            checks["no_inherited_context"] = bool(requests) and not any(
                marker in context
                for marker in (
                    "PRIVATE_CONTEXT_SENTINEL",
                    "PRIVATE_CONFIG_SENTINEL",
                    "<skills_instructions>",
                    "<multi_agent_role>",
                )
            )
            checks["no_auth_fallback"] = all(
                p["authentication"] and all(p["authentication"]) for p in probes.values()
            )
            checks["one_request_on_error"] = len(probes["error"]["requests"]) == 1
            checks["one_request_on_context_failure"] = len(probes["context"]["requests"]) == 1
            checks["cancellation"] = len(probes["cancel"]["requests"]) == 1 and (
                probes["cancel"]["error"] or ""
            ).startswith("TimeoutError:")
    except (Exception, KeyboardInterrupt) as error:
        errors.append(type(error).__name__ + ": " + str(error))
    write_json(output / "probes.json", probes)
    receipt = {
        "schema_version": "medical_codex_qualification_v1",
        "runtime": runtime,
        "policy": execution_policy(),
        "checks": {k: checks.get(k, False) for k in sorted(CHECKS)},
        "qualified": CHECKS <= checks.keys() and all(checks.values()),
        "errors": errors,
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


def validate_qualification(repo: Path, path: Path) -> dict[str, Any]:
    """Fail closed on any failed check, changed dependency or altered probe artifact."""
    path = private_path(repo, path, QUALIFICATIONS)
    receipt = read_json(path)
    if (
        receipt.get("schema_version") != "medical_codex_qualification_v1"
        or receipt.get("receipt_sha256")
        != content_hash({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        or receipt.get("qualified") is not True
        or set(receipt.get("checks", {})) != CHECKS
        or any(value is not True for value in receipt["checks"].values())
        or receipt.get("policy") != execution_policy()
    ):
        raise ValueError("Codex runtime qualification failed or is unsupported.")
    for relative, digest in receipt["artifacts"].items():
        artifact = private_path(repo, path.parent / relative, QUALIFICATIONS)
        if (
            path.parent not in artifact.parents
            or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Codex qualification artifacts changed.")
    if receipt["runtime"] != runtime_identity(path.parent / "catalogue.json"):
        raise ValueError("Codex runtime/code/catalogue/policy changed; requalification required.")
    # Reaudit actual wire data; an edited boolean cannot qualify exposed tools.
    probes = read_json(path.parent / "probes.json")
    if not probes.get("success", {}).get("requests"):
        raise ValueError("Codex qualification lacks actual wire evidence.")
    for request in probes["success"]["requests"]:
        validate_request(request)
    return receipt
