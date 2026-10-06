"""Evidence-linked reconstruction that preserves reported facts and competing interpretations."""

from __future__ import annotations

import copy
from typing import Any

from research_project.medical_review.records import content_hash, identity

CONTEXT_SCHEMA = "medical_study_context_v1"
FIELDS = (
    "scientific_aim",
    "target_population",
    "source_population",
    "analysis_population",
    "eligibility",
    "observation_unit",
    "exposure",
    "comparator",
    "assignment",
    "time_zero",
    "washout",
    "follow_up",
    "outcome_definition",
    "outcome_measurement",
    "intercurrent_events",
    "censoring",
    "estimand",
    "effect_scale",
    "missing_data",
    "prespecified_exploratory",
    "intended_use",
    "index_time",
    "reference_standard",
    "prediction_horizon",
    "threshold",
    "predictor_availability",
    "development_validation_setting",
    "design_flags",
)


def build_study_context(
    bundle: dict[str, Any], supplied: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build an auditable operator-supplied context; do not infer facts from preferred designs."""
    supplied = copy.deepcopy(supplied or {})
    study_ids = {row["study_id"] for row in bundle["studies"]}
    if not isinstance(supplied, dict) or not set(supplied) <= study_ids:
        raise ValueError("Context fields must be keyed by declared study identities.")
    known_evidence = {row["evidence_id"] for row in bundle["evidence"]}
    studies = []
    for study in bundle["studies"]:
        scoped_reports = {
            r["report_id"]
            for r in bundle["reports"]
            if study["study_id"] in r["study_ids"]
            and (len(r["study_ids"]) == 1 or r.get("mapping_reviewed") is True)
        }
        scoped_versions = {
            d.get("source_version_id")
            for d in bundle["documents"]
            if d["availability"] == "supplied" and scoped_reports.intersection(d["report_ids"])
        }
        scoped_evidence = {
            e["evidence_id"]
            for e in bundle["evidence"]
            if e["source_version_id"] in scoped_versions
        }
        fields = supplied.get(study["study_id"], {})
        normalized = _normalize_fields(fields, known_evidence, scoped_evidence)
        studies.append({"study_id": study["study_id"], "fields": normalized})
    comparisons = []
    comparison_fields = bundle.get("comparison_context_fields", {})
    declared_comparisons = bundle.get("comparisons", [])
    if not isinstance(comparison_fields, dict) or not set(comparison_fields) <= {
        c["comparison_id"] for c in declared_comparisons
    }:
        raise ValueError("Comparison reconstruction needs declared comparison scopes.")
    for comparison in declared_comparisons:
        scoped_reports = {
            r["report_id"]
            for r in bundle["reports"]
            if comparison["study_id"] in r["study_ids"]
            and (len(r["study_ids"]) == 1 or r.get("mapping_reviewed") is True)
        }
        if comparison.get("report_ids"):
            scoped_reports &= set(comparison["report_ids"])
        scoped_versions = {
            d.get("source_version_id")
            for d in bundle["documents"]
            if d["availability"] == "supplied" and scoped_reports.intersection(d["report_ids"])
        }
        scoped_evidence = {
            e["evidence_id"]
            for e in bundle["evidence"]
            if e["source_version_id"] in scoped_versions
        }
        fields = _normalize_fields(
            comparison_fields.get(comparison["comparison_id"], {}), known_evidence, scoped_evidence
        )
        comparisons.append(
            {
                "comparison_id": comparison["comparison_id"],
                "study_id": comparison["study_id"],
                "fields": fields,
            }
        )
    record = {
        "schema_version": CONTEXT_SCHEMA,
        "bundle_sha256": content_hash(bundle),
        "origin": "operator_supplied_or_unknown",
        "studies": studies,
        "comparisons": comparisons,
        "input_fields": supplied,
        "specialists_may_challenge": True,
    }
    return {**record, "context_id": identity("medicalcontext", record)}


def _check_evidence(ids: Any, known: set[str]) -> None:
    if (
        not isinstance(ids, list)
        or any(not isinstance(x, str) for x in ids)
        or not set(ids) <= known
    ):
        raise ValueError("Reconstruction references unknown source evidence.")


def validate_study_context(record: dict[str, Any], bundle: dict[str, Any]) -> None:
    if record != build_study_context(bundle, record.get("input_fields")):
        raise ValueError("Context identity, source binding or asserted fields were changed.")


def _normalize_fields(
    fields: Any, known_evidence: set[str], scoped_evidence: set[str]
) -> dict[str, Any]:
    if not isinstance(fields, dict) or not set(fields) <= set(FIELDS):
        raise ValueError("Unsupported study reconstruction field.")
    normalized = {}
    for name in FIELDS:
        value = copy.deepcopy(fields.get(name, {}))
        if not isinstance(value, dict) or not set(value) <= {
            "reported",
            "interpretations",
            "preferred_design",
        }:
            raise ValueError(
                "Reported facts, interpretations and preferred designs must be separate."
            )
        reported = value.get(
            "reported",
            {
                "status": "unknown",
                "value": None,
                "evidence_ids": [],
                "reason": "Not reconstructed.",
            },
        )
        if not isinstance(reported, dict) or not set(reported) <= {
            "status",
            "value",
            "evidence_ids",
            "reason",
        }:
            raise ValueError("Unsupported reported-field contract.")
        if reported.get("status") not in {"known", "unknown", "conflicting", "not_applicable"}:
            raise ValueError("Unsupported reconstruction uncertainty state.")
        ids = reported.get("evidence_ids", [])
        _check_evidence(ids, known_evidence)
        if reported["status"] in {"known", "conflicting"} and (
            not ids or reported.get("value") is None
        ):
            raise ValueError(
                "Asserted reconstruction requires source evidence and a reported value."
            )
        if reported["status"] in {"known", "conflicting"} and not set(ids) <= scoped_evidence:
            raise ValueError("Known reconstruction requires reviewed study/source scope mapping.")
        if reported["status"] in {"unknown", "not_applicable"} and not reported.get("reason"):
            raise ValueError("Uncertain or inapplicable fields require an explicit reason.")
        interpretations = value.get("interpretations", [])
        if not isinstance(interpretations, list):
            raise ValueError("Competing interpretations must be a list.")
        for interpretation in interpretations:
            if not isinstance(interpretation, dict) or not set(interpretation) <= {
                "value",
                "evidence_ids",
                "rationale",
            }:
                raise ValueError("Interpretations cannot contain official statuses.")
            _check_evidence(interpretation.get("evidence_ids", []), known_evidence)
            if not set(interpretation.get("evidence_ids", [])) <= scoped_evidence:
                raise ValueError("Interpretation requires reviewed study/source scope mapping.")
            if (
                not interpretation.get("value")
                or not interpretation.get("evidence_ids")
                or not interpretation.get("rationale")
            ):
                raise ValueError("Interpretations require evidence, value and rationale.")
        preferred = value.get("preferred_design")
        if preferred is not None and (
            not isinstance(preferred, dict)
            or set(preferred) - {"value", "rationale"}
            or not preferred.get("value")
            or not preferred.get("rationale")
        ):
            raise ValueError(
                "Preferred design is an explicitly justified proposal, not a source fact."
            )
        normalized[name] = {
            "reported": reported,
            "interpretations": interpretations,
            "preferred_design": preferred,
            "source_semantics_verified": False,
        }
    return normalized
