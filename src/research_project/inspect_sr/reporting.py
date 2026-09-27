"""Build human-readable INSPECT-SR report data without inferring judgments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from research_project.inspect_sr.adapters import (
    METHOD_TO_CHECKS,
    _candidate_identity_fields,
    _stable_candidate_id,
    build_candidate_dossier,
)
from research_project.inspect_sr.manual_evidence import validate_manual_evidence
from research_project.inspect_sr.records import EXPECTED_CHECK_IDS, validate_assessment
from research_project.inspect_sr.review import resolve_reviews
from research_project.inspect_sr.snapshot import validate_source_snapshot
from research_project.inspect_sr.validation import (
    validate_finalization,
    validate_reviewer_submission,
)


def build_report_model(
    *,
    assessment: Mapping[str, Any],
    catalogue: Mapping[str, Any],
    source_versions: Sequence[Mapping[str, Any]],
    evidence_records: Sequence[Mapping[str, Any]],
    candidate_dossier: Mapping[str, Any],
    reviewer_submissions: Sequence[Mapping[str, Any]],
    adjudication: Mapping[str, Any] | None,
    finalization: Mapping[str, Any] | None,
    method_receipts: Sequence[Mapping[str, Any]] = (),
    current_source_snapshot_sha256: str | None = None,
    source_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    assessment_copy = dict(assessment)
    validate_assessment(assessment_copy)
    official_checks = catalogue.get("checks")
    if not isinstance(official_checks, list) or [
        item.get("check_id") for item in official_checks
    ] != list(EXPECTED_CHECK_IDS):
        raise ValueError("Report catalogue must contain all 21 checks in canonical order.")
    candidate_evidence = candidate_dossier.get("candidate_evidence", [])
    unresolved_results = candidate_dossier.get("unresolved_results", [])
    coverage = candidate_dossier.get("coverage", [])
    if (
        not isinstance(candidate_evidence, list)
        or not isinstance(coverage, list)
        or not isinstance(unresolved_results, list)
    ):
        raise ValueError("Candidate dossier must expose candidate evidence and coverage lists.")
    evidence_by_id = {str(item.get("evidence_id")): dict(item) for item in evidence_records}
    expected_coverage = build_candidate_dossier(method_receipts, candidate_evidence)["coverage"]
    if (candidate_evidence and not coverage) or (coverage and coverage != expected_coverage):
        raise ValueError("Candidate coverage differs from its current method receipts.")
    for item in candidate_evidence:
        method_id = str(item.get("method_id", ""))
        check_id = str(item.get("check_id", ""))
        ids = item.get("evidence_ids")
        if (
            item.get("schema_version") != "inspect_sr_candidate_evidence_v2"
            or item.get("candidate_status") != "candidate_only"
            or check_id not in METHOD_TO_CHECKS.get(method_id, ())
            or not isinstance(ids, list)
            or not ids
            or set(ids) - evidence_by_id.keys()
        ):
            raise ValueError("Candidate lacks a validated check route and current source evidence.")
        matching = [
            receipt
            for receipt in method_receipts
            if receipt.get("method_id") == method_id and receipt.get("run_id") == item.get("run_id")
        ]
        if len(matching) != 1 or matching[0].get("execution") not in {"completed", "partial"}:
            raise ValueError("Candidate lacks one current evaluated method receipt.")
        if item.get("native_output_reference") != matching[0].get("output_reference"):
            raise ValueError("Candidate native output reference differs from its method receipt.")
        receipt_ids = set(str(matching[0].get("input_evidence_ids", "")).split(";"))
        if set(ids) - receipt_ids or any(
            evidence_by_id[evidence_id].get("locator") != item.get("source_locator")
            for evidence_id in ids
        ):
            raise ValueError("Candidate source evidence differs from receipt inputs or locator.")
        try:
            expected_candidate_id = _stable_candidate_id(_candidate_identity_fields(item))
        except (KeyError, TypeError) as exc:
            raise ValueError("Candidate result provenance is incomplete.") from exc
        if item.get("candidate_id") != expected_candidate_id:
            raise ValueError("Candidate result content does not match its immutable identity.")
    candidate_by_check: dict[str, list[dict[str, Any]]] = {
        check_id: [] for check_id in EXPECTED_CHECK_IDS
    }
    manual_by_check: dict[str, list[dict[str, Any]]] = {
        check_id: [] for check_id in EXPECTED_CHECK_IDS
    }
    for item in candidate_evidence:
        check_id = str(item.get("check_id", ""))
        if check_id not in candidate_by_check:
            raise ValueError("Candidate dossier references an unknown check.")
        candidate_by_check[check_id].append(
            {
                **dict(item),
                "source_raw_values": [
                    evidence_by_id[evidence_id].get("raw_value")
                    for evidence_id in item["evidence_ids"]
                ],
            }
        )
    for item in evidence_records:
        check_id = str(item.get("check_id", ""))
        if check_id in manual_by_check and item.get("record_type") == "manual_observation":
            manual_by_check[check_id].append(validate_manual_evidence(item))
    coverage_by_check = {str(row.get("check_id")): dict(row) for row in coverage}
    official_by_check = {str(row["check_id"]): row for row in official_checks}
    assessment_checks = {row["check_id"]: dict(row) for row in assessment_copy["checks"]}

    final_is_current = False
    finalization_source_status = "not_finalized"
    if finalization is not None:
        if finalization.get("schema_version") != "inspect_sr_finalization_v3":
            raise ValueError("Report finalization input must use the current v3 contract.")
        if finalization.get("record_type") != "human_finalization":
            raise ValueError(
                "Report finalization input must be an explicit human finalization record."
            )
        if finalization.get("assessment_id") != assessment_copy.get("assessment_id"):
            raise ValueError("Finalization belongs to a different assessment.")
        if finalization.get("guidance_sha256") != assessment_copy.get("guidance_sha256"):
            raise ValueError("Finalization guidance hash does not match the assessment.")
        if not source_versions or not evidence_records or len(reviewer_submissions) != 2:
            raise ValueError(
                "Finalized reports require source, evidence, and two reviewer records."
            )
        if source_snapshot is None:
            raise ValueError("Finalized reports require a verified local source snapshot.")
        validate_source_snapshot(
            source_snapshot, assessment_copy, source_versions, evidence_records
        )
        if current_source_snapshot_sha256 != source_snapshot["source_snapshot_sha256"]:
            raise ValueError("Report source snapshot does not match current records.")
        if catalogue.get("guidance_sha256") != assessment_copy["guidance_sha256"]:
            raise ValueError("Report catalogue guidance differs from the assessment.")
        validate_finalization(
            finalization,
            current_source_snapshot_sha256=current_source_snapshot_sha256,
        )
        for submission in reviewer_submissions:
            validate_reviewer_submission(submission)
            if (
                any(
                    submission.get(key) != assessment_copy.get(key)
                    for key in ("assessment_id", "trial_id", "guidance_sha256")
                )
                or submission.get("source_snapshot_sha256") != current_source_snapshot_sha256
            ):
                raise ValueError("Reviewer submission does not match current assessment or source.")
        if adjudication is None:
            raise ValueError("Finalized report requires its adjudication record.")
        resolved = resolve_reviews(reviewer_submissions[0], reviewer_submissions[1], adjudication)
        if (
            finalization.get("review_record_id") != resolved["resolved_review_id"]
            or finalization.get("adjudication_id") != adjudication.get("adjudication_id")
            or sorted(finalization.get("reviewer_submission_ids", []))
            != resolved["reviewer_submission_ids"]
        ):
            raise ValueError("Finalization references do not match the complete reviewed chain.")
        for recorded, expected in zip(finalization["checks"], resolved["checks"], strict=True):
            if any(
                recorded.get(key) != expected.get(key)
                for key in ("check_id", "response", "rationale", "evidence_ids")
            ):
                raise ValueError("Finalized response differs from its resolved human review.")
        available_ids = {item["evidence_id"] for item in evidence_records}
        for row in finalization["checks"]:
            if set(row.get("evidence_ids", [])) - available_ids:
                raise ValueError("Finalized response references missing source evidence.")
        if not current_source_snapshot_sha256:
            raise ValueError(
                "Current source snapshot hash is required to show finalized judgments."
            )
        final_is_current = True
        if finalization.get("source_snapshot_sha256") != current_source_snapshot_sha256:
            finalization_source_status = "changed_requires_reapproval"
        elif not finalization.get("adjudication_id"):
            finalization_source_status = "adjudication_required"
        elif final_is_current:
            finalization_source_status = "current"
        if final_is_current:
            if not isinstance(finalization.get("judgments"), Mapping):
                raise ValueError("Current finalization lacks its explicit human judgment record.")
            final_checks = finalization.get("checks")
            if not isinstance(final_checks, list) or [
                row.get("check_id") for row in final_checks
            ] != list(EXPECTED_CHECK_IDS):
                raise ValueError("Finalization must include all 21 checks in canonical order.")
            assessment_checks = {row["check_id"]: dict(row) for row in final_checks}

    checks = []
    for check_id in EXPECTED_CHECK_IDS:
        checks.append(
            {
                "check_id": check_id,
                "official_wording": official_by_check[check_id]["official_wording"],
                **assessment_checks[check_id],
                "coverage": coverage_by_check.get(check_id),
                "candidate_evidence": candidate_by_check[check_id],
                "manual_evidence": manual_by_check[check_id],
                "evidence_records": [
                    evidence_by_id[evidence_id]
                    for evidence_id in assessment_checks[check_id].get("evidence_ids", [])
                    if evidence_id in evidence_by_id
                ],
            }
        )
    status = "DRAFT — PENDING"
    judgments = None
    if final_is_current:
        status = (
            "FINALIZED — EARLY STOP"
            if finalization.get("workflow_status") == "finalized_early_stop"
            else "FINALIZED"
        )
        judgments = dict(finalization.get("judgments", {}))
    elif finalization_source_status == "changed_requires_reapproval":
        status = "DRAFT — SOURCE CHANGED"
    elif finalization_source_status == "adjudication_required":
        status = "DRAFT — ADJUDICATION REQUIRED"
    return {
        "schema_version": "inspect_sr_report_model_v3",
        "record_type": "inspect_sr_review_report_model",
        "report_status": status,
        "trial_id": assessment_copy["trial_id"],
        "assessment_id": assessment_copy["assessment_id"],
        "guidance_version": assessment_copy["guidance_version"],
        "guidance_sha256": assessment_copy["guidance_sha256"],
        "source_versions": [dict(item) for item in source_versions],
        "checks": checks,
        "method_receipts": [dict(item) for item in method_receipts],
        "reviewer_submissions": [dict(item) for item in reviewer_submissions],
        "adjudication": dict(adjudication) if adjudication else None,
        "finalization_id": finalization.get("finalization_id") if final_is_current else None,
        "finalization_source_status": finalization_source_status,
        "early_stop_reason": finalization.get("early_stop_reason") if final_is_current else None,
        "unresolved_results": [dict(item) for item in unresolved_results],
        "judgments": judgments,
        "domain_judgments": judgments.get("domains") if judgments is not None else None,
        "unresolved_items": [
            {
                "check_id": item["check_id"],
                "workflow_status": item["workflow_status"],
                "response": item.get("response"),
            }
            for item in checks
            if item["workflow_status"] in {"pending", "not_assessed_early_stop"}
        ],
        "judgment_note": (
            "Human finalization is shown as recorded; check responses are not converted to scores."
            if judgments is not None
            else "No current finalized adjudication is shown; "
            "no trustworthiness category is computed."
        ),
    }
