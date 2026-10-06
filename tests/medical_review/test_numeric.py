from __future__ import annotations

from decimal import Decimal

import pytest

from research_project.medical_review.numeric import calculate_request
from research_project.medical_review.records import content_hash


def request(bundle, kind, inputs):
    return {
        "schema_version": "medical_numeric_check_request_v1",
        "run_id": "synthetic-run",
        "proposal_id": "synthetic-proposal",
        "study_id": bundle["study_id"],
        "comparison_id": None,
        "bundle_sha256": content_hash(bundle),
        "kind": kind,
        "evidence_ids": [bundle["evidence"][0]["evidence_id"]],
        "population": "all-enrolled-participants",
        "horizon": "day-30",
        "orientation": "event-risk",
        "inputs": inputs,
        "reported_comparison": None,
    }


def value(result, metric):
    return Decimal(result["metrics"][metric]["value"])


def test_percentage_calculation_preserves_source_status_and_explicit_rounding(workspace):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "percentage", {"numerator": 8, "denominator": 10})
    req["reported_comparison"] = {
        "metric": "percentage",
        "value": "80.0",
        "precision": 1,
        "absolute_tolerance": "0",
        "population": req["population"],
        "horizon": req["horizon"],
        "orientation": req["orientation"],
        "estimation": "unadjusted",
        "denominator": 10,
    }
    result = calculate_request(req, bundle)
    assert value(result, "percentage") == 80
    assert result["comparison"]["status"] == "within_tolerance"
    assert result["input_verification"] == "proposed_transcription"
    assert result["qualified_method_result"] is False
    assert result["inspect_sr_candidate_eligible"] is False
    assert result["request"] == req
    assert calculate_request(req, bundle) == result


@pytest.mark.parametrize(
    "change", ["adjustment", "population", "horizon", "denominator", "orientation"]
)
def test_incompatible_reported_estimate_does_not_become_arithmetic_contradiction(workspace, change):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "percentage", {"numerator": 8, "denominator": 10})
    req["reported_comparison"] = {
        "metric": "percentage",
        "value": "20",
        "precision": 0,
        "absolute_tolerance": "0",
        "population": req["population"],
        "horizon": req["horizon"],
        "orientation": req["orientation"],
        "estimation": "unadjusted",
        "denominator": 10,
    }
    changes = {
        "adjustment": ("estimation", "adjusted"),
        "population": ("population", "per-protocol"),
        "horizon": ("horizon", "day-90"),
        "denominator": ("denominator", 50),
        "orientation": ("orientation", "event-free"),
    }
    key, replacement = changes[change]
    req["reported_comparison"][key] = replacement
    result = calculate_request(req, bundle)
    assert result["comparison"]["status"] == "not_comparable"
    assert result["comparison"]["discrepancy"] is None


def test_declared_counts_can_expose_2x2_arithmetic_discrepancy(workspace):
    _, _, _, bundle, _ = workspace
    req = request(
        bundle,
        "diagnostic_2x2",
        {
            "tp": 8,
            "fn": 2,
            "fp": 1,
            "tn": 9,
            "sampling": "cohort_representative",
            "metrics": ["sensitivity", "specificity", "lr_positive"],
            "target_prevalence": None,
            "prevalence_evidence_ids": [],
        },
    )
    req["reported_comparison"] = {
        "metric": "sensitivity",
        "value": "0.9",
        "precision": 2,
        "absolute_tolerance": "0",
        "population": req["population"],
        "horizon": req["horizon"],
        "orientation": req["orientation"],
        "estimation": "unadjusted",
        "denominator": 10,
    }
    result = calculate_request(req, bundle)
    assert value(result, "sensitivity") == Decimal("0.8")
    assert value(result, "specificity") == Decimal("0.9")
    assert value(result, "lr_positive") == 8
    assert result["comparison"]["status"] == "outside_tolerance"
    assert result["input_verification"] == "proposed_transcription"  # source review still separate


def test_case_control_ppv_cannot_use_investigator_set_case_fraction(workspace):
    _, _, _, bundle, _ = workspace
    req = request(
        bundle,
        "diagnostic_2x2",
        {
            "tp": 8,
            "fn": 2,
            "fp": 1,
            "tn": 9,
            "sampling": "case_control",
            "metrics": ["ppv"],
            "target_prevalence": None,
            "prevalence_evidence_ids": [],
        },
    )
    with pytest.raises(ValueError, match="prevalence"):
        calculate_request(req, bundle)
    req["inputs"]["target_prevalence"] = "0.1"
    req["inputs"]["prevalence_evidence_ids"] = req["evidence_ids"]
    result = calculate_request(req, bundle)
    assert abs(value(result, "ppv") - Decimal(8) / 17) < Decimal("1e-27")
    assert "target-prevalence assumption" in result["assumptions"][0]


def test_zero_cells_are_not_continuity_corrected(workspace):
    _, _, _, bundle, _ = workspace
    req = request(
        bundle,
        "diagnostic_2x2",
        {
            "tp": 10,
            "fn": 0,
            "fp": 0,
            "tn": 10,
            "sampling": "cohort_representative",
            "metrics": ["lr_positive", "lr_negative"],
            "target_prevalence": None,
            "prevalence_evidence_ids": [],
        },
    )
    result = calculate_request(req, bundle)
    assert result["metrics"]["lr_positive"] == {"status": "positive_infinity", "value": None}
    assert result["metrics"]["lr_negative"] == {"status": "finite", "value": "0"}
    assert result["continuity_correction"] is None
    req["inputs"]["tp"] = req["inputs"]["tn"] = 0
    result = calculate_request(req, bundle)
    assert result["metrics"]["lr_positive"]["status"] == "undefined"


