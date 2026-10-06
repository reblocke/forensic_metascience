from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_pytest_junit.py"


def test_required_lane_junit_gate_rejects_empty_and_skipped_suites(tmp_path: Path) -> None:
    for name, receipt in (
        ("empty", '<testsuites><testsuite tests="0" /></testsuites>'),
        ("skipped", '<testsuites><testsuite tests="2" skipped="1" /></testsuites>'),
    ):
        path = tmp_path / f"{name}.xml"
        path.write_text(receipt, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(path)], capture_output=True, text=True
        )
        assert result.returncode != 0
        assert "Incomplete required lane" in result.stderr


def test_required_lane_junit_gate_accepts_complete_suite(tmp_path: Path) -> None:
    path = tmp_path / "passed.xml"
    path.write_text(
        '<testsuites><testsuite tests="3" skipped="0" failures="0" errors="0" /></testsuites>',
        encoding="utf-8",
    )
    artifact = tmp_path / "accepted-report.pdf"
    artifact.write_bytes(b"synthetic artifact")
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(path), str(artifact)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "3 tests, zero skipped/failed" in result.stdout


def test_required_lane_junit_gate_rejects_missing_acceptance_artifact(tmp_path: Path) -> None:
    path = tmp_path / "passed.xml"
    path.write_text(
        '<testsuites><testsuite tests="1" skipped="0" failures="0" errors="0" /></testsuites>',
        encoding="utf-8",
    )
    missing_artifact = tmp_path / "missing-report.pdf"
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(path), str(missing_artifact)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "missing_artifacts" in result.stderr


def test_pinned_source_download_falls_back_only_to_configured_identical_bytes(
    tmp_path, monkeypatch
):
    import hashlib
    import io
    import urllib.error
    import urllib.request

    from research_project.method_setup import download_verified_source

    raw = b"pinned synthetic archive"
    package = {
        "name": "synthetic",
        "version": "1",
        "source_url": "https://primary.invalid/a",
        "fallback_source_urls": ["https://mirror.invalid/a"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    requests = []

    def fetch(url, timeout):
        requests.append(url)
        assert timeout == 30
        if url == package["source_url"]:
            raise urllib.error.HTTPError(url, 429, "Too many requests", {}, None)
        return io.BytesIO(raw)

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    destination = tmp_path / "source.tar.gz"
    receipt = download_verified_source(package, destination)
    assert destination.read_bytes() == raw
    assert receipt["source_url"] == package["fallback_source_urls"][0]
    assert requests == [package["source_url"], *package["fallback_source_urls"]]


def test_pinned_source_hash_mismatch_never_triggers_fallback(tmp_path, monkeypatch):
    import io
    import urllib.request

    import pytest

    from research_project.method_setup import download_verified_source

    requests = []

    def fetch(url, timeout):
        requests.append(url)
        return io.BytesIO(b"wrong archive")

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    package = {
        "name": "synthetic",
        "version": "1",
        "source_url": "https://primary.invalid/a",
        "fallback_source_urls": ["https://mirror.invalid/a"],
        "sha256": "0" * 64,
    }
    destination = tmp_path / "source.tar.gz"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        download_verified_source(package, destination)
    assert requests == [package["source_url"]]
    assert not destination.exists()


def test_pinned_source_exhaustion_and_existing_destination_fail_closed(tmp_path, monkeypatch):
    import urllib.error
    import urllib.request

    import pytest

    from research_project.method_setup import download_verified_source

    def fetch(url, timeout):
        raise urllib.error.HTTPError(url, 429, "Too many requests", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    package = {
        "name": "synthetic",
        "version": "1",
        "source_url": "https://primary.invalid/a",
        "fallback_source_urls": ["https://mirror.invalid/a"],
        "sha256": "0" * 64,
    }
    destination = tmp_path / "source.tar.gz"
    with pytest.raises(urllib.error.HTTPError):
        download_verified_source(package, destination)
    assert not destination.exists()
    destination.write_bytes(b"preserved archive")
    with pytest.raises(FileExistsError):
        download_verified_source(package, destination)
    assert destination.read_bytes() == b"preserved archive"
