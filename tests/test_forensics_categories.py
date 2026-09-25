from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import load_manifest, upsert_manifest_row
from research_project.meta_forensics import build_category_scores, compute_overall_meta_score
from research_project.numeric_integrity import (
    _digits_from_str,
    _to_int,
    assess_percent_compatibility,
    build_numeric_table,
    build_rsprite2_stub,
    build_scrutiny_cases,
    build_scrutiny_debit_input,
    build_scrutiny_duplicate_input,
    build_scrutiny_grim_input,
    build_scrutiny_grimmer_input,
    build_scrutiny_input,
    build_scrutiny_rounding_bias_input,
    build_statcheck_stub,
    summarize_numeric_flags,
)
from research_project.registration_forensics import derive_registration_claims, extract_registry_ids
from research_project.visual_forensics import (
    build_visual_checks,
    detect_caption_duplicates,
    detect_figure_numbering_gaps,
)


def _table1_long_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trial_id": "trial_x",
                "variable": "Age",
                "level": "all",
                "var_type": "continuous_median_range",
                "group": "early_tod",
                "n_group": 100,
                "value": 61.0,
                "percent": None,
                "decimals": 1,
                "reported_p": 0.50,
            },
            {
                "trial_id": "trial_x",
                "variable": "Age",
                "level": "all",
                "var_type": "continuous_median_range",
                "group": "late_tod",
                "n_group": 100,
                "value": 60.0,
                "percent": None,
                "decimals": 1,
                "reported_p": 0.50,
            },
            {
                "trial_id": "trial_x",
                "variable": "Sex",
                "level": "Male",
                "var_type": "categorical_count_percent",
                "group": "early_tod",
                "n_group": 100,
                "value": 90,
                "percent": 90.0,
                "decimals": 0,
                "reported_p": 1.0,
            },
            {
                "trial_id": "trial_x",
                "variable": "Sex",
                "level": "Male",
                "var_type": "categorical_count_percent",
                "group": "late_tod",
                "n_group": 100,
                "value": 91,
                "percent": 91.0,
                "decimals": 0,
                "reported_p": 1.0,
            },
        ]
    )


def test_numeric_integrity_builders_and_summary() -> None:
    table1 = _table1_long_fixture()
    numeric = build_numeric_table(table1)
    scrutiny = build_scrutiny_input(table1)
    summary = summarize_numeric_flags(numeric)

    assert len(numeric) == 2
    assert set(numeric["variable"]) == {"Sex"}
    assert len(scrutiny) == 2
    assert summary["n_rows"] == 2
    assert summary["n_reported_p"] == 2


def test_numeric_rsprite2_stub_builder() -> None:
    table1 = _table1_long_fixture()
    numeric = build_numeric_table(table1)
    rsprite2_stub = build_rsprite2_stub(numeric)

    assert len(rsprite2_stub) == 1
    assert rsprite2_stub.iloc[0]["variable"] == "Sex"
    assert rsprite2_stub.iloc[0]["level"] == "Male"
    assert rsprite2_stub.iloc[0]["abs_percent_between_arms"] == 1.0


