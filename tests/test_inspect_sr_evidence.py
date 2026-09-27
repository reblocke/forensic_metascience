from __future__ import annotations

import pytest

from research_project.inspect_sr.adapters import (
    CHECK_ROUTES,
    build_candidate_dossier,
    map_candidate_result,
)
from research_project.inspect_sr.manual_evidence import (
    manual_evidence_id,
    manual_template,
    validate_manual_evidence,
    validate_participant_flow_relation,
)
from research_project.inspect_sr.records import evidence_id


def _receipt(
    method_id: str,
    run_id: str,
    execution: str,
    n: int,
    evaluated: int,
    failed: int,
    flagged: int | None,
    input_evidence_ids: str = "evidence-1",
) -> dict:
    return {
        "schema_version": "method_receipt_v4",
        "run_id": run_id,
        "method_id": method_id,
        "method_version": "1",
        "package_name": method_id,
        "package_version": "1",
        "unit_of_evaluation": "fixture_unit",
        "input_evidence_ids": input_evidence_ids,
        "parameters": "fixture",
        "applicability": "eligible",
        "execution": execution,
        "result_status": "indeterminate" if execution != "completed" else "no_finding",
        "n_input": n,
        "n_eligible": n,
        "n_evaluated": evaluated,
        "n_failed": failed,
        "n_flagged": flagged,
        "output_reference": "raw.csv",
        "diagnostic": "fixture",
    }


def _source_evidence(
    locator: str = "page=4;paragraph=2", raw_value: str = "reported result"
) -> dict:
    source_version = "sourcever-1"
    return {
        "evidence_id": evidence_id(source_version, locator, raw_value, "pdf_text", "fixture-v1"),
        "source_version_id": source_version,
        "locator": locator,
        "raw_value": raw_value,
        "extraction_method": "pdf_text",
        "extraction_version": "fixture-v1",
    }


def test_all_checks_have_explicit_coverage_and_manual_evidence_routes() -> None:
    assert set(CHECK_ROUTES) == {
        *(f"1.{number}" for number in range(1, 4)),
        *(f"2.{number}" for number in range(1, 6)),
        *(f"3.{number}" for number in range(1, 3)),
        *(f"4.{number}" for number in range(1, 12)),
    }
    assert all(route["manual_route"] for route in CHECK_ROUTES.values())
    assert all("limitations" in route for route in CHECK_ROUTES.values())


def test_candidate_mapping_requires_completed_or_partial_receipt_and_exact_evidence() -> None:
    result = {
        "schema_version": "numeric_result_v2",
        "method_id": "statcheck",
        "run_id": "run-1",
        "result_id": "result-1",
        "input_evidence_ids": [],
        "candidate_kind": "statistical_text_discrepancy",
        "source_locator": "page=4;paragraph=2",
        "details": "synthetic result",
    }
    evidence_record = _source_evidence()
    result["input_evidence_ids"] = [evidence_record["evidence_id"]]
    receipt = _receipt(
        "statcheck", "run-1", "completed", 1, 1, 0, 0, evidence_record["evidence_id"]
    )
    evidence = [evidence_record]
    candidates = map_candidate_result(result, [receipt], evidence)
    assert candidates
    assert candidates[0]["check_id"] == "4.9"
    assert candidates[0]["candidate_status"] == "candidate_only"
    assert candidates[0]["evidence_ids"] == [evidence_record["evidence_id"]]
    assert "response" not in candidates[0]
    assert not map_candidate_result(result, [{**receipt, "execution": "failed"}], evidence)
    with pytest.raises(ValueError, match="method_receipt_v4"):
        map_candidate_result(result, [{**receipt, "schema_version": "method_receipt_v2"}], evidence)
    with pytest.raises(ValueError, match="evidence"):
        map_candidate_result(result, [receipt], [])
    with pytest.raises(ValueError, match="content identity"):
        map_candidate_result(result, [receipt], [{**evidence_record, "raw_value": "changed"}])
    with pytest.raises(ValueError, match="numeric_result_v2"):
        map_candidate_result({**result, "schema_version": "numeric_result_v1"}, [receipt], evidence)


def test_candidate_receipt_counts_reject_fractional_values() -> None:
    receipt = _receipt("statcheck", "run-1", "completed", 1, 1, 0, 0)
    with pytest.raises(ValueError, match="integer"):
        build_candidate_dossier([{**receipt, "n_evaluated": 1.5}], [])


