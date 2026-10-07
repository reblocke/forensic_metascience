"""Private, operator-attested source reference ledgers; never official assessments."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation import _code_sources as plan_code_sources
from research_project.medical_review.evaluation import load_evaluation_plan
from research_project.medical_review.numeric import scoped_evidence_ids
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
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

ATTESTATION_FIELDS = {
    "human_identity",
    "domain_qualifications",
    "date",
    "blinded_to_condition",
    "source_bytes_reviewed",
    "reviewed_source_version_ids",
}
ISSUE_FIELDS = {
    "study_id",
    "comparison_id",
    "issue_type",
    "important",
    "description",
    "evidence_ids",
}


def _exact(row: Any, fields: set[str], label: str) -> None:
    if not isinstance(row, dict) or set(row) != fields:
        raise ValueError(f"Unsupported evaluation reference {label} fields.")


def _text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Evaluation reference {label} requires explicit text.")


def _unique_strings(value: Any, label: str, *, nonempty: bool = False) -> None:
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or any(not isinstance(v, str) or not v.strip() for v in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"Evaluation reference {label} requires unique explicit identities.")


def _attestation(row: dict[str, Any], source_versions: set[str]) -> None:
    for field in ("human_identity", "domain_qualifications", "date"):
        _text(row[field], field)
    try:
        date = datetime.fromisoformat(row["date"])
    except ValueError as error:
        raise ValueError(
            "Evaluation reference date requires a timezone-aware timestamp."
        ) from error
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("Evaluation reference date requires a timezone-aware timestamp.")
    if row["blinded_to_condition"] is not True or row["source_bytes_reviewed"] is not True:
        raise ValueError(
            "Source reference requires explicit blinded source-byte review attestation."
        )
    _unique_strings(row["reviewed_source_version_ids"], "reviewed sources", nonempty=True)
    if set(row["reviewed_source_version_ids"]) != source_versions:
        raise ValueError("Source reference must account for every supplied source version.")


def _issue(row: dict[str, Any], bundle: dict[str, Any]) -> None:
    for field in ("description", "issue_type", "study_id"):
        _text(row[field], field)
    if row["comparison_id"] is not None:
        _text(row["comparison_id"], "comparison_id")
    if row["important"] is not None and type(row["important"]) is not bool:
        raise ValueError("Reference importance must be an explicit boolean or unknown/null.")
    _unique_strings(row["evidence_ids"], "evidence", nonempty=True)
    if not set(row["evidence_ids"]) <= scoped_evidence_ids(row, bundle):
        raise ValueError("Reference evidence is outside its reviewed study/comparison scope.")


def validate_reference_input(plan: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Preserve independent observations and explicit human resolution of every observation.

    Identities, domain qualifications, independence and blinding are operator
    attestations. Validation cannot authenticate a person or establish clinical truth.
    """
    _exact(data, {"schema_version", "plan_id", "case_reviews"}, "input")
    if data["schema_version"] != "medical_evaluation_reference_input_v1":
        raise ValueError("Unsupported evaluation reference schema.")
    if data["plan_id"] != plan["plan_id"]:
        raise ValueError("Evaluation reference plan identity mismatch.")
    if not isinstance(data["case_reviews"], list):
        raise ValueError("Evaluation reference requires explicit case review records.")
    cases = {case["case_id"]: case for case in plan["cases"]}
    seen, issues, scopes = set(), [], []
    for review in data["case_reviews"]:
        _exact(
            review, {"case_id", "assessors", "assessor_shortfall_reason", "adjudication"}, "case"
        )
        case_id = review["case_id"]
        _text(case_id, "case_id")
        if case_id not in cases or case_id in seen:
            raise ValueError("Unknown or duplicate reference case identity.")
        seen.add(case_id)
        case = cases[case_id]
        bundle = case["bundle"]
        versions = {
            d["source_version_id"] for d in bundle["documents"] if d["availability"] == "supplied"
        }
        assessors = review["assessors"]
        if not isinstance(assessors, list) or not assessors:
            raise ValueError("Source reference requires at least one explicit domain assessor.")
        if len(assessors) < 2:
            _text(review["assessor_shortfall_reason"], "assessor shortfall reason")
        elif review["assessor_shortfall_reason"] is not None:
            raise ValueError("Assessor shortfall reason is only applicable below two assessors.")
        assessor_ids, people, observations = set(), set(), {}
        for assessor in assessors:
            _exact(assessor, ATTESTATION_FIELDS | {"assessor_id", "issues"}, "assessor")
            _attestation(assessor, versions)
            _text(assessor["assessor_id"], "assessor_id")
            if assessor["assessor_id"] in assessor_ids or assessor["human_identity"] in people:
                raise ValueError("Reference assessors require distinct identities.")
            assessor_ids.add(assessor["assessor_id"])
            people.add(assessor["human_identity"])
            if not isinstance(assessor["issues"], list):
                raise ValueError(
                    "Assessor observations require an explicit array, including clean controls."
                )
            for row in assessor["issues"]:
                _exact(row, ISSUE_FIELDS | {"issue_id"}, "observation")
                _text(row["issue_id"], "issue_id")
                _issue(row, bundle)
                key = (assessor["assessor_id"], row["issue_id"])
                if key in observations:
                    raise ValueError("Duplicate assessor issue identity.")
                observations[key] = row
        adjudication = review["adjudication"]
        _exact(adjudication, ATTESTATION_FIELDS | {"rationale", "issues"}, "adjudication")
        _attestation(adjudication, versions)
        _text(adjudication["rationale"], "adjudication rationale")
        if not isinstance(adjudication["issues"], list):
            raise ValueError("Reference adjudication requires an explicit issues array.")
        accounted, reference_ids, resolved = set(), set(), []
        for row in adjudication["issues"]:
            _exact(
                row,
                ISSUE_FIELDS | {"reference_id", "disposition", "assessor_issue_refs", "rationale"},
                "adjudicated issue",
            )
            for field in ("reference_id", "rationale"):
                _text(row[field], field)
            _issue(row, bundle)
            if row["reference_id"] in reference_ids:
                raise ValueError("Duplicate adjudicated reference identity.")
            reference_ids.add(row["reference_id"])
            if row["disposition"] not in {"reference_issue", "plausible_but_wrong", "unresolved"}:
                raise ValueError("Unsupported source reference disposition.")
            if not isinstance(row["assessor_issue_refs"], list):
                raise ValueError("Reference observation membership requires an explicit array.")
            for member in row["assessor_issue_refs"]:
                _exact(member, {"assessor_id", "issue_id"}, "observation membership")
                for field in ("assessor_id", "issue_id"):
                    _text(member[field], field)
                key = (member["assessor_id"], member["issue_id"])
                if key not in observations or key in accounted:
                    raise ValueError("Unknown or multiply accounted reference observation.")
                observed = observations[key]
                if any(row[f] != observed[f] for f in ("study_id", "comparison_id")):
                    raise ValueError(
                        "Adjudication cannot redirect an observation into another study scope."
                    )
                accounted.add(key)
            evidence = {e["evidence_id"]: e for e in bundle["evidence"]}
            resolved.append(
                {
                    **copy.deepcopy(row),
                    "case_id": case_id,
                    "analysis_unit_id": case["analysis_unit_id"],
                    "source_evidence": [
                        copy.deepcopy(evidence[eid]) for eid in row["evidence_ids"]
                    ],
                }
            )
        if accounted != set(observations):
            raise ValueError("Reference adjudication must account for every assessor observation.")
        issues.extend(resolved)
        scopes.append(
            {
                "case_id": case_id,
                "analysis_unit_id": case["analysis_unit_id"],
                "status": "unresolved_source_reference"
                if any(r["disposition"] == "unresolved" for r in resolved)
                else (
                    "reference_issues_present"
                    if any(r["disposition"] == "reference_issue" for r in resolved)
                    else "no_reference_issue_in_reviewed_sources"
                ),
                "reviewed_source_version_ids": sorted(versions),
                "required_source_gaps": copy.deepcopy(
                    [
                        {
                            "check_id": r["check_id"],
                            "study_id": r["study_id"],
                            "comparison_id": r["comparison_id"],
                            "gaps": r["required_source_gaps"],
                        }
                        for r in case["review_plan"]["checks"]
                        if r["required_source_gaps"]
                    ]
                ),
                "universal_clean_claim": False,
                "independent_assessor_count": len(assessors),
                "assessor_shortfall_reason": review["assessor_shortfall_reason"],
                "independence_and_qualifications": "operator_attested_not_authenticated",
            }
        )
    if seen != set(cases):
        raise ValueError("Reference ledger must explicitly account for every planned case.")
    ledger = {
        "schema_version": "medical_evaluation_reference_ledger_v1",
        "plan_id": plan["plan_id"],
        "record_type": "operator_attested_source_reference",
        "original": copy.deepcopy(data),
        "case_reviews": copy.deepcopy(data["case_reviews"]),
        "reference_issues": issues,
        "case_reference_scope": scopes,
        "contains_synthetic_cases": any(c["synthetic"] for c in plan["cases"]),
        "reference_scope": "source_adjudicated_ledger_not_all_possible_scientific_defects",
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    ledger = {**ledger, "ledger_id": identity("medicalevaluationreference", ledger)}
    if len(json.dumps(ledger, ensure_ascii=False, indent=2).encode()) + 1 > MAX_JSON_BYTES:
        raise ValueError("Reference ledger exceeds 20 MiB; split explicitly without truncation.")
    return ledger


def _code_sources() -> dict[str, Path]:
    return {
        **plan_code_sources(),
        "evaluation_reference.py": Path(__file__),
        "numeric.py": Path(__file__).with_name("numeric.py"),
    }


def freeze_reference_ledger(repo_root: Path, plan_run: Path, input_path: Path) -> Path:
    """Freeze a new private ledger attempt; retain failures and never mutate the plan."""
    repo = repo_root.resolve()
    parent = private_path(repo, plan_run, PRIVATE_RUNS)
    parent_hash = hashlib.sha256((parent / "run_manifest.json").read_bytes()).hexdigest()
    plan = load_evaluation_plan(repo, parent)
    path = private_path(repo, input_path, PRIVATE_SOURCES / plan["evaluation_id"] / "evaluation")
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    data = parse_json(raw)
    ledger = validate_reference_input(plan, data)
    code_sources = _code_sources()
    code = {name: source.read_bytes() for name, source in code_sources.items()}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=plan["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=path,
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_reference_sha256": content_hash(ledger),
            "plan_run_reference": str(parent.relative_to(repo)),
            "plan_manifest_sha256": parent_hash,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        raw_path = run / "generated/medical_evaluation/raw/reference_input.json"
        raw_path.parent.mkdir(parents=True)
        with raw_path.open("xb") as stream:
            stream.write(raw)
        update_run(manifest, artifact=str(raw_path))
        for name, contents in code.items():
            target = run / "generated/medical_evaluation/code" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(contents)
            update_run(manifest, artifact=str(target))
        if (
            path.read_bytes() != raw
            or load_evaluation_plan(repo, parent) != plan
            or hashlib.sha256((parent / "run_manifest.json").read_bytes()).hexdigest()
            != parent_hash
            or any(code_sources[k].read_bytes() != v for k, v in code.items())
        ):
            raise ValueError("Reference plan/source/code/input changed while freezing.")
        target = run / "processed/medical_evaluation/reference_ledger.json"
        write_json(target, ledger)
        update_run(manifest, artifact=str(target))
        update_run(manifest, stage="evaluation-reference", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_reference_ledger(repo_root: Path, run_path: Path) -> dict[str, Any]:
    """Validate exact immutable ledger/parent/source lineage for dependent reuse."""
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if manifest["status"] != "completed" or not settings.get("medical_evaluation_reference_sha256"):
        raise ValueError("Evaluation reference run is not successfully frozen.")
    parent = private_path(repo, Path(settings["plan_run_reference"]), PRIVATE_RUNS)
    if (
        hashlib.sha256((parent / "run_manifest.json").read_bytes()).hexdigest()
        != settings["plan_manifest_sha256"]
    ):
        raise ValueError("Frozen reference parent plan manifest changed.")
    plan = load_evaluation_plan(repo, parent)
    raw = recorded_artifact(
        repo, run, manifest, "generated/medical_evaluation/raw/reference_input.json"
    ).read_bytes()
    ledger = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/reference_ledger.json")
    )
    archived_code = {
        name: hashlib.sha256(
            recorded_artifact(
                repo, run, manifest, "generated/medical_evaluation/code/" + name
            ).read_bytes()
        ).hexdigest()
        for name in _code_sources()
    }
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(ledger) != settings["medical_evaluation_reference_sha256"]
        or content_hash(archived_code) != settings["code_sha256"]
        or validate_reference_input(plan, parse_json(raw)) != ledger
    ):
        raise ValueError("Reference raw/code/plan binding or semantic accounting changed.")
    return {"run_root": run, "manifest": manifest, "plan": plan, "ledger": ledger}
