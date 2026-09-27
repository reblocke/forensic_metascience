from __future__ import annotations

from copy import deepcopy

import pytest

from research_project.inspect_sr.records import (
    EXPECTED_CHECK_IDS,
    create_assessment,
    validate_assessment,
)
from research_project.inspect_sr.review import (
    build_disagreement_table,
    build_private_query_draft,
    create_adjudication_record,
    create_review_revision,
    create_reviewer_submission,
    finalize_review,
    resolve_reviews,
    reviewer_export,
    validate_finalization,
    validate_judgment_set,
    validate_reviewer_submission,
)
from research_project.inspect_sr.validation import immutable_record_id


def _all_answers(response: str = "No") -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "response": response,
            "rationale": f"Reviewed {check_id}.",
            "evidence_ids": [],
        }
        for check_id in EXPECTED_CHECK_IDS
    ]


def _submissions() -> tuple[dict, dict]:
    assessment = create_assessment("trial-local-1", "1.1.2", "guidance-hash")
    first = create_reviewer_submission(
        assessment,
        reviewer_id="reviewer-a",
        source_snapshot_sha256="a" * 64,
        checks=_all_answers(),
    )
    second_answers = _all_answers()
    second_answers[0]["response"] = "Yes"
    second = create_reviewer_submission(
        assessment,
        reviewer_id="reviewer-b",
        source_snapshot_sha256="a" * 64,
        checks=second_answers,
    )
    return first, second


def test_reviewer_submissions_are_separate_and_disagreement_does_not_edit_them() -> None:
    first, second = _submissions()
    original_first = first["checks"][0]["response"]
    disagreement = build_disagreement_table(first, second)
    assert disagreement[0]["check_id"] == "1.1"
    assert disagreement[0]["status"] == "disagreement"
    assert first["checks"][0]["response"] == original_first == "No"
    assert second["checks"][0]["response"] == "Yes"
    same_reviewer = create_reviewer_submission(
        create_assessment("trial-local-1", "1.1.2", "guidance-hash"),
        reviewer_id="reviewer-a",
        source_snapshot_sha256="a" * 64,
        checks=_all_answers(),
    )
    with pytest.raises(ValueError, match="distinct reviewer"):
        build_disagreement_table(first, same_reviewer)
    assert reviewer_export(first, "reviewer-a")["submission_id"] == first["submission_id"]
    with pytest.raises(ValueError, match="own submission"):
        reviewer_export(first, "reviewer-b")
    altered = {**first, "checks": [dict(row) for row in first["checks"]]}
    altered["checks"][0]["response"] = "Yes"
    with pytest.raises(ValueError, match="identity"):
        validate_reviewer_submission(altered)


def test_consensus_is_a_separate_adjudication_referencing_both_originals() -> None:
    first, second = _submissions()
    adjudication = create_adjudication_record(
        first,
        second,
        adjudicator_id="adjudicator-a",
        decisions=[
            {
                "check_id": "1.1",
                "response": "Unclear",
                "rationale": "Notice identity needs a fresh source check.",
                "evidence_ids": [],
            }
        ],
    )
    assert adjudication["reviewer_submission_ids"] == [
        first["submission_id"],
        second["submission_id"],
    ]
    assert adjudication["decisions"][0]["response"] == "Unclear"
    assert first["checks"][0]["response"] == "No"


def test_finalization_preserves_resolved_adjudication_and_reviewer_references() -> None:
    first, second = _submissions()
    adjudication = create_adjudication_record(
        first,
        second,
        adjudicator_id="adjudicator-a",
        decisions=[
            {
                "check_id": "1.1",
                "response": "Unclear",
                "rationale": "Source identity remains unresolved.",
                "evidence_ids": [],
            }
        ],
    )
    resolved = resolve_reviews(first, second, adjudication)
    judgments = {
        "domains": [
            {"domain_id": str(i), "judgment": "some concerns", "rationale": "Reviewed."}
            for i in range(1, 5)
        ],
        "overall": {"judgment": "some concerns", "rationale": "Human synthesis."},
    }
    final = finalize_review(resolved, judgments)
    assert final["adjudication_id"] == adjudication["adjudication_id"]
    assert set(final["reviewer_submission_ids"]) == {
        first["submission_id"],
        second["submission_id"],
    }


def test_pending_checks_block_finalization_but_early_stop_is_explicit() -> None:
    assessment = create_assessment("trial-local-1", "1.1.2", "guidance-hash")
    pending = create_reviewer_submission(
        assessment,
        reviewer_id="reviewer-a",
        source_snapshot_sha256="a" * 64,
        checks=_all_answers()[:-1],
    )
    judgments = {
        "domains": [
            {
                "domain_id": str(domain_id),
                "judgment": "serious concerns",
                "rationale": "Evidence supports stopping review.",
            }
            for domain_id in range(1, 5)
        ],
        "overall": {"judgment": "serious concerns", "rationale": "Documented serious concern."},
    }
    with pytest.raises(ValueError, match="pending checks"):
        finalize_review(pending, judgments)
    final = finalize_review(
        pending,
        judgments,
        early_stop=True,
        early_stop_reason="Check 1.1 confirmed an applicable retraction.",
    )
    assert final["workflow_status"] == "finalized_early_stop"
    remaining = [item for item in final["checks"] if item["response"] is None]
    assert remaining and all(
        item["workflow_status"] == "not_assessed_early_stop" for item in remaining
    )
    altered = deepcopy(final)
    altered["early_stop_reason"] = None
    altered["judgments"]["overall"]["judgment"] = "no concerns"
    altered["judgments"]["domains"] = [
        {**domain, "judgment": "no concerns"} for domain in altered["judgments"]["domains"]
    ]
    altered["finalization_id"] = immutable_record_id(altered, "finalization_id", "finalization_")
    with pytest.raises(ValueError, match="Early-stop"):
        validate_finalization(altered, current_source_snapshot_sha256="a" * 64)


