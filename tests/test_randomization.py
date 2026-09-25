from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from research_project.numeric_integrity import build_numeric_table, build_scrutiny_input
from research_project.randomization import (
    build_csf_input,
    build_reported_tests,
    build_simdistr_input,
    parse_group_header,
    parse_table1_long,
)


def _table1_fixture() -> list[list[str]]:
    return [
        [
            "Characteristics",
            "Early ToD group (n = 105)",
            "Late ToD group (n = 105)",
            "P value",
        ],
        ["Age (year, median, range)", "61 (33-80)", "60 (34-77)", "0.53"],
        ["Sex (n, %)", "", "", ""],
        ["Male", "95 (90.5)", "95 (90.5)", "1.000"],
        ["Female", "10 (9.5)", "10 (9.5)", ""],
        ["Smoking history (n, %)", "", "", ""],
        ["Smoker", "84 (80.0)", "87 (82.9)", "0.590"],
        ["Never smoked", "21 (20.0)", "18 (17.1)", ""],
        ["PD-L1 TPS (n, %)", "", "", ""],
        ["<1%", "41 (39.0)", "47 (44.8)", "0.862"],
        ["1-49%", "31 (29.5)", "29 (27.5)", ""],
        [">=50%", "26 (24.8)", "22 (21.0)", ""],
        ["Unknown", "7 (6.7)", "7 (6.7)", ""],
        ["LIPI score (n, %)", "", "", ""],
        ["Low risk", "63 (60.0)", "58 (55.2)", "0.673"],
        ["Medium risk", "35 (33.3)", "37 (35.3)", ""],
        ["High risk", "7 (6.7)", "10 (9.5)", ""],
    ]


def _hierarchical_table_fixture() -> list[list[str | None]]:
    return [
        ["", "", "PCT", "Usual care"],
        ["N", "", "3092/6119 (50.5%)", "3027/6119 (49.5%)"],
        ["Age (years)", "Median [IQR]", "72 [57, 82]", "73 [58, 82]"],
        ["Gender (%)", "Male", "1533/3092 (49.6%)", "1519/3027 (50.2%)"],
        [None, "Female", "1557/3092 (50.4%)", "1508/3027 (49.8%)"],
        ["Comorbidities", "Diabetes Mellitus", "623/2738 (22.8%)", "651/2715 (24.0%)"],
        [None, "COPD", "624/2738 (22.8%)", "615/2715 (22.7%)"],
    ]


def test_parse_table1_long_extracts_expected_fields() -> None:
    table = _table1_fixture()
    parsed = parse_table1_long(table=table, trial_id="trial_x", source_page=3)

    assert not parsed.empty
    assert set(parsed["group"]) == {"early_tod", "late_tod"}
    assert set(parsed["trial_id"]) == {"trial_x"}

    age_rows = parsed[
        (parsed["variable"] == "Age (year, median, range)") & (parsed["level"] == "all")
    ]
    assert len(age_rows) == 2
    assert sorted(age_rows["value"].tolist()) == [60.0, 61.0]

    sex_rows = parsed[(parsed["variable"] == "Sex") & (parsed["level"] == "Male")]
    assert len(sex_rows) == 2
    assert sex_rows["reported_p"].dropna().iloc[0] == 1.0

    smoking_rows = parsed[
        (parsed["variable"] == "Smoking history") & (parsed["level"] == "Never smoked")
    ]
    assert len(smoking_rows) == 2
    assert smoking_rows["reported_p"].dropna().iloc[0] == 0.59


