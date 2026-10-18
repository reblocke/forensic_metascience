"""Offline recovery of a completed, registered Codex generation; never launches a model."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.bundle import validate_bundle
from research_project.medical_review.codex_citations import normalize_citations
from research_project.medical_review.codex_generation import (
    derived_payload,
    observed_metadata,
    reading_proposals,
    validate_generation,
)
from research_project.medical_review.codex_packet import validate_packet_content
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.run_manifest import create_run, update_run


def _parent(repo, run):
    manifest = validate_run_artifacts(repo, run)

    def artifact(name):
        return recorded_artifact(repo, run, manifest, name)

    request = read_json(artifact("generated/medical_review/attempt_requested.json"))
    result = read_json(artifact("generated/medical_review/attempt_result.json"))
    dependencies = request.get("dependencies", {})
    settings = manifest["effective_settings"]
    if (
        settings.get("execution_mode") != "codex_reading"
        or request.get("schema_version") != "medical_execution_request_v2"
        or request.get("run_id") != run.name
        or result.get("run_id") != run.name
        or request.get("request_id")
        != identity("medicalrequest", {k: v for k, v in request.items() if k != "request_id"})
        or result.get("attempt_id")
        != identity("medicalattempt", {k: v for k, v in result.items() if k != "attempt_id"})
        or result.get("status") != manifest["status"]
        or result.get("coverage_available") is not False
        or result.get("request_id") != request["request_id"]
        or request.get("dependencies_sha256") != content_hash(dependencies)
        or result.get("dependencies_sha256") != content_hash(dependencies)
        or any(settings.get(k) != v for k, v in dependencies.items())
        or dependencies.get("backend") != "codex_cli"
        or dependencies.get("allow_llm") is not True
        or dependencies.get("allow_web_search") is not False
    ):
        raise ValueError("Recovery parent request/result binding changed.")
    bundle = read_json(artifact("processed/medical_review/bundle.json"))
    if validate_bundle(repo, bundle) != dependencies["bundle_sha256"]:
        raise ValueError("Recovery bundle changed.")
    packet_raw = artifact("generated/medical_review/streams/stdin.txt").read_bytes()
    packet = parse_json(packet_raw)
    binding = bundle["codex_packet"]
    if (
        packet.get("schema_version") != "medical_codex_packet_v1"
        or packet.get("paper_id") != bundle.get("upstream_paper_id")
        or hashlib.sha256(packet_raw).hexdigest() != dependencies["packet_sha256"]
        or binding["packet_sha256"] != dependencies["packet_sha256"]
        or binding["policy_sha256"] != dependencies["policy_sha256"]
    ):
        raise ValueError("Recovery packet/policy binding changed.")
    validate_packet_content(repo, bundle, packet)
    qualification = read_json(artifact("generated/medical_review/qualification.json"))
    if (
        qualification.get("receipt_sha256") != dependencies["qualification_sha256"]
        or qualification["receipt_sha256"]
        != content_hash({k: v for k, v in qualification.items() if k != "receipt_sha256"})
        or qualification.get("qualified") is not True
        or qualification.get("assessment_only") is not False
        or content_hash(qualification.get("policy")) != dependencies["policy_sha256"]
        or qualification["policy"].get("model") != dependencies.get("requested_model")
        or qualification["policy"].get("provider") != dependencies.get("provider")
        or binding.get("qualification_sha256") != dependencies["qualification_sha256"]
    ):
        raise ValueError("Historical qualification binding changed.")
    approvals = []
    for row in manifest["input_fingerprints"]:
        path = private_path(repo, Path(row["path"]), PRIVATE_SOURCES)
        if path.suffix != ".json" or not path.is_file():
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Historical input fingerprint changed.")
        candidate = parse_json(raw)
        if content_hash(candidate) == dependencies["authorization_sha256"]:
            approvals.append(candidate)
    if len(approvals) != 1:
        raise ValueError("Historical source authorization unavailable or ambiguous.")
    auth = approvals[0]
    if (
        auth.get("bundle_sha256") != dependencies["bundle_sha256"]
        or auth.get("packet_sha256") != dependencies["packet_sha256"]
        or auth.get("execution_policy_sha256") != dependencies["policy_sha256"]
        or not datetime.fromisoformat(auth["valid_from"])
        <= datetime.fromisoformat(request["created_at"])
        <= datetime.fromisoformat(auth["valid_until"])
    ):
        raise ValueError("Historical authorization binding or validity changed.")
    raw = artifact("generated/medical_review/raw/generation.json").read_bytes()
    envelope = parse_json(raw)
    events_path = artifact("generated/medical_review/streams/events.jsonl")
    events = [
        parse_json(line.encode()) for line in events_path.read_text().splitlines() if line.strip()
    ]
    messages = [
        ev["item"]["text"]
        for ev in events
        if ev.get("type") == "item.completed" and ev.get("item", {}).get("type") == "agent_message"
    ]
    if (
        not events
        or events[-1].get("type") != "turn.completed"
        or sum(ev.get("type") == "turn.completed" for ev in events) != 1
        or any(ev.get("type") in ("turn.failed", "error") for ev in events)
        or not messages
        or parse_json(messages[-1].encode()) != envelope
    ):
        raise ValueError("Recovery requires a completed stream matching the saved generation.")
    validate_generation(repo, envelope, bundle, packet, version=2)
    return manifest, bundle, packet, envelope, raw, observed_metadata(events_path)


def _version():
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path(__file__).parent.glob("*.py"))
    }


def load_recovery_layer(repo, run, manifest, *, depth=0):
    """Reconstruct recovery and detect altered parents, mappings, imports or spans."""
    from research_project.medical_review.audit import load_dossier

    settings = manifest["effective_settings"]
    if (
        run.name != "codex-recovery-" + content_hash(settings)[:32]
        or settings.get("transform_version") != 2
    ):
        raise ValueError("Recovery identity or transformation version changed.")
    for name, digest in settings["code_hashes"].items():
        archive = recorded_artifact(repo, run, manifest, "generated/medical_review/code/" + name)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError("Recovery code archive changed.")
    parent = private_path(repo, Path(settings["parent_run"]), PRIVATE_RUNS)
    parent_manifest, bundle, packet, envelope, raw, runtime = _parent(repo, parent)
    lineage = read_json(
        recorded_artifact(repo, run, manifest, "generated/medical_review/recovery_lineage.json")
    )
    if (
        manifest["status"] != "completed"
        or settings.get("allow_llm") is not False
        or settings.get("offline") is not True
        or content_hash(parent_manifest) != settings["parent_manifest_sha256"]
        or lineage.get("schema_version") != "medical_codex_recovery_v1"
        or lineage.get("generation_sha256") != hashlib.sha256(raw).hexdigest()
        or lineage.get("packet_sha256")
        != hashlib.sha256(
            recorded_artifact(
                repo, parent, parent_manifest, "generated/medical_review/streams/stdin.txt"
            ).read_bytes()
        ).hexdigest()
        or lineage.get("citation_transform")
        != normalize_citations(envelope["review"], content_hash(envelope))[1]
    ):
        raise ValueError("Recovery lineage or transformation changed.")
    imported = private_path(repo, Path(lineage["import_run"]), PRIVATE_RUNS)
    dossier = load_dossier(repo, imported, _depth=depth + 1)
    if (
        content_hash(dossier["manifest"]) != lineage["import_manifest_sha256"]
        or read_json(
            recorded_artifact(
                repo, imported, dossier["manifest"], "generated/medical_review/raw/reviewer.json"
            )
        )
        != derived_payload(envelope, version=2)
        or dossier["bundle"] != bundle
    ):
        raise ValueError("Recovery derived import changed.")
    expected = reading_proposals(
        dossier["proposals"],
        envelope,
        bundle,
        packet,
        envelope_sha256=lineage["generation_sha256"],
        packet_sha256=lineage["packet_sha256"],
        runtime=runtime,
        version=2,
    )
    if (
        read_json(recorded_artifact(repo, run, manifest, "processed/medical_review/proposals.json"))
        != expected
    ):
        raise ValueError("Recovery scoped proposals or citation spans changed.")
    return {
        **dossier,
        "run_root": run,
        "manifest": manifest,
        "proposal_run_root": run,
        "proposals": expected,
        "lineage": [*dossier["lineage"], str(parent.relative_to(repo)), str(run.relative_to(repo))],
        "reading_execution": {
            "operation": "offline_recovery",
            "parent_run": str(parent.relative_to(repo)),
            "parent_status": parent_manifest["status"],
            "generation_sha256": lineage["generation_sha256"],
            "packet_sha256": lineage["packet_sha256"],
            "runtime_observed": runtime,
            "new_model_calls": 0,
            "requested": {
                "model": parent_manifest["effective_settings"]["requested_model"],
                "reasoning": "max",
            },
            "original_reviewer_executed": False,
        },
    }


def import_codex(repo_root: Path, from_run: Path) -> Path:
    """Import an already authorized saved response offline; keep its failed run unchanged."""
    repo = repo_root.resolve()
    parent = private_path(repo, from_run, PRIVATE_RUNS)
    manifest, bundle, packet, envelope, raw, runtime = _parent(repo, parent)
    settings = {
        "medical_codex_recovery_key": True,
        "parent_run": str(parent.relative_to(repo)),
        "parent_manifest_sha256": content_hash(manifest),
        "transform_version": 2,
        "code_hashes": _version(),
        "offline": True,
        "allow_llm": False,
        "allow_web_search": False,
        "new_model_calls": 0,
    }
    key = content_hash(settings)
    run_id = "codex-recovery-" + key[:32]
    output = repo / PRIVATE_RUNS
    destination = private_path(repo, output / bundle["study_id"] / run_id, PRIVATE_RUNS)
    if destination.exists():
        load_recovery_layer(repo, destination, validate_run_artifacts(repo, destination))
        return destination
    inputs = private_path(
        repo, PRIVATE_SOURCES / bundle["study_id"] / "codex_recovery" / key, PRIVATE_SOURCES
    )
    for name, value in [
        ("bundle.json", bundle),
        ("reviewer.json", derived_payload(envelope, version=2)),
    ]:
        path = inputs / name
        if path.exists():
            if read_json(path) != value:
                raise ValueError("Immutable recovery input changed.")
        else:
            write_json(path, value)
    imported = import_reviewer(repo, inputs / "bundle.json", inputs / "reviewer.json")
    run, manifest_path = create_run(
        repo_root=repo,
        output_root=output,
        study_id=bundle["study_id"],
        categories=["medical_review"],
        config_path=inputs / "bundle.json",
        input_paths=[parent / "run_manifest.json"],
        run_id=run_id,
        settings=settings,
    )
    try:
        packet_hash = bundle["codex_packet"]["packet_sha256"]
        lineage = {
            "schema_version": "medical_codex_recovery_v1",
            "generation_sha256": hashlib.sha256(raw).hexdigest(),
            "packet_sha256": packet_hash,
            "citation_transform": normalize_citations(envelope["review"], content_hash(envelope))[
                1
            ],
            "import_run": str(imported.relative_to(repo)),
            "import_manifest_sha256": content_hash(read_json(imported / "run_manifest.json")),
        }
        proposals = reading_proposals(
            read_json(imported / "processed/medical_review/proposals.json"),
            envelope,
            bundle,
            packet,
            envelope_sha256=lineage["generation_sha256"],
            packet_sha256=packet_hash,
            runtime=runtime,
            version=2,
        )
        for name, value in [
            ("generated/medical_review/recovery_lineage.json", lineage),
            ("processed/medical_review/proposals.json", proposals),
        ]:
            path = run / name
            write_json(path, value)
            update_run(manifest_path, artifact=str(path))
        for name in settings["code_hashes"]:
            path = run / "generated/medical_review/code" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(Path(__file__).with_name(name).read_bytes())
            update_run(manifest_path, artifact=str(path))
        if (
            content_hash(validate_run_artifacts(repo, parent)) != settings["parent_manifest_sha256"]
            or _version() != settings["code_hashes"]
        ):
            raise ValueError("Parent run or recovery code changed during import.")
        update_run(manifest_path, stage="import-codex", status="completed")
        update_run(manifest_path, status="completed")
        load_recovery_layer(repo, run, validate_run_artifacts(repo, run))
    except Exception as error:
        update_run(manifest_path, status="failed", error=str(error))
        raise
    return run
