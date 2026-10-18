from __future__ import annotations

import copy

import pytest
from support.codex_fixtures import prepared_fixture

from research_project.medical_review.codex_citations import normalize_citations, resolve_citation


def test_citation_ids_are_scoped_and_links_remapped(workspace):
    review = copy.deepcopy(workspace[4])
    first = review["findings"][0]
    second = copy.deepcopy(first)
    second["id"] = "second"
    second["source_objects"][0]["label"] = "Another excerpt"
    review["findings"].append(second)
    original = copy.deepcopy(review)
    normalized, ledger = normalize_citations(review, "generation")
    assert review == original
    assert (
        normalized["findings"][0]["source_objects"][0]["id"]
        != normalized["findings"][1]["source_objects"][0]["id"]
    )
    assert normalize_citations(review, "generation") == (normalized, ledger)
    for finding in normalized["findings"]:
        ids = {o["id"] for o in finding["source_objects"]}
        assert all(
            set(link["source_object_ids"]) <= ids for link in finding["claim_evidence_links"]
        )
    first["source_objects"].append(copy.deepcopy(first["source_objects"][0]))
    with pytest.raises(ValueError, match="Duplicate source object"):
        normalize_citations(review, "generation")


def test_exact_excerpt_unicode_and_ambiguity(workspace, monkeypatch):
    _, _, _, envelope, bundle, packet = prepared_fixture(workspace, monkeypatch)
    source = packet["sources"][0]
    unit = source["units"][0]
    unit["quote"] = "é unique τέλος"
    obj = envelope["review"]["findings"][0]["source_objects"][0]
    obj.update(id=unit["evidence_id"], text_quote="unique")
    link = resolve_citation(bundle, packet, obj, "synthetic", None)
    assert link["resolution"] == "exact"
    assert link["match_kind"] == "exact_excerpt"
    assert link["start_byte"] == 3 and link["end_byte"] == 9
    obj["url"] = "https://example.invalid/unbound-source"
    assert resolve_citation(bundle, packet, obj, "synthetic", None)["resolution"] == "unresolved"
    obj["url"] = None
    unit["quote"] = "aaa"
    obj["text_quote"] = "aa"
    assert resolve_citation(bundle, packet, obj, "synthetic", None)["resolution"] == "unresolved"
    unit["quote"] = "unique"
    obj.update(text_quote="unique", section="wrong")
    assert resolve_citation(bundle, packet, obj, "synthetic", None)["resolution"] == "unresolved"
    obj["section"] = unit["section"]
    source["report_ids"] = ["different-report"]
    with pytest.raises(ValueError, match="scope"):
        resolve_citation(bundle, packet, obj, "synthetic", None)


def test_dangling_reference_and_duplicate_finding_rejected(workspace):
    review = copy.deepcopy(workspace[4])
    review["findings"][0]["claim_evidence_links"][0]["source_object_ids"] = ["missing"]
    with pytest.raises(ValueError, match="unknown source object"):
        normalize_citations(review, "generation")
    review = copy.deepcopy(workspace[4])
    review["findings"].append(copy.deepcopy(review["findings"][0]))
    with pytest.raises(ValueError, match="Duplicate finding"):
        normalize_citations(review, "generation")


def test_multiple_comparison_associations_remain_one_proposal(workspace, monkeypatch):
    from support.codex_fixtures import execute_fixture

    from research_project.medical_review.audit import load_dossier
    from research_project.medical_review.codex_generation import validate_generation

    _, _, _, envelope, bundle, packet = prepared_fixture(workspace, monkeypatch, comparisons=True)
    extra = copy.deepcopy(envelope["associations"][0])
    extra["comparison_id"] = "beta"
    envelope["associations"].append(extra)
    validate_generation(workspace[0], envelope, bundle, packet, version=2)
    with pytest.raises(ValueError, match="exactly once"):
        validate_generation(workspace[0], envelope, bundle, packet, version=1)
    run, *_ = execute_fixture(workspace, monkeypatch, envelope=envelope, comparisons=True)
    proposals = load_dossier(workspace[0], run)["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["comparison_id"] is None
    assert {a["comparison_id"] for a in proposals[0]["scope_associations"]} == {"alpha", "beta"}
    envelope["associations"].append(extra)
    with pytest.raises(ValueError, match="Duplicate finding scope"):
        validate_generation(workspace[0], envelope, bundle, packet, version=2)
