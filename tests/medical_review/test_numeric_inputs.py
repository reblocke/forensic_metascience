from __future__ import annotations

import copy
import json

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.audit import load_dossier, verify_review
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.numeric_inputs import (
    load_input_reviews,
    record_input_review,
    required_input_fields,
)
from research_project.medical_review.records import content_hash
from research_project.medical_review.reporting import build_report_model


def arithmetic_run(workspace):
    repo, bundle_path, incoming, bundle, _ = workspace
    imported = import_reviewer(repo, bundle_path, incoming)
    proposal = load_dossier(repo, imported)["proposals"][0]
    request = {
        "schema_version": "medical_numeric_check_request_v1",
        "run_id": proposal["run_id"],
        "proposal_id": proposal["proposal_id"],
        "study_id": "synthetic",
        "comparison_id": None,
        "bundle_sha256": content_hash(bundle),
        "kind": "percentage",
        "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
        "population": "synthetic-participants",
        "horizon": "day-30",
        "orientation": "event-risk",
        "inputs": {"numerator": 1, "denominator": 2},
        "reported_comparison": None,
    }
    path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/numbers.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [request],
        },
    )
    run = verify_review(repo, imported, path)
    dossier = load_dossier(repo, run)
    result = dossier["arithmetic_results"][0]
    evidence = bundle["evidence"][0]
    data = {
        "schema_version": "medical_numeric_input_review_input_v1",
        "result_id": result["result_id"],
        "human_identity": "synthetic-numeric-reviewer",
        "date": "2026-10-06T12:00:00-06:00",
        "rationale": "Synthetic source-semantic attestation.",
        "source_bytes_reviewed": True,
        "source_semantics_reviewed": True,
        "field_bindings": [
            {
                "field": field,
                "value": value,
                "evidence_id": evidence["evidence_id"],
                "source_sha256": bundle["documents"][0]["sha256"],
                "locator": evidence["locator"],
                "raw_value": evidence["raw_value"],
                "interpretation": "Synthetic mapping reviewed.",
            }
            for field, value in required_input_fields(request).items()
        ],
    }
    return run, dossier, data


def test_input_review_is_separate_write_once_attestation_never_a_qualified_result(workspace):
    repo, *_ = workspace
    run, dossier, data = arithmetic_run(workspace)
    frozen = (run / "processed/medical_review/arithmetic_results.json").read_bytes()
    path = record_input_review(repo, run, data)
    assert path.exists()
    assert (run / "processed/medical_review/arithmetic_results.json").read_bytes() == frozen
    record = load_input_reviews(repo, dossier)[0]
    assert record["input_verification"] == "operator_attested_source_review"
    assert record["qualified_method_result"] is False
    assert record["inspect_sr_candidate_eligible"] is False
    model = build_report_model(repo, dossier)
    assert model["numeric_input_reviews"] == [record]
    assert model["arithmetic_results"][0]["input_verification"] == "proposed_transcription"
    with pytest.raises(ValueError, match="write-once"):
        record_input_review(repo, run, data)
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.parametrize(
    "change", ["missing_denominator", "wrong_value", "wrong_locator", "no_semantics", "authority"]
)
def test_input_review_rejects_incomplete_or_forged_transcription_authority(workspace, change):
    repo, *_ = workspace
    run, _, data = arithmetic_run(workspace)
    data = copy.deepcopy(data)
    if change == "missing_denominator":
        data["field_bindings"] = [
            r for r in data["field_bindings"] if r["field"] != "inputs.denominator"
        ]
    if change == "wrong_value":
        data["field_bindings"][0]["value"] = "fabricated"
    if change == "wrong_locator":
        data["field_bindings"][0]["locator"] = "page=99"
    if change == "no_semantics":
        data["source_semantics_reviewed"] = False
    if change == "authority":
        data["qualified_method_result"] = True
    with pytest.raises(ValueError, match="field|binding|source|attestation|contract"):
        record_input_review(repo, run, data)
    assert not (repo / "data/private/medical_reviews/synthetic/numeric_input_reviews").exists()


def test_input_review_tampering_cannot_survive_report_build(workspace):
    repo, *_ = workspace
    run, dossier, data = arithmetic_run(workspace)
    path = record_input_review(repo, run, data)
    record = json.loads(path.read_text())
    record["qualified_method_result"] = True
    write_json(path, record)
    with pytest.raises(ValueError, match="identity|authority"):
        build_report_model(repo, dossier)
