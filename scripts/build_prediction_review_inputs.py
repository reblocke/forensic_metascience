"""Build reusable numeric-review inputs from transcribed manuscript tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.numeric_integrity import (
    build_rsprite2_stub,
    build_scrutiny_cases,
    build_scrutiny_debit_input,
    build_scrutiny_duplicate_input,
    build_scrutiny_grim_input,
    build_scrutiny_grimmer_input,
    build_scrutiny_rounding_bias_input,
)
from research_project.prediction_review import (
    SUMMARY_TABLE_COLUMNS,
    build_numeric_summary_long_from_summary_rows,
    build_numeric_table_from_summary_rows,
    build_statcheck_stub_from_summary_rows,
    reconcile_flow_counts,
    search_confusion_matrices,
    summarize_calibration_deciles,
    validate_flow_counts,
    validate_summary_table,
    validate_table3,
    validate_tablee2,
)

RS2_COLUMNS = [
    "trial_id",
    "variable",
    "level",
    "group_a",
    "group_b",
    "percent_a",
    "percent_b",
    "abs_percent_between_arms",
]

SCRUTINY_INPUT_COLUMNS = ["trial_id", "item_label", "n", "x", "decimals"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def _load_summary_or_empty(path: Path, context: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SUMMARY_TABLE_COLUMNS)
    frame = pd.read_csv(path)
    return validate_summary_table(frame, context)


def main() -> None:
    args = parse_args()
    inputs_dir = args.in_dir / "inputs"
    metadata_path = args.in_dir / "metadata" / "prediction_review_extract_metadata.csv"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing review metadata: {metadata_path}")

    metadata = pd.read_csv(metadata_path)
    if metadata.empty:
        raise ValueError(f"Review metadata is empty: {metadata_path}")
    source_pdf = str(metadata.iloc[0]["source_pdf"])

    table1 = _load_summary_or_empty(inputs_dir / "table1_baseline_summary.csv", "table1")
    table2 = _load_summary_or_empty(inputs_dir / "table2_baseline_by_outcome.csv", "table2")
    tablee3 = _load_summary_or_empty(inputs_dir / "tablee3_correct_classification.csv", "tablee3")

    table3_path = inputs_dir / "table3_discrimination_metrics.csv"
    tablee2_path = inputs_dir / "tablee2_calibration_deciles.csv"
    flow_path = inputs_dir / "flow_counts.csv"
    manuscript_text_path = inputs_dir / "manuscript_text.txt"
    if not table3_path.exists():
        raise FileNotFoundError(f"Missing required review table: {table3_path}")
    if not tablee2_path.exists():
        raise FileNotFoundError(f"Missing required review table: {tablee2_path}")
    if not flow_path.exists():
        raise FileNotFoundError(f"Missing required flow counts: {flow_path}")
    if not manuscript_text_path.exists():
        raise FileNotFoundError(f"Missing manuscript text artifact: {manuscript_text_path}")

    table3 = validate_table3(pd.read_csv(table3_path))
    tablee2 = validate_tablee2(pd.read_csv(tablee2_path))
    flow_counts = validate_flow_counts(pd.read_csv(flow_path))
    manuscript_text = manuscript_text_path.read_text(encoding="utf-8")

    combined = pd.concat([table1, table2, tablee3], ignore_index=True)

    numeric_table = build_numeric_table_from_summary_rows(combined)
    statcheck_stub = build_statcheck_stub_from_summary_rows(table2)
    numeric_summary_long = build_numeric_summary_long_from_summary_rows(
        combined,
        source_pdf=source_pdf,
    )
    empty_scrutiny_input = pd.DataFrame(columns=SCRUTINY_INPUT_COLUMNS)
    scrutiny_cases = build_scrutiny_cases(
        scrutiny_input=empty_scrutiny_input,
        numeric_summary_long=numeric_summary_long,
        source_pdf=source_pdf,
    )
    scrutiny_grim_input = build_scrutiny_grim_input(scrutiny_cases)
    scrutiny_grimmer_input = build_scrutiny_grimmer_input(scrutiny_cases)
    scrutiny_debit_input = build_scrutiny_debit_input(scrutiny_cases)
    scrutiny_duplicates_input = build_scrutiny_duplicate_input(scrutiny_cases)
    scrutiny_rounding_bias_input = build_scrutiny_rounding_bias_input(scrutiny_cases)

    rsprite2_input = (
        build_rsprite2_stub(numeric_table)
        if not numeric_table.empty
        else pd.DataFrame(columns=RS2_COLUMNS)
    )
    if rsprite2_input.empty and not list(rsprite2_input.columns):
        rsprite2_input = pd.DataFrame(columns=RS2_COLUMNS)

    prospective_row = table3.loc[table3["cohort"].str.lower() == "prospective validation"]
    if prospective_row.empty:
        raise ValueError("Table 3 must include a `Prospective validation` row.")
    prospective = prospective_row.iloc[0]
    n_total = int(prospective["n_total"])
    n_events = int(prospective["n_events"])

    confusion_candidates = search_confusion_matrices(
        n_total=n_total,
        n_events=n_events,
        sensitivity=float(prospective["sensitivity"]),
        specificity=float(prospective["specificity"]),
        ppv=float(prospective["ppv"]),
        npv=float(prospective["npv"]),
    )
    calibration_totals = summarize_calibration_deciles(
        tablee2,
        expected_n_total=n_total,
        expected_n_events=n_events,
    )
    flow_checks = reconcile_flow_counts(flow_counts)

    out_inputs = args.out_dir / "inputs"
    out_inputs.mkdir(parents=True, exist_ok=True)

    combined_path = out_inputs / "summary_rows_combined.csv"
    numeric_alias_path = out_inputs / "numeric_table.csv"
    numeric_checks_path = out_inputs / "numeric_checks_input.csv"
    scrutiny_path = out_inputs / "scrutiny_input.csv"
    statcheck_input_path = out_inputs / "statcheck_input.csv"
    statcheck_text_path = out_inputs / "statcheck_text.txt"
    rsprite2_path = out_inputs / "rsprite2_input.csv"
    numeric_summary_path = out_inputs / "numeric_summary_long.csv"
    scrutiny_cases_path = out_inputs / "scrutiny_cases.csv"
    grim_path = out_inputs / "scrutiny_grim_input.csv"
    grimmer_path = out_inputs / "scrutiny_grimmer_input.csv"
    debit_path = out_inputs / "scrutiny_debit_input.csv"
    duplicates_path = out_inputs / "scrutiny_duplicates_input.csv"
    rounding_bias_path = out_inputs / "scrutiny_rounding_bias_input.csv"
    confusion_path = out_inputs / "table3_confusion_matrix_matches.csv"
    calibration_totals_path = out_inputs / "calibration_sum_checks.csv"
    flow_checks_path = out_inputs / "flow_reconciliation.csv"

    combined.to_csv(combined_path, index=False)
    numeric_table.to_csv(numeric_alias_path, index=False)
    numeric_table.to_csv(numeric_checks_path, index=False)
    empty_scrutiny_input.to_csv(scrutiny_path, index=False)
    statcheck_stub.to_csv(statcheck_input_path, index=False)
    statcheck_text_path.write_text(manuscript_text, encoding="utf-8")
    rsprite2_input.to_csv(rsprite2_path, index=False)
    numeric_summary_long.to_csv(numeric_summary_path, index=False)
    scrutiny_cases.to_csv(scrutiny_cases_path, index=False)
    scrutiny_grim_input.to_csv(grim_path, index=False)
    scrutiny_grimmer_input.to_csv(grimmer_path, index=False)
    scrutiny_debit_input.to_csv(debit_path, index=False)
    scrutiny_duplicates_input.to_csv(duplicates_path, index=False)
    scrutiny_rounding_bias_input.to_csv(rounding_bias_path, index=False)
    confusion_candidates.to_csv(confusion_path, index=False)
    calibration_totals.to_csv(calibration_totals_path, index=False)
    flow_checks.to_csv(flow_checks_path, index=False)

    print(f"Wrote {combined_path}")
    print(f"Wrote {numeric_alias_path}")
    print(f"Wrote {numeric_checks_path}")
    print(f"Wrote {scrutiny_path}")
    print(f"Wrote {statcheck_input_path}")
    print(f"Wrote {statcheck_text_path}")
    print(f"Wrote {rsprite2_path}")
    print(f"Wrote {numeric_summary_path}")
    print(f"Wrote {scrutiny_cases_path}")
    print(f"Wrote {grim_path}")
    print(f"Wrote {grimmer_path}")
    print(f"Wrote {debit_path}")
    print(f"Wrote {duplicates_path}")
    print(f"Wrote {rounding_bias_path}")
    print(f"Wrote {confusion_path}")
    print(f"Wrote {calibration_totals_path}")
    print(f"Wrote {flow_checks_path}")


if __name__ == "__main__":
    main()
