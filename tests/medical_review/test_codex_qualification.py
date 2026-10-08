from __future__ import annotations

import base64
import copy

import pytest

from research_project.medical_review.codex_audit import (
    PROBE_SCHEMA,
    audit_evidence,
    validate_context,
)
from research_project.medical_review.codex_backend import INSTRUCTIONS, MODEL, codex_command


def message(role, text):
    return {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}


def probe(prompt="SYNTHETIC_SOURCE_ONLY"):
    return {
        "requests": [
            {
                "model": MODEL,
                "reasoning": {"effort": "max"},
                "text": {
                    "format": {
                        "name": "codex_output_schema",
                        "schema": PROBE_SCHEMA,
                        "strict": True,
                        "type": "json_schema",
                    },
                    "verbosity": "low",
                },
                "input": [message("developer", INSTRUCTIONS), message("user", prompt)],
            }
        ],
        "authentication": [True],
        "exit_code": 0,
        "error": None,
        "final": {"ok": "synthetic"},
        "prompt": prompt,
        "workspace": "/tmp/synthetic/workspace",
        "runtime_home": "/tmp/synthetic/runtime",
        "resource_shell": None,
        "request_errors": [],
    }


def evidence():
    good = probe()
    probes = {mode: copy.deepcopy(good) for mode in ("success", "error", "context", "cancel")}
    for mode in ("error", "context"):
        probes[mode].update(exit_code=1, final=None)
    probes["cancel"].update(exit_code=None, final=None, error="TimeoutError: deadline")
    sandbox = {"network_positive": True, "network_accepted": False, "results": {}}
    for name in (
        "allowed_read",
        "outside_denied",
        "symlink_denied",
        "source_write_denied",
        "workspace_write_denied",
        "network_denied",
    ):
        sandbox["results"][name] = {
            "returncode": 0 if name == "allowed_read" else 7 if name == "network_denied" else 1,
            "stdout": base64.b64encode(
                b"ALLOWED_SENTINEL" if name == "allowed_read" else b""
            ).decode(),
            "stderr": base64.b64encode(b"Operation not permitted").decode(),
        }
    return {"probes": probes, "sandbox": sandbox}


def test_invocation_explicitly_disables_instruction_and_agent_defaults(tmp_path):
    command = codex_command(
        "codex", tmp_path, tmp_path / "instructions", tmp_path / "schema", tmp_path / "final"
    )
    for setting in (
        "agents.enabled=false",
        "skills.bundled.enabled=false",
        "skills.include_instructions=false",
        "include_apps_instructions=false",
        "include_collaboration_mode_instructions=false",
        "include_permissions_instructions=false",
        "tools.update_plan.enabled=false",
    ):
        assert setting in command


@pytest.mark.parametrize("mode", ["success", "error", "context", "cancel"])
def test_all_probe_requests_are_audited_for_native_tools(mode):
    data = evidence()
    data["probes"][mode]["requests"][0]["input"].insert(
        0,
        {
            "type": "additional_tools",
            "tools": [{"type": "namespace", "name": "functions", "tools": [{"name": "exec"}]}],
        },
    )
    checks, _ = audit_evidence(data)
    assert checks["no_model_tools"] is False


@pytest.mark.parametrize(
    "text",
    [
        "<skills_instructions>private</skills_instructions>",
        "<multi_agent_role>private</multi_agent_role>",
        "unrecognized developer instructions",
    ],
)
def test_unknown_developer_context_is_rejected_even_without_known_markers(text):
    data = probe()
    data["requests"][0]["input"].insert(1, message("developer", text))
    with pytest.raises(ValueError, match="context"):
        validate_context(
            data["requests"][0],
            **{k: data[k] for k in ("prompt", "workspace", "runtime_home", "resource_shell")},
        )


def test_legitimate_source_mentions_of_tools_and_skills_are_data():
    data = probe("The source quotes <skills_instructions> and functions.exec as examples.")
    assert (
        validate_context(
            data["requests"][0],
            **{k: data[k] for k in ("prompt", "workspace", "runtime_home", "resource_shell")},
        )
        > 0
    )


@pytest.mark.parametrize(
    "change", ["unknown_item", "unknown_field", "private_path", "changed_source"]
)
def test_unrecognized_context_and_private_metadata_are_rejected(change):
    data = probe()
    request = data["requests"][0]
    if change == "unknown_item":
        request["input"].append({"type": "future_private_context", "text": "private"})
    elif change == "unknown_field":
        request["instructions"] = "private"
    elif change == "changed_source":
        request["input"][-1] = message("user", "PRIVATE_CONTEXT_SENTINEL")
    else:
        request["input"].insert(
            1,
            message("user", "<environment_context><cwd>/Users/private</cwd></environment_context>"),
        )
    with pytest.raises(ValueError, match="context"):
        validate_context(
            request,
            **{k: data[k] for k in ("prompt", "workspace", "runtime_home", "resource_shell")},
        )