def test_loaded_reviewer_submission_rejects_null_rationale_with_recomputed_identity() -> None:
    first, _ = _submissions()
    malformed = deepcopy(first)
    malformed["checks"][0]["rationale"] = None
    malformed["submission_id"] = immutable_record_id(malformed, "submission_id", "submission_")
    with pytest.raises(ValueError, match="rationale"):
        validate_reviewer_submission(malformed)


def test_clear_finalization_accepts_unclear_as_completed_and_never_scores_yes_answers() -> None:
    assessment = create_assessment("trial-local-1", "1.1.2", "guidance-hash")
    answers = _all_answers()
    answers[0]["response"] = "Unclear"
    answers[1]["response"] = "Yes"
    submission = create_reviewer_submission(
        assessment,
        reviewer_id="reviewer-a",
        source_snapshot_sha256="a" * 64,
        checks=answers,
    )
    judgments = {
        "domains": [
            {
                "domain_id": str(domain_id),
                "judgment": "no concerns",
                "rationale": "Reviewer judgment after considering available evidence.",
            }
            for domain_id in range(1, 5)
        ],
        "overall": {"judgment": "no concerns", "rationale": "Human synthesis judgment."},
    }
    final = finalize_review(submission, judgments)
    assert final["workflow_status"] == "finalized"
    assert final["checks"][0]["response"] == "Unclear"
    assert final["checks"][0]["workflow_status"] == "assessed"
    assert final["judgments"]["overall"]["judgment"] == "no concerns"


def test_lower_overall_judgment_requires_human_justification() -> None:
    judgments = {
        "domains": [
            {
                "domain_id": str(domain_id),
                "judgment": "some concerns",
                "rationale": "Domain evidence.",
            }
            for domain_id in range(1, 5)
        ],
        "overall": {
            "judgment": "no concerns",
            "rationale": "Synthesis considered domain judgments.",
        },
    }
    with pytest.raises(ValueError, match="justification"):
        validate_judgment_set(judgments)
    judgments["overall"]["rationale"] = "Sensitivity analysis addresses the domain concern."
    judgments["overall"]["justification"] = (
        "The registered sensitivity analysis resolves the domain concern."
    )
    validated = validate_judgment_set(judgments)
    assert validated["warnings"]


def test_source_snapshot_change_requires_new_revision_and_invalidates_finalization() -> None:
    first, _ = _submissions()
    revised = create_review_revision(
        first, source_snapshot_sha256="b" * 64, change_reason="A corrected report was located."
    )
    assert revised["submission_revision"] == first["submission_revision"] + 1
    assert revised["supersedes_submission_id"] == first["submission_id"]
    assert revised["workflow_status"] == "requires_reapproval"
    final = {"workflow_status": "finalized", "source_snapshot_sha256": "a" * 64}
    with pytest.raises(ValueError, match="Source snapshot"):
        validate_finalization(final, current_source_snapshot_sha256="b" * 64)


def test_author_contact_route_only_builds_private_draft() -> None:
    draft = build_private_query_draft(
        reviewer_id="reviewer-a",
        source_id="report-1",
        source_locator="page=3",
        question="Could you clarify the recruitment dates?",
        rationale="Dates conflict across reports.",
    )
    assert draft["status"] == "draft_only"
    assert draft["delivery_status"] == "not_sent"
    assert "message_sent" not in draft


@pytest.mark.parametrize(
    "field,value", [("trial_id", "other-trial"), ("guidance_sha256", "b" * 64)]
)
def test_reviewer_identity_binds_trial_and_guidance(field: str, value: str) -> None:
    first, _ = _submissions()
    changed = deepcopy(first)
    changed[field] = value
    with pytest.raises(ValueError, match="identity"):
        validate_reviewer_submission(changed)


def test_assessment_identity_binds_trial_and_guidance() -> None:
    assessment = create_assessment("trial-original", "1.1.2", "a" * 64)
    for key, value in (("trial_id", "trial-changed"), ("guidance_sha256", "b" * 64)):
        changed = deepcopy(assessment)
        changed[key] = value
        with pytest.raises(ValueError, match="identity"):
            validate_assessment(changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trial_id", "other-trial"),
        ("adjudication_id", "other-adjudication"),
        ("guidance_sha256", "b" * 64),
    ],
)
def test_finalization_identity_binds_references(field: str, value: str) -> None:
    first, second = _submissions()
    adjudication = create_adjudication_record(
        first,
        second,
        adjudicator_id="chair",
        decisions=[
            {"check_id": "1.1", "response": "Unclear", "rationale": "Reviewed.", "evidence_ids": []}
        ],
    )
    final = finalize_review(
        resolve_reviews(first, second, adjudication),
        {
            "domains": [
                {"domain_id": str(i), "judgment": "some concerns", "rationale": "Reviewed."}
                for i in range(1, 5)
            ],
            "overall": {"judgment": "some concerns", "rationale": "Reviewed."},
        },
    )
    changed = deepcopy(final)
    changed[field] = value
    with pytest.raises(ValueError, match="identity"):
        validate_finalization(changed, current_source_snapshot_sha256="a" * 64)
