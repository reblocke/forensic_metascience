"""Immutable human review submissions, disagreement, adjudication, and finalization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from research_project.inspect_sr.records import CHECK_RESPONSES, EXPECTED_CHECK_IDS
from research_project.inspect_sr.validation import (
    validate_finalization as _validate_finalization,
)
from research_project.inspect_sr.validation import (
    validate_judgment_set as _validate_judgment_set,
)
from research_project.inspect_sr.validation import (
    validate_reviewer_submission,
)

__all__ = [
    "build_disagreement_table",
    "build_private_query_draft",
    "create_adjudication_record",
    "create_review_revision",
    "create_reviewer_submission",
    "finalize_review",
    "resolve_reviews",
    "reviewer_export",
    "validate_finalization",
    "validate_judgment_set",
]


def validate_finalization(
    finalization: Mapping[str, Any], *, current_source_snapshot_sha256: str
) -> None:
    _validate_finalization(
        finalization, current_source_snapshot_sha256=current_source_snapshot_sha256
    )


def _hash_id(prefix: str, record: Mapping[str, Any]) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_hash(value: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("Source snapshot must be a lowercase SHA-256 hash.")
    return value


def create_reviewer_submission(
    assessment: Mapping[str, Any],
    *,
    reviewer_id: str,
    source_snapshot_sha256: str,
    checks: Sequence[Mapping[str, Any]],
    submission_revision: int = 1,
) -> dict[str, Any]:
    if not reviewer_id.strip():
        raise ValueError("A reviewer identity is required.")
    source_hash = _source_hash(source_snapshot_sha256)
    if not assessment.get("assessment_id") or not assessment.get("trial_id"):
        raise ValueError("Reviewer submission requires an assessment with a trial identity.")
    supplied: dict[str, Mapping[str, Any]] = {}
    for row in checks:
        check_id = str(row.get("check_id", ""))
        if check_id not in EXPECTED_CHECK_IDS or check_id in supplied:
            raise ValueError(f"Unknown or duplicate reviewer check ID: {check_id}")
        disallowed = {"candidate_status", "method_id", "automated_response"}.intersection(row)
        if disallowed:
            raise ValueError("Automated candidate output cannot be submitted as a human response.")
        supplied[check_id] = row
    normalized_checks = []
    for check_id in EXPECTED_CHECK_IDS:
        source = supplied.get(check_id, {})
        response = source.get("response")
        if response is not None and response not in CHECK_RESPONSES:
            raise ValueError(f"Invalid response for check {check_id}.")
        rationale = str(source.get("rationale", "")).strip() or None
        if response is not None and not rationale:
            raise ValueError(f"Human response for check {check_id} requires a rationale.")
        evidence_ids = source.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or any(
            not str(item).strip() for item in evidence_ids
        ):
            raise ValueError(f"Evidence IDs for check {check_id} must be nonempty strings.")
        normalized_checks.append(
            {
                "check_id": check_id,
                "workflow_status": "assessed" if response is not None else "pending",
                "response": response,
                "rationale": rationale,
                "evidence_ids": list(dict.fromkeys(str(item) for item in evidence_ids)),
            }
        )
    content_identity = {
        "assessment_id": assessment["assessment_id"],
        "reviewer_id": reviewer_id,
        "source_snapshot_sha256": source_hash,
        "submission_revision": submission_revision,
        "checks": normalized_checks,
    }
    submission = {
        "schema_version": "inspect_sr_reviewer_submission_v1",
        "record_type": "human_reviewer_submission",
        "submission_id": _hash_id("submission_", content_identity),
        "assessment_id": assessment["assessment_id"],
        "trial_id": assessment["trial_id"],
        "guidance_version": assessment["guidance_version"],
        "guidance_sha256": assessment["guidance_sha256"],
        "source_snapshot_sha256": source_hash,
        "reviewer_id": reviewer_id,
        "submission_revision": submission_revision,
        "created_at": datetime.now(UTC).isoformat(),
        "workflow_status": (
            "submitted"
            if all(row["response"] is not None for row in normalized_checks)
            else "in_progress"
        ),
        "checks": normalized_checks,
    }
    validate_reviewer_submission(submission)
    return submission


def reviewer_export(submission: Mapping[str, Any], reviewer_id: str) -> dict[str, Any]:
    """Return only the named reviewer's own submission; this is not authentication."""
    validate_reviewer_submission(submission)
    if submission.get("reviewer_id") != reviewer_id:
        raise ValueError("Reviewer export can expose only that reviewer's own submission.")
    return dict(submission)


