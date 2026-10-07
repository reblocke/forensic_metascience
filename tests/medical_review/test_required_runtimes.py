from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("node", "flag", "message"),
    [
        (
            "tests/test_r_integration.py::test_native_method_adapters_match_independent_synthetic_expectations",
            "FORENSICS_REQUIRE_R_INTEGRATION",
            "Rscript is required",
        ),
        (
            "tests/test_inspect_sr_reporting.py::test_inspect_sr_report_qmd_renders_html_and_pdf_in_requested_directory",
            "FORENSICS_REQUIRE_REPORT_INTEGRATION",
            "Quarto is required",
        ),
    ],
)
def test_actual_required_lane_refuses_absent_runtime_instead_of_skipping(
    tmp_path, node, flag, message
):
    root = Path(__file__).resolve().parents[2]
    empty_path = tmp_path / "empty-executable-path"
    empty_path.mkdir()
    receipt = tmp_path / "expected-runtime-refusal.xml"
    env = {
        **os.environ,
        "PATH": str(empty_path),
        "PYTHONPATH": str(root / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        flag: "1",
    }
    env.pop("FM_TEST_ARTIFACT_DIR", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            node,
            f"--junitxml={receipt}",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1 and message in result.stdout, result.stdout + result.stderr
    suite = ET.parse(receipt).getroot().find("testsuite")
    assert suite is not None
    assert {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")} == {
        "tests": 1,
        "failures": 1,
        "errors": 0,
        "skipped": 0,
    }
    gate = subprocess.run(
        [sys.executable, str(root / "scripts/check_pytest_junit.py"), str(receipt)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert gate.returncode != 0 and "Incomplete required lane" in gate.stderr