def test_table1_preserves_source_numeric_strings_and_p_comparator() -> None:
    table = [
        ["Characteristics", "Arm A (n = 3)", "Arm B (n = 3)", "P value"],
        ["Age (years, median, range)", "61.20 (33.00-80.00)", "60.10 (34.00-77.00)", "P=1.2"],
        ["Outcome (n, %)", "1 (33%)", "1 (33.3%)", "P<0.001"],
    ]
    parsed = parse_table1_long(table=table, trial_id="trial_x", source_page=3)
    arm_a = parsed[(parsed["group"] == "a") & (parsed["variable"] == "Outcome")].iloc[0]
    assert arm_a["raw_value"] == "1 (33%)"
    assert arm_a["source_locator"]
    assert arm_a["reported_p_raw"] == "P<0.001"
    assert arm_a["reported_p_comparator"] == "<"
    assert arm_a["denominator_role"] == "unknown"
    age = parsed[parsed["variable"].str.startswith("Age")].iloc[0]
    assert age["raw_statistic_value"] == "61.20"
    assert age["reported_decimals"] == 2
    assert age["reported_p"] == 1.2
    assert age["reported_p_raw"] == "P=1.2"
    assert build_numeric_table(parsed[parsed["variable"] == "Outcome"])[
        "compatibility_status"
    ].tolist() == ["indeterminate", "indeterminate"]
    median_inputs = build_scrutiny_input(parsed)
    assert median_inputs.iloc[0]["x"] == "61.20"
    assert median_inputs.iloc[0]["decimals"] == 2


def test_malformed_counts_are_excluded_from_randomization_method_inputs() -> None:
    table = [
        ["Characteristics", "Arm A (n = 3)", "Arm B (n = 3)", "P value"],
        ["Event (n, %)", "4 (133.3%)", "-1 (-33.3%)", "0.50"],
    ]
    parsed = parse_table1_long(table=table, trial_id="trial_x", source_page=3)
    numeric = build_numeric_table(parsed)
    assert numeric["input_status"].tolist() == [
        "source_data_contradiction",
        "source_data_contradiction",
    ]
    assert build_simdistr_input(parsed).empty
    assert build_csf_input(parsed).empty
    try:
        parse_group_header("Arm A (n = 10.5)")
    except ValueError:
        pass
    else:
        raise AssertionError("A noninteger arm denominator must be rejected.")


def test_build_package_inputs_shapes_and_columns() -> None:
    parsed = parse_table1_long(table=_table1_fixture(), trial_id="trial_x", source_page=3)
    simdistr_df = build_simdistr_input(parsed)
    csf_df = build_csf_input(parsed)

    assert not simdistr_df.empty
    assert not csf_df.empty
    assert simdistr_df["9_observed_pval"].isna().all()
    assert list(simdistr_df.columns) == [
        "1_category",
        "2_outcome",
        "3_n_arm1",
        "4_n_arm2",
        "5_n_arm1_outcome",
        "6_n_arm2_outcome",
        "7_prop_arm1",
        "8_prop_arm2",
        "9_observed_pval",
    ]

    sex_rows = simdistr_df[simdistr_df["1_category"] == "Sex"]
    assert len(sex_rows) == 1
    assert sex_rows.iloc[0]["2_outcome"] == "Male"

    pdl1_rows = simdistr_df[simdistr_df["1_category"] == "PD-L1 TPS"]
    assert len(pdl1_rows) == 4

    assert csf_df["one_vs_rest"].all()
    assert set(csf_df["trial_id"]) == {"trial_x"}


def test_reported_omnibus_record_is_deduplicated_and_never_repeated_as_level_p() -> None:
    parsed = parse_table1_long(_table1_fixture(), "trial_x", 3)
    reported = build_reported_tests(parsed)
    pdl1 = reported[reported["parent_variable"] == "PD-L1 TPS"]
    assert len(pdl1) == 1
    assert pdl1.iloc[0]["reported_test_scope"] == "unknown"
    assert pdl1.iloc[0]["reported_test_method"] == "unknown"
    assert pdl1.iloc[0]["reported_test_tail"] == "unknown"
    assert pdl1.iloc[0]["analysis_population"] == "unknown"
    assert pdl1.iloc[0]["reported_p_comparator"] == "="

    recalc = build_csf_input(parsed)
    pdl1_rows = recalc[recalc["parent_variable"] == "PD-L1 TPS"]
    assert len(pdl1_rows) == 4
    assert pdl1_rows["reported_test_id"].nunique() == 1
    assert "reported_p" not in recalc
    assert recalc["recalculated_test_method"].eq("pearson_chi_square_2x2").all()
    assert recalc["recalculated_test_tail"].eq("two_sided").all()
    assert recalc["comparison_status"].eq("not_comparable").all()


