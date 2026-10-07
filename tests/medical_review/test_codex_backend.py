from __future__ import annotations

import os
import sys

import pytest

from research_project.medical_review.codex_backend import (
    MODEL,
    execution_policy,
    validate_request,
)
from research_project.medical_review.codex_process import bounded_process, session_lock


def test_policy_pins_model_reasoning_and_zero_retries():
    policy = execution_policy()
    assert policy["model"] == MODEL == "gpt-6-astra"
    assert policy["reasoning"] == "max"
    assert policy["max_duration_seconds"] == 600
    assert policy["request_max_retries"] == policy["stream_max_retries"] == 0
    assert policy["max_sessions"] == 1


@pytest.mark.parametrize(
    "tools", [[{"type": "web_search"}], [{"type": "function", "name": "exec"}]]
)
def test_request_audit_rejects_any_tool(tools):
    with pytest.raises(ValueError, match="tools"):
        validate_request({"model": MODEL, "reasoning": {"effort": "max"}, "tools": tools})


def test_request_audit_requires_requested_model_and_reasoning():
    with pytest.raises(ValueError, match="model|reasoning"):
        validate_request({"model": "different", "tools": [], "reasoning": {"effort": "max"}})


def test_request_audit_checks_nested_additional_tools():
    with pytest.raises(ValueError, match="tools"):
        validate_request(
            {
                "model": MODEL,
                "reasoning": {"effort": "max"},
                "input": [{"type": "additional_tools", "tools": [{"name": "apply_patch"}]}],
            }
        )


def process(tmp_path, script, **limits):
    return bounded_process(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        prompt=b"synthetic",
        output=tmp_path / "output",
        final=tmp_path / "final",
        duration=limits.get("duration", 5),
        event_bytes=limits.get("event_bytes", 1024),
        stderr_bytes=1024,
        final_bytes=1024,
    )


def test_process_timeout_preserves_partial_output_and_kills_children(tmp_path):
    with pytest.raises(TimeoutError, match="deadline"):
        process(
            tmp_path,
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c',"
            "\"import time,pathlib; time.sleep(1); pathlib.Path('escaped').touch()\"]); "
            "print('partial',flush=True);time.sleep(20)",
            duration=0.1,
        )
    assert (tmp_path / "output/events.jsonl").read_text() == "partial\n"
    # Child termination is observable: its delayed marker must never appear.
    import time

    time.sleep(1.1)
    assert not (tmp_path / "escaped").exists()


def test_stream_limit_preserves_received_overflow_and_fails(tmp_path):
    with pytest.raises(ValueError, match="stream byte limit"):
        process(tmp_path, "print('x'*2000,flush=True)", event_bytes=100)
    assert (tmp_path / "output/events.jsonl").stat().st_size > 100


def test_session_lock_rejects_concurrent_attempt_and_releases(tmp_path):
    lock = tmp_path / "lock"
    with session_lock(lock):
        with pytest.raises(ValueError, match="already active"):
            with session_lock(lock):
                pass
    with session_lock(lock):
        pass


def test_failed_qualification_never_becomes_valid_by_relabeling_checks(workspace, monkeypatch):
    import hashlib

    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import CHECKS, validate_qualification
    from research_project.medical_review.records import content_hash

    repo, *_ = workspace
    root = repo / "data/private/medical_reviews/runtime_qualifications/forged"
    catalogue = write_json(root / "catalogue.json", {"models": []})
    probes = write_json(
        root / "probes.json",
        {
            "success": {
                "requests": [
                    {
                        "model": MODEL,
                        "reasoning": {"effort": "max"},
                        "input": [{"type": "additional_tools", "tools": [{"name": "apply_patch"}]}],
                    }
                ]
            }
        },
    )
    runtime = {"synthetic": True}
    receipt = {
        "schema_version": "medical_codex_qualification_v1",
        "qualified": True,
        "checks": {key: True for key in CHECKS},
        "policy": execution_policy(),
        "runtime": runtime,
        "artifacts": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [catalogue, probes]
        },
    }
    receipt["receipt_sha256"] = content_hash(receipt)
    path = write_json(root / "qualification.json", receipt)
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity", lambda *_: runtime
    )
    with pytest.raises(ValueError, match="tools"):
        validate_qualification(repo, path)


def test_unsupported_runtime_produces_failed_offline_receipt(workspace, monkeypatch):
    from support.medical_review_fixtures import write_json

    from research_project.medical_review.codex_qualification import qualify_codex
    from research_project.medical_review.records import read_json

    def unsupported(*_):
        raise ValueError("Unsupported runtime")

    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.runtime_identity", unsupported
    )
    path = qualify_codex(workspace[0], catalogue=write_json(workspace[0] / "catalogue.json", {}))
    receipt = read_json(path)
    assert receipt["qualified"] is False and not any(receipt["checks"].values())
    assert "Unsupported runtime" in receipt["errors"][0]


def test_controller_crash_kills_orphan_and_releases_lock_after_cleanup(tmp_path):
    import subprocess
    import time
    from pathlib import Path

    from research_project.medical_review import codex_process

    lock = tmp_path / "session.lock"
    cleanup = tmp_path / "medical-codex-session-test"
    cleanup.mkdir()
    (cleanup / "credentials").write_text("SYNTHETIC_ONLY")
    worker = (
        "import time,pathlib; print('ready',flush=True);time.sleep(1);"
        "pathlib.Path('escaped-after-crash').touch();time.sleep(10)"
    )
    script = (
        "import sys,os;from pathlib import Path;"
        "from research_project.medical_review.codex_process import bounded_process,session_lock\n"
        "p=Path(sys.argv[1])\n"
        "with session_lock(p/'session.lock') as fd:\n"
        " bounded_process([sys.executable,'-c',sys.argv[2]],cwd=p,env={'PATH':os.defpath},"
        "prompt=b'synthetic',output=p/'streams',final=p/'final',duration=10,"
        "event_bytes=8192,stderr_bytes=8192,final_bytes=1024,lock_fd=fd,"
        "cleanup_directory=p/'medical-codex-session-test')\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path), worker],
        env={"PATH": os.defpath, "PYTHONPATH": str(Path(codex_process.__file__).parents[2])},
    )
    try:
        deadline = time.monotonic() + 5
        events = tmp_path / "streams/events.jsonl"
        while not events.exists() or "ready" not in events.read_text():
            assert parent.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.01)
        parent.kill()
        parent.wait(timeout=5)
        while cleanup.exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        with session_lock(lock):
            pass
        time.sleep(1.1)
        assert not (tmp_path / "escaped-after-crash").exists()
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