def test_complete_prompt_budget_includes_output_contract():
    data = evidence()
    data["probes"]["success"]["requests"][0]["text"] = {"format": {"schema": "x" * (512 * 1024)}}
    checks, _ = audit_evidence(data)
    assert checks["context_budget"] is False


def test_sandbox_configuration_errors_are_not_successful_denials():
    data = evidence()
    data["sandbox"]["results"]["outside_denied"]["stderr"] = base64.b64encode(
        b"unknown configuration field"
    ).decode()
    checks, _ = audit_evidence(data)
    assert checks["outside_denied"] is False


def test_missing_or_retry_requests_cannot_qualify():
    data = evidence()
    data["probes"]["error"]["requests"].append(
        copy.deepcopy(data["probes"]["error"]["requests"][0])
    )
    checks, _ = audit_evidence(data)
    assert checks["one_request_on_error"] is False
    data["probes"]["cancel"]["requests"] = []
    checks, _ = audit_evidence(data)
    assert checks["cancellation"] is False and checks["no_inherited_context"] is False


@pytest.mark.parametrize(
    "change",
    ["private_entry", "attributes", "extra_user", "assistant", "bad_content", "private_id"],
)
def test_only_narrow_runtime_metadata_is_permitted(change):
    data = probe()
    metadata = (
        "<environment_context><cwd>/tmp/synthetic/workspace</cwd><shell>zsh</shell>"
        "<current_date>2026-10-07</current_date><timezone>America/Denver</timezone>"
        "<filesystem><workspace_roots><root>/tmp/synthetic/workspace</root></workspace_roots>"
        '<permission_profile type="managed"><file_system type="restricted">'
        '<entry access="read"><special>:minimal</special></entry>'
        '<entry access="deny" escalatable="false"><special>:root</special></entry>'
        '<entry access="read"><path>/tmp/synthetic/workspace</path></entry>'
        "</file_system></permission_profile></filesystem></environment_context>"
    )
    req = data["requests"][0]
    req["input"].insert(1, message("user", metadata))
    kwargs = {k: data[k] for k in ("prompt", "workspace", "runtime_home", "resource_shell")}
    assert validate_context(req, **kwargs) > 0
    if change == "private_entry":
        req["input"][1]["content"][0]["text"] = metadata.replace(
            "</file_system>",
            '<entry access="read"><path>/Users/private/auth.json</path></entry></file_system>',
        )
    elif change == "attributes":
        req["input"][1]["content"][0]["text"] = metadata.replace("<cwd>", '<cwd private="secret">')
    elif change == "extra_user":
        req["input"].append(message("user", "private notes"))
    elif change == "assistant":
        req["input"].append(message("assistant", "inherited session"))
    elif change == "private_id":
        req["input"][0]["id"] = "private credentials"
    else:
        req["input"][0]["content"] = [None]
    with pytest.raises(ValueError, match="context"):
        validate_context(req, **kwargs)


