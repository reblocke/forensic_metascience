from __future__ import annotations

import base64
import json
import subprocess
import time
from datetime import datetime

import pytest

from research_project.medical_review import codex_runner
from research_project.medical_review.codex_generation import validate_generation


@pytest.mark.parametrize("path_kind", ["alias", "legacy"])
@pytest.mark.parametrize("scope", ["study", "comparison"])
@pytest.mark.parametrize("allowed", [False, True])
def test_every_resolvable_citation_obeys_association_scope(workspace, path_kind, scope, allowed):
    repo, _, _, bundle, upstream = workspace
    report_a = bundle["reports"][0]["report_id"]
    bundle["studies"].append({"study_id": "second", "trial_id": None})
    bundle["reports"].append(
        {"report_id": "report-b", "study_ids": ["second" if scope == "study" else "synthetic"]}
    )
    document = bundle["documents"][0]
    document["report_ids"] = ["report-b"]
    document["upstream_paths"].append("source-0001")
    bundle["comparisons"] = [
        {"study_id": "synthetic", "comparison_id": "alpha", "report_ids": [report_a]},
        {"study_id": "synthetic", "comparison_id": "beta", "report_ids": ["report-b"]},
    ]
    study = "second" if allowed and scope == "study" else "synthetic"
    comparison = ("beta" if allowed else "alpha") if scope == "comparison" else None
    packet = {
        "sources": [{"alias": "source-0001", "report_ids": ["report-b"]}],
        "checks": [
            {"study_id": study, "comparison_id": comparison, "check_id": "trial.assignment"}
        ],
    }
    upstream["findings"][0]["source_objects"][0]["path"] = (
        "source-0001" if path_kind == "alias" else "inputs/main.txt"
    )
    envelope = {
        "schema_version": "medical_codex_generation_v1",
        "review": upstream,
        "associations": [
            {
                "finding_id": "finding-1",
                "study_id": study,
                "comparison_id": comparison,
                "check_ids": ["trial.assignment"],
            }
        ],
    }
    if allowed:
        validate_generation(repo, envelope, bundle, packet)
    else:
        with pytest.raises(ValueError, match="different study/comparison scope"):
            validate_generation(repo, envelope, bundle, packet)


def synthetic_auth(expires):
    claims = {} if expires is None else {"exp": expires}
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {
            "id_token": "synthetic-id",
            "access_token": f"e30.{encoded}.synthetic",
            "refresh_token": "OPERATOR_REFRESH_CANARY",
            "account_id": "synthetic-account",
        },
    }


def launch_fixture(tmp_path, monkeypatch, expires):
    operator = tmp_path / "operator"
    authfile = operator / ".codex/auth.json"
    authfile.parent.mkdir(parents=True)
    authfile.write_text(json.dumps(synthetic_auth(expires)))
    monkeypatch.setattr(codex_runner.Path, "home", lambda: operator)
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text("{}")
    return authfile, catalogue


def test_launcher_uses_nonrefreshing_snapshot_and_isolated_login(tmp_path, monkeypatch):
    authfile, catalogue = launch_fixture(tmp_path, monkeypatch, time.time() + 3600)
    original = authfile.read_bytes()
    homes = []

    def login(command, **kwargs):
        home = codex_runner.Path(kwargs["env"]["CODEX_HOME"])
        homes.append(home)
        snapshot = json.loads((home / "auth.json").read_text())
        assert snapshot["auth_mode"] == "chatgptAuthTokens"
        assert snapshot["tokens"]["refresh_token"] == ""
        # The adopted CLI's get_token_data requires this even in token-only mode.
        timestamp = datetime.fromisoformat(snapshot["last_refresh"])
        assert timestamp.tzinfo is not None
        assert abs(timestamp.timestamp() - time.time()) < 10
        assert "OPERATOR_REFRESH_CANARY" not in (home / "auth.json").read_text()
        return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT", "")

    def generate(command, **kwargs):
        assert codex_runner.Path(kwargs["env"]["CODEX_HOME"]) == homes[0]
        return 0

    monkeypatch.setattr(codex_runner.subprocess, "run", login)
    monkeypatch.setattr(codex_runner, "bounded_process", generate)
    codex_runner._launch(
        b"synthetic",
        catalogue,
        tmp_path / "generated",
        {},
        {"max_duration_seconds": 600},
        0,
        executable="/synthetic/codex",
    )
    assert authfile.read_bytes() == original
    assert not homes[0].exists()


@pytest.mark.parametrize("expires", [None, 0, "unknown"])
def test_unknown_or_expired_access_token_starts_no_login_or_generation(
    tmp_path, monkeypatch, expires
):
    _, catalogue = launch_fixture(tmp_path, monkeypatch, expires)

    def forbidden(*_, **__):
        pytest.fail("Invalid access-token snapshot started a CLI process")

    monkeypatch.setattr(codex_runner.subprocess, "run", forbidden)
    monkeypatch.setattr(codex_runner, "bounded_process", forbidden)
    with pytest.raises(ValueError, match="access token"):
        codex_runner._launch(
            b"synthetic",
            catalogue,
            tmp_path / "generated",
            {},
            {"max_duration_seconds": 600},
            0,
            executable="/synthetic/codex",
        )
