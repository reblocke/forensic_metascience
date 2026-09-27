#!/usr/bin/env python3
"""Fail a required CI lane when pytest selected no tests or skipped any."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: check_pytest_junit.py <junit.xml> [required-artifact ...]")
    root = ET.parse(Path(sys.argv[1])).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
    missing_artifacts = [
        name
        for name in sys.argv[2:]
        if not Path(name).is_file() or Path(name).is_symlink() or Path(name).stat().st_size == 0
    ]
    if tests == 0 or skipped or failures or errors or missing_artifacts:
        raise SystemExit(
            f"Incomplete required lane: tests={tests}, skipped={skipped}, "
            f"failures={failures}, errors={errors}, "
            f"missing_artifacts={missing_artifacts}."
        )
    print(f"Required lane complete: {tests} tests, zero skipped/failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
