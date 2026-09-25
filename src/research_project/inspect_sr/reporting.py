"""Build human-readable INSPECT-SR report data without inferring judgments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from research_project.inspect_sr.manual_evidence import validate_manual_evidence
from research_project.inspect_sr.records import EXPECTED_CHECK_IDS, validate_assessment


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
) -> dict[str, Any]:
    assessment_copy = dict(assessment)
    validate_assessment(assessment_copy)
    official_checks = catalogue.get("checks")
    if not isinstance(official_checks, list) or [
        item.get("check_id") for item in official_checks
    ] != list(EXPECTED_CHECK_IDS):
        raise ValueError("Report catalogue must contain all 21 checks in canonical order.")
    candidate_evidence = candidate_dossier.get("candidate_evidence", [])
    coverage = candidate_dossier.get("coverage", [])
    if not isinstance(candidate_evidence, list) or not isinstance(coverage, list):
        raise ValueError("Candidate dossier must expose candidate evidence and coverage lists.")
    evidence_by_id = {str(item.get("evidence_id")): dict(item) for item in evidence_records}
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
        candidate_by_check[check_id].append(dict(item))
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
        if finalization.get("record_type") != "human_finalization":
            raise ValueError(
                "Report finalization input must be an explicit human finalization record."
            )
        if finalization.get("assessment_id") != assessment_copy.get("assessment_id"):
            raise ValueError("Finalization belongs to a different assessment.")
        if finalization.get("guidance_sha256") != assessment_copy.get("guidance_sha256"):
            raise ValueError("Finalization guidance hash does not match the assessment.")
        if not current_source_snapshot_sha256:
            raise ValueError(
                "Current source snapshot hash is required to show finalized judgments."
            )
        final_is_current = (
            finalization.get("source_snapshot_sha256") == current_source_snapshot_sha256
            and bool(finalization.get("adjudication_id"))
            and finalization.get("workflow_status") in {"finalized", "finalized_early_stop"}
        )
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
        "schema_version": "inspect_sr_report_model_v1",
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
