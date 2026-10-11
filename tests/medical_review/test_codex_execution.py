from __future__ import annotations

import json

import pytest
from support.codex_fixtures import execute_fixture, prepared_fixture
from support.medical_review_fixtures import write_json

from research_project.medical_review.audit import load_dossier
from research_project.medical_review.reporting import build_report_model
from research_project.medical_review.runner import run_review


def attempt(run):
    return json.loads((run / "generated/medical_review/attempt_result.json").read_text())


@pytest.mark.parametrize(
    "change",
    ["offline", "absent_auth", "expired", "packet", "policy", "model", "search", "qualification"],
)
def test_codex_denials_never_start_provider(workspace, monkeypatch, change):
    repo, *_ = workspace
    preparation, qualification, authpath, _, _, _ = prepared_fixture(workspace, monkeypatch)
    auth = json.loads(authpath.read_text())
    options = {
        "offline": False,
        "allow_llm": True,
        "provider": "openai",
        "model": "gpt-6-astra",
        "qualification_path": qualification,
        "authorization_path": authpath,
    }
    if change == "offline":
        options["offline"] = True
    if change == "absent_auth":
        options["authorization_path"] = None
    if change == "expired":
        auth["valid_until"] = "2000-01-01T00:00:00+00:00"
    if change == "packet":
        auth["packet_sha256"] = "f" * 64
    if change == "policy":
        auth["execution_policy_sha256"] = "f" * 64
    if change == "model":
        options["model"] = "other"
    if change == "search":
        options["allow_web_search"] = True
    if change == "qualification":

        def refuse(*_):
            raise ValueError("Runtime qualification failed.")

        monkeypatch.setattr(
            "research_project.medical_review.codex_runner.validate_qualification", refuse
        )
    write_json(authpath, auth)

    def forbidden(*_):
        pytest.fail("A denied request started the provider")

    monkeypatch.setattr("research_project.medical_review.codex_runner._launch", forbidden)
    run = run_review(repo, preparation["bundle"], backend="codex_cli", **options)
    result = attempt(run)
    assert result["status"] == "blocked" and result["model_calls"] == 0
    assert result["effective_permissions"] == {"allow_llm": False, "allow_web_search": False}
    assert result["coverage_available"] is False and result["cost_estimate"] is None
    assert load_dossier(repo, run)["proposals"] == []


def test_synthetic_generation_scope_lineage_and_reports_without_rewriting_import(
    workspace, monkeypatch
):
    repo, *_ = workspace
    run, preparation, qualification, authorization = execute_fixture(
        workspace, monkeypatch, comparisons=True
    )
    assert attempt(run)["status"] == "completed", attempt(run)
    dossier = load_dossier(repo, run)
    proposal = dossier["proposals"][0]
    assert proposal["comparison_id"] == "alpha" and proposal["study_id"] == "synthetic"
    assert proposal["check_ids"] == ["trial.assignment"]
    assert proposal["evidence_links"][0]["resolution"] == "exact"
    assert proposal["origin"]["type"] == "codex_reading"
    assert (
        proposal["origin"]["model"] is None
        and proposal["origin"]["requested_model"] == "gpt-6-astra"
    )
    assert proposal["qualified_result_ids"] == []
    imported = repo / attempt(run)["import_run_reference"]
    original = json.loads((imported / "processed/medical_review/proposals.json").read_text())[0]
    assert original["comparison_id"] is None and original["origin"]["type"] == "upstream_import"
    model = build_report_model(repo, dossier)
    assert model["proposal_statuses"][0]["human_status"] == "pending"
    assert "original Reviewer workflow was not executed" in model["rendered_markdown"]
    assert model["review_coverage_available"] is False
    assert all(c["assessment"] != "no_issue_identified" for c in model["coverage"])
    assert (
        run_review(
            repo,
            preparation["bundle"],
            backend="codex_cli",
            offline=False,
            allow_llm=True,
            provider="openai",
            model="gpt-6-astra",
            qualification_path=qualification,
            authorization_path=authorization,
            resume_run=run,
        )
        == run
    )