def test_equal_p_values_at_distinct_source_rows_remain_distinct_tests() -> None:
    table = [
        ["Characteristics", "Arm A (n = 4)", "Arm B (n = 4)", "P value"],
        ["Three-level factor (n, %)", "", "", ""],
        ["A", "2 (50%)", "2 (50%)", "0.50"],
        ["B", "1 (25%)", "1 (25%)", "0.50"],
        ["C", "1 (25%)", "1 (25%)", ""],
    ]
    parsed = parse_table1_long(table, "trial_x", 4)
    reported = build_reported_tests(parsed)
    assert len(reported[reported["parent_variable"] == "Three-level factor"]) == 2
    recalc = build_csf_input(parsed)
    level_ids = recalc.set_index("level")["reported_test_id"]
    assert level_ids["A"] != level_ids["B"]


def test_randomization_test_ids_and_order_are_stable_under_row_reordering() -> None:
    parsed = parse_table1_long(_table1_fixture(), "trial_x", 3)
    reversed_rows = parsed.iloc[::-1].reset_index(drop=True)
    first = build_csf_input(parsed)
    second = build_csf_input(reversed_rows)
    pd.testing.assert_frame_equal(build_simdistr_input(parsed), build_simdistr_input(reversed_rows))
    assert first["recalculated_test_id"].tolist() == second["recalculated_test_id"].tolist()
    assert first["recalculated_test_id"].is_unique
    assert (
        build_reported_tests(parsed)["reported_test_id"].tolist()
        == build_reported_tests(reversed_rows)["reported_test_id"].tolist()
    )


def test_builder_writes_separate_reported_test_records(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    parsed = parse_table1_long(_table1_fixture(), "trial_x", 3)
    input_path = tmp_path / "table1_long.csv"
    output_dir = tmp_path / "inputs"
    parsed.to_csv(input_path, index=False)
    subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts/build_randomization_inputs.py"),
            "--in",
            str(input_path),
            "--out",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(project_root / "src")},
    )
    reported = pd.read_csv(output_dir / "reported_tests_v1.csv")
    csf = pd.read_csv(output_dir / "csf_input_v2.csv")
    simdistr_input = pd.read_csv(output_dir / "simdistr_input_v2.csv")
    assert reported["reported_test_id"].is_unique
    assert "reported_p" not in csf.columns
    assert simdistr_input["9_observed_pval"].isna().all()
    pdl1 = reported[reported["parent_variable"] == "PD-L1 TPS"]
    assert len(pdl1) == 1


