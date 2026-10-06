"""Immutable verification lineage and separate, write-once private human decisions."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.bundle import validate_bundle
from research_project.medical_review.importer import _proposals, validate_upstream
from research_project.medical_review.numeric import calculate_request, scoped_evidence_ids
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    UPSTREAM_SCHEMA_HASH,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    write_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

VERIFICATION_FIELDS = {
    "proposal_id",
    "disposition",
    "reviewed_claim",
    "strongest_alternative",
    "rationale",
    "supporting_evidence_ids",
    "contradicting_evidence_ids",
    "missing_materials",
    "change_summary",
    "model",
    "backend",
    "prompt_sha256",
}
HUMAN_FIELDS = {
    "schema_version",
    "proposal_id",
    "disposition",
    "human_identity",
    "date",
    "rationale",
    "reviewed_evidence",
    "source_bytes_reviewed",
    "locators_reviewed",
    "supersedes",
}
DISPOSITIONS = {"pending", "confirmed_concern", "dismissed", "unresolved", "optional_improvement"}
MODEL_DISPOSITIONS = {
    "supported_candidate",
    "contradicted",
    "already_addressed",
    "optional_extension",
    "unresolved",
}


def _exact(record: Any, fields: set[str], label: str) -> None:
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError(f"Unsupported {label} contract fields.")


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be explicit nonblank text.")


def validate_record_identity(record: dict[str, Any], field: str, prefix: str) -> None:
    if record.get(field) != identity(prefix, {k: v for k, v in record.items() if k != field}):
        raise ValueError("Medical record content identity mismatch.")


def _unique_records(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    """Keep identical content references once without discarding their run lineage."""
    unique = {}
    for record in records:
        key = record[field]
        if key in unique and unique[key] != record:
            raise ValueError("Conflicting medical record content identity.")
        unique[key] = record
    return list(unique.values())


def validate_run_artifacts(
    repo: Path, run: Path, *, boundary: Path = PRIVATE_RUNS
) -> dict[str, Any]:
    """Inspect exact registered private artifacts, never discover a newest run."""
    run = private_path(repo, run, boundary)
    manifest = read_json(private_path(repo, run / "run_manifest.json", boundary))
    if manifest.get("schema_version") != "forensics_run_v3" or manifest.get("run_id") != run.name:
        raise ValueError("Medical run manifest identity mismatch.")
    if manifest.get("status") not in {"completed", "failed"}:
        raise ValueError("Medical run is nonterminal; a report snapshot cannot assume completion.")
    expected = hashlib.sha256(
        json.dumps(manifest["effective_settings"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if manifest.get("effective_settings_sha256") != expected:
        raise ValueError("Run effective-settings hash mismatch.")
    paths = set()
    for row in manifest.get("artifacts", []):
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) in paths:
            raise ValueError("Unsafe or duplicate registered artifact path.")
        artifact = private_path(repo, run / relative, boundary)
        if run not in artifact.parents or sha256_file(artifact) != row["sha256"]:
            raise ValueError("Registered medical artifact hash mismatch.")
        paths.add(str(relative))
    if not paths:
        raise ValueError("Medical run has no artifact receipts.")
    return manifest


def recorded_artifact(
    repo: Path, run: Path, manifest: dict[str, Any], relative: str, *, boundary: Path = PRIVATE_RUNS
) -> Path:
    if relative not in {r["path"] for r in manifest["artifacts"]}:
        raise ValueError("Required medical artifact receipt is missing.")
    return private_path(repo, run / relative, boundary)


def load_dossier(repo_root: Path, run_path: Path, *, _depth: int = 0) -> dict[str, Any]:
    """Load an explicitly named historical dossier with verified canonical lineage."""
    if _depth > 20:
        raise ValueError("Medical lineage exceeds the supported bounded depth.")
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]

    def load(name):
        return read_json(
            recorded_artifact(repo, run, manifest, f"processed/medical_review/{name}.json")
        )

    if settings.get("medical_consolidation_key"):
        parents = []
        for row in settings["source_runs"]:
            parent = load_dossier(repo, Path(row["reference"]), _depth=_depth + 1)
            if content_hash(parent["manifest"]) != row["manifest_sha256"]:
                raise ValueError("Consolidation parent manifest changed.")
            parents.append(parent)
        combined = _combined_dossier(parents, repo)
        if load("bundle") != combined["bundle"] or load("proposals") != combined["proposals"]:
            raise ValueError("Consolidated original source/proposal traceability changed.")
        return {
            **combined,
            "run_root": run,
            "manifest": manifest,
            "lineage": [*combined["lineage"], str(run.relative_to(repo))],
        }

    if settings.get("medical_verification_key"):
        parent = private_path(repo, Path(settings["source_run_reference"]), PRIVATE_RUNS)
        dossier = load_dossier(repo, parent, _depth=_depth + 1)
        if settings["source_manifest_sha256"] != content_hash(dossier["manifest"]):
            raise ValueError("Verification parent manifest changed.")
        if manifest["status"] == "failed":
            return {
                **dossier,
                "run_root": run,
                "manifest": manifest,
                "lineage": [*dossier["lineage"], str(run.relative_to(repo))],
                "failures": [*dossier.get("failures", []), manifest.get("error", "Failed pass")],
            }
        records = load("verification")
        for record in records:
            _validate_verification_record(record, dossier)
        arithmetic = load("arithmetic_results")
        for result in arithmetic:
            validate_record_identity(result, "result_id", "medicalarithmetic")
            expected = calculate_request(result["request"], dossier["bundle"])
            if result["calculator"]["source_sha256"] == expected["calculator"]["source_sha256"]:
                if result != expected:
                    raise ValueError("Arithmetic output differs from its bound calculator.")
            else:
                archived = recorded_artifact(
                    repo, run, manifest, "generated/medical_review/code/numeric.py"
                )
                if (
                    hashlib.sha256(archived.read_bytes()).hexdigest()
                    != result["calculator"]["source_sha256"]
                ):
                    raise ValueError("Historical calculator archive hash mismatch.")
                if (
                    set(result) != set(expected)
                    or result["request_sha256"] != expected["request_sha256"]
                    or result["qualified_method_result"] is not False
                    or result["inspect_sr_candidate_eligible"] is not False
                    or result["input_verification"] != "proposed_transcription"
                ):
                    raise ValueError("Historical arithmetic contract/authority mismatch.")
        handoffs = []
        handoff_path = "processed/medical_review/method_handoffs.json"
        if "method_handoffs_requested" in settings or handoff_path in {
            r["path"] for r in manifest["artifacts"]
        }:
            from research_project.medical_review.method_handoffs import validate_method_handoff

            handoffs = load("method_handoffs")
            for handoff in handoffs:
                validate_method_handoff(repo, dossier, handoff)
        arithmetic_references = [*dossier["arithmetic_results"], *arithmetic]
        method_references = [*dossier.get("method_handoffs", []), *handoffs]
        if settings.get("record_references_unique") is True:
            arithmetic_references = _unique_records(arithmetic_references, "result_id")
            method_references = _unique_records(method_references, "handoff_id")
        return {
            **dossier,
            "run_root": run,
            "manifest": manifest,
            "verification": [*dossier["verification"], *records],
            "arithmetic_results": arithmetic_references,
            "method_handoffs": method_references,
            "lineage": [*dossier["lineage"], str(run.relative_to(repo))],
        }
    if settings.get("medical_report_key"):
        parent = private_path(repo, Path(settings["source_run_reference"]), PRIVATE_RUNS)
        dossier = load_dossier(repo, parent, _depth=_depth + 1)
        if settings["source_manifest_sha256"] != content_hash(dossier["manifest"]):
            raise ValueError("Report parent manifest changed.")
        if manifest["status"] == "completed":
            from research_project.medical_review.reporting import validate_report_model

            model = load("report_model")
            archived = recorded_artifact(
                repo, run, manifest, "generated/medical_review/code/reporting.py"
            )
            if hashlib.sha256(archived.read_bytes()).hexdigest() != model[
                "renderer_source_sha256"
            ] or (
                settings["report_model_sha256"] != content_hash(model)
                or settings["report_code_sha256"] != model["renderer_source_sha256"]
            ):
                raise ValueError("Report model or renderer archive binding changed.")
            validate_report_model(model, dossier)
        return {
            **dossier,
            "run_root": run,
            "manifest": manifest,
            "lineage": [*dossier["lineage"], str(run.relative_to(repo))],
            "failures": [
                *dossier.get("failures", []),
                *(
                    [manifest.get("error", "Failed render")]
                    if manifest["status"] == "failed"
                    else []
                ),
            ],
        }
    if settings.get("execution_mode"):
        result = read_json(
            recorded_artifact(repo, run, manifest, "generated/medical_review/attempt_result.json")
        )
        validate_record_identity(result, "attempt_id", "medicalattempt")
        if result.get("import_run_reference"):
            parent = private_path(repo, Path(result["import_run_reference"]), PRIVATE_RUNS)
            dossier = load_dossier(repo, parent, _depth=_depth + 1)
            if settings.get("bundle_sha256") != content_hash(dossier["bundle"]):
                raise ValueError("Replay import bundle binding changed.")
            return {
                **dossier,
                "run_root": run,
                "manifest": manifest,
                "lineage": [*dossier["lineage"], str(run.relative_to(repo))],
            }
        bundle, context, plan, coverage = [
            load(k) for k in ("bundle", "study_context", "review_plan", "coverage")
        ]
        validate_bundle(repo, bundle)
        return {
            "run_root": run,
            "manifest": manifest,
            "bundle": bundle,
            "study_context": context,
            "review_plan": plan,
            "coverage": coverage,
            "proposals": [],
            "verification": [],
            "arithmetic_results": [],
            "method_handoffs": [],
            "parser_preflight": None,
            "lineage": [str(run.relative_to(repo))],
            "repo_root": repo,
            "upstream_metadata": {},
            "failures": [manifest["error"]] if manifest.get("error") else [],
        }
    if not settings.get("medical_import_key"):
        raise ValueError("Unsupported medical dossier run type.")
    bundle, context, plan, proposals, coverage = [
        load(k) for k in ("bundle", "study_context", "review_plan", "proposals", "coverage")
    ]
    validate_bundle(repo, bundle)
    raw = recorded_artifact(
        repo, run, manifest, "generated/medical_review/raw/reviewer.json"
    ).read_bytes()
    payload = parse_json(raw)
    validate_upstream(payload, repo, UPSTREAM_SCHEMA_HASH)
    declared_origin = proposals[0]["origin"]["output_upstream_revision"] if proposals else None
    expected = _proposals(
        payload,
        bundle,
        content_hash(bundle),
        run.name,
        hashlib.sha256(raw).hexdigest(),
        declared_origin,
    )
    for proposal in expected:
        proposal["context_sha256"] = content_hash(context)
        proposal["plan_sha256"] = content_hash(plan)
    if proposals != expected:
        raise ValueError("Original imported proposal contract or authority changed.")
    return {
        "run_root": run,
        "manifest": manifest,
        "bundle": bundle,
        "study_context": context,
        "review_plan": plan,
        "proposals": proposals,
        "coverage": coverage,
        "parser_preflight": load("parser_preflight"),
        "verification": [],
        "arithmetic_results": [],
        "method_handoffs": [],
        "lineage": [str(run.relative_to(repo))],
        "proposal_run_root": run,
        "repo_root": repo,
        "upstream_metadata": {k: v for k, v in payload.items() if k != "findings"},
        "failures": [],
    }


def _proposal(dossier: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    matches = [p for p in dossier["proposals"] if p["proposal_id"] == proposal_id]
    if len(matches) != 1:
        raise ValueError("Verification requires one original known proposal.")
    return matches[0]


def _proposal_reference(dossier: dict[str, Any], proposal_id: str) -> str:
    references = dossier.get("proposal_run_references", {})
    if proposal_id in references:
        return references[proposal_id]
    return str(dossier["proposal_run_root"].relative_to(dossier["repo_root"]))


def _combined_dossier(dossiers: list[dict[str, Any]], repo: Path) -> dict[str, Any]:
    if not 2 <= len(dossiers) <= 16:
        raise ValueError("Consolidation requires 2–16 explicit source runs.")
    if any(d.get("proposal_run_references") for d in dossiers):
        raise ValueError(
            "Nested consolidation is unsupported; select explicit original review branches."
        )
    first = dossiers[0]
    for dossier in dossiers[1:]:
        for key in ("bundle", "study_context", "review_plan", "parser_preflight"):
            if dossier[key] != first[key]:
                raise ValueError(
                    "Consolidation requires identical bundle/context/plan/preflight snapshots."
                )
    proposals = {}
    references = {}
    for dossier in dossiers:
        for proposal in dossier["proposals"]:
            key = proposal["proposal_id"]
            if key in proposals and proposals[key] != proposal:
                raise ValueError("Conflicting original proposal identity in consolidation.")
            proposals[key] = proposal
            references[key] = _proposal_reference(dossier, key)
    return {
        **first,
        "proposals": list(proposals.values()),
        "proposal_run_references": references,
        "coverage": [
            {**row, "review_run_reference": str(d["run_root"].relative_to(repo))}
            for d in dossiers
            for row in d["coverage"]
        ],
        "verification": list(
            {r["verification_id"]: r for d in dossiers for r in d["verification"]}.values()
        ),
        "arithmetic_results": _unique_records(
            [r for d in dossiers for r in d["arithmetic_results"]], "result_id"
        ),
        "method_handoffs": _unique_records(
            [r for d in dossiers for r in d.get("method_handoffs", [])], "handoff_id"
        ),
        "failures": [r for d in dossiers for r in d.get("failures", [])],
        "lineage": list(dict.fromkeys(r for d in dossiers for r in d["lineage"])),
        "upstream_metadata": {
            "contributing_reviews": [
                {
                    "run_reference": str(d["run_root"].relative_to(repo)),
                    "metadata": d.get("upstream_metadata", {}),
                }
                for d in dossiers
            ]
        },
    }


def consolidate_reviews(repo_root: Path, source_runs: list[Path]) -> Path:
    """Consolidate explicitly named compatible review snapshots without evidence multiplication."""
    repo = repo_root.resolve()
    if not 2 <= len(source_runs) <= 16:
        raise ValueError("Consolidation requires 2–16 explicit source runs.")
    dossiers = [load_dossier(repo, p) for p in source_runs]
    if len({d["run_root"] for d in dossiers}) != len(dossiers):
        raise ValueError("Duplicate source run in consolidation.")
    combined = _combined_dossier(dossiers, repo)
    if (
        len(json.dumps(combined["proposals"], ensure_ascii=False, indent=2).encode())
        > MAX_JSON_BYTES
    ):
        raise ValueError("Consolidated proposals exceed 20 MiB; bounded splitting required.")
    binding = {
        "source_runs": [
            {
                "reference": str(d["run_root"].relative_to(repo)),
                "manifest_sha256": content_hash(d["manifest"]),
            }
            for d in dossiers
        ]
    }
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=combined["bundle"]["study_id"],
        categories=["medical_review"],
        config_path=dossiers[0]["run_root"] / "processed/medical_review/bundle.json",
        input_paths=[],
        settings={
            **binding,
            "medical_consolidation_key": content_hash(binding),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        for key in ("bundle", "proposals"):
            path = run / f"processed/medical_review/{key}.json"
            write_json(path, combined[key])
            update_run(manifest, artifact=str(path))
        for row in binding["source_runs"]:
            current = load_dossier(repo, Path(row["reference"]))
            if content_hash(current["manifest"]) != row["manifest_sha256"]:
                raise ValueError("Consolidation parent changed during execution.")
        update_run(manifest, stage="medical-consolidation", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def _ids(ids: Any, known: set[str], label: str) -> None:
    if (
        not isinstance(ids, list)
        or any(not isinstance(x, str) for x in ids)
        or not set(ids) <= known
    ):
        raise ValueError(f"Unknown or unscoped {label} evidence.")


def _verification(row: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    _exact(row, VERIFICATION_FIELDS, "model verification")
    proposal = _proposal(dossier, row["proposal_id"])
    if row["disposition"] not in MODEL_DISPOSITIONS:
        raise ValueError("Unsupported model verification disposition.")
    if row["reviewed_claim"] != proposal["claim"]:
        raise ValueError("Verification must preserve the implicated original claim.")
    for field in ("strongest_alternative", "rationale", "change_summary"):
        _text(row[field], field)
    known = scoped_evidence_ids(proposal, dossier["bundle"])
    for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
        _ids(row[field], known, field)
    if row["disposition"] == "supported_candidate" and not row["supporting_evidence_ids"]:
        raise ValueError("Supported verification requires cited supporting evidence.")
    if (
        row["disposition"] in {"contradicted", "already_addressed"}
        and not row["contradicting_evidence_ids"]
    ):
        raise ValueError(
            "Demotion requires cited counterevidence, not an unsupported model assertion."
        )
    if not isinstance(row["missing_materials"], list) or any(
        not isinstance(x, str) for x in row["missing_materials"]
    ):
        raise ValueError("Missing verification materials must be explicit.")
    for field in ("model", "backend"):
        if row[field] is not None:
            _text(row[field], field)
    if row["prompt_sha256"] is not None and not re.fullmatch(
        r"[a-f0-9]{64}", str(row["prompt_sha256"])
    ):
        raise ValueError("Verification prompt hash is invalid.")
    record = {
        "schema_version": "medical_verification_v1",
        **copy.deepcopy(row),
        "original_proposal_sha256": content_hash(proposal),
        "original_run_id": proposal["run_id"],
        "original_proposal_run_reference": _proposal_reference(dossier, proposal["proposal_id"]),
        "bundle_sha256": content_hash(dossier["bundle"]),
        "origin": "offline_supplied_counterevidence",
        "independently_human_confirmed": False,
    }
    return {**record, "verification_id": identity("medicalverification", record)}


def _validate_verification_record(record: dict[str, Any], dossier: dict[str, Any]) -> None:
    row = {k: record[k] for k in VERIFICATION_FIELDS}
    if _verification(row, dossier) != record:
        raise ValueError("Verification record content/authority changed.")


def verify_review(repo_root: Path, source_run: Path, input_path: Path) -> Path:
    """Append an offline verification pass as a fresh run, never mutate its parent."""
    repo = repo_root.resolve()
    dossier = load_dossier(repo, source_run)
    path = private_path(repo, input_path, PRIVATE_SOURCES / dossier["bundle"]["study_id"])
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    data = parse_json(raw)
    fields = {"schema_version", "counterevidence", "numeric_requests"}
    if isinstance(data, dict) and "method_handoffs" in data:
        fields.add("method_handoffs")
    _exact(data, fields, "verification input")
    if data["schema_version"] != "medical_verification_input_v1":
        raise ValueError("Unsupported verification input schema.")
    if not isinstance(data["counterevidence"], list) or not isinstance(
        data["numeric_requests"], list
    ):
        raise ValueError("Verification proposals/requests must be lists.")
    records = [_verification(row, dossier) for row in data["counterevidence"]]
    if len({r["proposal_id"] for r in records}) != len(records):
        raise ValueError("A verification pass has duplicate proposal dispositions.")
    arithmetic = []
    for request in data["numeric_requests"]:
        proposal = _proposal(dossier, request["proposal_id"])
        if (
            request["run_id"] != proposal["run_id"]
            or request["study_id"] != proposal["study_id"]
            or request["comparison_id"] != proposal["comparison_id"]
        ):
            raise ValueError("Numeric request must bind the original proposal run and scope.")
        arithmetic.append(calculate_request(request, dossier["bundle"]))
    if len({r["request_sha256"] for r in arithmetic}) != len(arithmetic):
        raise ValueError("Duplicate numerical request in verification pass.")
    from research_project.medical_review.method_handoffs import build_method_handoff

    requests = data.get("method_handoffs", [])
    if not isinstance(requests, list) or len(requests) > 64:
        raise ValueError(
            "Verification method handoffs require a bounded list of at most 64 requests."
        )
    handoffs = [build_method_handoff(repo, dossier, row) for row in requests]
    if len({r["handoff_id"] for r in handoffs}) != len(handoffs):
        raise ValueError("Duplicate numerical handoff in verification pass.")
    for value in (records, arithmetic, handoffs):
        if len(json.dumps(value, ensure_ascii=False, indent=2).encode()) > MAX_JSON_BYTES:
            raise ValueError(
                "Verification artifacts exceed 20 MiB; explicit bounded splitting required."
            )
    package = Path(__file__).parent
    code_sources = {
        name: package / name for name in ("audit.py", "numeric.py", "method_handoffs.py")
    }
    if handoffs:
        code_sources.update(
            {
                "inspect_sr_adapters.py": package.parent / "inspect_sr/adapters.py",
                "inspect_sr_records.py": package.parent / "inspect_sr/records.py",
            }
        )
    code_bytes = {name: source.read_bytes() for name, source in code_sources.items()}
    code_hash = content_hash(
        {name: hashlib.sha256(raw_code).hexdigest() for name, raw_code in code_bytes.items()}
    )
    binding = {
        "source_manifest_sha256": content_hash(dossier["manifest"]),
        "source_run_reference": str(dossier["run_root"].relative_to(repo)),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "code_sha256": code_hash,
    }
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=dossier["bundle"]["study_id"],
        categories=["medical_review"],
        config_path=dossier["run_root"] / "processed/medical_review/bundle.json",
        input_paths=[path],
        settings={
            **binding,
            "medical_verification_key": content_hash(binding),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
            "method_handoffs_requested": len(requests),
            "record_references_unique": True,
        },
    )
    try:
        raw_path = run / "generated/medical_review/raw/verification_input.json"
        raw_path.parent.mkdir(parents=True)
        with raw_path.open("xb") as stream:
            stream.write(raw)
        update_run(manifest, artifact=str(raw_path))
        for name, raw_code in code_bytes.items():
            code_path = run / "generated/medical_review/code" / name
            code_path.parent.mkdir(parents=True, exist_ok=True)
            with code_path.open("xb") as stream:
                stream.write(raw_code)
            update_run(manifest, artifact=str(code_path))
        if (
            content_hash(load_dossier(repo, source_run)["manifest"])
            != binding["source_manifest_sha256"]
        ):
            raise ValueError("Verification parent changed during execution.")
        if path.read_bytes() != raw or any(
            code_sources[name].read_bytes() != value for name, value in code_bytes.items()
        ):
            raise ValueError("Verification input or code changed during execution.")
        from research_project.medical_review.method_handoffs import validate_method_handoff

        for handoff in handoffs:
            validate_method_handoff(repo, dossier, handoff)
        for name, value in [
            ("bundle", dossier["bundle"]),
            ("verification", records),
            ("arithmetic_results", arithmetic),
            ("method_handoffs", handoffs),
        ]:
            artifact = run / f"processed/medical_review/{name}.json"
            write_json(artifact, value)
            update_run(manifest, artifact=str(artifact))
        update_run(manifest, stage="medical-verification", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def _human_record(data: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    _exact(data, HUMAN_FIELDS, "human disposition")
    if (
        data["schema_version"] != "medical_human_disposition_input_v1"
        or data["disposition"] not in DISPOSITIONS
    ):
        raise ValueError("Unsupported human disposition schema/status.")
    for field in ("human_identity", "date", "rationale"):
        _text(data[field], field)
    try:
        timestamp = datetime.fromisoformat(data["date"])
    except ValueError as error:
        raise ValueError("Human date requires an ISO timestamp.") from error
    if timestamp.tzinfo is None:
        raise ValueError("Human date must include timezone precision.")
    if data["source_bytes_reviewed"] is not True or data["locators_reviewed"] is not True:
        raise ValueError("Independent source/locator review requires explicit human attestation.")
    proposal = _proposal(dossier, data["proposal_id"])
    rows = data["reviewed_evidence"]
    known = scoped_evidence_ids(proposal, dossier["bundle"])
    if not isinstance(rows, list) or not rows:
        raise ValueError("Human disposition requires reviewed source evidence.")
    seen = set()
    for row in rows:
        _exact(row, {"evidence_id", "source_sha256", "locator", "raw_value"}, "reviewed evidence")
        if row["evidence_id"] not in known or row["evidence_id"] in seen:
            raise ValueError("Human record evidence identity is unknown, unscoped or duplicated.")
        evidence = next(
            e for e in dossier["bundle"]["evidence"] if e["evidence_id"] == row["evidence_id"]
        )
        doc = next(
            d
            for d in dossier["bundle"]["documents"]
            if d.get("source_version_id") == evidence["source_version_id"]
        )
        if (
            row["source_sha256"] != doc["sha256"]
            or row["locator"] != evidence["locator"]
            or row["raw_value"] != evidence["raw_value"]
        ):
            raise ValueError(
                "Human reviewed source hash/locator/evidence quotation does not match."
            )
        seen.add(row["evidence_id"])
    if data["supersedes"] is not None and not re.fullmatch(
        r"medicalhuman_[a-f0-9]{64}", str(data["supersedes"])
    ):
        raise ValueError("Invalid human supersession identity.")
    record = {
        **copy.deepcopy(data),
        "schema_version": "medical_human_disposition_v1",
        "original_proposal_sha256": content_hash(proposal),
        "original_origin": proposal["origin"],
        "original_run_id": proposal["run_id"],
        "original_proposal_run_reference": _proposal_reference(dossier, proposal["proposal_id"]),
        "bundle_sha256": content_hash(dossier["bundle"]),
        "record_type": "operator_attested_human_decision",
        "official_assessment": None,
    }
    return {**record, "disposition_id": identity("medicalhuman", record)}


def load_human_history(repo: Path, dossier: dict[str, Any]) -> list[dict[str, Any]]:
    root = private_path(
        repo,
        PRIVATE_SOURCES / dossier["bundle"]["study_id"] / "human_dispositions",
        PRIVATE_SOURCES,
    )
    if not root.exists():
        return []
    history = []
    originals = {}
    proposals = {p["proposal_id"]: p for p in dossier["proposals"]}
    for path in sorted(root.glob("medicalhuman_*.json")):
        record = read_json(private_path(repo, path, PRIVATE_SOURCES))
        validate_record_identity(record, "disposition_id", "medicalhuman")
        if path.stem != record["disposition_id"]:
            raise ValueError("Human disposition filename identity mismatch.")
        if record["proposal_id"] not in proposals:
            continue  # historical other bundle/proposal
        input_row = {k: record[k] for k in HUMAN_FIELDS}
        input_row["schema_version"] = "medical_human_disposition_input_v1"
        reference = record["original_proposal_run_reference"]
        if reference not in originals:
            originals[reference] = load_dossier(repo, Path(reference))
        if _human_record(input_row, originals[reference]) != record:
            raise ValueError("Human disposition source/provenance contract changed.")
        history.append(record)
    ids = {r["disposition_id"]: r for r in history}
    superseded = set()
    for record in history:
        previous = record["supersedes"]
        if previous is not None:
            if (
                previous not in ids
                or previous in superseded
                or previous == record["disposition_id"]
            ):
                raise ValueError("Human history has a missing, duplicate or cyclic supersession.")
            old = ids[previous]
            if (
                old["proposal_id"] != record["proposal_id"]
                or old["human_identity"] != record["human_identity"]
            ):
                raise ValueError("Human supersession must preserve proposal and reviewer identity.")
            superseded.add(previous)
    # Content-addressed supersession preserves history; edited hashes fail before traversal.
    return history


def validate_human_record(repo: Path, record: dict[str, Any]) -> None:
    """Validate retained source/authority fields without consulting newest decisions."""
    validate_record_identity(record, "disposition_id", "medicalhuman")
    original = load_dossier(repo, Path(record["original_proposal_run_reference"]))
    data = {k: record[k] for k in HUMAN_FIELDS}
    data["schema_version"] = "medical_human_disposition_input_v1"
    if _human_record(data, original) != record:
        raise ValueError("Human disposition source/provenance contract changed.")


def record_human_disposition(repo_root: Path, source_run: Path, data: dict[str, Any]) -> Path:
    """Operator-only write-once record; software checks attestations, not human independence."""
    repo = repo_root.resolve()
    dossier = load_dossier(repo, source_run)
    record = _human_record(data, dossier)
    root = private_path(
        repo,
        PRIVATE_SOURCES / dossier["bundle"]["study_id"] / "human_dispositions",
        PRIVATE_SOURCES,
    )
    root.mkdir(parents=True, exist_ok=True)
    lock = private_path(repo, root / ".disposition.lock", PRIVATE_SOURCES)
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        history = load_human_history(repo, dossier)
        previous = record["supersedes"]
        if previous is not None:
            matches = [r for r in history if r["disposition_id"] == previous]
            if len(matches) != 1 or any(r["supersedes"] == previous for r in history):
                raise ValueError("Human revision requires a current, nonsuperseded record.")
            if (
                matches[0]["human_identity"] != record["human_identity"]
                or matches[0]["proposal_id"] != record["proposal_id"]
            ):
                raise ValueError("A reviewer cannot supersede another identity/proposal record.")
        elif any(
            r["proposal_id"] == record["proposal_id"]
            and r["human_identity"] == record["human_identity"]
            for r in history
        ):
            raise ValueError(
                "Existing human decision requires explicit current-record supersession."
            )
        path = private_path(repo, root / (record["disposition_id"] + ".json"), PRIVATE_SOURCES)
        write_json(path, record)
    return path
