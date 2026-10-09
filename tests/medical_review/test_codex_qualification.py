from __future__ import annotations

import base64
import copy
import json

import pytest

from research_project.medical_review.codex_audit import (
    NATIVE_PROBES,
    PROBE_SCHEMA,
    TOOL_DENIAL_MARKER,
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


def retained_receipt(repo, *, assessment=False):
    """Complete synthetic observations for testing receipt validation, never CLI evidence."""
    import hashlib
    from pathlib import Path

    from research_project.medical_review.codex_audit import PROBE_MODES, PROMPT
    from research_project.medical_review.codex_backend import ADOPTED_RUNTIME, execution_policy
    from research_project.medical_review.codex_qualification import (
        _probe_command,
        _provider_response,
    )
    from research_project.medical_review.records import content_hash, write_json

    data = evidence()
    for mode in ("event_limit", "final_limit", "stderr_limit", "invalid_config", *NATIVE_PROBES):
        data["probes"][mode] = probe()
    runtime = {
        "executable_path": "/tmp/synthetic/bin/codex",
        "resource_shell_sha256": None,
        "adopted_runtime": None if assessment else ADOPTED_RUNTIME.copy(),
    }
    root = repo / "data/private/medical_reviews/runtime_qualifications/synthetic-v3"
    write_json(root / "catalogue.json", {"synthetic": True})
    if not assessment:
        write_json(
            root / "source-build/build-manifest.json",
            {
                "source": {"commit": ADOPTED_RUNTIME["source_commit"]},
                "target": ADOPTED_RUNTIME["target"],
                "executable_sha256": ADOPTED_RUNTIME["executable_sha256"],
                "artifacts": {"native_patch": {"sha256": ADOPTED_RUNTIME["native_patch_sha256"]}},
            },
        )
    for mode in PROBE_MODES:
        p = data["probes"][mode]
        p["prompt"] = PROMPT
        for request in p["requests"]:
            request["input"][-1] = message("user", PROMPT)
        p.update(
            provider_port=12345,
            command=_probe_command(
                runtime["executable_path"],
                Path("/tmp/synthetic"),
                12345,
                mode,
                disable_tools=not assessment,
            ),
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
        if mode in NATIVE_PROBES:
            stderr = TOOL_DENIAL_MARKER
            p.update(exit_code=1, error=None, final=None, tool_denial_error=True)
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
            status, content_type, body = _provider_response(mode, index)
            response_root = root / mode / "responses"
            response_root.mkdir(exist_ok=True)
            (response_root / f"{index:03d}.body").write_bytes(body)
            write_json(
                response_root / f"{index:03d}.json",
                {"status": status, "content_type": content_type},
            )
            write_json(root / mode / "requests" / f"{index:03d}.json", request)
            write_json(
                root / mode / "requests" / f"{index:03d}.headers.json",
                {"authorization": "Bearer synthetic-only"},
            )
    write_json(root / "evidence.json", data)
    checks, _ = audit_evidence(data)
    assert all(checks.values())
    receipt = {
        "schema_version": "medical_codex_qualification_v4",
        "runtime_adoption": None if assessment else ADOPTED_RUNTIME.copy(),
        "source_build_manifest": None if assessment else "source-build/build-manifest.json",
        "assessment_only": assessment,
        "qualified": not assessment,
        "all_checks_passed": True,
        "errors": [],
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
        "legacy",
        "legacy_v3",
        "errors",
        "adoption",
        "response",
        "dispatch_marker",
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
def test_version_four_receipts_reaudit_raw_evidence_and_refuse_assessment(
    workspace, monkeypatch, change
):
    import hashlib

    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import validate_qualification
    from research_project.medical_review.records import content_hash

    repo = workspace[0]
    path, receipt, data, runtime = retained_receipt(repo)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity",
        lambda *_, **__: runtime,
    )
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.validate_build_manifest",
        lambda path, _: json.loads(path.read_text()),
    )
    assert validate_qualification(repo, path)["qualified"] is True
    if change == "legacy":
        receipt["schema_version"] = "medical_codex_qualification_v2"
    elif change == "legacy_v3":
        receipt["schema_version"] = "medical_codex_qualification_v3"
    elif change == "errors":
        receipt["errors"] = ["Configuration failure"]
    elif change == "adoption":
        receipt["runtime_adoption"] = None
    elif change == "response":
        (path.parent / "tool_direct/responses/000.body").write_bytes(b"no call issued")
    elif change == "dispatch_marker":
        (path.parent / "tool_direct/streams/stderr.txt").write_bytes(b"configuration error")
        data["probes"]["tool_direct"]["stderr_bytes"] = len(b"configuration error")
        write_json(path.parent / "evidence.json", data)
    elif change == "assessment":
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
    path, receipt, _, runtime = retained_receipt(repo, assessment=True)
    receipt["assessment_only"] = True
    receipt["receipt_sha256"] = content_hash(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    write_json(path, receipt)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity",
        lambda *_, **__: runtime,
    )
    with pytest.raises(ValueError, match="assessment-only"):
        prepare_packet(repo, bundle, qualification=path)


@pytest.mark.parametrize(
    "change", ["missing", "configuration", "retry", "timeout", "wrong_error", "success"]
)
def test_unsolicited_tool_calls_require_one_request_and_fatal_policy_rejection(change):
    from research_project.medical_review.codex_audit import NATIVE_PROBES

    data = evidence()
    for mode in NATIVE_PROBES:
        data["probes"][mode] = probe()
        data["probes"][mode].update(exit_code=1, final=None, tool_denial_error=True)
    checks, _ = audit_evidence(data)
    assert checks["native_calls_rejected"] is True
    p = data["probes"][NATIVE_PROBES[0]]
    if change == "missing":
        p["requests"] = []
    elif change == "configuration":
        p.update(requests=[], unknown_config_error=True)
    elif change == "retry":
        p["requests"] *= 2
    elif change == "timeout":
        p.update(exit_code=None, error="TimeoutError: deadline")
    elif change == "wrong_error":
        p["tool_denial_error"] = False
    else:
        p["exit_code"] = 0
    checks, _ = audit_evidence(data)
    assert checks["native_calls_rejected"] is False


def test_build_manifest_requires_explicit_assessment_executable(workspace):
    from research_project.medical_review.codex_qualification import qualify_codex

    with pytest.raises(ValueError, match="assessment-only"):
        qualify_codex(
            workspace[0],
            catalogue=workspace[0] / "catalogue",
            probe_build_manifest=workspace[0] / "manifest",
        )


def test_invalid_build_provenance_stops_before_any_sandbox_or_provider(workspace, monkeypatch):
    from pathlib import Path

    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import qualify_codex
    from research_project.medical_review.records import read_json

    repo = workspace[0]
    root = repo / "data/private/medical_reviews/runtime_candidates/invalid-build"
    root.mkdir(parents=True)
    binary = root / "codex"
    binary.write_text("synthetic")
    manifest = write_json(root / "build-manifest.json", {"qualified": True})
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity",
        lambda *_, **__: {"executable_path": str(binary)},
    )

    def forbidden(*_, **__):
        pytest.fail("Invalid provenance reached runtime probes")

    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification._sandbox_checks", forbidden
    )
    receipt = read_json(
        qualify_codex(
            repo, catalogue=Path("unused"), probe_executable=binary, probe_build_manifest=manifest
        )
    )
    assert receipt["qualified"] is False and receipt["assessment_only"] is True
    assert not receipt["all_checks_passed"]
    assert "build" in receipt["errors"][0]