def test_randomization_r_runner_gates_design_and_fixed_block_count_check(tmp_path: Path) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript is unavailable; production R integration is unverified.")
    project_root = Path(__file__).resolve().parents[1]
    csf = pd.DataFrame(
        [
            {
                "trial_id": "synthetic",
                "parent_variable": "Three-level factor",
                "variable": "Three-level factor",
                "level": level,
                "n_arm1": 2,
                "n_arm2": 1,
                "count_arm1": count_a,
                "count_arm2": count_b,
                "prop_arm1": count_a / 2,
                "prop_arm2": float(count_b),
                "reported_test_id": "reported_test_1",
                "reported_percent_decimals_arm1": i - 1,
                "reported_percent_decimals_arm2": 3 - i,
                "one_vs_rest": True,
                "recalculated_test_id": f"recalc_{i}",
            }
            for i, (level, count_a, count_b) in enumerate(
                [("A", 1, 0), ("B", 1, 0), ("C", 0, 1)], start=1
            )
        ]
    )
    reported = pd.DataFrame(
        [
            {
                "schema_version": "reported_test_v1",
                "reported_test_id": "reported_test_1",
                "trial_id": "synthetic",
                "parent_variable": "Three-level factor",
                "reported_p": 0.04,
                "reported_p_raw": "P<0.05",
                "reported_p_comparator": "<",
                "reported_test_scope": "unknown",
                "reported_test_method": "unknown",
                "reported_test_tail": "unknown",
                "analysis_population": "unknown",
            }
        ]
    )
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    csf.to_csv(input_dir / "csf_input_v2.csv", index=False)
    reported.to_csv(input_dir / "reported_tests_v1.csv", index=False)

    def run(output_name: str, *args: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
        output_dir = tmp_path / output_name
        subprocess.run(
            [
                rscript,
                str(project_root / "scripts/run_randomization_forensics.R"),
                "--in",
                str(input_dir),
                "--out",
                str(output_dir),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = pd.read_csv(output_dir / "row_level_results_v2.csv")
        allocation = pd.read_csv(output_dir / "allocation_arithmetic_v1.csv")
        receipt = pd.read_csv(output_dir / "randomization_run_receipt_v1.csv").iloc[0].to_dict()
        return rows, allocation, receipt

    rows, allocation, receipt = run("default", "--allocation-design", "mrn_parity")
    assert rows["comparison_status"].eq("not_comparable").all()
    assert rows["flagged_p_delta_0_05"].isna().all()
    assert rows["row_chisq_p"].isna().all()
    assert rows["recalculated_p_status"].eq("unsupported_design").all()
    assert allocation.iloc[0]["status"] == "unsupported_design"
    assert receipt["inferential_diagnostic_status"] == "not_requested"
    assert pd.isna(receipt["seed"])
    assert (
        "fisher_reported" not in pd.read_csv(tmp_path / "default/pooled_descriptive_v2.csv").columns
    )
    reported_output = pd.read_csv(tmp_path / "default/reported_test_records_v1.csv")
    assert reported_output.iloc[0]["reported_p_comparator"] == "<"

    _, valid_block, _ = run(
        "valid_block",
        "--allocation-design",
        "fixed_block_4_single_list_1to1",
        "--allocation-counts-basis",
        "randomized",
        "--allocation-n-arm1",
        "3",
        "--allocation-n-arm2",
        "2",
        "--strata-count",
        "1",
        "--list-count",
        "1",
    )
    assert valid_block.iloc[0]["status"] == "consistent_with_design"

    _, excluded, _ = run(
        "post_exclusion",
        "--allocation-design",
        "fixed_block_4_single_list_1to1",
        "--allocation-counts-basis",
        "post_exclusion",
        "--allocation-n-arm1",
        "3",
        "--allocation-n-arm2",
        "2",
        "--strata-count",
        "1",
        "--list-count",
        "1",
    )
    assert excluded.iloc[0]["status"] == "unsupported_count_basis"

    _, multiple_strata, _ = run(
        "multiple_strata",
        "--allocation-design",
        "fixed_block_4_single_list_1to1",
        "--allocation-counts-basis",
        "randomized",
        "--allocation-n-arm1",
        "3",
        "--allocation-n-arm2",
        "2",
        "--strata-count",
        "2",
        "--list-count",
        "1",
    )
    assert multiple_strata.iloc[0]["status"] == "unsupported_structure"

    _, _, seeded_receipt = run(
        "seeded_missing_dependency",
        "--allocation-design",
        "unrestricted_individual_1to1",
        "--expert-opt-in",
        "true",
        "--seed",
        "123",
        "--m",
        "25",
    )
    assert seeded_receipt["seed"] == 123
    assert seeded_receipt["inferential_diagnostic_status"] == "dependency_missing"
    assert seeded_receipt["rng_kind"]
    seeded_rows = pd.read_csv(tmp_path / "seeded_missing_dependency/row_level_results_v2.csv")
    assert seeded_rows["recalculated_p_status"].eq("evaluated").all()
    assert seeded_rows["row_chisq_p"].notna().all()
    runtime_input = pd.read_csv(
        tmp_path / "seeded_missing_dependency/simdistr_runtime_input_v1.csv"
    )
    assert set(runtime_input["decimals"]) == {0, 1, 2}


def test_parse_hierarchical_supplement_baseline_table() -> None:
    parsed = parse_table1_long(
        table=_hierarchical_table_fixture(),
        trial_id="trial_y",
        source_page=12,
    )

    assert not parsed.empty
    assert set(parsed["group"]) == {"pct", "usual_care"}

    age_rows = parsed[(parsed["variable"] == "Age (years)") & (parsed["level"] == "all")]
    assert len(age_rows) == 2
    assert sorted(age_rows["value"].tolist()) == [72.0, 73.0]

    male_rows = parsed[(parsed["variable"] == "Gender (%)") & (parsed["level"] == "Male")]
    assert len(male_rows) == 2
    assert sorted(male_rows["n_group"].tolist()) == [3027, 3092]

    simdistr_df = build_simdistr_input(parsed)
    csf_df = build_csf_input(parsed)
    assert not simdistr_df.empty
    assert not csf_df.empty
