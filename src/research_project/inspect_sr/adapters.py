"""Candidate-only routes from method receipts to INSPECT-SR evidence dossiers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from numbers import Integral, Real
from typing import Any

from research_project.inspect_sr.records import evidence_id as calculate_evidence_id


def _route(
    label: str, methods: tuple[str, ...], manual_route: str, limitations: str
) -> dict[str, Any]:
    return {
        "short_label": label,
        "method_ids": methods,
        "manual_route": manual_route,
        "limitations": limitations,
    }


CHECK_ROUTES: dict[str, dict[str, Any]] = {
    "1.1": _route(
        "Retraction",
        (),
        "Record dated notice, source, relevance, and resolution.",
        "No search is not a negative search; notice identity and relevance require review.",
    ),
    "1.2": _route(
        "Other post-publication notices",
        (),
        "Record correction, expression of concern, or other notice and its resolution.",
        "A benign amendment or corrected typo is not automatically concerning.",
    ),
    "1.3": _route(
        "Related-team concerns",
        (),
        "Record a verified related-work source and identity link.",
        "Name similarity or association alone is not index-study evidence.",
    ),
    "2.1": _route(
        "Ethics approval",
        (),
        "Record ethics/governance statements and searched sources.",
        "Unavailable documentation does not establish that approval was absent.",
    ),
    "2.2": _route(
        "Registration timing",
        (),
        "Record registration source, dates, precision, and retrieval status.",
        "Date screens are metadata candidates; unavailable retrieval is not a negative.",
    ),
    "2.3": _route(
        "Registry/report consistency",
        (),
        "Compare semantically equivalent protocol/report/registry claims.",
        "Do not route outcome-reporting-only risk-of-bias questions here.",
    ),
    "2.4": _route(
        "Recruitment feasibility",
        (),
        "Record recruitment interval, sites, capacity, and supporting sources.",
        "A large sample or short interval alone does not establish implausibility.",
    ),
    "2.5": _route(
        "Methods/resources plausibility",
        (),
        "Record field-expert context and actual resource evidence.",
        "Requires contextual expertise; unusual methods alone are not a verdict.",
    ),
    "3.1": _route(
        "Text/table consistency",
        (),
        "Record exact cross-source text/table claims and context.",
        "Boilerplate, expected structure, and figure mentions need contextual review.",
    ),
    "3.2": _route(
        "Figure integrity",
        (),
        "Inspect and record actual images/panels, source version, and visual reviewer.",
        "No current method receipt routes caption or numbering signals; "
        "image inspection requires a human image or panel record.",
    ),
    "4.1": _route(
        "Eligibility/data agreement",
        (),
        "Compare eligibility criteria with the analyzed population and exceptions.",
        "Confirm population and legitimate exclusions from source evidence.",
    ),
    "4.2": _route(
        "Allocation counts",
        (),
        "Record randomization-list counts, design, strata, and exclusions.",
        "Use randomized counts and account for every allocation list.",
    ),
    "4.3": _route(
        "Baseline plausibility",
        (),
        "Review design-qualified descriptive and expert diagnostics.",
        "No unqualified pooled-P or 1-P interpretation.",
    ),
    "4.4": _route(
        "Within-report result agreement",
        (),
        "Link typed text/table/figure evidence for the same outcome and estimand.",
        "Compare matching population, time, unit, and estimand only.",
    ),
    "4.5": _route(
        "Follow-up plausibility",
        (),
        "Record retention and follow-up accounting by population/timepoint.",
        "Good retention alone is not suspicious.",
    ),
    "4.6": _route(
        "Participant accounting",
        (),
        "Record verified participant-flow relationships and arithmetic.",
        "Categories must be mutually exclusive and share population/timepoint.",
    ),
    "4.7": _route(
        "Outcome plausibility",
        (),
        "Record contextual clinical/outcome review and revisit at synthesis.",
        "A surprising effect size is not itself a mathematical contradiction.",
    ),
    "4.8": _route(
        "Integer-summary compatibility",
        ("scrutiny_grim_map", "scrutiny_grimmer_map", "scrutiny_debit_map"),
        "Record statistic kind, scale, n, denominator, and printed precision.",
        "Only eligible mean/count summaries with validated source semantics are in scope.",
    ),
    "4.9": _route(
        "Statistical consistency",
        ("statcheck",),
        "Record source report text and test definition including tail, adjustment, and comparator.",
        "Preserve scope, rounding, and inequality; incomplete parsing is indeterminate.",
    ),
    "4.10": _route(
        "Other numerical contradictions",
        ("scrutiny_duplicates", "scrutiny_rounding_bias"),
        "Record each scoped arithmetic constraint and source locator.",
        "A small tested subset cannot support a global consistency conclusion.",
    ),
    "4.11": _route(
        "Between-report consistency",
        (),
        "Link reviewed report/trial mappings and compare source versions.",
        "Do not combine distinct cohorts, analyses, or corrected versions indiscriminately.",
    ),
}

METHOD_TO_CHECKS: dict[str, tuple[str, ...]] = {
    method_id: tuple(
        check_id for check_id, route in CHECK_ROUTES.items() if method_id in route["method_ids"]
    )
    for method_id in sorted(
        {method for route in CHECK_ROUTES.values() for method in route["method_ids"]}
    )
}


def _validate_method_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("schema_version") != "method_receipt_v4":
        raise ValueError("Candidate mapping requires a validated method_receipt_v4 record.")
    required = {
        "run_id",
        "method_id",
        "method_version",
        "package_name",
        "package_version",
        "unit_of_evaluation",
        "input_evidence_ids",
        "parameters",
        "applicability",
        "execution",
        "result_status",
        "n_input",
        "n_eligible",
        "n_evaluated",
        "n_failed",
        "n_flagged",
        "output_reference",
        "diagnostic",
    }
    if required - receipt.keys() or any(
        not str(receipt.get(field, "")).strip()
        for field in ("run_id", "method_id", "method_version", "package_name", "unit_of_evaluation")
    ):
        raise ValueError("Method receipt is missing required v4 provenance fields.")
    if receipt.get("applicability") not in {"eligible", "ineligible", "unknown", "mixed"}:
        raise ValueError("Method receipt has an unknown applicability state.")
    if receipt.get("execution") not in {
        "not_requested",
        "not_implemented",
        "dependency_missing",
        "blocked",
        "failed",
        "partial",
        "completed",
    }:
        raise ValueError("Method receipt has an unknown execution state.")
    n_input, n_eligible, n_evaluated, n_failed = (
        _receipt_count(receipt[field], field)
        for field in ("n_input", "n_eligible", "n_evaluated", "n_failed")
    )
    if min(n_input, n_eligible, n_evaluated, n_failed) < 0:
        raise ValueError("Method receipt counts cannot be negative.")
    if n_eligible > n_input or n_evaluated > n_eligible or n_evaluated + n_failed > n_eligible:
        raise ValueError("Method receipt counts violate eligibility/evaluation bounds.")
    flagged = receipt.get("n_flagged")
    if isinstance(flagged, float) and math.isnan(flagged):
        flagged = None
    if flagged is not None:
        flagged = _receipt_count(flagged, "n_flagged")
        if flagged < 0 or flagged > n_evaluated:
            raise ValueError("Method receipt flagged count exceeds evaluated units.")
    execution = receipt["execution"]
    status = receipt.get("result_status")
    if status not in {"findings_present", "no_finding", "not_evaluated", "indeterminate"}:
        raise ValueError("Method receipt has an unknown result status.")
    if execution == "completed" and (
        n_evaluated < 1 or n_failed != 0 or n_evaluated != n_eligible or flagged is None
    ):
        raise ValueError("Completed receipts require full evaluated coverage and a flag count.")
    if execution == "completed" and receipt["applicability"] not in {"eligible", "mixed"}:
        raise ValueError("Completed receipt applicability conflicts with evaluated units.")
    if execution == "completed" and status != ("findings_present" if flagged > 0 else "no_finding"):
        raise ValueError("Completed receipt result status conflicts with its flag count.")
    if execution == "partial" and (
        n_evaluated < 1 or n_failed < 1 or n_evaluated + n_failed != n_eligible
    ):
        raise ValueError("Partial receipts must account for every eligible unit.")
    if execution == "partial" and status != "indeterminate":
        raise ValueError("Partial receipt result status must remain indeterminate.")
    if execution in {"not_requested", "not_implemented", "dependency_missing", "blocked"} and (
        n_evaluated != 0 or flagged is not None
    ):
        raise ValueError("An unexecuted receipt cannot claim evaluated results or flags.")
    if execution == "not_requested" and status != "not_evaluated":
        raise ValueError("Not-requested receipt result status must remain not_evaluated.")
    if execution not in {"completed", "partial", "not_requested"} and status != "indeterminate":
        raise ValueError("Unsuccessful receipt result status must remain indeterminate.")


def _receipt_count(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Method receipt {field} must be a nonnegative integer.")
    if isinstance(value, Integral):
        result = int(value)
    elif isinstance(value, Real) and math.isfinite(float(value)) and float(value).is_integer():
        result = int(value)
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        result = int(value)
    else:
        raise ValueError(f"Method receipt {field} must be a nonnegative integer.")
    if result < 0:
        raise ValueError(f"Method receipt {field} must be a nonnegative integer.")
    return result


def _stable_candidate_id(identity: Mapping[str, Any]) -> str:
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "candidate_" + hashlib.sha256(encoded).hexdigest()


def _optional_numeric_result(value: Any, field: str) -> float | int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError(f"Numeric result {field} must be a finite number or null.")
    return int(value) if isinstance(value, Integral) else float(value)


def _candidate_identity_fields(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": candidate["run_id"],
        "method_id": candidate["method_id"],
        "method_version": candidate["method_version"],
        "result_id": candidate["result_id"],
        "candidate_kind": candidate["candidate_kind"],
        "details": candidate["details"],
        "evidence_ids": sorted(candidate["evidence_ids"]),
        "metric": candidate["metric"],
        "value_numeric": candidate["value_numeric"],
        "p_value": candidate["p_value"],
        "anomaly_flag": candidate["anomaly_flag"],
        "source_scope": candidate["source_scope"],
        "source_locator": candidate["source_locator"],
        "native_output_reference": candidate["native_output_reference"],
    }


def _evidence_id_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.split(";")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = list(value)
    else:
        values = []
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def map_candidate_result(
    result: Mapping[str, Any],
    method_receipts: Sequence[Mapping[str, Any]],
    evidence_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Map one result row to candidate records only after receipt/evidence validation."""
    if result.get("schema_version") != "numeric_result_v2":
        raise ValueError("Candidate mapping requires the numeric_result_v2 contract.")
    method_id = _clean_text(result.get("method_id"))
    if method_id == "scrutiny_rounding_bias":
        raise ValueError("Rounding-bias candidates are blocked pending a qualified input contract.")
    result_run_id = _clean_text(result.get("run_id"))
    result_id = _clean_text(result.get("result_id"))
    source_locator = _clean_text(result.get("source_locator"))
    if not result_run_id or not result_id or not source_locator:
        raise ValueError("Candidate result requires a stable result ID and exact source locator.")
    matches = [
        item
        for item in method_receipts
        if item.get("method_id") == method_id and item.get("run_id") == result_run_id
    ]
    if len(matches) > 1:
        raise ValueError("Candidate result has ambiguous matching method receipts.")
    receipt = matches[0] if matches else None
    if receipt is None:
        return []
    _validate_method_receipt(receipt)
    if receipt.get("execution") not in {"completed", "partial"}:
        return []
    try:
        evaluated = int(receipt.get("n_evaluated") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Method receipt n_evaluated must be an integer.") from exc
    if evaluated < 1:
        return []
    checks = METHOD_TO_CHECKS.get(method_id, ())
    if not checks:
        return []
    evidence_ids = _evidence_id_list(result.get("input_evidence_ids"))
    if not evidence_ids:
        raise ValueError("Candidate result requires exact input evidence IDs.")
    receipt_evidence_ids = set(_evidence_id_list(receipt.get("input_evidence_ids")))
    if set(evidence_ids) - receipt_evidence_ids:
        return []
    evidence_by_id = {str(row.get("evidence_id")): row for row in evidence_records}
    missing = sorted(set(evidence_ids) - evidence_by_id.keys())
    if missing:
        raise ValueError(f"Candidate result references unavailable evidence IDs: {missing}")
    for evidence_id in evidence_ids:
        record = evidence_by_id[evidence_id]
        if not record.get("source_version_id"):
            raise ValueError(f"Candidate evidence {evidence_id} lacks a source version.")
        try:
            expected_evidence_id = calculate_evidence_id(
                str(record["source_version_id"]),
                str(record["locator"]),
                str(record["raw_value"]),
                str(record["extraction_method"]),
                str(record["extraction_version"]),
            )
        except (KeyError, AttributeError) as exc:
            raise ValueError(
                f"Candidate evidence {evidence_id} lacks identity provenance."
            ) from exc
        if expected_evidence_id != evidence_id:
            raise ValueError(
                f"Candidate evidence {evidence_id} does not match its content identity."
            )
        if str(record["locator"]).strip() != source_locator:
            return []
    result_fields = {
        "run_id": str(receipt["run_id"]),
        "result_id": result_id,
        "method_version": str(receipt["method_version"]),
        "candidate_kind": _clean_text(result.get("candidate_kind", "method_result")),
        "details": _clean_text(result.get("details")),
        "metric": _clean_text(result.get("metric")) or None,
        "value_numeric": _optional_numeric_result(result.get("value_numeric"), "value_numeric"),
        "p_value": _optional_numeric_result(result.get("p_value"), "p_value"),
        "anomaly_flag": result.get("anomaly_flag"),
        "source_scope": _clean_text(result.get("source_unit")) or None,
        "source_locator": source_locator,
        "native_output_reference": str(receipt["output_reference"]),
    }
    if (
        result_fields["anomaly_flag"] is not None
        and not isinstance(result_fields["anomaly_flag"], bool)
        and type(result_fields["anomaly_flag"]).__name__ != "bool_"
    ):
        raise ValueError("Numeric result anomaly_flag must be boolean or null.")
    if result_fields["anomaly_flag"] is not None:
        result_fields["anomaly_flag"] = bool(result_fields["anomaly_flag"])
    identity_fields = {
        **result_fields,
        "method_id": method_id,
        "evidence_ids": evidence_ids,
    }
    candidate_id = _stable_candidate_id(_candidate_identity_fields(identity_fields))
    candidates = []
    for check_id in checks:
        route = CHECK_ROUTES[check_id]
        candidate = {
            "schema_version": "inspect_sr_candidate_evidence_v2",
            "candidate_id": candidate_id,
            "check_id": check_id,
            "run_id": str(receipt.get("run_id", "")),
            "method_id": method_id,
            "candidate_kind": result_fields["candidate_kind"],
            "evidence_ids": evidence_ids,
            "source_locator": source_locator,
            **result_fields,
            "details": result_fields["details"],
            "candidate_status": "candidate_only",
            "method_execution": receipt["execution"],
            "limitations": route["limitations"],
        }
        if check_id == "3.2":
            candidate["image_inspection_status"] = "not_performed"
        candidates.append(candidate)
    return candidates


def build_candidate_dossier(
    method_receipts: Sequence[Mapping[str, Any]],
    candidate_records: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Report per-check method coverage and candidate records without check responses."""
    receipts_by_method: dict[str, list[Mapping[str, Any]]] = {}
    for receipt in method_receipts:
        _validate_method_receipt(receipt)
        receipts_by_method.setdefault(str(receipt.get("method_id", "")), []).append(receipt)
    coverage: list[dict[str, Any]] = []
    for check_id, route in CHECK_ROUTES.items():
        methods = route["method_ids"]
        matched = [receipt for method in methods for receipt in receipts_by_method.get(method, [])]
        if not methods:
            status, reason = "manual_only", "No automated route is supported for this check."
        elif not matched:
            status, reason = "missing", "No method receipt is available."
        else:
            evaluated = []
            for receipt in matched:
                try:
                    count = int(receipt.get("n_evaluated") or 0)
                except (TypeError, ValueError):
                    count = 0
                if receipt.get("execution") in {"completed", "partial"} and count > 0:
                    evaluated.append(receipt)
            if evaluated:
                status, reason = (
                    "available",
                    "Receipt confirms evaluated method coverage; "
                    "candidate evidence still requires review.",
                )
            elif all(receipt.get("applicability") == "ineligible" for receipt in matched):
                status, reason = "ineligible", "All recorded methods mark their inputs ineligible."
            elif all(
                receipt.get("execution") in {"not_requested", "not_implemented"}
                for receipt in matched
            ):
                status, reason = "missing", "No method was executed for this check."
            else:
                status, reason = (
                    "failed",
                    "A receipt records blocked, failed, missing-dependency, "
                    "or zero-evaluation coverage.",
                )
        coverage.append(
            {
                "check_id": check_id,
                "status": status,
                "reason": reason,
                "method_ids": list(methods),
                "candidate_count": sum(
                    item.get("check_id") == check_id for item in candidate_records
                ),
                "manual_route": route["manual_route"],
                "limitations": route["limitations"],
            }
        )
    return {"coverage": coverage, "candidate_evidence": [dict(item) for item in candidate_records]}
