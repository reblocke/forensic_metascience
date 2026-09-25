from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import load_manifest, upsert_manifest_row
from research_project.meta_forensics import build_category_scores, compute_overall_meta_score
from research_project.numeric_integrity import (
    build_numeric_table,
    build_rsprite2_stub,
    build_scrutiny_cases,
    build_scrutiny_debit_input,
    build_scrutiny_duplicate_input,
    build_scrutiny_grim_input,
    build_scrutiny_grimmer_input,
    build_scrutiny_input,
    build_scrutiny_rounding_bias_input,
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
    ]
    cases = build_scrutiny_cases(
        scrutiny_input=pd.DataFrame(),
        numeric_summary_long=pd.DataFrame(rows),
    )
    grim_input = build_scrutiny_grim_input(cases)
    grimmer_input = build_scrutiny_grimmer_input(cases)
    debit_input = build_scrutiny_debit_input(cases)

    assert cases["eligible_grim"].tolist() == [
        True,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert cases["eligible_grimmer"].tolist() == cases["eligible_grim"].tolist()
    assert cases["eligible_debit"].tolist() == [
        False,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert cases.loc[1, "exclude_reason_debit"] == "measurement_scale_not_bernoulli"
    assert len(grim_input) == len(grimmer_input) == 2
    assert len(debit_input) == 1
    assert set(grim_input["method_revision"]) == {"numeric_eligibility_v2"}
    assert set(debit_input["measurement_scale"]) == {"bernoulli"}


def test_numeric_r_boundary_revalidates_method_eligibility() -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise RuntimeError("Rscript is required for the numeric eligibility boundary regression.")
    expression = r"""
source("scripts/run_numeric_forensics.R")
valid <- tibble::tibble(
  n = c(100, 100, 100, 100), analysis_n = c(100, 100, 100, 100),
  x = c("0.60", "0.60", "0.60", "0.60"),
  sd = c("0.20", "0.20", "0.20", "0.20"),
  statistic_kind = c("arithmetic_mean", "median", "arithmetic_mean", "arithmetic_mean"),
  measurement_scale = c("integer_valued", "integer_valued", "continuous_bounded", "bernoulli"),
  raw_or_adjusted = "raw", weighting = "unweighted",
  imputation_status = "not_imputed", transformation_status = "none",
  granularity_transformation = "",
  eligibility_evidence = "Methods describe the summary and scale.",
  method_revision = "numeric_eligibility_v2"
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
