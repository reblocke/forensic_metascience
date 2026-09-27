"""Private, deterministic source/evidence snapshots for review currency checks."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from research_project.inspect_sr.manual_evidence import validate_manual_evidence
from research_project.inspect_sr.records import evidence_id, source_version_id, validate_assessment


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _snapshot_content(
    assessment: Mapping[str, Any],
    source_versions: Sequence[Mapping[str, Any]],
    evidence_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_assessment(assessment)
    sources = sorted(
        (dict(item) for item in source_versions), key=lambda row: row["source_version_id"]
    )
    evidence = sorted((dict(item) for item in evidence_records), key=lambda row: row["evidence_id"])
    source_ids = [item["source_version_id"] for item in sources]
    evidence_ids = [item["evidence_id"] for item in evidence]
    if (
        not sources
        or len(source_ids) != len(set(source_ids))
        or len(evidence_ids) != len(set(evidence_ids))
    ):
        raise ValueError("Source snapshot needs unique source-version and evidence identities.")
    by_source = {item["source_version_id"]: item for item in sources}
    for version in sources:
        if version.get("schema_version") != "inspect_sr_source_version_v2":
            raise ValueError("Source snapshot needs current source-version records with paths.")
        digest = version.get("content_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Source version needs a SHA-256 content hash.")
        if version.get("source_version_id") != source_version_id(version["source_id"], digest):
            raise ValueError("Source-version identity does not match its source and content.")
        source = Path(str(version.get("source_path", ""))).resolve(strict=True)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("Current source bytes differ from the prepared source version.")
    for item in evidence:
        version = by_source.get(item.get("source_version_id"))
        if version is None or item.get("source_id") != version["source_id"]:
            raise ValueError("Evidence references a missing or mismatched source version.")
        if item.get("record_type") == "manual_observation":
            validate_manual_evidence(item)
        elif item.get("record_type") == "source_evidence":
            if item.get("content_sha256") != version["content_sha256"] or item.get(
                "evidence_id"
            ) != evidence_id(
                version["source_version_id"],
                item["locator"],
                item["raw_value"],
                item["extraction_method"],
                item["extraction_version"],
            ):
                raise ValueError("Source evidence identity or source hash is invalid.")
        else:
            raise ValueError("Unsupported evidence record in source snapshot.")
    return {
        "schema_version": "inspect_sr_source_snapshot_v1",
        "record_type": "private_source_snapshot",
        "assessment_id": assessment["assessment_id"],
        "trial_id": assessment["trial_id"],
        "guidance_sha256": assessment["guidance_sha256"],
        "source_versions": sources,
        "evidence_records": evidence,
    }


def create_source_snapshot(
    assessment: Mapping[str, Any],
    source_versions: Sequence[Mapping[str, Any]],
    evidence_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    content = _snapshot_content(assessment, source_versions, evidence_records)
    return {**content, "source_snapshot_sha256": _digest(content)}


def validate_source_snapshot(
    snapshot: Mapping[str, Any],
    assessment: Mapping[str, Any],
    source_versions: Sequence[Mapping[str, Any]],
    evidence_records: Sequence[Mapping[str, Any]],
) -> None:
    expected = create_source_snapshot(assessment, source_versions, evidence_records)
    if dict(snapshot) != expected:
        raise ValueError("Source snapshot content or identity is stale or mismatched.")
