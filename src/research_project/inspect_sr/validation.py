"""Validation for reviewer submissions, human judgments, and finalization."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from research_project.inspect_sr.records import CHECK_RESPONSES, EXPECTED_CHECK_IDS

JUDGMENTS = {"no concerns", "some concerns", "serious concerns"}
JUDGMENT_RANK = {"no concerns": 0, "some concerns": 1, "serious concerns": 2}


def immutable_record_id(record: Mapping[str, Any], id_field: str, prefix: str) -> str:
    """Bind every serialized v3 record field except its own content ID."""
    payload = {key: value for key, value in record.items() if key != id_field}
    return (
        prefix
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    )


def validate_reviewer_submission(submission: Mapping[str, Any]) -> None:
    if submission.get("schema_version") != "inspect_sr_reviewer_submission_v3":
        raise ValueError("Unsupported reviewer submission schema.")
    if submission.get("record_type") != "human_reviewer_submission":
        raise ValueError("Review input must be an explicit human reviewer submission.")
    if not submission.get("reviewer_id") or not submission.get("assessment_id"):
        raise ValueError("Reviewer submission requires reviewer and assessment identities.")
    if not submission.get("trial_id") or not submission.get("guidance_sha256"):
        raise ValueError("Reviewer submission requires trial and guidance identities.")
    checks = submission.get("checks")
    if not isinstance(checks, list) or [row.get("check_id") for row in checks] != list(
        EXPECTED_CHECK_IDS
    ):
        raise ValueError("Reviewer submission must preserve all 21 checks in canonical order.")
    for row in checks:
        if row.get("candidate_status") is not None or row.get("method_id") is not None:
            raise ValueError("Automated candidate text cannot impersonate a reviewer response.")
        response = row.get("response")
        if response is not None and response not in CHECK_RESPONSES:
            raise ValueError(f"Invalid check response for {row['check_id']}.")
        if response is None and row.get("workflow_status") != "pending":
            raise ValueError(f"Unanswered check {row['check_id']} must remain pending.")
        if response is not None:
            if row.get("workflow_status") != "assessed":
                raise ValueError(f"Answered check {row['check_id']} must be assessed.")
            if not str(row.get("rationale", "")).strip():
                raise ValueError(f"Check {row['check_id']} needs a reviewer rationale.")
            if not isinstance(row.get("evidence_ids"), list):
                raise ValueError(f"Check {row['check_id']} evidence_ids must be a list.")
    expected_id = immutable_record_id(submission, "submission_id", "submission_")
    if submission.get("submission_id") != expected_id:
        raise ValueError("Reviewer submission content does not match its immutable identity.")


def validate_judgment_set(judgments: Mapping[str, Any]) -> dict[str, Any]:
    domains = judgments.get("domains")
    if not isinstance(domains, list) or len(domains) != 4:
        raise ValueError("Four human domain judgments are required.")
    domain_ids = {str(domain.get("domain_id")) for domain in domains}
    if domain_ids != {"1", "2", "3", "4"}:
        raise ValueError("Domain judgments must cover domains 1 through 4 exactly once.")
    for domain in domains:
        if domain.get("judgment") not in JUDGMENTS:
            raise ValueError("Invalid human domain judgment.")
        if not str(domain.get("rationale", "")).strip():
            raise ValueError(f"Domain {domain['domain_id']} requires a rationale.")
    overall = judgments.get("overall")
    if not isinstance(overall, Mapping) or overall.get("judgment") not in JUDGMENTS:
        raise ValueError("A human overall judgment is required.")
    if not str(overall.get("rationale", "")).strip():
        raise ValueError("Overall judgment requires a rationale.")
    warnings = []
    lower_than_domain = any(
        JUDGMENT_RANK[overall["judgment"]] < JUDGMENT_RANK[domain["judgment"]] for domain in domains
    )
    if lower_than_domain:
        if not str(overall.get("justification", "")).strip():
            raise ValueError(
                "Overall judgment below a domain judgment requires an explicit justification."
            )
        warnings.append(
            "Overall judgment is less concerning than at least one domain; "
            "justification is recorded."
        )
    return {
        "domains": [dict(item) for item in domains],
        "overall": dict(overall),
        "warnings": warnings,
    }


def validate_finalization(
    finalization: Mapping[str, Any], *, current_source_snapshot_sha256: str
) -> None:
    if finalization.get("workflow_status") not in {"finalized", "finalized_early_stop"}:
        raise ValueError("Review record is not finalized.")
    if finalization.get("source_snapshot_sha256") != current_source_snapshot_sha256:
        raise ValueError(
            "Source snapshot changed; a new review revision and approval are required."
        )
    if finalization.get("schema_version") != "inspect_sr_finalization_v3":
        raise ValueError("Unsupported finalization schema.")
    checks = finalization.get("checks")
    if not isinstance(checks, list) or [row.get("check_id") for row in checks] != list(
        EXPECTED_CHECK_IDS
    ):
        raise ValueError("Finalization must contain all 21 checks in canonical order.")
    for row in checks:
        status, response = row.get("workflow_status"), row.get("response")
        if status == "assessed":
            if response not in CHECK_RESPONSES or not str(row.get("rationale", "")).strip():
                raise ValueError("Finalized responses require an allowed response and rationale.")
            if not isinstance(row.get("evidence_ids"), list):
                raise ValueError("Finalized response evidence_ids must be a list.")
        elif status == "not_assessed_early_stop":
            if (
                response is not None
                or finalization.get("workflow_status") != "finalized_early_stop"
            ):
                raise ValueError("Only early-stopped finalizations may have unassessed checks.")
        else:
            raise ValueError("Finalization contains a pending or invalid check state.")
    validate_judgment_set(finalization.get("judgments", {}))
    expected_id = immutable_record_id(finalization, "finalization_id", "finalization_")
    if finalization.get("finalization_id") != expected_id:
        raise ValueError("Finalization content does not match its immutable identity.")
