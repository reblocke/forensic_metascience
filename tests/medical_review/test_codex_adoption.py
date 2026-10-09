from __future__ import annotations

import hashlib
import json
import subprocess

import pytest

from research_project.medical_review import codex_backend, codex_qualification, codex_runner


def test_production_command_requires_tool_ceiling(tmp_path):
    args = ("codex", tmp_path, tmp_path / "instructions", tmp_path / "schema", tmp_path / "final")
    assert "tools.enabled=false" in codex_backend.codex_command(*args)
    with pytest.raises(ValueError, match="assessment"):
        codex_backend.codex_command(*args, disable_tools=False)
    control = codex_backend.codex_command(
        *args, provider_url="http://127.0.0.1:12345/v1", disable_tools=False
    )
    assert "tools.enabled=false" not in control


def test_adoption_pins_exact_build_and_policy():
    policy = codex_backend.execution_policy()
    assert policy["schema_version"] == "medical_codex_policy_v3"
    assert policy["adopted_runtime"]["runtime_id"] == "codex-cli-0.161.0-medical-no-tools-v1"
    assert policy["adopted_runtime"]["executable_sha256"] == (
        "8229baba8ad7387cbf2636b0116c8abd6d94cf87f503b327c78abc47b44c619a"
    )


@pytest.mark.parametrize("url", ["https://example.com/v1", "http://127.0.0.1:12345@example.com/v1"])
def test_default_tools_cannot_use_a_nonloopback_provider(tmp_path, url):
    with pytest.raises(ValueError, match="assessment"):
        codex_backend.codex_command(
            "codex",
            tmp_path,
            tmp_path / "instructions",
            tmp_path / "schema",
            tmp_path / "final",
            provider_url=url,
            disable_tools=False,
        )


@pytest.mark.parametrize("change", ["binary", "os", "architecture"])
def test_wrong_runtime_fails_before_executable_starts(tmp_path, monkeypatch, change):
    binary = tmp_path / "codex"
    binary.write_bytes(b"synthetic same-version executable")
    monkeypatch.setattr(codex_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(codex_backend.platform, "machine", lambda: "arm64")
    if change != "binary":
        monkeypatch.setitem(
            codex_backend.ADOPTED_RUNTIME,
            "executable_sha256",
            hashlib.sha256(binary.read_bytes()).hexdigest(),
        )
    if change == "os":
        monkeypatch.setattr(codex_backend.platform, "system", lambda: "Linux")
    if change == "architecture":
        monkeypatch.setattr(codex_backend.platform, "machine", lambda: "x86_64")

    def forbidden(*_, **__):
        pytest.fail("An unsupported executable started")

    monkeypatch.setattr(codex_backend.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="adopted"):
        codex_backend.runtime_identity(tmp_path / "catalogue", runtime_executable=binary)


@pytest.mark.parametrize("change", ["missing_manifest", "missing_executable", "mixed_modes"])
def test_operational_selection_requires_exclusive_pair(workspace, change):
    options = {"runtime_executable": workspace[0] / "codex"}
    if change == "missing_executable":
        options = {"runtime_build_manifest": workspace[0] / "manifest"}
    if change == "mixed_modes":
        options.update(
            runtime_build_manifest=workspace[0] / "manifest",
            probe_executable=workspace[0] / "other",
        )
    with pytest.raises(ValueError, match="together|exclusive"):
        codex_qualification.qualify_codex(workspace[0], catalogue=workspace[0] / "cat", **options)


def test_wrong_adopted_provenance_cannot_start_probes(workspace, monkeypatch):
    repo = workspace[0]
    root = repo / "data/private/medical_reviews/runtime_candidates/synthetic"
    root.mkdir(parents=True)
    binary, manifest = root / "codex", root / "manifest"
    binary.write_text("synthetic")
    manifest.write_text("{}")
    monkeypatch.setattr(
        codex_qualification, "runtime_identity", lambda *_, **__: {"executable_path": str(binary)}
    )
    monkeypatch.setattr(codex_qualification, "validate_build_manifest", lambda *_: {})

    def forbidden(*_, **__):
        pytest.fail("Unadopted provenance started probes")

    monkeypatch.setattr(codex_qualification, "_sandbox_checks", forbidden)
    receipt = codex_qualification.qualify_codex(
        repo, catalogue=root / "cat", runtime_executable=binary, runtime_build_manifest=manifest
    )
    result = json.loads(receipt.read_text())
    assert result["assessment_only"] is False and result["qualified"] is False
    assert "adopted" in result["errors"][0]


def test_launcher_uses_receipt_executable_for_login_and_generation(tmp_path, monkeypatch):
    home = tmp_path / "operator"
    auth = home / ".codex/auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text(json.dumps({"auth_mode": "chatgpt", "OPENAI_API_KEY": None, "tokens": {}}))
    monkeypatch.setattr(codex_runner.Path, "home", lambda: home)

    def forbidden(*_, **__):
        pytest.fail("Launch rediscovered PATH")

    monkeypatch.setattr(codex_runner.shutil, "which", forbidden)
    calls = []

    def login(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT", "")

    def generate(command, **kwargs):
        calls.append(command)
        assert "tools.enabled=false" in command
        return 0

    monkeypatch.setattr(codex_runner.subprocess, "run", login)
    monkeypatch.setattr(codex_runner, "bounded_process", generate)
    catalogue = tmp_path / "catalogue"
    catalogue.write_text("{}")
    codex_runner._launch(
        b"synthetic",
        catalogue,
        tmp_path / "generated",
        {},
        {"max_duration_seconds": 600},
        0,
        executable="/synthetic/pinned/codex",
    )
    assert len(calls) == 2
    assert all(command[0] == "/synthetic/pinned/codex" for command in calls)


@pytest.mark.parametrize("change_at", [2, 3])
def test_runtime_change_preserves_failure_without_import_or_retry(
    workspace, monkeypatch, change_at
):
    from support.codex_fixtures import prepared_fixture

    from research_project.medical_review.codex_process import session_lock
    from research_project.medical_review.runner import run_review

    repo = workspace[0]
    prepared, qpath, authpath, envelope, _, _ = prepared_fixture(workspace, monkeypatch)
    qualification = json.loads(qpath.read_text())
    validations, launches = [], []

    def validate(*_):
        validations.append(True)
        if len(validations) == change_at:
            raise ValueError("Runtime changed; requalification required.")
        return qualification

    def generate(packet, catalogue, generated, schema, limits, lock_fd, *, executable):
        launches.append(executable)
        (generated / "raw").mkdir()
        (generated / "raw/generation.json").write_text(json.dumps(envelope))
        (generated / "streams").mkdir()
        (generated / "streams/events.jsonl").write_text('{"type":"turn.completed"}\n')

    monkeypatch.setattr(codex_runner, "validate_qualification", validate)
    monkeypatch.setattr(codex_runner, "_launch", generate)
    run = run_review(
        repo,
        prepared["bundle"],
        backend="codex_cli",
        offline=False,
        allow_llm=True,
        provider="openai",
        model="gpt-6-astra",
        qualification_path=qpath,
        authorization_path=authpath,
    )
    result = json.loads((run / "generated/medical_review/attempt_result.json").read_text())
    assert result["status"] == "failed" and result["import_run_reference"] is None
    assert result["coverage_available"] is False
    assert len(launches) == change_at - 2
    if launches:
        assert (run / "generated/medical_review/raw/generation.json").is_file()
    with session_lock(repo / "data/private/medical_reviews/codex_session.lock"):
        pass
