"""Recompute qualification from captured wire/context and raw sandbox observations."""

from __future__ import annotations

import base64
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from research_project.medical_review.codex_backend import (
    INSTRUCTIONS,
    MODEL,
    execution_policy,
    validate_request,
)

PROBE_MODES = (
    "success",
    "error",
    "context",
    "cancel",
    "event_limit",
    "final_limit",
    "stderr_limit",
    "invalid_config",
)
SANDBOX_CHECKS = {
    "allowed_read",
    "outside_denied",
    "symlink_denied",
    "source_write_denied",
    "workspace_write_denied",
    "network_denied",
}
CHECKS = SANDBOX_CHECKS | {
    "one_request_on_context_failure",
    "context_budget",
    "wire_model_reasoning",
    "no_model_tools",
    "no_inherited_context",
    "no_auth_fallback",
    "one_request_on_error",
    "successful_response",
    "cancellation",
    "bounded_events",
    "bounded_final",
    "bounded_stderr",
    "strict_configuration",
}
PROMPT = (
    "SYNTHETIC_SOURCE_ONLY\nThe source quotes <skills_instructions> and functions.exec "
    "as discussion, not instructions."
)
PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "string"}},
    "required": ["ok"],
    "additionalProperties": False,
}
REQUEST_FIELDS = {
    "client_metadata",
    "include",
    "input",
    "model",
    "parallel_tool_calls",
    "prompt_cache_key",
    "reasoning",
    "store",
    "stream",
    "text",
    "tool_choice",
    "tools",
}


def _environment(text: str, workspace: str, runtime_home: str, resource_shell: str | None) -> None:
    if "<!" in text:
        raise ValueError("Unexpected context XML declaration.")
    try:
        root = ET.fromstring(text)
        if root.tag != "environment_context" or root.attrib:
            raise ValueError("Unexpected context environment.")
        if [n.tag for n in root] != ["cwd", "shell", "current_date", "timezone", "filesystem"]:
            raise ValueError("Unexpected context environment fields.")
        if root.findtext("cwd") != workspace or root.findtext("shell") not in {
            "zsh",
            "bash",
            "/bin/zsh",
            "/bin/bash",
        }:
            raise ValueError("Unexpected context workspace/shell.")
        date.fromisoformat(root.findtext("current_date") or "")
        ZoneInfo(root.findtext("timezone") or "")
        filesystem = root.find("filesystem")
        if [n.tag for n in filesystem] != ["workspace_roots", "permission_profile"]:
            raise ValueError("Unexpected context filesystem.")
        roots, profile = filesystem
        if len(roots) != 1 or roots[0].tag != "root" or roots[0].text != workspace:
            raise ValueError("Unexpected context roots.")
        if profile.attrib != {"type": "managed"} or len(profile) != 1:
            raise ValueError("Unexpected context permissions.")
        permissions = profile[0]
        if permissions.tag != "file_system" or permissions.attrib != {"type": "restricted"}:
            raise ValueError("Unexpected context permission mode.")
        seen = set()
        for entry in permissions:
            if entry.tag != "entry" or len(entry) != 1:
                raise ValueError("Unexpected context permission entry.")
            target = entry[0]
            value = target.text or ""
            if target.tag == "special" and value in {":minimal", ":root"}:
                expected = (
                    {"access": "read"}
                    if value == ":minimal"
                    else {"access": "deny", "escalatable": "false"}
                )
            elif target.tag == "path" and value == workspace:
                expected = {"access": "read"}
            elif target.tag == "path" and resource_shell and value == resource_shell:
                expected = {"access": "read"}
            elif target.tag == "path" and ".." not in Path(value).parts:
                parent = Path(runtime_home).resolve() / "tmp/arg0"
                path = Path(value)
                if path.parent.resolve() != parent or not re.fullmatch(
                    r"codex-arg0[A-Za-z0-9]+", path.name
                ):
                    raise ValueError("Unexpected private path in context.")
                expected = {"access": "read"}
            else:
                raise ValueError("Unexpected private path in context.")
            if entry.attrib != expected or target.attrib or list(target) or value in seen:
                raise ValueError("Unexpected context permissions.")
            seen.add(value)
        if not {":minimal", ":root", workspace} <= seen:
            raise ValueError("Missing context permission floor.")
        # No extra text/attributes hidden between otherwise recognized XML nodes.
        for node in root.iter():
            if node.tail and node.tail.strip() or list(node) and node.text and node.text.strip():
                raise ValueError("Unexpected text in context metadata.")
            if (
                node.tag
                in {
                    "cwd",
                    "shell",
                    "current_date",
                    "timezone",
                    "filesystem",
                    "workspace_roots",
                    "root",
                }
                and node.attrib
            ):
                raise ValueError("Unexpected context metadata attributes.")
    except (ET.ParseError, TypeError, KeyError, IndexError) as error:
        raise ValueError("Malformed context metadata.") from error