def test_numeric_precision_denominator_and_percentage_contract() -> None:
    assert _digits_from_str("1.20") == 2
    assert _digits_from_str("1.2") == 1
    assert _digits_from_str("1.2e-3") is None
    assert _to_int(10.5) is None
    assert _to_int(-2) == -2
    assert _to_int(float("nan")) is None
    assert _to_int(float("inf")) is None

    common = {
        "denominator_role": "analyzed",
        "weighting": "unweighted",
        "rounding_convention": "nearest_half_up",
    }
    assert (
        assess_percent_compatibility(
            count=1, denominator=3, reported_percent="33", reported_decimals=0, **common
        )
        == "compatible"
    )
    assert (
        assess_percent_compatibility(
            count=1, denominator=3, reported_percent="33.3", reported_decimals=1, **common
        )
        == "compatible"
    )
    assert (
        assess_percent_compatibility(
            count=1, denominator=3, reported_percent="34.0", reported_decimals=1, **common
        )
        == "incompatible"
    )
    assert (
        assess_percent_compatibility(
            count=1,
            denominator=3,
            reported_percent="33.3",
            reported_decimals=1,
            denominator_role="unknown",
            weighting="unweighted",
            rounding_convention="unknown",
        )
        == "indeterminate"
    )
    assert (
        assess_percent_compatibility(
            count=4, denominator=3, reported_percent="133.3", reported_decimals=1, **common
        )
        == "source_data_contradiction"
    )
    assert (
        assess_percent_compatibility(
            count=1,
            denominator=8,
            reported_percent="12",
            reported_decimals=0,
            denominator_role="analyzed",
            weighting="unweighted",
            rounding_convention="nearest_half_even",
        )
        == "compatible"
    )
    assert (
        assess_percent_compatibility(
            count=1,
            denominator=8,
            reported_percent="13",
            reported_decimals=0,
            denominator_role="analyzed",
            weighting="unweighted",
            rounding_convention="nearest_half_up",
        )
        == "compatible"
    )
    assert (
        assess_percent_compatibility(
            count=1,
            denominator=3,
            reported_percent="33.3",
            reported_decimals=1,
            denominator_role="analyzed",
            weighting="weighted",
            rounding_convention="nearest_half_up",
        )
        == "indeterminate"
    )

    invalid_counts = pd.DataFrame([1, -1, 4, float("nan"), 1], columns=["count"])
    invalid_counts["n_group"] = [3, 3, 3, 3, float("inf")]
    numeric_rows = pd.DataFrame(
        {
            "trial_id": "trial_x",
            "variable": "Event",
            "level": "yes",
            "group": "arm_a",
            "value": invalid_counts["count"],
            "n_group": invalid_counts["n_group"],
            "percent": 33.0,
            "reported_percent_raw": "33",
            "reported_percent_decimals": 0,
            "decimals": 0,
            "reported_p": None,
            "var_type": "categorical_count_percent",
        }
    )
    assert build_numeric_table(numeric_rows)["input_status"].tolist() == [
        "ok",
        "source_data_contradiction",
        "source_data_contradiction",
        "input_error",
        "input_error",
    ]


def test_p_value_inequality_and_out_of_range_value_are_preserved() -> None:
    rows = pd.DataFrame(
        [
            {
                "trial_id": "trial_x",
                "variable": "A",
                "reported_p": 0.001,
                "reported_p_raw": "P<0.001",
                "reported_p_comparator": "<",
            },
            {
                "trial_id": "trial_x",
                "variable": "B",
                "reported_p": 1.2,
                "reported_p_raw": "P=1.2",
                "reported_p_comparator": "=",
            },
        ]
    )
    statcheck = build_statcheck_stub(rows)
    assert statcheck["reported_p"].tolist() == [0.001, 1.2]
    assert statcheck["reported_p_raw"].tolist() == ["P<0.001", "P=1.2"]
    assert statcheck["reported_p_comparator"].tolist() == ["<", "="]
    assert statcheck["input_status"].tolist() == ["ok", "source_value_out_of_range"]


