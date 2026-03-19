from __future__ import annotations

import math

import pandas as pd

from research_project.prediction_review import (
    FLOW_COLUMNS,
    SUMMARY_TABLE_COLUMNS,
    TABLE3_COLUMNS,
    TABLEE2_COLUMNS,
    reconcile_flow_counts,
    search_confusion_matrices,
    summarize_calibration_deciles,
    validate_flow_counts,
    validate_summary_table,
    validate_table3,
    validate_tablee2,
)


def _summary_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "study_prediction_review",
                "source_table": "table2_baseline_by_outcome",
                "source_page": 23,
                "variable": "Male sex",
                "level": "male",
                "measure_type": "categorical_count_percent",
                "group_label": "group_a",
                "n_group": 82,
                "count": 51,
                "percent": 62,
                "percent_digits": 0,
                "mean": None,
                "sd": None,
                "median": None,
                "q1": None,
                "q3": None,
                "digits_x": None,
                "digits_sd": None,
                "p_reported": 0.40,
            },
            {
                "study_id": "study_prediction_review",
                "source_table": "table2_baseline_by_outcome",
                "source_page": 23,
                "variable": "Age at diagnosis",
                "level": "all",
                "measure_type": "continuous_mean_sd",
                "group_label": "group_b",
                "n_group": 51,
                "count": None,
                "percent": None,
                "percent_digits": None,
                "mean": 64,
                "sd": 14,
                "median": None,
                "q1": None,
                "q3": None,
                "digits_x": 0,
                "digits_sd": 0,
                "p_reported": 0.38,
            },
            {
                "study_id": "study_prediction_review",
                "source_table": "table2_baseline_by_outcome",
                "source_page": 23,
                "variable": "Diagnosis delay",
                "level": "all",
                "measure_type": "continuous_median_iqr",
                "group_label": "group_b",
                "n_group": 51,
                "count": None,
                "percent": None,
                "percent_digits": None,
                "mean": None,
                "sd": None,
                "median": 1.0,
                "q1": 0.7,
                "q3": 1.4,
                "digits_x": None,
                "digits_sd": None,
                "p_reported": 0.08,
            },
        ],
        columns=SUMMARY_TABLE_COLUMNS,
    )


def _table3_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "study_prediction_review",
                "source_table": "table3_discrimination_metrics",
                "source_page": 24,
                "cohort": "Prospective validation",
                "n_total": 40,
                "n_events": 13,
                "c_statistic": 0.79,
                "c_stat_low": 0.68,
                "c_stat_high": 0.90,
                "sensitivity": 69,
                "sensitivity_low": 50,
                "sensitivity_high": 84,
                "specificity": 82,
                "specificity_low": 62,
                "specificity_high": 93,
                "ppv": 64,
                "ppv_low": 43,
                "ppv_high": 80,
                "npv": 84,
                "npv_low": 65,
                "npv_high": 94,
            }
        ],
        columns=TABLE3_COLUMNS,
    )


def _tablee2_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "study_prediction_review",
                "source_table": "tablee2_calibration_deciles",
                "source_page": 31,
                "group_id": group_id,
                "probability": probability,
                "observed_outcomes": observed,
                "expected_outcomes": expected,
                "total_individuals": total,
            }
            for group_id, probability, observed, expected, total in [
                (1, 0.10, 1, 1, 10),
                (2, 0.25, 2, 3, 10),
                (3, 0.45, 4, 5, 10),
                (4, 0.70, 6, 7, 10),
            ]
        ],
        columns=TABLEE2_COLUMNS,
    )


def _flow_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "study_prediction_review",
                "source_figure": "figure1_flow",
                "source_page": 25,
                "stage": stage,
                "count": count,
            }
            for stage, count in [
                ("assessed_for_eligibility", 120),
                ("did_not_meet_eligibility_criteria", 80),
                ("eligible", 40),
                ("approached", 37),
                ("enrolled", 20),
                ("declined_consent", 17),
                ("included_in_analysis", 18),
                ("excluded_from_analysis", 2),
                ("excluded_reason_1", 1),
                ("excluded_reason_2", 1),
            ]
        ],
        columns=FLOW_COLUMNS,
    )


def test_prediction_review_validators_accept_expected_inputs() -> None:
    summary = validate_summary_table(_summary_fixture(), "table2")
    table3 = validate_table3(_table3_fixture())
    tablee2 = validate_tablee2(_tablee2_fixture())
    flow = validate_flow_counts(_flow_fixture())

    assert len(summary) == 3
    assert len(table3) == 1
    assert len(tablee2) == 4
    assert len(flow) == 10
    assert table3.iloc[0]["n_total"] == 40


def test_prediction_review_confusion_search_finds_no_exact_match() -> None:
    matches = search_confusion_matrices(
        n_total=40,
        n_events=13,
        sensitivity=69,
        specificity=82,
        ppv=64,
        npv=84,
    )

    assert not matches.empty
    assert not matches["exact_rounded_match"].any()

    best = matches.iloc[0]
    assert (best["tp"], best["fp"], best["tn"], best["fn"]) == (9, 5, 22, 4)
    assert math.isclose(best["total_abs_delta"], 1.6503866503866504, rel_tol=0, abs_tol=1e-9)


def test_prediction_review_calibration_summary_matches_displayed_totals() -> None:
    summary = summarize_calibration_deciles(
        _tablee2_fixture(),
        expected_n_total=133,
        expected_n_events=51,
    )

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["n_groups"] == 4
    assert row["total_individuals_sum"] == 40
    assert row["observed_outcomes_sum"] == 13
    assert row["displayed_expected_outcomes_sum"] == 16
    assert row["displayed_expected_minus_observed"] == 3


def test_prediction_review_flow_reconciliation_flags_gap_between_eligible_and_approached() -> None:
    checks = reconcile_flow_counts(_flow_fixture())

    assert len(checks) == 5
    assert checks["pass_flag"].sum() == 4

    gap = checks.loc[checks["check_name"] == "eligible_minus_approached_gap"].iloc[0]
    assert gap["delta"] == 3
    assert not gap["pass_flag"]
