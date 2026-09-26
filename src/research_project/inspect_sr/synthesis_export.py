"""Protocol-controlled trial dispositions kept separate from scientific outcomes."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from research_project.inspect_sr.records import EXPECTED_CHECK_IDS
from research_project.inspect_sr.validation import validate_finalization, validate_judgment_set

POLICY_SCHEMA = "inspect_sr_synthesis_policy_v1"
DISPOSITIONS = {"include", "exclude"}
JUDGMENT_KEYS = ("no concerns", "some concerns", "serious concerns")


def validate_synthesis_policy(policy: Mapping[str, Any], *, guidance_sha256: str) -> dict[str, Any]:
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise ValueError("Unsupported synthesis policy schema.")
    if not all(
        str(policy.get(field, "")).strip()
        for field in ("policy_id", "policy_version", "approved_by", "approved_at", "rationale")
    ):
        raise ValueError("Synthesis policy requires version, approval, date, and rationale.")
    if not str(policy.get("policy_version", "")).strip():
        raise ValueError("Synthesis policy version is required.")
    try:
        date.fromisoformat(str(policy["approved_at"]))
    except ValueError as exc:
        raise ValueError("Synthesis policy approval date must be an ISO date.") from exc
    if policy.get("source_guidance_sha256") != guidance_sha256:
        raise ValueError("Synthesis policy guidance hash is stale or mismatched.")
    if not re.fullmatch(r"[a-f0-9]{64}", guidance_sha256):
        raise ValueError("Synthesis policy requires a valid guidance SHA-256 hash.")
    primary, sensitivity = policy.get("primary"), policy.get("sensitivity")
    for label, mapping in (("primary", primary), ("sensitivity", sensitivity)):
        if not isinstance(mapping, Mapping) or set(mapping) != set(JUDGMENT_KEYS):
            raise ValueError(f"Synthesis policy {label} must explicitly map all human judgments.")
        if any(value not in DISPOSITIONS for value in mapping.values()):
            raise ValueError(f"Synthesis policy {label} dispositions must be include or exclude.")
    if any(primary[key] != sensitivity[key] for key in ("no concerns", "serious concerns")):
        raise ValueError("Primary and sensitivity policies may only differ for some concerns.")
    if primary["some concerns"] == sensitivity["some concerns"]:
        raise ValueError(
            "Primary and sensitivity policies must declare both some-concerns choices."
        )
    return dict(policy)


def _finalized_adjudicated(review: Mapping[str, Any]) -> bool:
    if review.get("schema_version") != "inspect_sr_finalization_v2":
        return False
    if review.get("record_type") != "human_finalization":
        return False
    if review.get("workflow_status") not in {"finalized", "finalized_early_stop"}:
        return False
    if not review.get("adjudication_id"):
        return False
    reviewer_ids = review.get("reviewer_submission_ids")
    if not isinstance(reviewer_ids, list) or len(set(reviewer_ids)) != 2:
        return False
    judgments = review.get("judgments")
    if not isinstance(judgments, Mapping):
        return False
    try:
        validate_judgment_set(judgments)
    except (TypeError, ValueError, KeyError):
        return False
    if not review.get("trial_id") or not re.fullmatch(
        r"[a-f0-9]{64}", str(review.get("source_snapshot_sha256", ""))
    ):
        return False
    try:
        validate_finalization(
            review, current_source_snapshot_sha256=str(review.get("source_snapshot_sha256", ""))
        )
    except (TypeError, ValueError, KeyError):
        return False
    checks = review.get("checks")
    if not isinstance(checks, list) or [row.get("check_id") for row in checks] != list(
        EXPECTED_CHECK_IDS
    ):
        return False
    for row in checks:
        status = row.get("workflow_status")
        if status not in {"assessed", "not_assessed_early_stop"}:
            return False
        if status == "assessed":
            if row.get("response") not in {"Yes", "No", "Unclear", "Not applicable"}:
                return False
            if not str(row.get("rationale", "")).strip():
                return False
            if not isinstance(row.get("evidence_ids"), list):
                return False
        elif row.get("response") is not None:
            return False
    return True


def _disposition(
    review: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    policy_variant: str,
    unresolved_policy: str,
) -> tuple[str, bool | None, str]:
    if review is None or not _finalized_adjudicated(review):
        if unresolved_policy == "block":
            raise ValueError(
                "Unresolved assessments without a finalized adjudicated review "
                "block synthesis inclusion export."
            )
        return "unresolved", None, "No current finalized adjudicated review is available."
    judgment = review["judgments"]["overall"]["judgment"]
    disposition = policy[policy_variant][judgment]
    return disposition, disposition == "include", f"Human overall judgment: {judgment}."


def build_synthesis_export(
    reviews: Sequence[Mapping[str, Any]],
    report_rows: Sequence[Mapping[str, Any]],
    comparison_rows: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    guidance_sha256: str,
    current_source_snapshot_sha256_by_trial: Mapping[str, str],
    unresolved_policy: str,
    policy_variant: str,
    public: bool = False,
    public_trial_ids: Sequence[str] = (),
    public_reviewed_by: str | None = None,
) -> dict[str, Any]:
    validated_policy = validate_synthesis_policy(policy, guidance_sha256=guidance_sha256)
    if unresolved_policy not in {"block", "list"}:
        raise ValueError("Choose unresolved_policy='block' or 'list' explicitly.")
    if policy_variant not in {"primary", "sensitivity"}:
        raise ValueError("policy_variant must be primary or sensitivity.")
    by_trial: dict[str, Mapping[str, Any] | None] = {}
    for review in reviews:
        trial_id = str(review.get("trial_id", "")).strip()
        if not trial_id or trial_id in by_trial:
            raise ValueError("Each synthesis input needs one unique persistent trial ID.")
        if review.get("guidance_sha256") != guidance_sha256:
            if unresolved_policy == "block":
                raise ValueError("Guidance changed; a new reviewed revision is required.")
            by_trial[trial_id] = None
        elif review.get("source_snapshot_sha256") != current_source_snapshot_sha256_by_trial.get(
            trial_id
        ):
            if unresolved_policy == "block":
                raise ValueError("Source snapshot changed; a new reviewed revision is required.")
            by_trial[trial_id] = None
        else:
            by_trial[trial_id] = review
    if public:
        if not public_reviewed_by or not public_trial_ids:
            raise ValueError("Public export requires explicit trial selection and review identity.")
        selected = set(public_trial_ids)
        if selected - by_trial.keys():
            raise ValueError("Public selection contains unknown trial IDs.")
    else:
        selected = set(by_trial)

    trial_rows: list[dict[str, Any]] = []
    for trial_id in sorted(selected):
        review = by_trial[trial_id]
        disposition, include, reason = _disposition(
            review, validated_policy, policy_variant, unresolved_policy
        )
        trial_rows.append(
            {
                "trial_id": trial_id,
                "disposition": disposition,
                "include": include,
                "reason": reason,
                "policy_id": validated_policy["policy_id"],
                "policy_version": validated_policy["policy_version"],
                "policy_variant": policy_variant,
            }
        )
    disposition_by_trial = {row["trial_id"]: row for row in trial_rows}

    def join_rows(rows: Sequence[Mapping[str, Any]], label: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        joined: list[dict[str, Any]] = []
        row_id_key = "report_id" if label == "report" else "comparison_id"
        for source_row in rows:
            trial_id = str(source_row.get("trial_id", "")).strip()
            row_id = str(source_row.get(row_id_key, ""))
            if not trial_id or not row_id:
                raise ValueError(f"Every {label} row needs a persistent row ID and trial ID.")
            if row_id in seen:
                raise ValueError(f"Duplicate {label} ID would violate join cardinality: {row_id}")
            seen.add(row_id)
            if trial_id not in disposition_by_trial:
                raise ValueError(
                    f"{label} row references trial without an export disposition: {trial_id}"
                )
            disposition = disposition_by_trial[trial_id]
            synthesis_fields = {
                "synthesis_disposition": disposition["disposition"],
                "synthesis_include": disposition["include"],
                "synthesis_reason": disposition["reason"],
                "synthesis_policy_id": disposition["policy_id"],
                "synthesis_policy_version": disposition["policy_version"],
                "synthesis_policy_variant": disposition["policy_variant"],
            }
            if public:
                joined.append(
                    {
                        row_id_key: row_id,
                        "trial_id": trial_id,
                        **synthesis_fields,
                    }
                )
            else:
                joined.append({**dict(source_row), **synthesis_fields})
        if len(joined) != len(rows):
            raise ValueError(f"{label} join changed row cardinality.")
        return joined

    report_dispositions = join_rows(report_rows, "report")
    comparison_dispositions = join_rows(comparison_rows, "comparison")
    result = {
        "schema_version": "inspect_sr_synthesis_export_v2",
        "policy_id": validated_policy["policy_id"],
        "policy_version": validated_policy["policy_version"],
        "policy_variant": policy_variant,
        "guidance_sha256": guidance_sha256,
        "unresolved_policy": unresolved_policy,
        "trial_dispositions": trial_rows,
        "report_dispositions": report_dispositions,
        "comparison_dispositions": comparison_dispositions,
        "public_export": public,
    }
    return result