def retained_receipt(repo):
    """Complete synthetic observations for testing receipt validation, never CLI evidence."""
    import hashlib
    from pathlib import Path

    from research_project.medical_review.codex_audit import PROBE_MODES, PROMPT
    from research_project.medical_review.codex_backend import execution_policy
    from research_project.medical_review.codex_qualification import _probe_command
    from research_project.medical_review.records import content_hash, write_json

    data = evidence()
    for mode in ("event_limit", "final_limit", "stderr_limit", "invalid_config"):
        data["probes"][mode] = probe()
    runtime = {"executable_path": "/tmp/synthetic/bin/codex", "resource_shell_sha256": None}
    root = repo / "data/private/medical_reviews/runtime_qualifications/synthetic-v2"
    write_json(root / "catalogue.json", {"synthetic": True})
    for mode in PROBE_MODES:
        p = data["probes"][mode]
        p["prompt"] = PROMPT
        for request in p["requests"]:
            request["input"][-1] = message("user", PROMPT)
        p.update(
            provider_port=12345,
            command=_probe_command(runtime["executable_path"], Path("/tmp/synthetic"), 12345, mode),
            unknown_config_error=False,
            event_bytes=0,
            stderr_bytes=0,
            final_bytes=0,
        )
        streams = root / mode / "streams"
        streams.mkdir(parents=True)
        (streams / "stdin.txt").write_text(PROMPT)
        events, stderr = b"", b""
        if mode.endswith("limit"):
            p.update(exit_code=None, error="ValueError: byte limit exceeded", final=None)
            if mode == "event_limit":
                events = b"x" * 65
            if mode == "stderr_limit":
                stderr = b"x" * 17
            if mode == "final_limit":
                p["final"] = {"ok": "x" * 1100}
        if mode == "invalid_config":
            stderr = b"unknown qualification_canary_unsupported"
            p.update(exit_code=1, error=None, final=None, unknown_config_error=True)
        if mode in {"stderr_limit", "invalid_config"}:
            p.update(requests=[], authentication=[])
        (streams / "events.jsonl").write_bytes(events)
        (streams / "stderr.txt").write_bytes(stderr)
        p.update(event_bytes=len(events), stderr_bytes=len(stderr))
        if p["final"] is not None:
            write_json(root / mode / "final.json", p["final"])
            p["final_bytes"] = (root / mode / "final.json").stat().st_size
        for index, request in enumerate(p["requests"]):
            write_json(root / mode / "requests" / f"{index:03d}.json", request)
            write_json(
                root / mode / "requests" / f"{index:03d}.headers.json",
                {"authorization": "Bearer synthetic-only"},
            )
    write_json(root / "evidence.json", data)
    checks, _ = audit_evidence(data)
    assert all(checks.values())
    receipt = {
        "schema_version": "medical_codex_qualification_v2",
        "assessment_only": False,
        "qualified": True,
        "all_checks_passed": True,
        "checks": checks,
        "policy": execution_policy(),
        "runtime": runtime,
        "artifacts": {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        },
    }
    receipt["receipt_sha256"] = content_hash(receipt)
    path = root / "qualification.json"
    write_json(path, receipt)
    return path, receipt, data, runtime


@pytest.mark.parametrize(
    "change",
    [
        "assessment",
        "receipt_hash",
        "artifact",
        "omit_artifact",
        "raw_request",
        "raw_header",
        "configuration",
        "relabeled_checks",
        "raw_sandbox",
    ],
)
def test_version_two_receipts_reaudit_raw_evidence_and_refuse_assessment(
    workspace, monkeypatch, change
):
    import hashlib

    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import validate_qualification
    from research_project.medical_review.records import content_hash

    repo = workspace[0]
    path, receipt, data, runtime = retained_receipt(repo)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity", lambda *_: runtime
    )
    assert validate_qualification(repo, path)["qualified"] is True
    if change == "assessment":
        receipt["assessment_only"] = True
    elif change == "receipt_hash":
        receipt["receipt_sha256"] = "tampered"
    elif change == "artifact":
        (path.parent / "success/streams/events.jsonl").write_text("tampered")
    elif change == "omit_artifact":
        del receipt["artifacts"]["success/requests/000.json"]
    elif change == "raw_request":
        write_json(path.parent / "error/requests/000.json", {"tools": [{"name": "exec"}]})
    elif change == "raw_header":
        write_json(
            path.parent / "error/requests/000.headers.json", {"Authorization": "Bearer real-key"}
        )
    elif change == "configuration":
        data["probes"]["success"]["command"].append("--enable-shell")
    elif change == "relabeled_checks":
        req = data["probes"]["context"]["requests"][0]
        req["input"].append(
            message("developer", "<skills_instructions>private</skills_instructions>")
        )
        write_json(path.parent / "context/requests/000.json", req)
    else:
        data["sandbox"]["results"]["outside_denied"]["stderr"] = base64.b64encode(
            b"unknown configuration field"
        ).decode()
    if change in {"configuration", "relabeled_checks", "raw_sandbox"}:
        write_json(path.parent / "evidence.json", data)
    if change not in {"omit_artifact", "artifact"}:
        for name in receipt["artifacts"]:
            receipt["artifacts"][name] = hashlib.sha256(
                (path.parent / name).read_bytes()
            ).hexdigest()
    if change != "receipt_hash":
        receipt["receipt_sha256"] = content_hash(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        )
    write_json(path, receipt)
    with pytest.raises(ValueError, match="qualification"):
        validate_qualification(repo, path)


def test_passing_candidate_receipt_cannot_prepare_a_packet(workspace, monkeypatch):
    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_packet import prepare_packet
    from research_project.medical_review.records import content_hash

    repo, bundle, *_ = workspace
    path, receipt, _, runtime = retained_receipt(repo)
    receipt["assessment_only"] = True
    receipt["receipt_sha256"] = content_hash(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    write_json(path, receipt)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity", lambda *_: runtime
    )
    with pytest.raises(ValueError, match="assessment-only"):
        prepare_packet(repo, bundle, qualification=path)