def test_validated_candidate_remains_ineligible_for_preparation(workspace, monkeypatch):
    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_packet import prepare_packet
    from research_project.medical_review.codex_qualification import validate_assessment
    from research_project.medical_review.records import content_hash

    repo, bundle, *_ = workspace
    path, receipt, _, runtime = retained_receipt(repo, assessment=True)
    receipt.update(assessment_only=True, qualified=False)
    receipt["receipt_sha256"] = content_hash(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    write_json(path, receipt)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity",
        lambda *_, **__: runtime,
    )
    assert validate_assessment(repo, path)["qualified"] is False
    with pytest.raises(ValueError, match="assessment-only"):
        prepare_packet(repo, bundle, qualification=path)


def test_post_final_probe_uses_the_runtime_final_answer_phase():
    import json

    from research_project.medical_review.codex_qualification import _native_response

    events = [
        json.loads(row[6:])
        for row in _native_response("tool_after_final").decode().splitlines()
        if row.startswith("data: ")
    ]
    items = events[-1]["response"]["output"]
    assert items[0]["type"] == "message" and items[0]["phase"] == "final_answer"
    assert items[1]["type"] == "custom_tool_call" and items[1]["namespace"] == "functions"


def test_assessment_flags_cannot_be_promoted_to_operational_receipt(workspace):
    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import validate_qualification
    from research_project.medical_review.records import content_hash

    repo = workspace[0]
    path, receipt, _, _ = retained_receipt(repo, assessment=True)
    receipt.update(assessment_only=False, qualified=True)
    receipt["receipt_sha256"] = content_hash(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    write_json(path, receipt)
    with pytest.raises(ValueError, match="qualification"):
        validate_qualification(repo, path)
