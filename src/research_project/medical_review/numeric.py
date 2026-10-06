"""Bounded deterministic arithmetic, separate from R method qualification and source review."""

from __future__ import annotations

import copy
import hashlib
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from research_project.medical_review.records import content_hash, identity

FIELDS = {
    "schema_version",
    "run_id",
    "proposal_id",
    "study_id",
    "comparison_id",
    "bundle_sha256",
    "kind",
    "evidence_ids",
    "population",
    "horizon",
    "orientation",
    "inputs",
    "reported_comparison",
}
PRECISION = 34


def _exact(record: Any, fields: set[str], label: str) -> None:
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError(f"Unsupported {label} contract fields.")


def _count(value: Any) -> Decimal:
    if type(value) is not int or value < 0:
        raise ValueError("Arithmetic counts require nonnegative integers.")
    return Decimal(value)


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError(
            "Reported values, tolerances and prevalence require bounded decimal strings."
        )
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal input.") from error
    if not result.is_finite() or abs(result.as_tuple().exponent) > 100:
        raise ValueError("Decimal inputs must be finite within the supported exponent range.")
    return result


def _metric(value: Decimal | None) -> dict[str, Any]:
    if value is None or value.is_nan():
        return {"status": "undefined", "value": None}
    if value.is_infinite():
        return {"status": "positive_infinity" if value > 0 else "negative_infinity", "value": None}
    return {"status": "finite", "value": str(value)}


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return Decimal("Infinity") if numerator > 0 else None
    return numerator / denominator


def _difference(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    return None if left is None or right is None else left - right


def _evidence_scope(request: dict[str, Any], bundle: dict[str, Any]) -> set[str]:
    if request["study_id"] not in {s["study_id"] for s in bundle["studies"]}:
        raise ValueError("Numeric request references an unknown study scope.")
    reports = {
        r["report_id"]
        for r in bundle["reports"]
        if request["study_id"] in r["study_ids"]
        and (len(r["study_ids"]) == 1 or r.get("mapping_reviewed") is True)
    }
    if request["comparison_id"] is not None:
        comparisons = [
            c
            for c in bundle.get("comparisons", [])
            if c["comparison_id"] == request["comparison_id"]
            and c["study_id"] == request["study_id"]
        ]
        if len(comparisons) != 1:
            raise ValueError("Numeric request references an unknown comparison scope.")
        if comparisons[0].get("report_ids"):
            reports &= set(comparisons[0]["report_ids"])
    versions = {
        d.get("source_version_id")
        for d in bundle["documents"]
        if d["availability"] == "supplied" and reports.intersection(d["report_ids"])
    }
    return {e["evidence_id"] for e in bundle["evidence"] if e["source_version_id"] in versions}


def _check_evidence(ids: Any, known: set[str]) -> None:
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(x, str) for x in ids)
        or not set(ids) <= known
    ):
        raise ValueError("Numeric inputs require declared evidence in their reviewed study scope.")


