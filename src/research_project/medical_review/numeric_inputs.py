"""Operator-attested numeric source review, separate from execution and qualification."""

from __future__ import annotations

import copy
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import load_dossier, validate_record_identity
from research_project.medical_review.records import (
    PRIVATE_SOURCES,
    content_hash,
    identity,
    private_path,
    read_json,
    write_json,
)

INPUT_FIELDS = {
    "schema_version",
    "result_id",
    "human_identity",
    "date",
    "rationale",
    "source_bytes_reviewed",
    "source_semantics_reviewed",
    "field_bindings",
}
BINDING_FIELDS = {
    "field",
    "value",
    "evidence_id",
    "source_sha256",
    "locator",
    "raw_value",
    "interpretation",
}


def required_input_fields(request: dict[str, Any]) -> dict[str, Any]:
    """Enumerate every non-null arithmetic input and semantic comparison assumption."""
    fields = {}

    def leaves(value, field):
        if isinstance(value, dict):
            for key, child in sorted(value.items()):
                leaves(child, f"{field}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                leaves(child, f"{field}[{index}]")
        elif value is not None:
            fields[field] = value

    for key in ("kind", "population", "horizon", "orientation", "inputs", "reported_comparison"):
        leaves(request[key], key)
    return fields


def _record(data: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    if (
        set(data) != INPUT_FIELDS
        or data["schema_version"] != "medical_numeric_input_review_input_v1"
    ):
        raise ValueError("Unsupported numeric source-review contract fields.")
    results = [r for r in dossier["arithmetic_results"] if r["result_id"] == data["result_id"]]
    if len(results) != 1:
        raise ValueError("Numeric input review requires one exact executed result.")
    result = results[0]
    for key in ("human_identity", "date", "rationale"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(
                "Numeric source review requires explicit human identity/date/rationale."
            )
    if datetime.fromisoformat(data["date"]).tzinfo is None:
        raise ValueError("Numeric source review requires a timezone-qualified timestamp.")
    if data["source_bytes_reviewed"] is not True or data["source_semantics_reviewed"] is not True:
        raise ValueError("Numeric source-semantic review requires explicit operator attestation.")
    expected = required_input_fields(result["request"])
    bindings = data["field_bindings"]
    if not isinstance(bindings, list) or len(bindings) != len(expected):
        raise ValueError("Numeric field bindings must account for every input and assumption.")
    seen = set()
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != BINDING_FIELDS:
            raise ValueError("Unsupported numeric field-binding contract.")
        field = binding["field"]
        if (
            field not in expected
            or field in seen
            or type(binding["value"]) is not type(expected[field])
            or binding["value"] != expected[field]
        ):
            raise ValueError("Numeric field binding differs from the exact executed input.")
        seen.add(field)
        evidence = [
            e
            for e in dossier["bundle"]["evidence"]
            if e["evidence_id"] == binding["evidence_id"]
            and e["evidence_id"] in result["request"]["evidence_ids"]
        ]
        if len(evidence) != 1:
            raise ValueError("Numeric source binding requires declared result evidence.")
        evidence = evidence[0]
        doc = next(
            d
            for d in dossier["bundle"]["documents"]
            if d.get("source_version_id") == evidence["source_version_id"]
        )
        if any(binding[k] != evidence[k] for k in ("locator", "raw_value")) or (
            binding["source_sha256"] != doc["sha256"]
            or not isinstance(binding["interpretation"], str)
            or not binding["interpretation"].strip()
        ):
            raise ValueError("Numeric source hash/locator/interpretation binding does not match.")
    record = {
        **copy.deepcopy(data),
        "schema_version": "medical_numeric_input_review_v1",
        "result_sha256": content_hash(result),
        "request_sha256": result["request_sha256"],
        "bundle_sha256": content_hash(dossier["bundle"]),
        "source_run_reference": str(dossier["run_root"].relative_to(dossier["repo_root"])),
        "input_verification": "operator_attested_source_review",
        "qualified_method_result": False,
        "inspect_sr_candidate_eligible": False,
        "official_assessment": None,
    }
    return {**record, "input_review_id": identity("medicalinputreview", record)}


def validate_input_review(repo: Path, record: dict[str, Any]) -> None:
    """Validate a retained attestation against its explicit original result snapshot."""
    validate_record_identity(record, "input_review_id", "medicalinputreview")
    original = load_dossier(repo, Path(record["source_run_reference"]))
    data = {k: record[k] for k in INPUT_FIELDS}
    data["schema_version"] = "medical_numeric_input_review_input_v1"
    if _record(data, original) != record:
        raise ValueError("Numeric input-review source/authority contract changed.")


def load_input_reviews(repo: Path, dossier: dict[str, Any]) -> list[dict[str, Any]]:
    root = private_path(
        repo,
        PRIVATE_SOURCES / dossier["bundle"]["study_id"] / "numeric_input_reviews",
        PRIVATE_SOURCES,
    )
    results = {r["result_id"] for r in dossier["arithmetic_results"]}
    records = []
    for path in sorted(root.glob("medicalinputreview_*.json")):
        record = read_json(private_path(repo, path, PRIVATE_SOURCES))
        validate_record_identity(record, "input_review_id", "medicalinputreview")
        if path.stem != record["input_review_id"]:
            raise ValueError("Numeric input-review filename identity mismatch.")
        if record["result_id"] not in results:
            continue
        validate_input_review(repo, record)
        records.append(record)
    return records


def record_input_review(repo_root: Path, source_run: Path, data: dict[str, Any]) -> Path:
    """Record explicit source-semantic attestation; never rewrite result or method receipt."""
    repo = repo_root.resolve()
    dossier = load_dossier(repo, source_run)
    record = _record(data, dossier)
    root = private_path(
        repo,
        PRIVATE_SOURCES / dossier["bundle"]["study_id"] / "numeric_input_reviews",
        PRIVATE_SOURCES,
    )
    root.mkdir(parents=True, exist_ok=True)
    lock = private_path(repo, root / ".input-review.lock", PRIVATE_SOURCES)
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        existing = load_input_reviews(repo, dossier)
        if any(
            r["result_id"] == record["result_id"]
            and r["human_identity"] == record["human_identity"]
            for r in existing
        ):
            raise ValueError(
                "Numeric input reviews are write-once; corrected inputs need a new request."
            )
        path = private_path(repo, root / (record["input_review_id"] + ".json"), PRIVATE_SOURCES)
        write_json(path, record)
    return path
