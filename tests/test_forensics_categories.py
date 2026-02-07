from __future__ import annotations

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
    assert cases["eligible_grim"].sum() == 3
    assert cases["eligible_grimmer"].sum() == 2
    assert cases["eligible_debit"].sum() == 1
    assert len(grim_input) == 3
    assert len(grimmer_input) == 2
    assert len(debit_input) == 1
    assert len(duplicate_input) == 3
    assert len(rounding_bias_input) == 3


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
        "Methods randomization was performed in a 1:1 ratio. Trial NCT12345678.",
        "Open-label study.",
    ]
    protocol_pages = [
        "Section 3.2 randomization in 1:1 ratio. Registration NCT12345678.",
        "Blinded endpoint review.",
    ]
    ids = extract_registry_ids(report_pages[0])
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=report_pages,
        protocol_page_texts=protocol_pages,
    )

    assert ids == ["NCT12345678"]
    assert not claims.empty
    assert "allocation_ratio" in claims["claim"].tolist()
    ratio_row = claims[claims["claim"] == "allocation_ratio"].iloc[0]
    assert ratio_row["match_status"]


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
    }
    scores = build_category_scores(summary_tables)
    overall = compute_overall_meta_score(scores)

    assert set(scores["category"]) == {"randomization", "numeric", "registration", "visual"}
    assert 0.0 <= overall["overall_score"] <= 1.0
    assert overall["risk_tier"] in {"low", "moderate", "high"}


def test_manifest_upsert_replaces_existing_category(tmp_path: Path) -> None:
    manifest_path = tmp_path / "forensics_manifest.csv"
    upsert_manifest_row(
        manifest_path,
        study_id="trial_x",
        source_pdf="report.pdf",
        category="numeric",
        extract_confidence="high",
        page_ref="3",
        table_ref="table1",
        analysis_ready=False,
    )
    upsert_manifest_row(
        manifest_path,
        study_id="trial_x",
        source_pdf="report.pdf",
        category="numeric",
        extract_confidence="high",
        page_ref="3",
        table_ref="table1",
        analysis_ready=True,
    )

    manifest = load_manifest(manifest_path)
    assert len(manifest) == 1
    assert bool(manifest.iloc[0]["analysis_ready"]) is True
