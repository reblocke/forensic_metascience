"""Synthetic transport substitution; never a runtime qualification receipt."""

from __future__ import annotations

import copy
import json
import os
import sys

from research_project.medical_review.codex_backend import execution_policy
from research_project.medical_review.codex_packet import prepare_packet
from research_project.medical_review.codex_process import bounded_process
from research_project.medical_review.codex_qualification import CHECKS
from research_project.medical_review.runner import run_review
from support.medical_review_fixtures import write_json


def prepared_fixture(workspace, monkeypatch, *, comparisons=False):
    repo, bundle_path, _, bundle, upstream = workspace
    if comparisons:
        bundle["comparisons"] = [
            {
                "study_id": "synthetic",
                "comparison_id": name,
                "report_ids": [bundle["reports"][0]["report_id"]],
                "profile_ids": ["clinical_trial"],
            }
            for name in ("alpha", "beta")
        ]
        bundle["planned_checks"] = []
        write_json(bundle_path, bundle)
    qualification = {
        "schema_version": "medical_codex_qualification_v4",
        "qualified": True,
        "assessment_only": False,
        "all_checks_passed": True,
        "checks": {k: True for k in CHECKS},
        "policy": execution_policy(),
        "runtime": {
            "synthetic_transport_substitution": True,
            "executable_path": "/synthetic/transport-substitution/codex",
        },
        "receipt_sha256": "synthetic-test-only",
    }
    qpath = write_json(
        repo / "data/private/medical_reviews/runtime_qualifications/synthetic/qualification.json",
        qualification,
    )
    monkeypatch.setattr(
        "research_project.medical_review.codex_packet.validate_qualification",
        lambda *_: qualification,
    )
    monkeypatch.setattr(
        "research_project.medical_review.codex_runner.validate_qualification",
        lambda *_: qualification,
    )
    preparation = prepare_packet(
        repo, bundle_path, qualification=qpath, profiles=["clinical_trial"]
    )
    packet = json.loads(preparation["packet"].read_text())
    indexed = json.loads(preparation["bundle"].read_text())
    auth = json.loads(preparation["authorization_template"].read_text())
    from datetime import UTC, datetime, timedelta

    auth.update(
        approver="synthetic-human",
        rationale="Synthetic software test only.",
        valid_from=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        valid_until=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )
    authpath = write_json(
        repo / "data/private/medical_reviews/synthetic/authorizations/codex.json", auth
    )
    envelope = {
        "schema_version": "medical_codex_generation_v1",
        "review": copy.deepcopy(upstream),
        "associations": [],
    }
    unit = packet["sources"][0]["units"][0]
    obj = envelope["review"]["findings"][0]["source_objects"][0]
    obj.update(
        path=packet["sources"][0]["alias"],
        section=unit["section"],
        text_quote=unit["quote"],
        page=unit["page"],
        page_label=unit["page_label"],
    )
    finding = envelope["review"]["findings"][0]
    finding["location"].update(
        section=unit["section"],
        text_quote=unit["quote"],
        page=unit["page"],
        page_label=unit["page_label"],
    )
    envelope["associations"] = [
        {
            "finding_id": finding["id"],
            "study_id": "synthetic",
            "comparison_id": "alpha" if comparisons else None,
            "check_ids": ["trial.assignment"],
        }
    ]
    return preparation, qpath, authpath, envelope, indexed, packet


def execute_fixture(workspace, monkeypatch, *, envelope=None, comparisons=False):
    repo, *_ = workspace
    preparation, qualification, authorization, default, _, _ = prepared_fixture(
        workspace, monkeypatch, comparisons=comparisons
    )
    envelope = default if envelope is None else envelope
    output = write_json(
        repo / "data/private/medical_reviews/synthetic/synthetic-provider.json", envelope
    )

    def launch(packet, catalogue, generated, schema, limits, lock_fd, *, executable):
        assert executable == "/synthetic/transport-substitution/codex"
        final = generated / "raw/generation.json"
        final.parent.mkdir(parents=True)
        script = (
            "import pathlib,sys; "
            "pathlib.Path(sys.argv[2]).write_bytes(pathlib.Path(sys.argv[1]).read_bytes());"
            'print(\'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\')'
        )
        assert (
            bounded_process(
                [sys.executable, "-c", script, str(output), str(final)],
                cwd=repo,
                env={"PATH": os.defpath},
                prompt=packet,
                output=generated / "streams",
                final=final,
                duration=5,
                event_bytes=8192,
                stderr_bytes=8192,
                final_bytes=2 * 1024 * 1024,
                lock_fd=lock_fd,
            )
            == 0
        )

    monkeypatch.setattr("research_project.medical_review.codex_runner._launch", launch)
    run = run_review(
        repo,
        preparation["bundle"],
        backend="codex_cli",
        offline=False,
        allow_llm=True,
        provider="openai",
        model="gpt-6-astra",
        authorization_path=authorization,
        qualification_path=qualification,
    )
    return run, preparation, qualification, authorization
