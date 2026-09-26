from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from research_project.inspect_sr.adapters import map_candidate_result
from research_project.inspect_sr.records import source_version_id
from research_project.numeric_integrity import (
    attach_source_evidence,
    build_scrutiny_cases,
    build_scrutiny_debit_input,
    build_scrutiny_duplicate_input,
    build_scrutiny_grim_input,
    build_scrutiny_grimmer_input,
    build_scrutiny_rounding_bias_input,
)

PINNED_R_PACKAGES = {
    "scrutiny": "0.6.2",
    "statcheck": "1.5.0",
    "simdistr": "1.0.1",
}

pytestmark = pytest.mark.native_r


def _rscript() -> str:
    executable = shutil.which("Rscript")
    required = os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1"
    if executable is None:
        if required:
            pytest.fail("Rscript is required by FORENSICS_REQUIRE_R_INTEGRATION=1")
        pytest.skip("Rscript unavailable; native method integration is not covered here")
    return executable


def _require_pinned_r_packages(rscript: str) -> None:
    required = os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1"
    expression = "; ".join(
        f'actual <- as.character(utils::packageVersion("{name}")); '
        f'if (actual != "{version}") stop("{name} version ", actual, " != pinned {version}")'
        for name, version in PINNED_R_PACKAGES.items()
    )
    result = subprocess.run([rscript, "-e", expression], capture_output=True, text=True)
    if result.returncode != 0:
        if required:
            pytest.fail(f"Pinned native R packages are required:\n{result.stderr}")
        pytest.skip("Pinned native R packages are unavailable; package lane is not covered")


def _write_numeric_fixture(input_dir: Path) -> list[dict[str, str]]:
    input_dir.mkdir(parents=True)

    def write_numeric_csv(frame: pd.DataFrame, name: str) -> None:
        frame = frame.copy()
        for column in (
            "x",
            "sd",
            "x_str",
            "sd_str",
            "raw_value",
            "raw_count",
            "reported_percent_raw",
            "reported_p",
            "reported_p_raw",
            "reported_p_comparator",
        ):
            if column not in frame:
                frame[column] = pd.NA
        frame.to_csv(input_dir / name, index=False)

    summary = pd.DataFrame(
        [
            {
                "trial_id": "synthetic_native",
                "source_pdf": "synthetic.pdf",
                "source_table": "synthetic_table",
                "source_page": 1,
                "source_locator": f"table1:row{i}",
                "raw_value": "0.5" if i == 1 else "0.50",
                "reported_decimals": i,
                "reported_p_raw": "P=.50",
                "reported_p_comparator": "=",
                "variable": "synthetic mean",
                "level": "all",
                "group": f"arm_{i}",
                "n": 100,
                "analysis_n": 100,
                "x_str": "0.5" if i == 1 else "0.50",
                "sd_str": "0.5" if i == 1 else "0.50",
                "digits_x": i,
                "digits_sd": i,
                "statistic_kind": "arithmetic_mean",
                "measurement_scale": "bernoulli",
                "raw_or_adjusted": "raw",
                "weighting": "unweighted",
                "imputation_status": "not_imputed",
                "transformation_status": "none",
                "granularity_transformation": "",
                "eligibility_evidence": "synthetic fixture explicitly declares raw count mean",
            }
            for i in (1, 2)
        ]
    )
    cases = build_scrutiny_cases(pd.DataFrame(), summary, source_pdf="synthetic.pdf")
    source_hash = "a" * 64
    cases, evidence_records = attach_source_evidence(
        cases,
        [
            {
                "source_id": "synthetic-report",
                "source_name": "synthetic.pdf",
                "source_version_id": source_version_id("synthetic-report", source_hash),
                "content_sha256": source_hash,
            }
        ],
    )
    write_numeric_csv(cases, "scrutiny_cases.csv")
    write_numeric_csv(build_scrutiny_grim_input(cases), "scrutiny_grim_input.csv")
    write_numeric_csv(build_scrutiny_grimmer_input(cases), "scrutiny_grimmer_input.csv")
    write_numeric_csv(build_scrutiny_debit_input(cases), "scrutiny_debit_input.csv")
    write_numeric_csv(build_scrutiny_duplicate_input(cases), "scrutiny_duplicates_input.csv")
    write_numeric_csv(build_scrutiny_rounding_bias_input(cases), "scrutiny_rounding_bias_input.csv")

    numeric_checks = pd.DataFrame(
        [
            {
                "trial_id": "synthetic_native",
                "variable": "synthetic mean",
                "level": "all",
                "group": "arm_1",
                "source_unit": "synthetic:table1:row1",
                "abs_percent_delta": 0.0,
                "legacy_abs_percent_delta": 0.0,
                "compatibility_status": "compatible",
                "reported_percent": 50.0,
                "computed_percent": 50.0,
                "reported_p": 0.5,
            }
        ]
    )
    write_numeric_csv(numeric_checks, "numeric_checks_input.csv")
    statcheck_input = pd.DataFrame(columns=["trial_id", "source_unit"])
    write_numeric_csv(statcheck_input, "statcheck_input.csv")
    rsprite2_input = pd.DataFrame(
        columns=[
            "trial_id",
            "variable",
            "level",
            "group_a",
            "group_b",
            "percent_a",
            "percent_b",
            "abs_percent_between_arms",
        ]
    )
    write_numeric_csv(rsprite2_input, "rsprite2_input.csv")
    (input_dir / "statcheck_text.txt").write_text(
        "The synthetic test reported t(28) = 2.20, p = .036.", encoding="utf-8"
    )
    return evidence_records