def test_rounding_bias_receipt_cannot_emit_candidate_evidence() -> None:
    evidence_record = _source_evidence()
    result = {
        "schema_version": "numeric_result_v2",
        "method_id": "scrutiny_rounding_bias",
        "run_id": "run-1",
        "result_id": "rounding-result-1",
        "input_evidence_ids": [evidence_record["evidence_id"]],
        "candidate_kind": "rounding_bias",
        "source_locator": evidence_record["locator"],
        "details": "synthetic adversarial result",
    }
    receipt = _receipt(
        "scrutiny_rounding_bias",
        "run-1",
        "completed",
        1,
        1,
        0,
        1,
        evidence_record["evidence_id"],
    )
    with pytest.raises(ValueError, match="Rounding-bias candidates are blocked"):
        map_candidate_result(result, [receipt], [evidence_record])


def test_caption_signal_cannot_complete_image_integrity_route() -> None:
    result = {
        "schema_version": "numeric_result_v2",
        "method_id": "visual_caption_similarity",
        "result_id": "figure-pair-1",
        "run_id": "run-1",
        "input_evidence_ids": ["caption-1", "caption-2"],
        "candidate_kind": "caption_similarity",
        "source_locator": "figures=1,3",
        "details": "synthetic repeated caption",
    }
    receipt = _receipt("visual_caption_similarity", "run-1", "completed", 2, 2, 0, 0)
    evidence = [
        {"evidence_id": "caption-1", "source_version_id": "sourcever-1"},
        {"evidence_id": "caption-2", "source_version_id": "sourcever-1"},
    ]
    candidates = map_candidate_result(result, [receipt], evidence)
    assert candidates == []
    coverage = build_candidate_dossier([receipt], candidates)["coverage"]
    figure_integrity = next(row for row in coverage if row["check_id"] == "3.2")
    assert figure_integrity["status"] == "manual_only"


def test_dossier_separates_missing_failed_ineligible_and_available_methods() -> None:
    receipts = [
        _receipt("statcheck", "run-1", "dependency_missing", 1, 0, 0, None),
        _receipt("scrutiny_grim_map", "run-1", "completed", 2, 2, 0, 0),
    ]
    dossier = build_candidate_dossier(receipts, [])
    coverage = {item["check_id"]: item for item in dossier["coverage"]}
    assert coverage["4.9"]["status"] == "failed"
    assert coverage["4.8"]["status"] == "available"
    assert coverage["1.1"]["status"] == "manual_only"
    assert all("response" not in item for item in dossier["coverage"])


def test_candidate_mapping_never_uses_a_receipt_from_another_run() -> None:
    result = {
        "schema_version": "numeric_result_v2",
        "method_id": "statcheck",
        "run_id": "run-b",
        "result_id": "result-1",
        "input_evidence_ids": ["evidence-1"],
        "source_locator": "page=1",
    }
    receipt = _receipt("statcheck", "run-a", "completed", 1, 1, 0, 0)
    evidence = [_source_evidence("page=1")]
    result["input_evidence_ids"] = [evidence[0]["evidence_id"]]
    assert map_candidate_result(result, [receipt], evidence) == []


def test_candidate_evidence_must_be_in_exact_receipt_input_set() -> None:
    result = {
        "schema_version": "numeric_result_v2",
        "method_id": "statcheck",
        "run_id": "run-1",
        "result_id": "result-1",
        "input_evidence_ids": ["evidence-2"],
        "source_locator": "page=1",
    }
    receipt = _receipt("statcheck", "run-1", "completed", 1, 1, 0, 0)
    evidence = [_source_evidence("page=1")]
    result["input_evidence_ids"] = [evidence[0]["evidence_id"]]
    assert map_candidate_result(result, [receipt], evidence) == []


def test_manual_evidence_requires_source_date_locator_and_explanation() -> None:
    template = manual_template("2.1")
    assert template["check_id"] == "2.1"
    with pytest.raises(ValueError, match="source_id"):
        validate_manual_evidence({**template, "observation": "Approval statement found."})
    record = {
        **template,
        "source_id": "report-1",
        "source_version_id": "sourcever-1",
        "observed_at": "2026-09-25T12:00:00Z",
        "locator": "page=2;section=ethics",
        "observation": "Approval statement found.",
        "explanation": "Review the cited approval against the trial record.",
        "reviewer_id": "reviewer-a",
        "search_status": "located",
    }
    record["evidence_id"] = manual_evidence_id(record)
    validated = validate_manual_evidence(record)
    assert validated["check_id"] == "2.1"
    assert validated["evidence_id"].startswith("manual_")
    assert "response" not in record


def test_flow_relationship_requires_matching_population_and_mutually_exclusive_branches() -> None:
    relationship = {
        "source_version_id": "sourcever-1",
        "locator": "figure=1;panel=a",
        "population": "randomized participants",
        "timepoint": "randomization",
        "category_ids": ["randomized", "excluded"],
        "mutually_exclusive": False,
        "same_population_timepoint": True,
    }
    with pytest.raises(ValueError, match="mutually exclusive"):
        validate_participant_flow_relation(relationship)
