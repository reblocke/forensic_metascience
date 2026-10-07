from __future__ import annotations

import hashlib
import json

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.audit import (
    load_dossier,
    record_human_disposition,
    verify_review,
)
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.records import content_hash


def review(workspace):
    repo, bundle_path, incoming, *_ = workspace
    run = import_reviewer(repo, bundle_path, incoming)
    return run, json.loads((run / "processed/medical_review/proposals.json").read_text())[0]


def pass_input(proposal, evidence):
    return {
        "schema_version": "medical_verification_input_v1",
        "counterevidence": [
            {
                "proposal_id": proposal["proposal_id"],
                "disposition": "contradicted",
                "reviewed_claim": proposal["claim"],
                "strongest_alternative": "The supplement clarifies the prespecified comparison.",
                "rationale": "The original criticism is explained by cited source evidence.",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [evidence],
                "missing_materials": [],
                "change_summary": "Demote the original criticism.",
                "model": None,
                "backend": None,
                "prompt_sha256": None,
            }
        ],
        "numeric_requests": [],
    }


def decision(dossier, proposal, disposition="confirmed_concern", supersedes=None):
    evidence = dossier["bundle"]["evidence"][0]
    doc = next(
        d
        for d in dossier["bundle"]["documents"]
        if d.get("source_version_id") == evidence["source_version_id"]
    )
    return {
        "schema_version": "medical_human_disposition_input_v1",
        "proposal_id": proposal["proposal_id"],
        "disposition": disposition,
        "human_identity": "synthetic-reviewer",
        "date": "2026-10-06T12:00:00-06:00",
        "rationale": "Independent source review by the synthetic human.",
        "reviewed_evidence": [
            {
                "evidence_id": evidence["evidence_id"],
                "source_sha256": doc["sha256"],
                "locator": evidence["locator"],
                "raw_value": evidence["raw_value"],
            }
        ],
        "source_bytes_reviewed": True,
        "locators_reviewed": True,
        "supersedes": supersedes,
    }


def test_counterevidence_appends_new_run_and_preserves_original_proposal(workspace):
    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    before = (source / "processed/medical_review/proposals.json").read_bytes()
    path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/pass.json",
        pass_input(proposal, bundle["evidence"][0]["evidence_id"]),
    )
    derived = verify_review(repo, source, path)
    dossier = load_dossier(repo, derived)
    assert dossier["verification"][0]["disposition"] == "contradicted"
    assert dossier["verification"][0]["independently_human_confirmed"] is False
    assert dossier["proposals"][0] == proposal
    assert dossier["verification"][0]["original_proposal_sha256"] == content_hash(proposal)
    assert (source / "processed/medical_review/proposals.json").read_bytes() == before
    assert derived != source
    assert (
        derived / "generated/medical_review/raw/verification_input.json"
    ).read_bytes() == path.read_bytes()
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.parametrize(
    "field", ["human_verified", "method_receipt", "official_assessment", "response"]
)
def test_model_verification_cannot_claim_human_or_official_authority(workspace, field):
    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    data = pass_input(proposal, bundle["evidence"][0]["evidence_id"])
    data["counterevidence"][0][field] = True
    path = write_json(repo / "data/private/medical_reviews/synthetic/verification/pass.json", data)
    with pytest.raises(ValueError, match="contract|fields"):
        verify_review(repo, source, path)
    assert not (repo / "data/private/inspect_sr").exists()


def test_counterevidence_needs_real_evidence_and_original_claim(workspace):
    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    data = pass_input(proposal, "fabricated")
    path = write_json(repo / "data/private/medical_reviews/synthetic/verification/pass.json", data)
    with pytest.raises(ValueError, match="evidence"):
        verify_review(repo, source, path)
    data = pass_input(proposal, bundle["evidence"][0]["evidence_id"])
    data["counterevidence"][0]["reviewed_claim"] = "Changed claim"
    write_json(path, data)
    with pytest.raises(ValueError, match="claim"):
        verify_review(repo, source, path)


def test_human_decision_is_write_once_and_revision_retains_history(workspace):
    repo, *_ = workspace
    source, proposal = review(workspace)
    dossier = load_dossier(repo, source)
    data = decision(dossier, proposal)
    first = record_human_disposition(repo, source, data)
    original = first.read_bytes()
    identifier = json.loads(original)["disposition_id"]
    second = record_human_disposition(
        repo, source, decision(dossier, proposal, "dismissed", identifier)
    )
    revised = json.loads(second.read_text())
    assert first.read_bytes() == original and second != first
    assert revised["supersedes"] == identifier
    assert revised["original_proposal_sha256"] == content_hash(proposal)
    assert revised["original_origin"] == proposal["origin"]
    assert revised["official_assessment"] is None
    with pytest.raises(ValueError, match="superseded|current"):
        record_human_disposition(
            repo, source, decision(dossier, proposal, "unresolved", identifier)
        )
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.parametrize(
    "change",
    ["missing_identity", "wrong_source", "wrong_quote", "no_attestation", "official_fields"],
)
def test_human_disposition_requires_identity_source_bytes_and_independent_attestation(
    workspace, change
):
    repo, *_ = workspace
    source, proposal = review(workspace)
    dossier = load_dossier(repo, source)
    data = decision(dossier, proposal)
    if change == "missing_identity":
        data["human_identity"] = ""
    if change == "wrong_source":
        data["reviewed_evidence"][0]["source_sha256"] = "f" * 64
    if change == "wrong_quote":
        data["reviewed_evidence"][0]["raw_value"] = "Fabricated quotation"
    if change == "no_attestation":
        data["source_bytes_reviewed"] = False
    if change == "official_fields":
        data["official_assessment"] = "serious concerns"
    with pytest.raises(ValueError, match="identity|source|evidence|attestation|contract"):
        record_human_disposition(repo, source, data)
    assert not (repo / "data/private/medical_reviews/synthetic/human_dispositions").exists()