def test_malformed_simdistr_output_raises_instead_of_becoming_no_finding() -> None:
    rscript = _rscript()
    project_root = Path(__file__).resolve().parents[1]
    expression = (
        f'source("{project_root / "scripts/run_randomization_forensics.R"}"); '
        'result <- tryCatch(parse_simdistr_output("not a simdistr table"), '
        "error = function(e) conditionMessage(e)); "
        'stopifnot(is.character(result), grepl("Could not parse simdistr output", result))'
    )
    subprocess.run([rscript, "-e", expression], check=True, capture_output=True, text=True)


def test_native_method_adapters_match_independent_synthetic_expectations() -> None:
    rscript = _rscript()
    _require_pinned_r_packages(rscript)
    expression = r"""
source("scripts/run_numeric_forensics.R")
base <- tibble::tibble(
  case_id = c("valid", "invalid"), trial_id = "synthetic", source_unit = "table:row",
  variable = "binary_count", level = "event", group = "arm",
  x = c("0.25", "0.26"), sd = c("0.50", "0.51"), n = c(4, 4),
  digits_x = c(2L, 2L), digits_sd = c(2L, 2L)
)
# Four binary observations with one event have mean 0.25 and sample SD 0.50.
# A mean of 0.26 or SD of 0.51 is incompatible at two printed decimals.
grim <- run_scrutiny_grim(base)$raw
grimmer <- run_scrutiny_grimmer(dplyr::mutate(base, x = "0.25"))$raw
debit <- run_scrutiny_debit(dplyr::mutate(base, x = "0.25"))$raw
stopifnot(identical(grim$consistency, c(TRUE, FALSE)))
stopifnot(identical(grimmer$consistency, c(TRUE, FALSE)))
stopifnot(identical(debit$consistency, c(TRUE, FALSE)))
duplicates <- run_scrutiny_duplicates(tibble::tibble(
  case_id = c("a", "b", "c"), trial_id = "synthetic", source_unit = "table:row",
  variable = "binary_count", level = "event", group = "arm",
  x = c("0.25", "0.25", "0.75"), sd = c("0.50", "0.50", "0.43"), n = c(4, 4, 4)
))$raw
stopifnot(identical(duplicates$x_dup, c(TRUE, TRUE, FALSE)))
statcheck <- run_statcheck("t(28) = 2.20, p = .036. t(28) = 2.20, p = .90.")$raw
stopifnot(identical(statcheck$error, c(FALSE, TRUE)))
stopifnot(all(abs(statcheck$computed_p - 0.0362) < 0.001))
"""
    subprocess.run([rscript, "-e", expression], check=True, capture_output=True, text=True)
    blocked = subprocess.run(
        [
            rscript,
            "scripts/run_numeric_forensics.R",
            "--in",
            "input",
            "--out",
            "output",
            "--scrutiny-seq",
            "true",
        ],
        capture_output=True,
        text=True,
    )
    assert blocked.returncode != 0 and "blocked" in blocked.stderr