def test_empty_findings_still_incomplete(workspace, monkeypatch):
    _, _, _, _, upstream = workspace
    empty = {
        "schema_version": "medical_codex_generation_v1",
        "review": {**upstream, "findings": []},
        "associations": [],
    }
    run, *_ = execute_fixture(workspace, monkeypatch, envelope=empty)
    assert attempt(run)["status"] == "completed"
    dossier = load_dossier(workspace[0], run)
    assert dossier["proposals"] == []
    assert all(c["coverage_available"] is False for c in dossier["coverage"])


def test_forged_human_or_official_fields_fail_and_failed_resume_is_refused(workspace, monkeypatch):
    _, _, _, _, upstream = workspace
    forged = {
        "schema_version": "medical_codex_generation_v1",
        "review": upstream,
        "associations": [],
        "human_disposition": "confirmed_concern",
    }
    run, preparation, qualification, authorization = execute_fixture(
        workspace, monkeypatch, envelope=forged
    )
    assert attempt(run)["status"] == "failed"
    assert (run / "generated/medical_review/raw/generation.json").is_file()
    original = (run / "run_manifest.json").read_bytes()
    with pytest.raises(ValueError, match="validated success"):
        run_review(
            workspace[0],
            preparation["bundle"],
            backend="codex_cli",
            offline=False,
            allow_llm=True,
            provider="openai",
            model="gpt-6-astra",
            qualification_path=qualification,
            authorization_path=authorization,
            resume_run=run,
        )
    assert (run / "run_manifest.json").read_bytes() == original


def test_verification_and_human_disposition_bind_scoped_reading_layer(workspace, monkeypatch):
    from datetime import UTC, datetime

    from research_project.medical_review.audit import (
        record_human_disposition,
        validate_human_record,
        verify_review,
    )

    repo, *_ = workspace
    run, *_ = execute_fixture(workspace, monkeypatch, comparisons=True)
    dossier = load_dossier(repo, run)
    proposal = dossier["proposals"][0]
    evidence = next(
        e
        for e in dossier["bundle"]["evidence"]
        if e["evidence_id"] == proposal["evidence_links"][0]["evidence_id"]
    )
    doc = next(
        d
        for d in dossier["bundle"]["documents"]
        if d["source_version_id"] == evidence["source_version_id"]
    )
    verification = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/codex.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [],
        },
    )
    verified = verify_review(repo, run, verification)
    assert load_dossier(repo, verified)["reading_execution"] == dossier["reading_execution"]
    human = record_human_disposition(
        repo,
        verified,
        {
            "schema_version": "medical_human_disposition_input_v1",
            "proposal_id": proposal["proposal_id"],
            "disposition": "unresolved",
            "human_identity": "synthetic-assessor",
            "date": datetime.now(UTC).isoformat(),
            "rationale": "Synthetic software test only; no medical adjudication.",
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
            "supersedes": None,
        },
    )
    record = json.loads(human.read_text())
    assert record["original_proposal_run_reference"] == run.relative_to(repo).as_posix()
    validate_human_record(repo, record)
    assert (
        build_report_model(repo, load_dossier(repo, verified))["proposal_statuses"][0][
            "human_status"
        ]
        == "unresolved"
    )


def test_inexact_generated_citation_remains_unresolved(workspace, monkeypatch):
    _, _, _, envelope, _, _ = prepared_fixture(workspace, monkeypatch)
    envelope["review"]["findings"][0]["source_objects"][0]["text_quote"] = "Inexact synthetic quote"
    run, *_ = execute_fixture(workspace, monkeypatch, envelope=envelope)
    assert attempt(run)["status"] == "completed"
    dossier = load_dossier(workspace[0], run)
    assert dossier["proposals"][0]["evidence_links"][0]["resolution"] == "unresolved"
    assert dossier["proposals"][0]["qualified_result_ids"] == []


def test_unknown_comparison_scope_fails_without_discarding_generation(workspace, monkeypatch):
    _, _, _, envelope, _, _ = prepared_fixture(workspace, monkeypatch)
    envelope["associations"][0]["comparison_id"] = "undeclared-comparison"
    run, *_ = execute_fixture(workspace, monkeypatch, envelope=envelope)
    assert attempt(run)["status"] == "failed"
    assert "scope" in attempt(run)["reason"]
    assert (run / "generated/medical_review/raw/generation.json").exists()
    assert load_dossier(workspace[0], run)["proposals"] == []