def test_human_cannot_silently_supersede_another_reviewers_record(workspace):
    repo, *_ = workspace
    source, proposal = review(workspace)
    dossier = load_dossier(repo, source)
    first = record_human_disposition(repo, source, decision(dossier, proposal))
    data = decision(dossier, proposal, "dismissed", json.loads(first.read_text())["disposition_id"])
    data["human_identity"] = "different-synthetic-reviewer"
    with pytest.raises(ValueError, match="reviewer|identity"):
        record_human_disposition(repo, source, data)


def test_tampered_registered_proposal_refuses_verification(workspace):
    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    path = source / "processed/medical_review/proposals.json"
    data = json.loads(path.read_text())
    data[0]["human_verified"] = True
    write_json(path, data)
    with pytest.raises(ValueError, match="hash|artifact"):
        load_dossier(repo, source)


def test_reimported_context_requires_explicit_human_revision_and_keeps_original_binding(
    workspace, monkeypatch
):
    from research_project.medical_review import importer
    from research_project.medical_review.audit import load_human_history

    repo, bundle_path, incoming, *_ = workspace
    source, proposal = review(workspace)
    old_dossier = load_dossier(repo, source)
    first = record_human_disposition(repo, source, decision(old_dossier, proposal))
    old_record = json.loads(first.read_text())
    original = first.read_bytes()
    monkeypatch.setattr(importer, "_adapter_hash", lambda: "f" * 64)
    newer = importer.import_reviewer(repo, bundle_path, incoming)
    dossier = load_dossier(repo, newer)
    newer_proposal = dossier["proposals"][0]
    assert newer_proposal["proposal_id"] == proposal["proposal_id"]
    history = load_human_history(repo, dossier)
    assert history[0]["original_proposal_sha256"] != content_hash(newer_proposal)
    revised = record_human_disposition(
        repo, newer, decision(dossier, newer_proposal, "unresolved", old_record["disposition_id"])
    )
    assert json.loads(revised.read_text())["original_proposal_sha256"] == content_hash(
        newer_proposal
    )
    assert first.read_bytes() == original


def test_executed_arithmetic_retains_original_request_and_archives_calculator(workspace):
    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    data = pass_input(proposal, bundle["evidence"][0]["evidence_id"])
    data["numeric_requests"] = [
        {
            "schema_version": "medical_numeric_check_request_v1",
            "run_id": proposal["run_id"],
            "proposal_id": proposal["proposal_id"],
            "study_id": proposal["study_id"],
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
    ]
    path = write_json(repo / "data/private/medical_reviews/synthetic/verification/pass.json", data)
    derived = verify_review(repo, source, path)
    dossier = load_dossier(repo, derived)
    result = dossier["arithmetic_results"][0]
    assert result["input_verification"] == "proposed_transcription"
    assert result["qualified_method_result"] is False
    assert result["request"] == data["numeric_requests"][0]
    archive = derived / "generated/medical_review/code/numeric.py"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == result["calculator"]["source_sha256"]


def test_midpass_input_drift_preserves_failed_run_without_fabricated_verification(
    workspace, monkeypatch
):
    from research_project.medical_review import audit

    repo, _, _, bundle, *_ = workspace
    source, proposal = review(workspace)
    path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/pass.json",
        pass_input(proposal, bundle["evidence"][0]["evidence_id"]),
    )
    original = path.read_bytes()
    real_create = audit.create_run
    created = []

    def changed_input(**kwargs):
        result = real_create(**kwargs)
        created.append(result[0])
        path.write_text("{}")
        return result

    monkeypatch.setattr(audit, "create_run", changed_input)
    with pytest.raises(ValueError, match="changed during"):
        verify_review(repo, source, path)
    failed = created[0]
    dossier = load_dossier(repo, failed)
    assert dossier["manifest"]["status"] == "failed"
    assert dossier["verification"] == [] and dossier["failures"]
    assert (
        failed / "generated/medical_review/raw/verification_input.json"
    ).read_bytes() == original


def test_misplaced_bundle_refuses_before_reading_another_studys_sources(workspace, monkeypatch):
    from research_project.medical_review import bundle as bundle_module

    repo, _, _, bundle, _ = workspace
    path = write_json(repo / "data/private/medical_reviews/other/bundle.json", bundle)

    def forbidden_read(*args, **kwargs):
        pytest.fail("Source file read before the bundle study-directory authorization boundary.")

    monkeypatch.setattr(bundle_module, "_verify_file", forbidden_read)
    with pytest.raises(ValueError, match="private boundary"):
        bundle_module.load_bundle(repo, path)