def build_disagreement_table(
    first: Mapping[str, Any], second: Mapping[str, Any]
) -> list[dict[str, Any]]:
    validate_reviewer_submission(first)
    validate_reviewer_submission(second)
    if (
        first["submission_id"] == second["submission_id"]
        or first["reviewer_id"] == second["reviewer_id"]
    ):
        raise ValueError("Independent review comparison requires distinct reviewer submissions.")
    if first["assessment_id"] != second["assessment_id"]:
        raise ValueError("Reviewer submissions must reference the same assessment.")
    if first["source_snapshot_sha256"] != second["source_snapshot_sha256"]:
        raise ValueError("Reviewer submissions must use the same source snapshot.")
    left = {row["check_id"]: row for row in first["checks"]}
    right = {row["check_id"]: row for row in second["checks"]}
    table = []
    for check_id in EXPECTED_CHECK_IDS:
        response_a, response_b = left[check_id]["response"], right[check_id]["response"]
        status = (
            "incomplete"
            if response_a is None or response_b is None
            else "agreement"
            if response_a == response_b
            else "disagreement"
        )
        table.append(
            {
                "check_id": check_id,
                "reviewer_a_id": first["reviewer_id"],
                "reviewer_a_response": response_a,
                "reviewer_b_id": second["reviewer_id"],
                "reviewer_b_response": response_b,
                "status": status,
            }
        )
    return table


