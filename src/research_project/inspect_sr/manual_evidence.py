"""Append-only manual evidence records and validation for INSPECT-SR dossiers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from research_project.inspect_sr.adapters import CHECK_ROUTES

SEARCH_STATES = {"not_started", "located", "searched_not_located", "not_accessible"}


def manual_template(check_id: str) -> dict[str, Any]:
    if check_id not in CHECK_ROUTES:
        raise ValueError(f"Unknown INSPECT-SR check ID: {check_id}")
    return {
        "schema_version": "inspect_sr_manual_evidence_v1",
        "check_id": check_id,
        "record_type": "manual_observation",
        "evidence_id": None,
        "source_id": None,
        "source_version_id": None,
        "observed_at": None,
        "locator": None,
        "observation": None,
        "explanation": None,
        "alternate_explanations": [],
        "reviewer_id": None,
        "search_status": "not_started",
        "supersedes_evidence_id": None,
        "image_inspected": False,
        "image_ids": [],
    }


def validate_manual_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    if (
        record.get("schema_version") != "inspect_sr_manual_evidence_v1"
        or record.get("record_type") != "manual_observation"
    ):
        raise ValueError("Manual evidence requires the current observation record contract.")
    check_id = str(record.get("check_id", ""))
    if check_id not in CHECK_ROUTES:
        raise ValueError(f"Unknown INSPECT-SR check ID: {check_id}")
    required = (
        "source_id",
        "source_version_id",
        "observed_at",
        "locator",
        "observation",
        "explanation",
        "reviewer_id",
    )
    missing = [
        field
        for field in required
        if record.get(field) is None or not str(record.get(field, "")).strip()
    ]
    if missing:
        raise ValueError(f"Manual evidence is missing required fields: {', '.join(missing)}")
    if record.get("search_status") not in SEARCH_STATES:
        raise ValueError("Manual evidence has an invalid search status.")
    timestamp = str(record["observed_at"]).strip()
    try:
        date.fromisoformat(timestamp)
    except ValueError:
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "Manual evidence observed_at must be an ISO date or timestamp."
            ) from exc
    if "response" in record or "human_judgment" in record:
        raise ValueError("Manual evidence cannot contain an official response or judgment.")
    alternatives = record.get("alternate_explanations", [])
    if not isinstance(alternatives, list) or any(
        not isinstance(value, str) or not value.strip() for value in alternatives
    ):
        raise ValueError("Alternate explanations must be a list of nonempty text values.")
    if check_id == "3.2" and record.get("image_inspected") is True:
        image_ids = record.get("image_ids")
        if not isinstance(image_ids, list) or not image_ids:
            raise ValueError("Image inspection requires explicit image or panel evidence IDs.")
    validated = dict(record)
    expected_id = manual_evidence_id(validated)
    if validated.get("evidence_id") not in {None, expected_id}:
        raise ValueError("Manual evidence ID does not match its immutable observation content.")
    validated["evidence_id"] = expected_id
    return validated


def manual_evidence_id(record: Mapping[str, Any]) -> str:
    identity = {
        key: record.get(key)
        for key in (
            "check_id",
            "source_id",
            "source_version_id",
            "observed_at",
            "locator",
            "observation",
            "explanation",
            "alternate_explanations",
            "reviewer_id",
            "search_status",
            "supersedes_evidence_id",
            "image_inspected",
            "image_ids",
        )
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "manual_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_participant_flow_relation(record: Mapping[str, Any]) -> dict[str, Any]:
    required = ("source_version_id", "locator", "population", "timepoint")
    missing = [field for field in required if not str(record.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Participant-flow relation is missing: {', '.join(missing)}")
    categories = record.get("category_ids")
    if not isinstance(categories, list) or len(set(categories)) < 2:
        raise ValueError("Participant-flow relation requires distinct category IDs.")
    if record.get("same_population_timepoint") is not True:
        raise ValueError("Participant-flow arithmetic requires the same population and timepoint.")
    if record.get("mutually_exclusive") is not True:
        raise ValueError("Participant-flow arithmetic requires mutually exclusive categories.")
    return dict(record)
