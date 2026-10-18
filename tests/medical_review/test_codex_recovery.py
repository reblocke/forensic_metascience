from __future__ import annotations

import copy
import hashlib
import json

import pytest
from support.codex_fixtures import execute_fixture

from research_project.medical_review.audit import load_dossier
from research_project.medical_review.codex_recovery import import_codex
from research_project.medical_review.records import content_hash, read_json


def forbid(*args, **kwargs):
    raise AssertionError("Offline recovery attempted a live operation")


def test_offline_recovery_preserves_parent_and_reuses_import(workspace, monkeypatch):
    parent, *_ = execute_fixture(workspace, monkeypatch)
    repo = workspace[0]
    before = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in parent.rglob("*") if p.is_file()
    }
    monkeypatch.setattr("research_project.medical_review.codex_runner._launch", forbid)
    monkeypatch.setattr(
        "research_project.medical_review.codex_runner._authentication_snapshot", forbid
    )
    monkeypatch.setattr(
        "research_project.medical_review.codex_qualification.validate_qualification", forbid
    )
    recovered = import_codex(repo, parent)
    assert import_codex(repo, parent) == recovered
    dossier = load_dossier(repo, recovered)
    assert len(dossier["proposals"]) == 1
    assert dossier["proposals"][0]["evidence_links"][0]["match_kind"] == "whole_unit"
    assert dossier["proposals"][0]["qualified_result_ids"] == []
    from research_project.medical_review.reporting import build_report_model

    model = build_report_model(repo, dossier)
    assert model["proposal_statuses"][0]["human_status"] == "pending"
    assert model["review_coverage_available"] is False
    assert dossier["reading_execution"]["new_model_calls"] == 0
    assert before == {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in parent.rglob("*") if p.is_file()
    }
    assert dossier["manifest"]["effective_settings"]["allow_llm"] is False


@pytest.mark.parametrize(
    "artifact", ["raw/generation.json", "streams/stdin.txt", "streams/events.jsonl"]
)
def test_changed_parent_artifact_rejected(workspace, monkeypatch, artifact):
    parent, *_ = execute_fixture(workspace, monkeypatch)
    path = parent / "generated/medical_review" / artifact
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="hash mismatch"):
        import_codex(workspace[0], parent)


def register_modified(run, path):
    manifest_path = run / "run_manifest.json"
    m = json.loads(manifest_path.read_text())
    for row in m["artifacts"]:
        if row["path"] == str(path.relative_to(run)):
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(m))


def test_incomplete_stream_rejected_even_with_registered_hash(workspace, monkeypatch):
    parent, *_ = execute_fixture(workspace, monkeypatch)
    path = parent / "generated/medical_review/streams/events.jsonl"
    events = path.read_text().splitlines()
    path.write_text(
        "\n".join(x for x in events if json.loads(x).get("type") != "turn.completed") + "\n"
    )
    register_modified(parent, path)
    with pytest.raises(ValueError, match="completed stream"):
        import_codex(workspace[0], parent)


def test_span_tamper_detected_after_registered_hash_update(workspace, monkeypatch):
    parent, *_ = execute_fixture(workspace, monkeypatch)
    run = import_codex(workspace[0], parent)
    path = run / "processed/medical_review/proposals.json"
    proposals = read_json(path)
    proposals[0]["evidence_links"][0]["end_byte"] += 1
    path.write_text(json.dumps(proposals))
    register_modified(run, path)
    with pytest.raises(ValueError, match="citation spans"):
        load_dossier(workspace[0], run)


def test_source_change_rejected(workspace, monkeypatch):
    parent, *_ = execute_fixture(workspace, monkeypatch)
    bundle = read_json(parent / "processed/medical_review/bundle.json")
    path = workspace[0] / next(
        d["path"] for d in bundle["documents"] if d["availability"] == "supplied"
    )
    path.write_text(path.read_text() + " changed")
    with pytest.raises(ValueError):
        import_codex(workspace[0], parent)


def test_conflicted_saved_generation_recovers_without_rewriting_failure(workspace, monkeypatch):
    from support.codex_fixtures import prepared_fixture

    _, _, _, envelope, _, packet = prepared_fixture(workspace, monkeypatch)
    f = envelope["review"]["findings"][0]
    source = packet["sources"][0]
    unit = source["units"][0]
    old = f["source_objects"][0]["id"]
    f["source_objects"][0].update(id=unit["evidence_id"], path=None, text_quote=unit["quote"][:10])
    for link in f["claim_evidence_links"]:
        link["source_object_ids"] = [
            unit["evidence_id"] if k == old else k for k in link["source_object_ids"]
        ]
    second = copy.deepcopy(f)
    second["id"] = "second"
    second["source_objects"][0]["label"] = "Second label"
    envelope["review"]["findings"].append(second)
    association = copy.deepcopy(envelope["associations"][0])
    association["finding_id"] = "second"
    envelope["associations"].append(association)
    # Produce the same historical validation failure, not a new-model recovery.
    from research_project.medical_review.codex_generation import validate_generation

    monkeypatch.setattr(
        "research_project.medical_review.codex_runner.validate_generation",
        lambda repo, e, b, p, **kwargs: validate_generation(repo, e, b, p, version=1),
    )
    parent, *_ = execute_fixture(workspace, monkeypatch, envelope=envelope)
    original = read_json(parent / "run_manifest.json")
    assert original["status"] == "failed"
    assert (
        "Conflicting source object identity"
        in read_json(parent / "generated/medical_review/attempt_result.json")["reason"]
    )
    run = import_codex(workspace[0], parent)
    dossier = load_dossier(workspace[0], run)
    assert len(dossier["proposals"]) == 2
    assert all(
        p["evidence_links"][0]["match_kind"] == "exact_excerpt" for p in dossier["proposals"]
    )
    assert content_hash(read_json(parent / "run_manifest.json")) == content_hash(original)


def test_legacy_lineage_keeps_original_transformation(workspace, monkeypatch):
    from research_project.medical_review import codex_runner
    from research_project.medical_review.codex_generation import (
        derived_payload,
        reading_proposals,
        validate_generation,
    )
    from research_project.medical_review.records import write_json

    monkeypatch.setattr(
        codex_runner, "derived_payload", lambda e, **kw: derived_payload(e, version=1)
    )
    monkeypatch.setattr(
        codex_runner,
        "validate_generation",
        lambda *args, **kw: validate_generation(*args, version=1),
    )

    def legacy_proposals(*args, **kwargs):
        kwargs["version"] = 1
        return reading_proposals(*args, **kwargs)

    monkeypatch.setattr(codex_runner, "reading_proposals", legacy_proposals)

    def legacy_write(path, value):
        if path.name == "reading_lineage.json":
            value = {**value, "schema_version": "medical_codex_lineage_v1"}
            value.pop("citation_transform")
        write_json(path, value)

    monkeypatch.setattr(codex_runner, "write_json", legacy_write)
    run, *_ = execute_fixture(workspace, monkeypatch)
    # Restore the real new loader functions before reading the old lineage.
    monkeypatch.setattr(codex_runner, "derived_payload", derived_payload)
    monkeypatch.setattr(codex_runner, "validate_generation", validate_generation)
    monkeypatch.setattr(codex_runner, "reading_proposals", reading_proposals)
    dossier = load_dossier(workspace[0], run)
    assert dossier["proposals"][0]["evidence_links"][0]["resolution"] == "exact"
    assert "match_kind" not in dossier["proposals"][0]["evidence_links"][0]