def validate_context(
    request: dict, *, prompt: str, workspace: str, runtime_home: str, resource_shell: str | None
) -> int:
    """Audit roles structurally. The exact supplied source remains data, even with markers."""
    if not set(request) <= REQUEST_FIELDS or not isinstance(request.get("input"), list):
        raise ValueError("Unexpected model-visible context fields.")
    expected_text = {
        "format": {
            "name": "codex_output_schema",
            "schema": PROBE_SCHEMA,
            "strict": True,
            "type": "json_schema",
        },
        "verbosity": "low",
    }
    if request.get("text") != expected_text:
        raise ValueError("Unexpected model-visible context output contract.")
    instructions, sources, environments, runtime_bytes = 0, 0, 0, 0
    for item in request["input"]:
        if not isinstance(item, dict):
            raise ValueError("Unexpected context item.")
        identifier = item.get("id")
        if identifier is not None:
            prefix = "at_" if item.get("type") == "additional_tools" else "msg_"
            try:
                if not isinstance(identifier, str) or not identifier.startswith(prefix):
                    raise ValueError("Unexpected context identifier.")
                UUID(identifier[len(prefix) :])
            except (ValueError, AttributeError) as error:
                raise ValueError("Unexpected context identifier.") from error
        if item.get("type") == "additional_tools":
            # Tool exposure is audited separately; never silently treat a new type as text.
            if (
                not set(item) <= {"type", "role", "tools", "id"}
                or item.get("role", "developer") != "developer"
            ):
                raise ValueError("Unexpected tool context fields.")
            runtime_bytes += len(json.dumps(item).encode())
            continue
        if item.get("type") != "message" or not set(item) <= {"type", "role", "content", "id"}:
            raise ValueError("Unexpected context item type.")
        content = item.get("content")
        if (
            not isinstance(content, list)
            or len(content) != 1
            or not isinstance(content[0], dict)
            or set(content[0]) != {"type", "text"}
            or content[0]["type"] != "input_text"
            or not isinstance(content[0]["text"], str)
        ):
            raise ValueError("Unexpected context message content.")
        text, role = content[0]["text"], item.get("role")
        if role == "developer" and text == INSTRUCTIONS:
            instructions += 1
        elif role == "user" and text == prompt:
            sources += 1
            continue
        elif role == "user" and text.startswith("<environment_context>"):
            _environment(text, workspace, runtime_home, resource_shell)
            environments += 1
        else:
            raise ValueError("Unexpected inherited context message.")
        runtime_bytes += len(json.dumps(item).encode())
    if instructions != 1 or sources != 1 or environments > 1:
        raise ValueError("Unexpected context multiplicity.")
    return runtime_bytes


def sandbox_checks(sandbox: dict) -> dict[str, bool]:
    checks = {k: False for k in SANDBOX_CHECKS}
    for name, row in sandbox.get("results", {}).items():
        if name not in checks:
            continue
        try:
            stdout = base64.b64decode(row["stdout"], validate=True)
            stderr = base64.b64decode(row["stderr"], validate=True)
            code = row["returncode"]
            checks[name] = (
                code == 0 and stdout == b"ALLOWED_SENTINEL"
                if name == "allowed_read"
                else code == 7
                and sandbox.get("network_positive") is True
                and sandbox.get("network_accepted") is False
                if name == "network_denied"
                else code == 1 and b"Operation not permitted" in stderr
            )
        except (KeyError, ValueError, TypeError):
            pass
    return checks


