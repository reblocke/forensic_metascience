from __future__ import annotations

import json

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.bundle import load_bundle, resolve_source_object
from research_project.medical_review.codex_packet import prepare_packet, validate_packet
from research_project.medical_review.records import content_hash


def test_packet_indexes_sources_without_private_annotations(workspace):
    repo, path, _, bundle, _ = workspace
    bundle["context_fields"] = {
        "synthetic": {
            "target_population": {
                "reported": {
                    "status": "unknown",
                    "value": None,
                    "evidence_ids": [],
                    "reason": "OPERATOR_ANSWER_SENTINEL",
                }
            }
        }
    }
    bundle["studies"][0]["human_identity"] = "HUMAN_SENTINEL"
    bundle["evidence"][0]["private_rationale"] = "PRIVATE_RATIONALE_SENTINEL"
    write_json(path, bundle)
    result = prepare_packet(repo, path, qualification=None, profiles=["clinical_trial"])
    packet = json.loads(result["packet"].read_text())
    raw = result["packet"].read_text()
    assert not any(
        x in raw
        for x in [
            "OPERATOR_ANSWER_SENTINEL",
            "HUMAN_SENTINEL",
            "PRIVATE_RATIONALE_SENTINEL",
            "data/private",
        ]
    )
    indexed, digest = load_bundle(repo, result["bundle"])
    assert digest != content_hash(bundle) and indexed["revision"] == bundle["revision"] + 1
    assert json.loads(path.read_text()) == bundle
    unit = packet["sources"][0]["units"][0]
    link = resolve_source_object(
        indexed,
        {
            "id": "new-citation",
            "path": packet["sources"][0]["alias"],
            "text_quote": unit["quote"],
            "section": unit["section"],
        },
    )
    assert link["resolution"] == "exact"
    assert unit["evidence_id"] == link["evidence_id"]
    assert all(e.get("source_semantics_verified") is not True for e in indexed["evidence"])
    assert packet["comparisons"] == []
    assert packet["checks"] and packet["guidance_status"].startswith("unavailable")
    validated = validate_packet(repo, result["bundle"])
    assert validated["packet"] == packet
    auth = json.loads(result["authorization_template"].read_text())
    assert auth["approver"] is None and auth["valid_until"] is None


def test_preparation_is_deterministic_and_refuses_changed_packet(workspace):
    repo, path, *_ = workspace
    first = prepare_packet(repo, path, qualification=None, profiles=["clinical_trial"])
    assert prepare_packet(repo, path, qualification=None, profiles=["clinical_trial"]) == first
    with first["packet"].open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="packet"):
        validate_packet(repo, first["bundle"])


def test_oversize_source_refused_before_extraction(workspace):
    repo, path, *_ = workspace
    with pytest.raises(ValueError, match="source.byte"):
        prepare_packet(repo, path, qualification=None, max_source_bytes=1)


@pytest.mark.parametrize("profiles", [["other"], ["protocol"], ["methods"]])
def test_preparation_preserves_unresolved_protocol_and_unsupported_routing(workspace, profiles):
    repo, path, _, bundle, _ = workspace
    if profiles == ["methods"]:
        bundle["planned_checks"] = []
        write_json(path, bundle)
    preparation = prepare_packet(repo, path, qualification=None, profiles=profiles)
    packet = validate_packet(repo, preparation["bundle"])["packet"]
    assert packet["routing"]["requested_profiles"] == profiles
    if profiles != ["protocol"]:
        assert packet["routing"]["unsupported_profiles"] == profiles
    else:
        assert packet["routing"]["routing_status"] == "unresolved"
    if profiles in (["protocol"], ["other"]):
        assert any(c["check_id"] == "trial.assignment" for c in packet["checks"])


def test_complete_prompt_reserve_includes_wire_escaping_and_runtime_context(workspace):
    from research_project.medical_review.codex_backend import INSTRUCTIONS, execution_policy
    from research_project.medical_review.codex_generation import output_schema
    from research_project.medical_review.codex_packet import _prompt_bytes

    raw = json.dumps({"source": '"' * 2000}).encode()
    visible = {
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": raw.decode()}],
            }
        ],
        "text": {
            "format": {
                "name": "codex_output_schema",
                "schema": output_schema(workspace[0]),
                "strict": True,
                "type": "json_schema",
            },
            "verbosity": "low",
        },
    }
    expected = (
        len(json.dumps(visible, ensure_ascii=False).encode())
        + len(INSTRUCTIONS.encode())
        + execution_policy()["max_runtime_context_bytes"]
    )
    assert _prompt_bytes(workspace[0], raw) >= expected