def calculate_request(request: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """Calculate reviewed functions only; correct arithmetic never verifies source semantics."""
    _exact(request, FIELDS, "numeric request")
    if request["schema_version"] != "medical_numeric_check_request_v1":
        raise ValueError("Unsupported numeric request schema.")
    if request["bundle_sha256"] != content_hash(bundle):
        raise ValueError("Numeric request bundle binding does not match.")
    for field in ("run_id", "proposal_id", "population", "horizon", "orientation"):
        if not isinstance(request[field], str) or not request[field].strip():
            raise ValueError("Numeric scope/population/horizon/orientation must be explicit.")
    known = _evidence_scope(request, bundle)
    _check_evidence(request["evidence_ids"], known)
    inputs = request["inputs"]
    assumptions = ["Source transcriptions and semantic assumptions require independent review."]
    denominators = {}
    with localcontext() as context:
        context.prec = PRECISION
        if request["kind"] == "percentage":
            _exact(inputs, {"numerator", "denominator"}, "percentage inputs")
            numerator, denominator = _count(inputs["numerator"]), _count(inputs["denominator"])
            if numerator > denominator:
                raise ValueError("Percentage numerator exceeds its declared denominator.")
            metrics = {"percentage": _metric(_ratio(100 * numerator, denominator))}
            denominators = {"percentage": inputs["denominator"]}
        elif request["kind"] == "participant_flow":
            _exact(inputs, {"total", "mutually_exclusive", "categories"}, "participant flow inputs")
            if inputs["mutually_exclusive"] is not True:
                raise ValueError(
                    "Participant-flow categories must be established as mutually exclusive."
                )
            categories = inputs["categories"]
            if not isinstance(categories, list) or not categories:
                raise ValueError("Participant flow requires explicit accounting categories.")
            labels, total = set(), 0
            for category in categories:
                _exact(category, {"label", "count", "population", "horizon"}, "flow category")
                if (
                    not isinstance(category["label"], str)
                    or not category["label"].strip()
                    or category["label"] in labels
                ):
                    raise ValueError("Participant-flow categories need distinct labels.")
                if (
                    category["population"] != request["population"]
                    or category["horizon"] != request["horizon"]
                ):
                    raise ValueError(
                        "Participant-flow categories must share population and time horizon."
                    )
                labels.add(category["label"])
                total += int(_count(category["count"]))
            declared = int(_count(inputs["total"]))
            metrics = {
                "accounted_total": _metric(Decimal(total)),
                "accounting_difference": _metric(Decimal(total - declared)),
            }
            denominators = {name: inputs["total"] for name in metrics}
            assumptions.append(
                "Mutual exclusivity is a declared source-semantic assumption, not arithmetic proof."
            )
        elif request["kind"] == "binary_risk_contrast":
            _exact(
                inputs,
                {
                    "exposed_events",
                    "exposed_total",
                    "control_events",
                    "control_total",
                    "estimation",
                },
                "binary risk inputs",
            )
            if inputs["estimation"] != "unadjusted":
                raise ValueError("Only unadjusted binary risks are reconstructed from raw counts.")
            e, n, c, m = [
                _count(inputs[k])
                for k in ("exposed_events", "exposed_total", "control_events", "control_total")
            ]
            if e > n or c > m:
                raise ValueError(
                    "Binary event counts exceed their declared population denominators."
                )
            risk_e, risk_c = (_ratio(e, n) if n else None), (_ratio(c, m) if m else None)
            metrics = {
                "exposed_risk": _metric(risk_e),
                "control_risk": _metric(risk_c),
                "risk_difference": _metric(_difference(risk_e, risk_c)),
                "risk_ratio": _metric(_ratio(risk_e, risk_c)),
                "odds_ratio": _metric(_ratio(e * (m - c), c * (n - e)))
                if n and m
                else _metric(None),
            }
            denominators = {
                "exposed_risk": inputs["exposed_total"],
                "control_risk": inputs["control_total"],
                **{
                    name: {"exposed": inputs["exposed_total"], "control": inputs["control_total"]}
                    for name in ("risk_difference", "risk_ratio", "odds_ratio")
                },
            }
            assumptions.append(
                "Exposed-minus-control risk; unadjusted, unweighted, non-survival counts only."
            )
        elif request["kind"] == "diagnostic_2x2":
            _exact(
                inputs,
                {
                    "tp",
                    "fn",
                    "fp",
                    "tn",
                    "sampling",
                    "metrics",
                    "target_prevalence",
                    "prevalence_evidence_ids",
                },
                "diagnostic inputs",
            )
            if inputs["sampling"] not in {"case_control", "cohort_representative", "unknown"}:
                raise ValueError("Diagnostic sampling must be explicit.")
            tp, fn, fp, tn = [_count(inputs[k]) for k in ("tp", "fn", "fp", "tn")]
            se = _ratio(tp, tp + fn) if tp + fn else None
            sp = _ratio(tn, tn + fp) if tn + fp else None
            available = {
                "sensitivity": se,
                "specificity": sp,
                "lr_positive": _ratio(se, None if sp is None else 1 - sp),
                "lr_negative": _ratio(None if se is None else 1 - se, sp),
            }
            requested = inputs["metrics"]
            if (
                not isinstance(requested, list)
                or not requested
                or len(set(requested)) != len(requested)
                or not set(requested) <= set(available) | {"ppv", "npv"}
            ):
                raise ValueError(
                    "Unsupported diagnostic metric; "
                    "joint marginal LR multiplication is not implemented."
                )
            if set(requested) & {"ppv", "npv"}:
                if inputs["target_prevalence"] is None:
                    if inputs["sampling"] != "cohort_representative":
                        raise ValueError(
                            "Clinical PPV/NPV requires a target-prevalence assumption "
                            "for case-control/unknown sampling."
                        )
                    available["ppv"], available["npv"] = _ratio(tp, tp + fp), _ratio(tn, tn + fn)
                else:
                    prevalence = _decimal(inputs["target_prevalence"])
                    if not 0 <= prevalence <= 1:
                        raise ValueError("Target prevalence must be a probability.")
                    _check_evidence(inputs["prevalence_evidence_ids"], known)
                    available["ppv"] = (
                        None
                        if se is None or sp is None
                        else _ratio(se * prevalence, se * prevalence + (1 - sp) * (1 - prevalence))
                    )
                    available["npv"] = (
                        None
                        if se is None or sp is None
                        else _ratio(
                            sp * (1 - prevalence), sp * (1 - prevalence) + (1 - se) * prevalence
                        )
                    )
                    assumptions.insert(
                        0,
                        "Explicit target-prevalence assumption; "
                        "clinical applicability is unverified.",
                    )
            metrics = {name: _metric(available[name]) for name in requested}
            denominators = {
                "sensitivity": int(tp + fn),
                "specificity": int(tn + fp),
                "lr_positive": {
                    "reference_positive": int(tp + fn),
                    "reference_negative": int(tn + fp),
                },
                "lr_negative": {
                    "reference_positive": int(tp + fn),
                    "reference_negative": int(tn + fp),
                },
                "ppv": int(tp + fp) if inputs["target_prevalence"] is None else None,
                "npv": int(tn + fn) if inputs["target_prevalence"] is None else None,
            }
        else:
            raise ValueError(
                "Unsupported arithmetic request; "
                "inferential CI/P-value checks require qualified methods."
            )
        comparison = _comparison(request, metrics, denominators)
    result = {
        "schema_version": "medical_arithmetic_result_v1",
        "request_sha256": content_hash(request),
        "request": copy.deepcopy(request),
        "calculator": {
            "id": "medical_bounded_arithmetic",
            "version": "1",
            "decimal_precision": PRECISION,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "metrics": metrics,
        "metric_denominators": denominators,
        "comparison": comparison,
        "assumptions": assumptions,
        "continuity_correction": None,
        "input_verification": "proposed_transcription",
        "qualified_method_result": False,
        "inspect_sr_candidate_eligible": False,
    }
    return {**result, "result_id": identity("medicalarithmetic", result)}


def _comparison(
    request: dict[str, Any], metrics: dict[str, Any], denominators: dict[str, Any]
) -> dict[str, Any]:
    reported = request["reported_comparison"]
    if reported is None:
        return {"status": "not_requested", "discrepancy": None}
    _exact(
        reported,
        {
            "metric",
            "value",
            "precision",
            "absolute_tolerance",
            "population",
            "horizon",
            "orientation",
            "estimation",
            "denominator",
        },
        "reported comparison",
    )
    name = reported["metric"]
    if name not in metrics:
        raise ValueError("Reported metric is outside the requested arithmetic scope.")
    if (
        reported["estimation"] != "unadjusted"
        or any(reported[k] != request[k] for k in ("population", "horizon", "orientation"))
        or reported["denominator"] != denominators.get(name)
    ):
        return {
            "status": "not_comparable",
            "discrepancy": None,
            "reason": "Population, horizon, orientation, denominator or estimation differs.",
        }
    if metrics[name]["status"] != "finite":
        return {
            "status": "undefined_or_infinite",
            "discrepancy": None,
            "reason": "No finite comparison; zero cells were not corrected.",
        }
    precision = reported["precision"]
    if type(precision) is not int or not 0 <= precision <= 24:
        raise ValueError("Reported decimal precision must be explicit within 0..24.")
    expected, value = Decimal(metrics[name]["value"]), _decimal(reported["value"])
    tolerance = _decimal(reported["absolute_tolerance"])
    if tolerance < 0:
        raise ValueError("Absolute tolerance must be nonnegative.")
    rounding = Decimal(1).scaleb(-precision) / 2
    difference = abs(expected - value)
    outside = difference > tolerance + rounding
    return {
        "status": "outside_tolerance" if outside else "within_tolerance",
        "discrepancy": outside,
        "absolute_difference": str(difference),
        "absolute_tolerance": str(tolerance),
        "reported_rounding_half_unit": str(rounding),
        "qualification": "Arithmetic comparison only; input semantics remain unverified.",
    }