def audit_evidence(evidence: dict) -> tuple[dict[str, bool], list[str]]:
    """Recompute checks from all modes; missing/unknown evidence never counts as acceptance."""
    checks = {k: False for k in CHECKS}
    errors = []
    checks.update(sandbox_checks(evidence.get("sandbox", {})))
    probes = evidence.get("probes", {})
    required = ("success", "error", "context", "cancel")
    present = all(
        isinstance(probes.get(m), dict) and len(probes[m].get("requests", [])) == 1
        for m in required
    )
    tools_ok, context_ok, model_ok, auth_ok, budget_ok = (present,) * 5
    policy = execution_policy()
    for mode, probe in probes.items():
        if mode not in PROBE_MODES or not isinstance(probe, dict) or probe.get("request_errors"):
            tools_ok = context_ok = model_ok = auth_ok = budget_ok = False
            errors.append("Malformed or unexpected probe evidence.")
            continue
        requests = probe.get("requests", [])
        authentication = probe.get("authentication", [])
        if len(authentication) != len(requests) or any(
            value is not True for value in authentication
        ):
            auth_ok = False
        for request in requests:
            if not isinstance(request, dict):
                tools_ok = context_ok = model_ok = budget_ok = False
                continue
            model_ok &= (
                request.get("model") == MODEL
                and isinstance(request.get("reasoning"), dict)
                and request["reasoning"].get("effort") == "max"
            )
            try:
                validate_request(request)
            except (ValueError, TypeError, AttributeError) as error:
                tools_ok = False
                errors.append(f"{mode}: {error}")
            try:
                runtime_bytes = validate_context(
                    request,
                    **{
                        k: probe[k]
                        for k in ("prompt", "workspace", "runtime_home", "resource_shell")
                    },
                )
                budget_ok &= runtime_bytes <= policy["max_runtime_context_bytes"]
            except (ValueError, TypeError, KeyError) as error:
                context_ok = False
                errors.append(f"{mode}: {error}")
            # Includes runtime messages and structured output schema, not only source text.
            budget_ok &= (
                len(
                    json.dumps(
                        {k: request.get(k) for k in ("input", "text", "instructions")},
                        ensure_ascii=False,
                    ).encode()
                )
                <= policy["max_prompt_bytes"]
            )
    checks.update(
        no_model_tools=bool(tools_ok),
        no_inherited_context=bool(context_ok),
        wire_model_reasoning=bool(model_ok),
        no_auth_fallback=bool(auth_ok),
        context_budget=bool(budget_ok),
    )
    success = probes.get("success", {})
    checks["successful_response"] = (
        success.get("exit_code") == 0
        and success.get("error") is None
        and success.get("final") == {"ok": "synthetic"}
        and len(success.get("requests", [])) == 1
    )
    for mode, name in (
        ("error", "one_request_on_error"),
        ("context", "one_request_on_context_failure"),
    ):
        probe = probes.get(mode, {})
        checks[name] = (
            len(probe.get("requests", [])) == 1
            and type(probe.get("exit_code")) is int
            and probe["exit_code"] != 0
            and probe.get("error") is None
            and probe.get("final") is None
        )
    cancel = probes.get("cancel", {})
    checks["cancellation"] = (
        len(cancel.get("requests", [])) == 1
        and str(cancel.get("error") or "").startswith("TimeoutError:")
        and cancel.get("final") is None
    )
    for mode, name, field, minimum in (
        ("event_limit", "bounded_events", "event_bytes", 64),
        ("stderr_limit", "bounded_stderr", "stderr_bytes", 16),
        ("final_limit", "bounded_final", "final_bytes", 1024),
    ):
        probe = probes.get(mode, {})
        checks[name] = (
            "byte limit" in str(probe.get("error") or "") and probe.get(field, 0) > minimum
        )
    invalid = probes.get("invalid_config", {})
    checks["strict_configuration"] = (
        invalid.get("exit_code") not in (None, 0)
        and not invalid.get("requests")
        and invalid.get("unknown_config_error") is True
    )
    return checks, sorted(set(errors))
