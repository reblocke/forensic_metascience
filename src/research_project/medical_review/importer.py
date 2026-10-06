"""Lossless, offline import of one pinned Reviewer output contract."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from research_project.medical_review.bundle import load_bundle, resolve_source_object
from research_project.medical_review.context import build_study_context
from research_project.medical_review.preflight import structural_preflight
from research_project.medical_review.records import (
    COVERAGE_SCHEMA,
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    PROPOSAL_SCHEMA,
    REPORT_SCHEMA,
    UPSTREAM_COMMIT,
    UPSTREAM_SCHEMA_HASH,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
    validate_coverage,
    write_json,
)
from research_project.medical_review.routing import build_review_plan
from research_project.run_manifest import create_run, update_run


class IncompleteImportError(ValueError):
    """A preserved historical import needs an explicit new recovery attempt."""


def validate_upstream(payload: Any, repo_root: Path, schema_sha256: str) -> None:
    """Validate the pinned schema's small vocabulary; unknown versions fail closed."""
    if schema_sha256 != UPSTREAM_SCHEMA_HASH:
        raise ValueError("Unsupported upstream schema hash; migration requires explicit review.")
    schema_path = repo_root / "config/medical_review/upstream/reviewer_output.schema.json"
    if hashlib.sha256(schema_path.read_bytes()).hexdigest() != UPSTREAM_SCHEMA_HASH:
        raise ValueError("Pinned upstream schema hash mismatch.")
    provenance = read_json(schema_path.parent / "provenance.json")
    if provenance.get("commit") != UPSTREAM_COMMIT:
        raise ValueError("Unsupported upstream contract revision.")
    for item in provenance["files"]:
        source = schema_path.parent / item["local_path"]
        if source.parent != schema_path.parent or source.is_symlink():
            raise ValueError("Unsafe upstream provenance path.")
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Upstream provenance hash mismatch.")
    schema = read_json(schema_path)
    _validate(payload, schema, schema, "reviewer")
    ids = set()
    objects = {}
    for finding in payload["findings"]:
        if not finding["id"].strip() or finding["id"] in ids:
            raise ValueError("Duplicate finding ID or missing finding identity.")
        ids.add(finding["id"])
        source_ids = set()
        for obj in finding["source_objects"]:
            if obj["id"] in source_ids:
                raise ValueError("Duplicate source object ID in finding.")
            source_ids.add(obj["id"])
            if obj["id"] in objects and objects[obj["id"]] != obj:
                raise ValueError("Conflicting source object identity.")
            objects[obj["id"]] = obj
            if obj.get("path") and ".." in obj["path"].replace("\\", "/").split("/"):
                raise ValueError("Source reference path traversal refused.")
        for link in finding["claim_evidence_links"]:
            if not set(link["source_object_ids"]) <= source_ids:
                raise ValueError("Claim references an unknown source object.")
        if finding["assessment"] == "cannot_verify" and not finding["cannot_verify_reason"]:
            raise ValueError("Unverifiable upstream assessment requires its original reason.")


