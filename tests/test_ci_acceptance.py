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
