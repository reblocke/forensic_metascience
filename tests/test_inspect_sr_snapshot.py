from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from research_project.inspect_sr.records import create_assessment, evidence_id, source_version_id
from research_project.inspect_sr.snapshot import create_source_snapshot, validate_source_snapshot


def test_snapshot_binds_current_source_bytes_and_evidence(tmp_path: Path) -> None:
    source = tmp_path / "report.txt"
    source.write_text("0.50", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    version_id = source_version_id("report-1", digest)
    version = {
        "schema_version": "inspect_sr_source_version_v2",
        "record_type": "source_version",
        "source_id": "report-1",
        "source_version_id": version_id,
        "source_name": source.name,
        "source_path": str(source),
        "content_sha256": digest,
    }
    evidence = {
        "schema_version": "inspect_sr_evidence_v2",
        "record_type": "source_evidence",
        "source_id": "report-1",
        "source_version_id": version_id,
        "content_sha256": digest,
        "locator": "page=1",
        "raw_value": "0.50",
        "extraction_method": "manual",
        "extraction_version": "1",
    }
    evidence["evidence_id"] = evidence_id(version_id, "page=1", "0.50", "manual", "1")
    assessment = create_assessment("trial-1", "1.1.2", "a" * 64)
    snapshot = create_source_snapshot(assessment, [version], [evidence])
    validate_source_snapshot(snapshot, assessment, [version], [evidence])
    source.write_text("0.51", encoding="utf-8")
    with pytest.raises(ValueError, match="source bytes"):
        validate_source_snapshot(snapshot, assessment, [version], [evidence])
    source.write_text("0.50", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence identity"):
        validate_source_snapshot(
            snapshot, assessment, [version], [{**evidence, "raw_value": "0.51"}]
        )
    with pytest.raises(ValueError, match="snapshot"):
        validate_source_snapshot(
            snapshot, assessment, [{**version, "source_name": "substituted.txt"}], [evidence]
        )
    with pytest.raises(ValueError, match="Assessment identity"):
        validate_source_snapshot(
            snapshot, {**assessment, "guidance_sha256": "b" * 64}, [version], [evidence]
        )
    with pytest.raises(ValueError, match="snapshot"):
        validate_source_snapshot(snapshot, assessment, [version], [])