def _validate(value: Any, rule: dict[str, Any], schema: dict[str, Any], location: str) -> None:
    if "$ref" in rule:
        name = rule["$ref"].removeprefix("#/$defs/")
        return _validate(value, schema["$defs"][name], schema, location)
    if "anyOf" in rule:
        for alternative in rule["anyOf"]:
            try:
                _validate(value, alternative, schema, location)
                return
            except ValueError:
                pass
        raise ValueError(f"Unsupported upstream value at {location}.")
    types = rule.get("type")
    allowed = types if isinstance(types, list) else [types]
    predicates = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in {int, float},
        "null": value is None,
    }
    if not any(predicates.get(t, False) for t in allowed):
        raise ValueError(f"Unsupported upstream type at {location}.")
    if "enum" in rule and value not in rule["enum"]:
        raise ValueError(f"Unsupported upstream enum at {location}.")
    if isinstance(value, str) and len(value) < rule.get("minLength", 0):
        raise ValueError(f"Missing upstream text at {location}.")
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        missing = set(rule.get("required", [])) - value.keys()
        unexpected = value.keys() - properties.keys()
        if missing or (rule.get("additionalProperties") is False and unexpected):
            raise ValueError(
                f"Unexpected or missing upstream fields at {location}: "
                f"{sorted(missing | unexpected)}"
            )
        for key, child in value.items():
            _validate(child, properties[key], schema, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate(child, rule["items"], schema, f"{location}[{index}]")


def _coverage(bundle: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    missing = [
        row["source_id"]
        for row in bundle["documents"]
        if row["availability"] not in {"supplied", "not_applicable"}
    ]
    for check in plan["checks"]:
        row = {
            "schema_version": COVERAGE_SCHEMA,
            **check,
            "execution": "not_requested",
            "assessment": "cannot_verify" if check.get("required_source_gaps") else "not_assessed",
            "coverage_available": False,
            "planned_units": None,
            "inspected_units": None,
            "omitted_units": None,
            "evidence_ids": [],
            "missing_materials": missing,
            "stop_reason": "Upstream contract provides no per-check coverage records.",
        }
        validate_coverage(row)
        result.append(row)
    return result


def _proposals(
    payload: dict[str, Any],
    bundle: dict[str, Any],
    bundle_hash: str,
    run_id: str,
    raw_hash: str,
    generating_revision: str | None,
) -> list[dict[str, Any]]:
    result = []
    classes = {
        "parser_artifact": "parser_artifact",
        "cannot_verify": "unverifiable_question",
        "copyedit_issue": "optional_improvement",
        "bibliography_maintenance": "optional_improvement",
        "reference_integrity": "source_discrepancy",
        "manuscript_issue": "methodological_concern",
    }
    for finding in payload["findings"]:
        namespace = {
            "bundle_sha256": bundle_hash,
            "reviewer": payload["reviewer"],
            "paper_id": payload["paper_id"],
            "upstream_finding_id": finding["id"],
        }
        proposal = {
            "schema_version": PROPOSAL_SCHEMA,
            "proposal_id": identity("medicalproposal", namespace),
            "run_id": run_id,
            "bundle_sha256": bundle_hash,
            "context_sha256": None,
            "plan_sha256": None,
            "study_id": bundle["study_id"],
            "report_ids": [r["report_id"] for r in bundle["reports"]],
            "comparison_id": None,
            "reviewer_role": payload["reviewer"],
            "original_finding_id": finding["id"],
            "original": finding,
            "original_sha256": content_hash(finding),
            "origin": {
                "type": "upstream_import",
                "adapter_upstream_revision": UPSTREAM_COMMIT,
                "output_upstream_revision": generating_revision,
                "schema_sha256": UPSTREAM_SCHEMA_HASH,
                "raw_sha256": raw_hash,
                "raw_reference": "generated/medical_review/raw/reviewer.json",
                "model": None,
                "backend": None,
                "prompt_sha256": None,
            },
            "normalized_concern": finding["finding_summary"],
            "claim": finding["claim_text"],
            "classification": classes[finding["issue_type"]],
            "proposed_severity": finding["severity"],
            "severity_rationale": None,
            "model_confidence": finding["confidence"],
            "confidence_calibrated": False,
            "bias_direction": "unknown",
            "check_ids": [],
            "evidence_links": [
                resolve_source_object(bundle, obj) for obj in finding["source_objects"]
            ],
            "qualified_result_ids": [],
            "numeric_check_request": None,
            "repair": finding["suggested_fix"],
        }
        result.append(proposal)
    return result


def import_reviewer(
    repo_root: Path,
    bundle_path: Path,
    input_path: Path,
    *,
    schema_sha256: str = UPSTREAM_SCHEMA_HASH,
    output_root: Path | None = None,
    generating_revision: str | None = None,
    profiles: list[str] | None = None,
    attempt_suffix: str | None = None,
) -> Path:
    """Import exact bytes into one immutable private run; duplicate content reuses it."""
    repo = repo_root.resolve()
    bundle_path = private_path(repo, bundle_path, PRIVATE_SOURCES)
    bundle, bundle_hash = load_bundle(repo, bundle_path)
    context = build_study_context(bundle, bundle.get("context_fields"))
    plan = build_review_plan(bundle, context, profiles or bundle.get("profile_ids"), repo)
    preflight = structural_preflight(repo, bundle)
    incoming = private_path(repo, input_path, PRIVATE_SOURCES / bundle["study_id"])
    with incoming.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    payload = parse_json(raw)
    validate_upstream(payload, repo, schema_sha256)
    if payload["paper_id"] != bundle.get("upstream_paper_id"):
        raise ValueError("Upstream paper identity must map explicitly to the supplied bundle.")
    if generating_revision is not None and generating_revision != UPSTREAM_COMMIT:
        raise ValueError("Unverified generating revision; unsupported upstream adapter revision.")
    raw_hash = hashlib.sha256(raw).hexdigest()
    adapter_hash = _adapter_hash()
    # Include exact bytes and caller-declared origin; identical replay has one run identity.
    run_key = content_hash(
        {
            "bundle": bundle_hash,
            "raw": raw_hash,
            "generating_revision": generating_revision,
            "adapter_sha256": adapter_hash,
            "context_sha256": content_hash(context),
            "plan_sha256": content_hash(plan),
            "preflight_sha256": content_hash(preflight),
        }
    )
    run_id = f"medical-import-{run_key[:32]}"
    if attempt_suffix is not None:
        if not re.fullmatch(r"[a-z0-9]{8}", attempt_suffix):
            raise ValueError("Invalid explicit import recovery attempt identity.")
        run_id += f"-{attempt_suffix}"
    output = private_path(repo, output_root or PRIVATE_RUNS, PRIVATE_RUNS)
    destination = private_path(repo, output / bundle["study_id"] / run_id, PRIVATE_RUNS)
    proposals = _proposals(payload, bundle, bundle_hash, run_id, raw_hash, generating_revision)
    for proposal in proposals:
        proposal["context_sha256"] = content_hash(context)
        proposal["plan_sha256"] = content_hash(plan)
    origins = private_path(
        repo, PRIVATE_SOURCES / bundle["study_id"] / "import_origins", PRIVATE_SOURCES
    )
    for proposal in proposals:
        path = origins / (proposal["proposal_id"] + ".json")
        if path.exists():
            old = read_json(private_path(repo, path, PRIVATE_SOURCES))
            if (
                old.get("schema_version") != "medical_import_origin_v1"
                or old.get("proposal_id") != proposal["proposal_id"]
                or old.get("origin_id")
                != identity(
                    "medicalorigin",
                    {key: value for key, value in old.items() if key != "origin_id"},
                )
            ):
                raise ValueError("Import origin identity mismatch; historical reference corrupted.")
            if old.get("original_sha256") != proposal["original_sha256"]:
                raise ValueError(
                    "Upstream finding identity conflict; previous import remains unchanged."
                )
    if destination.exists():
        _validate_replay(destination, run_key)
        return destination
    run, manifest = create_run(
        repo_root=repo,
        output_root=output,
        study_id=bundle["study_id"],
        categories=["medical_review"],
        config_path=bundle_path,
        input_paths=[
            incoming,
            *[
                repo / row["path"]
                for row in bundle["documents"]
                if row["availability"] == "supplied"
            ],
            *[repo / row["parsed_path"] for row in bundle["evidence"]],
            repo / "config/medical_review/check_catalogue.json",
            repo / "config/medical_review/guidance_registry.json",
            *[repo / row["path"] for row in plan["prompt_sources"]],
        ],
        run_id=run_id,
        settings={
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
            "medical_import_key": run_key,
            "bundle_sha256": bundle_hash,
            "upstream_schema_sha256": UPSTREAM_SCHEMA_HASH,
            "raw_sha256": raw_hash,
            "adapter_sha256": adapter_hash,
            "plan_sha256": content_hash(plan),
            "context_sha256": content_hash(context),
        },
    )
    try:
        raw_path = run / "generated/medical_review/raw/reviewer.json"
        raw_path.parent.mkdir(parents=True)
        with raw_path.open("xb") as stream:
            stream.write(raw)
        update_run(manifest, artifact=str(raw_path))
        if hashlib.sha256(incoming.read_bytes()).hexdigest() != raw_hash:
            raise ValueError("Upstream input changed during import; original attempt preserved.")
        _, current_bundle_hash = load_bundle(repo, bundle_path)
        if current_bundle_hash != bundle_hash:
            raise ValueError("Source bundle changed during import; original attempt preserved.")
        if _adapter_hash() != adapter_hash:
            raise ValueError("Adapter code changed during import; original attempt preserved.")
        if build_review_plan(bundle, context, profiles or bundle.get("profile_ids"), repo) != plan:
            raise ValueError("Review plan changed during import; original attempt preserved.")
        coverage = _coverage(bundle, plan)
        model = {
            "schema_version": REPORT_SCHEMA,
            "run_id": run_id,
            "bundle_sha256": bundle_hash,
            "title": "AI-assisted manuscript audit: unverified proposals",
            "scope": {"study_id": bundle["study_id"], "documents": bundle["documents"]},
            "study_context": context,
            "review_plan": plan,
            "parser_preflight": preflight,
            "proposals": proposals,
            "coverage": coverage,
            "human_status": "pending",
            "official_assessment": None,
            "verification": [],
            "human_dispositions": [],
            "import_status": "completed",
            "upstream_run_status": payload["run_status"],
            "review_coverage_available": False,
            "original_summary": payload["summary"],
            "original_notes": payload["notes"],
        }
        for name, value in (
            ("bundle.json", bundle),
            ("study_context.json", context),
            ("review_plan.json", plan),
            ("parser_preflight.json", preflight),
            ("coverage.json", coverage),
            ("proposals.json", proposals),
            ("report_model.json", model),
        ):
            path = run / "processed/medical_review" / name
            write_json(path, value)
            update_run(manifest, artifact=str(path))
        for proposal in proposals:
            path = origins / (proposal["proposal_id"] + ".json")
            if not path.exists():
                origin = {
                    "schema_version": "medical_import_origin_v1",
                    "proposal_id": proposal["proposal_id"],
                    "original_sha256": proposal["original_sha256"],
                    "first_run_id": run_id,
                }
                write_json(path, {**origin, "origin_id": identity("medicalorigin", origin)})
        update_run(manifest, stage="import-reviewer", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def _adapter_hash() -> str:
    package = Path(__file__).resolve().parent
    paths = [
        package / name
        for name in (
            "records.py",
            "bundle.py",
            "importer.py",
            "context.py",
            "routing.py",
            "preflight.py",
        )
    ]
    paths += [package.parent / "run_manifest.py", package.parent / "inspect_sr/records.py"]
    return content_hash([hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])


def _validate_replay(run: Path, key: str) -> None:
    manifest_path = run / "run_manifest.json"
    if manifest_path.is_symlink() or run.resolve() not in manifest_path.resolve().parents:
        raise ValueError("Unsafe import manifest symlink; replay refused.")
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema_version") != "forensics_run_v3"
        or manifest.get("status") != "completed"
    ):
        raise IncompleteImportError(
            "Historical import is incomplete; preserve it for explicit recovery."
        )
    if manifest.get("effective_settings", {}).get("medical_import_key") != key:
        raise ValueError("Import identity conflicts with the existing run.")
    required = {
        "generated/medical_review/raw/reviewer.json",
        *(
            f"processed/medical_review/{name}.json"
            for name in (
                "bundle",
                "study_context",
                "review_plan",
                "parser_preflight",
                "coverage",
                "proposals",
                "report_model",
            )
        ),
    }
    artifacts = manifest.get("artifacts", [])
    if not required <= {row.get("path") for row in artifacts}:
        raise ValueError("Import artifact receipt is incomplete.")
    for artifact in artifacts:
        relative = Path(artifact["path"])
        path = run / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or run.resolve() not in path.resolve().parents
        ):
            raise ValueError("Unsafe import artifact reference.")
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]
        ):
            raise ValueError("Completed import artifact hash mismatch; replay refused.")