def test_simdistr_extreme_binary_fixtures_have_known_outputs() -> None:
    rscript = _rscript()
    _require_pinned_r_packages(rscript)
    expression = r"""
runtime <- data.frame(
  trial = c(1, 1), variable = c(1, 1), group = c(1, 2),
  participants = c(100, 100), mean = c(0, 0), sd = c(NA, NA),
  decimals = c(2, 2), type = c(2, 2), name = c("synthetic", "synthetic")
)
set.seed(123)
equal <- capture.output(simdistr::sim_distr(100, runtime, FALSE))
# Both arms are deterministically all zero, so all simulated squared differences
# equal the observed zero: (Pr[<] + Pr[<=]) / 2 = (0 + 1) / 2.
stopifnot(any(grepl("synthetic[[:space:]]+0[.]5", equal)))
runtime$mean <- c(0, 1)
set.seed(123)
separated <- capture.output(simdistr::sim_distr(100, runtime, FALSE))
# A 0-versus-1 difference is the maximum possible binary-arm difference.
stopifnot(any(grepl("synthetic[[:space:]]+1([[:space:]]|$)", separated)))
"""
    subprocess.run([rscript, "-e", expression], check=True, capture_output=True, text=True)


def test_numeric_production_runner_executes_pinned_method_packages(tmp_path: Path) -> None:
    rscript = _rscript()
    _require_pinned_r_packages(rscript)
    project_root = Path(__file__).resolve().parents[1]
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "numeric-output"
    evidence_records = _write_numeric_fixture(input_dir)
    bias_input_path = input_dir / "scrutiny_rounding_bias_input.csv"
    bias_input = pd.read_csv(bias_input_path)
    pd.concat([bias_input, bias_input.iloc[[0]]], ignore_index=True).to_csv(
        bias_input_path, index=False
    )
    subprocess.run(
        [
            rscript,
            str(project_root / "scripts/run_numeric_forensics.R"),
            "--in",
            str(tmp_path),
            "--out",
            str(output_dir),
            "--run-id",
            "native-run-fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipts = pd.read_csv(output_dir / "numeric_method_receipts.csv").set_index("method_id")
    assert set(receipts["run_id"]) == {"native-run-fixture"}
    for method_id in (
        "scrutiny_grim_map",
        "scrutiny_grimmer_map",
        "scrutiny_debit_map",
        "scrutiny_duplicates",
        "scrutiny_rounding_bias",
        "statcheck",
    ):
        receipt = receipts.loc[method_id]
        assert receipt["execution"] == "completed", (method_id, receipt.to_dict())
        assert receipt["n_evaluated"] >= 1, (method_id, receipt.to_dict())
    rounding_receipt = receipts.loc["scrutiny_rounding_bias"]
    assert rounding_receipt["n_input"] == 3
    assert rounding_receipt["n_eligible"] == 2
    assert rounding_receipt["n_evaluated"] == 2
    assert set(pd.read_csv(output_dir / "numeric_package_status.csv")["version"].dropna()) >= {
        "0.6.2",
        "1.5.0",
    }
    assert pd.read_csv(output_dir / "numeric_standardized_results.csv").shape[0] > 0
    results_v2 = pd.read_csv(output_dir / "numeric_standardized_results_v2.csv")
    assert set(results_v2["schema_version"]) == {"numeric_result_v2"}
    assert set(results_v2["run_id"]) == {"native-run-fixture"}
    assert results_v2["result_id"].notna().all()
    assert "source_locator" in results_v2.columns
    assert "input_evidence_ids" in results_v2.columns
    candidate_rows = []
    result_records = results_v2.astype(object).where(pd.notna(results_v2), None).to_dict("records")
    receipt_records = (
        receipts.reset_index()
        .astype(object)
        .where(pd.notna(receipts.reset_index()), None)
        .to_dict("records")
    )
    for result in result_records:
        if not result.get("source_locator") or not result.get("input_evidence_ids"):
            continue
        candidate_rows.extend(map_candidate_result(result, receipt_records, evidence_records))
    assert candidate_rows
    assert all(candidate["candidate_status"] == "candidate_only" for candidate in candidate_rows)


def test_randomization_production_runner_executes_seeded_pinned_simdistr(
    tmp_path: Path,
) -> None:
    rscript = _rscript()
    _require_pinned_r_packages(rscript)
    project_root = Path(__file__).resolve().parents[1]
    input_dir = tmp_path / "randomization-input"
    input_dir.mkdir()
    csf = pd.DataFrame(
        [
            {
                "schema_version": "baseline_csf_v3",
                "trial_id": "synthetic_native",
                "parent_variable": "binary outcome",
                "variable": "binary outcome",
                "level": "event",
                "n_arm1": 100,
                "n_arm2": 100,
                "count_arm1": 33,
                "count_arm2": 41,
                "prop_arm1": 0.33,
                "prop_arm2": 0.41,
                "reported_percent_raw_arm1": "33.0",
                "reported_percent_raw_arm2": "41.0",
                "reported_percent_decimals_arm1": 1,
                "reported_percent_decimals_arm2": 1,
                "reported_test_id": "synthetic_reported_test",
                "one_vs_rest": True,
                "recalculated_test_id": "synthetic_recalc_1",
            }
        ]
    )
    csf.to_csv(input_dir / "csf_input_v3.csv", index=False)
    pd.DataFrame(
        [
            {
                "schema_version": "reported_test_v1",
                "reported_test_id": "synthetic_reported_test",
                "trial_id": "synthetic_native",
                "parent_variable": "binary outcome",
                "reported_p": 0.2,
                "reported_p_raw": "P=.20",
                "reported_p_comparator": "=",
                "reported_test_scope": "unknown",
                "reported_test_method": "unknown",
                "reported_test_tail": "unknown",
                "analysis_population": "unknown",
            }
        ]
    ).to_csv(input_dir / "reported_tests_v1.csv", index=False)

    output_tables = []
    for run_name in ("sim-1", "sim-2"):
        output_dir = tmp_path / run_name
        subprocess.run(
            [
                rscript,
                str(project_root / "scripts/run_randomization_forensics.R"),
                "--in",
                str(input_dir),
                "--out",
                str(output_dir),
                "--allocation-design",
                "unrestricted_individual_1to1",
                "--expert-opt-in",
                "true",
                "--seed",
                "123",
                "--m",
                "100",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = pd.read_csv(output_dir / "randomization_run_receipt_v1.csv").iloc[0]
        assert receipt["simdistr_version"] == "1.0.1"
        assert receipt["inferential_diagnostic_status"] == "completed"
        values = pd.read_csv(output_dir / "simdistr_variable_pvalues_v1.csv")
        assert values["execution_status"].eq("completed").all()
        assert values["simdistr_pvalue"].notna().any()
        output_tables.append(values["simdistr_pvalue"].tolist())
    assert output_tables[0] == output_tables[1]