def test_binary_effects_keep_orientation_and_undefined_zero_risks(workspace):
    _, _, _, bundle, _ = workspace
    req = request(
        bundle,
        "binary_risk_contrast",
        {
            "exposed_events": 0,
            "exposed_total": 10,
            "control_events": 0,
            "control_total": 10,
            "estimation": "unadjusted",
        },
    )
    result = calculate_request(req, bundle)
    assert value(result, "risk_difference") == 0
    assert result["metrics"]["risk_ratio"]["status"] == "undefined"
    req["inputs"]["exposed_events"] = 1
    assert calculate_request(req, bundle)["metrics"]["risk_ratio"]["status"] == "positive_infinity"
    req["inputs"]["estimation"] = "weighted"
    with pytest.raises(ValueError, match="unadjusted"):
        calculate_request(req, bundle)


def test_flow_categories_require_exclusivity_and_same_population_timepoint(workspace):
    _, _, _, bundle, _ = workspace
    inputs = {
        "total": 10,
        "mutually_exclusive": True,
        "categories": [
            {
                "label": "completed",
                "count": 8,
                "population": "all-enrolled-participants",
                "horizon": "day-30",
            },
            {
                "label": "lost",
                "count": 2,
                "population": "all-enrolled-participants",
                "horizon": "day-30",
            },
        ],
    }
    req = request(bundle, "participant_flow", inputs)
    assert value(calculate_request(req, bundle), "accounted_total") == 10
    inputs["mutually_exclusive"] = False
    with pytest.raises(ValueError, match="exclusive"):
        calculate_request(req, bundle)
    inputs["mutually_exclusive"] = True
    inputs["categories"][1]["horizon"] = "day-90"
    with pytest.raises(ValueError, match="population|time|horizon"):
        calculate_request(req, bundle)


@pytest.mark.parametrize("field", ["human_verified", "method_receipt", "official_assessment"])
def test_model_fields_cannot_promote_arithmetic_authority(workspace, field):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "percentage", {"numerator": 1, "denominator": 2})
    req[field] = True
    with pytest.raises(ValueError, match="contract|fields"):
        calculate_request(req, bundle)


def test_fabricated_evidence_and_unreviewed_scope_refuse_calculation(workspace):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "percentage", {"numerator": 1, "denominator": 2})
    req["evidence_ids"] = ["fabricated"]
    with pytest.raises(ValueError, match="evidence"):
        calculate_request(req, bundle)
    req["evidence_ids"] = [bundle["evidence"][0]["evidence_id"]]
    req["bundle_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="bundle"):
        calculate_request(req, bundle)


def test_rounding_boundary_and_undefined_percentage_remain_explicit(workspace):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "percentage", {"numerator": 1, "denominator": 3})
    req["reported_comparison"] = {
        "metric": "percentage",
        "value": "33.3",
        "precision": 1,
        "absolute_tolerance": "0",
        "population": req["population"],
        "horizon": req["horizon"],
        "orientation": req["orientation"],
        "estimation": "unadjusted",
        "denominator": 3,
    }
    assert calculate_request(req, bundle)["comparison"]["status"] == "within_tolerance"
    req["inputs"] = {"numerator": 0, "denominator": 0}
    req["reported_comparison"]["denominator"] = 0
    result = calculate_request(req, bundle)
    assert result["metrics"]["percentage"]["status"] == "undefined"
    assert result["comparison"]["discrepancy"] is None
    assert result["comparison"]["status"] == "undefined_or_infinite"


@pytest.mark.parametrize(
    "counts",
    [
        {"numerator": True, "denominator": 2},
        {"numerator": -1, "denominator": 2},
        {"numerator": 3, "denominator": 2},
    ],
)
def test_invalid_counts_are_not_repaired(workspace, counts):
    _, _, _, bundle, _ = workspace
    with pytest.raises(ValueError, match="count|numerator"):
        calculate_request(request(bundle, "percentage", counts), bundle)


def test_arithmetic_cannot_infer_p_value_method_or_execute_generated_code(workspace):
    _, _, _, bundle, _ = workspace
    req = request(bundle, "ci_pvalue", {"code": "untrusted arbitrary code"})
    with pytest.raises(ValueError, match="Unsupported arithmetic"):
        calculate_request(req, bundle)


def test_numerical_inputs_cannot_borrow_another_studys_evidence(workspace):
    _, _, _, bundle, _ = workspace
    bundle["studies"].append({"study_id": "unrelated-study"})
    req = request(bundle, "percentage", {"numerator": 1, "denominator": 2})
    req["study_id"] = "unrelated-study"
    with pytest.raises(ValueError, match="evidence"):
        calculate_request(req, bundle)


def test_participant_accounting_preserves_exact_integer_difference(workspace):
    _, _, _, bundle, _ = workspace
    count = 10**35
    req = request(
        bundle,
        "participant_flow",
        {
            "total": count,
            "mutually_exclusive": True,
            "categories": [
                {
                    "label": "first",
                    "count": count,
                    "population": "all-enrolled-participants",
                    "horizon": "day-30",
                },
                {
                    "label": "extra",
                    "count": 1,
                    "population": "all-enrolled-participants",
                    "horizon": "day-30",
                },
            ],
        },
    )
    assert value(calculate_request(req, bundle), "accounting_difference") == 1
