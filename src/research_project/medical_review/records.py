"""Dependency-light identities, private boundaries, and medical record validation."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

BUNDLE_SCHEMA = "medical_review_bundle_v1"
PROPOSAL_SCHEMA = "medical_reviewer_proposal_v1"
COVERAGE_SCHEMA = "medical_review_coverage_v1"
REPORT_SCHEMA = "medical_review_report_model_v1"
UPSTREAM_COMMIT = "c591f4a498f6dc5083153811d6f678339cfb7c78"
UPSTREAM_SCHEMA_HASH = "9399e39d1be1b6584bd452086bcb6f2f80a90b34826b8467658c3c88c8742641"
PRIVATE_SOURCES = Path("data/private/medical_reviews")
PRIVATE_RUNS = Path("data/processed/forensics_runs/private_reviews")
MAX_JSON_BYTES = 20 * 1024 * 1024


def content_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def identity(prefix: str, value: Any) -> str:
    return f"{prefix}_{content_hash(value)}"


def read_json(path: Path) -> Any:
    """Reject duplicate keys, nonfinite numbers, and oversized input without repair."""
    with path.open("rb") as stream:
        return parse_json(stream.read(MAX_JSON_BYTES + 1))


def parse_json(raw: bytes) -> Any:
    """Parse one immutable snapshot; retain the same bytes as the original output."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")

    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(
            "JSON input exceeds the explicit 20 MiB limit; bounded splitting required."
        )
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)

    def finite(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Nonfinite JSON number.")
        if isinstance(item, dict):
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)

    finite(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def private_path(repo_root: Path, path: Path, boundary: Path) -> Path:
    """Require containment in a fixed, ignored private boundary, including absent paths."""
    repo = repo_root.resolve()
    candidate = path if path.is_absolute() else repo / path
    if ".." in candidate.parts:
        raise ValueError("Path traversal is not permitted in private storage.")
    resolved = candidate.resolve()
    allowed = repo / boundary
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError("Path must remain inside its private boundary; symlink escapes refused.")
    relative = resolved.relative_to(repo)
    cursor = repo
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("Private paths cannot contain symlinks.")
    cursor = candidate
    while cursor.resolve() != repo and cursor != cursor.parent:
        if cursor.is_symlink():
            raise ValueError("Private paths cannot contain symlinks.")
        cursor = cursor.parent
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", str(relative)],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("Private path must be protected by repository ignore rules.")
    tracked = subprocess.run(
        ["git", "ls-files", "--", str(relative)],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0 or tracked.stdout.strip():
        raise ValueError("Private paths must not contain tracked repository files.")
    return resolved


def validate_coverage(record: dict[str, Any]) -> None:
    if record.get("schema_version") != COVERAGE_SCHEMA:
        raise ValueError("Unsupported medical coverage schema.")
    if record.get("applicability") not in {"applicable", "not_applicable", "unknown"}:
        raise ValueError("Invalid coverage applicability.")
    if record.get("execution") not in {
        "not_requested",
        "not_started",
        "completed",
        "partial",
        "failed",
        "blocked",
        "unsupported",
    }:
        raise ValueError("Invalid coverage execution.")
    if record.get("assessment") not in {
        "potential_issue",
        "no_issue_identified",
        "not_reported_in_supplied_sources",
        "cannot_verify",
        "not_assessed",
    }:
        raise ValueError("Invalid coverage assessment.")
    for field in ("planned_units", "inspected_units", "omitted_units"):
        count = record.get(field)
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Coverage unit counts must be nonnegative integers or null.")
    if record.get("assessment") == "no_issue_identified":
        if (
            record["execution"] != "completed"
            or record["applicability"] != "applicable"
            or not record.get("evidence_ids")
            or not record.get("inspected_units")
            or record.get("missing_materials")
            or record.get("unresolved_required_sources")
        ):
            raise ValueError("No-issue assessment requires completed, evidenced positive coverage.")
    if record["execution"] in {"failed", "blocked", "not_started", "not_requested", "unsupported"}:
        if record["assessment"] not in {"not_assessed", "cannot_verify"}:
            raise ValueError("Unexecuted or failed checks cannot supply substantive assessments.")