def test_printed_numeric_strings_survive_python_readr_python_roundtrip(tmp_path) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise RuntimeError("Rscript is required for the numeric precision roundtrip regression.")
    source = tmp_path / "numeric.csv"
    destination = tmp_path / "roundtrip.csv"
    pd.DataFrame({"x": ["1.20", "1.2"], "sd": ["0.40", "0.4"]}).to_csv(source, index=False)
    expression = (
        'source("scripts/run_numeric_forensics.R"); '
        f'd <- read_numeric_csv("{source}"); '
        'stopifnot(identical(d$x, c("1.20", "1.2"))); '
        f'readr::write_csv(d, "{destination}")'
    )
    subprocess.run(
        [rscript, "-e", expression],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    roundtrip = pd.read_csv(destination, dtype={"x": "string", "sd": "string"})
    assert roundtrip["x"].tolist() == ["1.20", "1.2"]
    assert roundtrip["sd"].tolist() == ["0.40", "0.4"]


def test_scrutiny_case_eligibility_and_method_inputs() -> None:
    scrutiny_input = pd.DataFrame(
        [
            {
                "trial_id": "trial_x",
                "item_label": "Age [early_tod]",
                "n": 100,
                "x": 61.0,
                "decimals": 1,
            }
        ]
    )
    numeric_summary_long = pd.DataFrame(
        [
            {
                "trial_id": "trial_x",
                "source_pdf": "report.pdf",
                "source_table": "table1",
                "source_page": 3,
                "variable": "Age",
                "level": "all",
                "group": "late_tod",
                "n": 100,
                "x_str": "60.1",
                "sd_str": "12.3",
                "digits_x": 1,
                "digits_sd": 1,
            },
            {
                "trial_id": "trial_x",
                "source_pdf": "report.pdf",
                "source_table": "table1",
                "source_page": 3,
                "variable": "Outcome proportion",
                "level": "all",
                "group": "early_tod",
                "n": 100,
                "x_str": "0.60",
                "sd_str": "0.49",
                "digits_x": 2,
                "digits_sd": 2,
            },
        ]
    )

    cases = build_scrutiny_cases(
        scrutiny_input=scrutiny_input,
        numeric_summary_long=numeric_summary_long,
        source_pdf="report.pdf",
    )
    grim_input = build_scrutiny_grim_input(cases)
    grimmer_input = build_scrutiny_grimmer_input(cases)
    debit_input = build_scrutiny_debit_input(cases)
    duplicate_input = build_scrutiny_duplicate_input(cases)
    rounding_bias_input = build_scrutiny_rounding_bias_input(cases)

    assert len(cases) == 3
    assert cases["eligible_grim"].sum() == 0
    assert cases["eligible_grimmer"].sum() == 0
    assert cases["eligible_debit"].sum() == 0
    assert len(grim_input) == 0
    assert len(grimmer_input) == 0
    assert len(debit_input) == 0
    assert cases.loc[0, "statistic_kind"] == "median"
    assert cases.loc[0, "exclude_reason_grim"] == "statistic_not_arithmetic_mean"
    assert cases.loc[2, "exclude_reason_debit"] == "measurement_scale_not_bernoulli"
    assert len(duplicate_input) == 3
    assert len(rounding_bias_input) == 3


def test_scrutiny_eligibility_requires_documented_summary_semantics() -> None:
    common = {
        "trial_id": "trial_x",
        "source_pdf": "report.pdf",
        "source_table": "table2",
        "source_page": 4,
        "variable": "Outcome",
        "level": "all",
        "group": "arm_a",
        "n": 100,
        "x_str": "0.60",
        "sd_str": "0.20",
        "digits_x": 2,
        "digits_sd": 2,
        "statistic_kind": "arithmetic_mean",
        "measurement_scale": "integer_valued",
        "raw_or_adjusted": "raw",
        "weighting": "unweighted",
        "analysis_n": 100,
        "imputation_status": "not_imputed",
        "transformation_status": "none",
        "granularity_transformation": "",
        "eligibility_evidence": "Table 2 footnote: unadjusted arithmetic mean; integer score.",
    }
    rows = [
        common,
        {
            **common,
            "variable": "Bounded continuous outcome",
            "measurement_scale": "continuous_bounded",
            "eligibility_evidence": "Table 2 reports a bounded continuous score.",
        },
        {
            **common,
            "variable": "Binary outcome",
            "measurement_scale": "bernoulli",
            "eligibility_evidence": "Methods: coded 0/1; unadjusted arm mean and SD.",
        },
        {
            **common,
            "variable": "Adjusted score",
            "raw_or_adjusted": "adjusted",
            "eligibility_evidence": "Adjusted model estimate.",
        },
        {
            **common,
            "variable": "Unknown scale",
            "measurement_scale": "unknown",
            "eligibility_evidence": "No measurement-scale description found.",
        },
        {**common, "variable": "Weighted summary", "weighting": "weighted"},
        {**common, "variable": "Imputed summary", "imputation_status": "imputed"},
        {
            **common,
            "variable": "Unsupported transformation",
            "transformation_status": "transformed",
        },
        {**common, "variable": "Mismatched n", "analysis_n": 90},
        {**common, "variable": "Noninteger n", "n": 10.5, "analysis_n": 10.5},
        {**common, "variable": "Negative n", "n": -1, "analysis_n": -1},
        {**common, "variable": "NaN n", "n": float("nan"), "analysis_n": float("nan")},
        {**common, "variable": "Infinite n", "n": float("inf"), "analysis_n": float("inf")},
        {**common, "variable": "Precision mismatch", "x_str": "1.20", "digits_x": 1},
    ]
    cases = build_scrutiny_cases(
        scrutiny_input=pd.DataFrame(),
        numeric_summary_long=pd.DataFrame(rows),
    )
    grim_input = build_scrutiny_grim_input(cases)
    grimmer_input = build_scrutiny_grimmer_input(cases)
    debit_input = build_scrutiny_debit_input(cases)

    assert cases["eligible_grim"].tolist() == [True, False, True] + [False] * 11
    assert cases["eligible_grimmer"].tolist() == cases["eligible_grim"].tolist()
    assert cases["eligible_debit"].tolist() == [False, False, True] + [False] * 11
    assert cases.loc[1, "exclude_reason_debit"] == "measurement_scale_not_bernoulli"
    assert len(grim_input) == len(grimmer_input) == 2
    assert len(debit_input) == 1
    assert set(grim_input["method_revision"]) == {"numeric_eligibility_precision_v3"}
    assert set(debit_input["measurement_scale"]) == {"bernoulli"}


def test_numeric_r_boundary_revalidates_method_eligibility() -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise RuntimeError("Rscript is required for the numeric eligibility boundary regression.")
    expression = r"""
source("scripts/run_numeric_forensics.R")
valid <- tibble::tibble(
  n = c(100, 100, 100, 100, 10.5, 100),
  analysis_n = c(100, 100, 100, 100, 10.5, 100),
  digits_x = c(2, 2, 2, 2, 2, 2), digits_sd = c(2, 2, 2, 2, 2, 2),
  x = c("0.60", "0.60", "0.60", "0.60", "0.60", "0.6"),
  sd = c("0.20", "0.20", "0.20", "0.20", "0.20", "0.20"),
  statistic_kind = c("arithmetic_mean", "median", rep("arithmetic_mean", 4)),
  measurement_scale = c(
    "integer_valued", "integer_valued", "continuous_bounded", "bernoulli",
    "integer_valued", "integer_valued"
  ),
  raw_or_adjusted = "raw", weighting = "unweighted",
  imputation_status = "not_imputed", transformation_status = "none",
  granularity_transformation = "",
  eligibility_evidence = "Methods describe the summary and scale.",
  method_revision = "numeric_eligibility_precision_v3"
)
stopifnot(nrow(validate_scrutiny_input(valid, "grim")) == 2L)
stopifnot(nrow(validate_scrutiny_input(valid, "debit")) == 1L)
legacy <- valid[, setdiff(names(valid), c("measurement_scale", "method_revision"))]
stopifnot(nrow(validate_scrutiny_input(legacy, "grim")) == 0L)
"""
    subprocess.run(
        [rscript, "-e", expression],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def test_scrutiny_builders_return_header_only_when_empty() -> None:
    scrutiny_input = pd.DataFrame(columns=["trial_id", "item_label", "n", "x", "decimals"])
    numeric_summary_long = pd.DataFrame(
        columns=[
            "trial_id",
            "source_pdf",
            "source_table",
            "source_page",
            "variable",
            "level",
            "group",
            "n",
            "x_str",
            "sd_str",
            "digits_x",
            "digits_sd",
        ]
    )

    cases = build_scrutiny_cases(
        scrutiny_input=scrutiny_input,
        numeric_summary_long=numeric_summary_long,
        source_pdf="report.pdf",
    )
    grim_input = build_scrutiny_grim_input(cases)
    grimmer_input = build_scrutiny_grimmer_input(cases)
    debit_input = build_scrutiny_debit_input(cases)
    duplicate_input = build_scrutiny_duplicate_input(cases)
    rounding_bias_input = build_scrutiny_rounding_bias_input(cases)

    assert cases.empty
    assert grim_input.empty
    assert grimmer_input.empty
    assert debit_input.empty
    assert duplicate_input.empty
    assert rounding_bias_input.empty
    assert "case_id" in grim_input.columns
    assert "sd" in grimmer_input.columns
    assert "sd" in debit_input.columns
    assert "x" in duplicate_input.columns
    assert "digits_x" in rounding_bias_input.columns


def test_registration_claims_and_registry_id_extraction() -> None:
    report_pages = [
        "Methods randomisation was performed in a 1:1 ratio. Trial ISRCTN12345678.",
        "Open-label study; participants were not masked.",
    ]
    protocol_pages = [
        "Section 3.2 randomization in 1:1 ratio. Registration ISRCTN12345678.",
        "Open-\u00adlabel trial with blinded endpoint review.",
    ]
    ids = extract_registry_ids(report_pages[0])
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=report_pages,
        protocol_page_texts=protocol_pages,
    )

    assert ids == ["ISRCTN12345678"]
    assert not claims.empty
    assert "allocation_ratio" in claims["claim"].tolist()
    ratio_row = claims[claims["claim"] == "allocation_ratio"].iloc[0]
    assert ratio_row["match_status"]
    registry_row = claims[claims["claim"] == "registry_id_overlap"].iloc[0]
    assert registry_row["match_status"]
    randomization_row = claims[claims["claim"] == "randomization_phrase"].iloc[0]
    assert randomization_row["match_status"]
    blinding_row = claims[claims["claim"] == "blinding_phrase"].iloc[0]
    assert blinding_row["match_status"]


def test_visual_forensics_caption_checks() -> None:
    page_texts = [
        "Figure 1: Baseline curve overview.\nFigure 2: Survival by subgroup.",
        "Figure 3: Baseline curve overview.",
    ]
    checks = build_visual_checks(page_texts, "trial_x")
    dupes = detect_caption_duplicates(checks, similarity_threshold=0.85)
    gaps = detect_figure_numbering_gaps(checks)

    assert len(checks) == 3
    assert not dupes.empty
    assert gaps == []


def test_meta_forensics_score_aggregation() -> None:
    summary_tables = {
        "randomization": pd.DataFrame([{"fisher_recalc": 0.20}]),
        "numeric": pd.DataFrame([{"median_abs_percent_delta": 0.4}]),
        "registration": pd.DataFrame([{"mismatch_rate": 0.25}]),
        "visual": pd.DataFrame([{"near_duplicate_rate": 0.10}]),
        "transparency": pd.DataFrame([{"transparency_evidence_burden": 0.25}]),
    }
    scores = build_category_scores(summary_tables)
    overall = compute_overall_meta_score(scores)

    assert set(scores["category"]) == {
        "randomization",
        "numeric",
        "registration",
        "visual",
        "transparency",
    }
    assert 0.0 <= overall["overall_score"] <= 1.0
    assert overall["evidence_burden_score"] == overall["overall_score"]
    assert overall["risk_tier"] in {"low", "moderate", "high"}
    assert overall["review_priority"] == overall["risk_tier"]


def test_manifest_upsert_replaces_existing_category(tmp_path: Path) -> None:
    manifest_path = tmp_path / "forensics_manifest.csv"
    upsert_manifest_row(
        manifest_path,
        study_id="trial_x",
        source_pdf="report.pdf",
        category="transparency",
        extract_confidence="high",
        page_ref="3",
        table_ref="table1",
        analysis_ready=False,
    )
    upsert_manifest_row(
        manifest_path,
        study_id="trial_x",
        source_pdf="report.pdf",
        category="transparency",
        extract_confidence="high",
        page_ref="3",
        table_ref="table1",
        analysis_ready=True,
    )

    manifest = load_manifest(manifest_path)
    assert len(manifest) == 1
    assert bool(manifest.iloc[0]["analysis_ready"]) is True