def create_adjudication_record(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    *,
    adjudicator_id: str,
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    disagreements = build_disagreement_table(first, second)
    if not adjudicator_id.strip():
        raise ValueError("Adjudicator identity is required.")
    disagreement_ids = {row["check_id"] for row in disagreements if row["status"] == "disagreement"}
    normalized: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        check_id = str(decision.get("check_id", ""))
        if check_id not in disagreement_ids or check_id in normalized:
            raise ValueError(
                "Adjudication decisions must address each listed disagreement at most once."
            )
        response = decision.get("response")
        rationale = str(decision.get("rationale", "")).strip()
        evidence_ids = decision.get("evidence_ids", [])
        if response not in CHECK_RESPONSES or not rationale or not isinstance(evidence_ids, list):
            raise ValueError(
                f"Adjudication for {check_id} needs a response, rationale, and evidence list."
            )
        normalized[check_id] = {
            "check_id": check_id,
            "response": response,
            "rationale": rationale,
            "evidence_ids": list(dict.fromkeys(str(item) for item in evidence_ids)),
        }
    content_identity = {
        "reviewer_submission_ids": sorted([first["submission_id"], second["submission_id"]]),
        "adjudicator_id": adjudicator_id,
        "decisions": normalized,
    }
    result = {
        "schema_version": "inspect_sr_adjudication_v1",
        "record_type": "human_adjudication",
        "adjudication_id": _hash_id("adjudication_", content_identity),
        "assessment_id": first["assessment_id"],
        "reviewer_submission_ids": [first["submission_id"], second["submission_id"]],
        "reviewer_ids": [first["reviewer_id"], second["reviewer_id"]],
        "adjudicator_id": adjudicator_id,
        "source_snapshot_sha256": first["source_snapshot_sha256"],
        "created_at": datetime.now(UTC).isoformat(),
        "decisions": [normalized[key] for key in EXPECTED_CHECK_IDS if key in normalized],
        "disagreement_table": disagreements,
    }
    return result


def resolve_reviews(
    first: Mapping[str, Any], second: Mapping[str, Any], adjudication: Mapping[str, Any]
) -> dict[str, Any]:
    disagreements = build_disagreement_table(first, second)
    expected_ids = sorted([first["submission_id"], second["submission_id"]])
    if sorted(adjudication.get("reviewer_submission_ids", [])) != expected_ids:
        raise ValueError("Adjudication does not reference these original reviewer submissions.")
    decisions = {row["check_id"]: row for row in adjudication.get("decisions", [])}
    rows_a = {row["check_id"]: row for row in first["checks"]}
    rows_b = {row["check_id"]: row for row in second["checks"]}
    resolved = []
    for disagreement in disagreements:
        check_id = disagreement["check_id"]
        left, right = rows_a[check_id], rows_b[check_id]
        if disagreement["status"] == "agreement":
            row = {
                "check_id": check_id,
                "response": left["response"],
                "rationale": "Reviewer agreement: "
                + left["rationale"]
                + " / "
                + right["rationale"],
                "evidence_ids": list(dict.fromkeys(left["evidence_ids"] + right["evidence_ids"])),
                "workflow_status": "assessed",
            }
        elif disagreement["status"] == "disagreement" and check_id in decisions:
            decision = decisions[check_id]
            row = {**decision, "workflow_status": "assessed"}
        else:
            row = {
                "check_id": check_id,
                "response": None,
                "rationale": None,
                "evidence_ids": [],
                "workflow_status": "pending",
            }
        resolved.append(row)
    return {
        "schema_version": "inspect_sr_resolved_review_v1",
        "record_type": "resolved_human_review",
        "assessment_id": first["assessment_id"],
        "trial_id": first["trial_id"],
        "guidance_version": first["guidance_version"],
        "guidance_sha256": first["guidance_sha256"],
        "reviewer_submission_ids": expected_ids,
        "adjudication_id": adjudication["adjudication_id"],
        "source_snapshot_sha256": first["source_snapshot_sha256"],
        "checks": resolved,
    }


def validate_judgment_set(judgments: Mapping[str, Any]) -> dict[str, Any]:
    return _validate_judgment_set(judgments)


def finalize_review(
    review_record: Mapping[str, Any],
    judgments: Mapping[str, Any],
    *,
    early_stop: bool = False,
    early_stop_reason: str = "",
) -> dict[str, Any]:
    if review_record.get("record_type") not in {
        "human_reviewer_submission",
        "resolved_human_review",
    }:
        raise ValueError("Finalization requires a human reviewer or resolved review record.")
    checks = [dict(row) for row in review_record["checks"]]
    if not early_stop and any(row["response"] is None for row in checks):
        raise ValueError("Finalization is blocked by pending checks.")
    validated_judgments = validate_judgment_set(judgments)
    if early_stop:
        if not early_stop_reason.strip():
            raise ValueError("Early stopping requires an explicit rationale.")
        if validated_judgments["overall"]["judgment"] != "serious concerns":
            raise ValueError(
                "Justified early stopping requires a human serious-concerns overall judgment."
            )
        if not any(
            domain["judgment"] == "serious concerns" for domain in validated_judgments["domains"]
        ):
            raise ValueError(
                "Justified early stopping requires a serious-concerns domain judgment."
            )
        for row in checks:
            if row["response"] is None:
                row["workflow_status"] = "not_assessed_early_stop"
    else:
        for row in checks:
            row["workflow_status"] = "assessed"
    finalization = {
        "schema_version": "inspect_sr_finalization_v1",
        "record_type": "human_finalization",
        "finalization_id": _hash_id(
            "finalization_",
            {
                "review_record_id": review_record.get(
                    "submission_id", review_record.get("adjudication_id")
                ),
                "judgments": validated_judgments,
                "early_stop_reason": early_stop_reason,
            },
        ),
        "assessment_id": review_record["assessment_id"],
        "trial_id": review_record["trial_id"],
        "guidance_version": review_record["guidance_version"],
        "guidance_sha256": review_record["guidance_sha256"],
        "review_record_id": review_record.get(
            "submission_id", review_record.get("adjudication_id")
        ),
        "reviewer_submission_ids": review_record.get("reviewer_submission_ids", []),
        "source_snapshot_sha256": review_record["source_snapshot_sha256"],
        "workflow_status": "finalized_early_stop" if early_stop else "finalized",
        "early_stop_reason": early_stop_reason if early_stop else None,
        "checks": checks,
        "judgments": validated_judgments,
        "finalized_at": datetime.now(UTC).isoformat(),
    }
    return finalization


def create_review_revision(
    previous: Mapping[str, Any], *, source_snapshot_sha256: str, change_reason: str
) -> dict[str, Any]:
    if not change_reason.strip():
        raise ValueError("A review revision requires a documented change reason.")
    source_hash = _source_hash(source_snapshot_sha256)
    revision = int(previous.get("submission_revision", previous.get("review_revision", 1))) + 1
    checks = [
        {
            "check_id": check_id,
            "workflow_status": "pending",
            "response": None,
            "rationale": None,
            "evidence_ids": [],
        }
        for check_id in EXPECTED_CHECK_IDS
    ]
    identity = {
        "assessment_id": previous["assessment_id"],
        "reviewer_id": previous["reviewer_id"],
        "revision": revision,
        "source_snapshot_sha256": source_hash,
        "supersedes": previous["submission_id"],
        "change_reason": change_reason,
    }
    result = {
        "schema_version": "inspect_sr_reviewer_submission_v1",
        "record_type": "human_reviewer_submission",
        "submission_id": _hash_id("submission_", identity),
        "assessment_id": previous["assessment_id"],
        "trial_id": previous["trial_id"],
        "guidance_version": previous["guidance_version"],
        "guidance_sha256": previous["guidance_sha256"],
        "source_snapshot_sha256": source_hash,
        "reviewer_id": previous["reviewer_id"],
        "submission_revision": revision,
        "supersedes_submission_id": previous["submission_id"],
        "change_reason": change_reason,
        "workflow_status": "requires_reapproval",
        "checks": checks,
    }
    validate_reviewer_submission(result)
    return result


def build_private_query_draft(
    *, reviewer_id: str, source_id: str, source_locator: str, question: str, rationale: str
) -> dict[str, str]:
    values = (reviewer_id, source_id, source_locator, question, rationale)
    if any(not value.strip() for value in values):
        raise ValueError(
            "A private query draft requires reviewer, source, locator, question, and rationale."
        )
    return {
        "schema_version": "inspect_sr_author_query_draft_v1",
        "record_type": "private_author_query_draft",
        "reviewer_id": reviewer_id,
        "source_id": source_id,
        "source_locator": source_locator,
        "question": question,
        "rationale": rationale,
        "status": "draft_only",
        "delivery_status": "not_sent",
    }
