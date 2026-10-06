"""Read source bundles without changing sources or claiming extraction fidelity."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from research_project.inspect_sr.records import evidence_id, source_version_id
from research_project.medical_review.records import (
    BUNDLE_SCHEMA,
    PRIVATE_SOURCES,
    content_hash,
    private_path,
    read_json,
)

AVAILABILITY = {
    "supplied",
    "referenced_but_missing",
    "inaccessible",
    "excluded_by_permission",
    "not_applicable",
}
ROLES = {
    "manuscript",
    "supplement",
    "protocol",
    "sap",
    "registry_snapshot",
    "registry_history",
    "correction",
    "analysis_output",
}


def load_bundle(repo_root: Path, path: Path) -> tuple[dict[str, Any], str]:
    bundle_path = private_path(repo_root, path, PRIVATE_SOURCES)
    bundle = read_json(bundle_path)
    if not isinstance(bundle, dict) or bundle.get("schema_version") != BUNDLE_SCHEMA:
        raise ValueError("Unsupported medical source bundle schema.")
    study = bundle.get("study_id", "")
    if not isinstance(study, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", study):
        raise ValueError("Bundle study_id must be a valid local study identity.")
    scope = PRIVATE_SOURCES / study
    private_path(repo_root, bundle_path, scope)
    if type(bundle.get("revision")) is not int or bundle["revision"] < 1:
        raise ValueError("Bundle revision must be a positive integer.")
    studies, reports, documents, evidence = [
        bundle.get(key) for key in ("studies", "reports", "documents", "evidence")
    ]
    if any(
        not isinstance(items, list) or any(not isinstance(x, dict) for x in items)
        for items in (studies, reports, documents, evidence)
    ):
        raise ValueError("Bundle studies, reports, documents and evidence must be record lists.")
    _unique(studies, "study_id")
    _unique(reports, "report_id")
    _unique(documents, "source_id")
    _unique(evidence, "evidence_id")
    study_ids = {row["study_id"] for row in studies}
    if study not in study_ids:
        raise ValueError("Bundle primary study must be declared.")
    report_ids = {row["report_id"] for row in reports}
    for report in reports:
        mapping = report.get("study_ids")
        if not isinstance(mapping, list) or not mapping or not set(mapping) <= study_ids:
            raise ValueError("Report relationships require known, explicit study identities.")
    versions = {}
    for doc in documents:
        if doc.get("role") not in ROLES or doc.get("availability") not in AVAILABILITY:
            raise ValueError("Invalid source role or availability.")
        if not set(doc.get("report_ids", [])) <= report_ids or not doc.get("report_ids"):
            raise ValueError("Documents require known report relationships.")
        if doc["availability"] != "supplied":
            if doc.get("path") is not None:
                raise ValueError("Unavailable sources cannot be represented by file paths.")
            continue
        if doc.get("permissions", {}).get("local_processing") is not True:
            raise ValueError("Source has no explicit local-processing permission.")
        _verify_file(repo_root, doc.get("path"), doc.get("sha256"), scope)
        version = source_version_id(doc["source_id"], doc["sha256"])
        if doc.get("source_version_id") != version:
            raise ValueError("Source version identity does not match the exact source hash.")
        versions[version] = doc
    for ev in evidence:
        if ev.get("source_version_id") not in versions:
            raise ValueError("Evidence requires a supplied, verified source version.")
        parser = ev.get("parser", {})
        expected = evidence_id(
            ev["source_version_id"],
            ev.get("locator", ""),
            ev.get("raw_value", ""),
            parser.get("id", ""),
            parser.get("version", ""),
        )
        if ev["evidence_id"] != expected:
            raise ValueError("Evidence identity does not match locator, raw value and parser.")
        parsed = _verify_file(repo_root, ev.get("parsed_path"), ev.get("parsed_sha256"), scope)
        if ev.get("raw_value") not in parsed.read_text(encoding="utf-8"):
            raise ValueError("Evidence quote is absent from the declared parsed artifact.")
        page = ev.get("page_index")
        if page is not None and (type(page) is not int or page < 0):
            raise ValueError("Page index must be a nonnegative integer or null.")
    checks = bundle.get("planned_checks", [])
    if not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks):
        raise ValueError("Planned checks must be a list.")
    keys = set()
    for check in checks:
        key = (check.get("check_id"), check.get("study_id"), check.get("comparison_id"))
        if not key[0] or key[1] not in study_ids or key in keys:
            raise ValueError("Planned checks require unique known study/comparison scopes.")
        if check.get("applicability") not in {"applicable", "not_applicable", "unknown"}:
            raise ValueError("Planned check applicability must remain explicit.")
        if not check.get("rationale"):
            raise ValueError("Planned check scope requires a rationale.")
        keys.add(key)
    return bundle, content_hash(bundle)


def _unique(rows: list[dict[str, Any]], key: str) -> None:
    values = [row.get(key) for row in rows]
    if any(not isinstance(x, str) or not x.strip() for x in values) or len(set(values)) != len(
        values
    ):
        raise ValueError(f"Missing or duplicate bundle {key}.")


def _verify_file(repo_root: Path, value: Any, digest: Any, scope: Path) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError("Supplied artifacts require an explicit path and hash.")
    path = private_path(repo_root, Path(value), scope)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("Source or parsed artifact hash mismatch.")
    return path


def resolve_source_object(bundle: dict[str, Any], obj: dict[str, Any]) -> dict[str, Any]:
    """Resolve a declared exact anchor; this is not visual/source-semantic verification."""
    unresolved = {
        "source_object_id": obj["id"],
        "resolution": "unresolved",
        "evidence_id": None,
        "reason": "Missing, ambiguous or inexact source reference.",
    }
    matches = [
        doc
        for doc in bundle["documents"]
        if doc["availability"] == "supplied" and obj.get("path") in doc.get("upstream_paths", [])
    ]
    if len(matches) != 1 or not obj.get("text_quote"):
        return unresolved
    doc = matches[0]
    reports = [row for row in bundle["reports"] if row["report_id"] in doc["report_ids"]]
    if any(
        len(row["study_ids"]) > 1 and row.get("mapping_reviewed") is not True for row in reports
    ):
        return {**unresolved, "reason": "Unreviewed multi-study report mapping."}
    if not any(obj.get(key) is not None for key in ("page", "page_label", "section")):
        return unresolved
    anchors = [
        ev
        for ev in bundle["evidence"]
        if ev["source_version_id"] == doc["source_version_id"]
        and ev["raw_value"] == obj["text_quote"]
        and all(
            obj.get(k) is None or obj[k] == ev.get(target)
            for k, target in (
                ("page", "upstream_page"),
                ("page_label", "page_label"),
                ("section", "section"),
            )
        )
    ]
    if len(anchors) != 1:
        return unresolved
    ev = anchors[0]
    return {
        "source_object_id": obj["id"],
        "resolution": "exact",
        "evidence_id": ev["evidence_id"],
        "source_version_id": ev["source_version_id"],
        "locator": ev["locator"],
        "visual_inspected": ev.get("visual_inspected") is True,
        "input_verification": "proposed_transcription",
        "reason": None,
    }
