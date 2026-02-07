"""Build package-oriented numeric-integrity input tables."""

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    in_dir = args.in_dir
    out_dir = args.out_dir

    numeric_path = in_dir / "inputs" / "numeric_table.csv"
    scrutiny_path = in_dir / "inputs" / "scrutiny_input.csv"
    statcheck_path = in_dir / "inputs" / "statcheck_input.csv"
    statcheck_text_path = in_dir / "inputs" / "statcheck_text.txt"
    summary_long_path = in_dir / "inputs" / "numeric_summary_long.csv"
    metadata_path = in_dir / "metadata" / "numeric_extract_metadata.csv"
    if not numeric_path.exists():
        raise FileNotFoundError(f"Missing numeric table: {numeric_path}")
    if not scrutiny_path.exists():
        raise FileNotFoundError(f"Missing scrutiny table: {scrutiny_path}")
    if not statcheck_path.exists():
        raise FileNotFoundError(f"Missing statcheck table: {statcheck_path}")
    if not statcheck_text_path.exists():
        raise FileNotFoundError(f"Missing statcheck text file: {statcheck_text_path}")
    if not summary_long_path.exists():
        raise FileNotFoundError(f"Missing numeric summary table: {summary_long_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing numeric metadata file: {metadata_path}")

    numeric_table = pd.read_csv(numeric_path)
    scrutiny_input = pd.read_csv(scrutiny_path)
    statcheck_input = pd.read_csv(statcheck_path)
    statcheck_text = statcheck_text_path.read_text(encoding="utf-8")
    summary_long = pd.read_csv(summary_long_path)
    metadata = pd.read_csv(metadata_path)

    source_pdf = ""
    if not metadata.empty and "source_pdf" in metadata.columns:
        source_pdf = str(metadata.iloc[0]["source_pdf"])

    scrutiny_cases = build_scrutiny_cases(
        scrutiny_input=scrutiny_input,
        numeric_summary_long=summary_long,
        source_pdf=source_pdf,
    )
    scrutiny_grim_input = build_scrutiny_grim_input(scrutiny_cases)
    scrutiny_grimmer_input = build_scrutiny_grimmer_input(scrutiny_cases)
    scrutiny_debit_input = build_scrutiny_debit_input(scrutiny_cases)
    scrutiny_duplicate_input = build_scrutiny_duplicate_input(scrutiny_cases)
    scrutiny_rounding_bias_input = build_scrutiny_rounding_bias_input(scrutiny_cases)
    rsprite2_stub = build_rsprite2_stub(numeric_table)

    inputs_dir = out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    numeric_ready_path = inputs_dir / "numeric_checks_input.csv"
    scrutiny_ready_path = inputs_dir / "scrutiny_input.csv"
    statcheck_ready_path = inputs_dir / "statcheck_input.csv"
    rsprite2_ready_path = inputs_dir / "rsprite2_input.csv"
    statcheck_text_ready_path = inputs_dir / "statcheck_text.txt"
    summary_long_ready_path = inputs_dir / "numeric_summary_long.csv"
    scrutiny_cases_path = inputs_dir / "scrutiny_cases.csv"
    scrutiny_grim_path = inputs_dir / "scrutiny_grim_input.csv"
    scrutiny_grimmer_path = inputs_dir / "scrutiny_grimmer_input.csv"
    scrutiny_debit_path = inputs_dir / "scrutiny_debit_input.csv"
    scrutiny_duplicates_path = inputs_dir / "scrutiny_duplicates_input.csv"
    scrutiny_rounding_bias_path = inputs_dir / "scrutiny_rounding_bias_input.csv"

    numeric_table.to_csv(numeric_ready_path, index=False)
    scrutiny_input.to_csv(scrutiny_ready_path, index=False)
    statcheck_input.to_csv(statcheck_ready_path, index=False)
    rsprite2_stub.to_csv(rsprite2_ready_path, index=False)
    statcheck_text_ready_path.write_text(statcheck_text, encoding="utf-8")
    summary_long.to_csv(summary_long_ready_path, index=False)
    scrutiny_cases.to_csv(scrutiny_cases_path, index=False)
    scrutiny_grim_input.to_csv(scrutiny_grim_path, index=False)
    scrutiny_grimmer_input.to_csv(scrutiny_grimmer_path, index=False)
    scrutiny_debit_input.to_csv(scrutiny_debit_path, index=False)
    scrutiny_duplicate_input.to_csv(scrutiny_duplicates_path, index=False)
    scrutiny_rounding_bias_input.to_csv(scrutiny_rounding_bias_path, index=False)

    print(f"Wrote {numeric_ready_path}")
    print(f"Wrote {scrutiny_ready_path}")
    print(f"Wrote {statcheck_ready_path}")
    print(f"Wrote {rsprite2_ready_path}")
    print(f"Wrote {statcheck_text_ready_path}")
    print(f"Wrote {summary_long_ready_path}")
    print(f"Wrote {scrutiny_cases_path}")
    print(f"Wrote {scrutiny_grim_path}")
    print(f"Wrote {scrutiny_grimmer_path}")
    print(f"Wrote {scrutiny_debit_path}")
    print(f"Wrote {scrutiny_duplicates_path}")
    print(f"Wrote {scrutiny_rounding_bias_path}")


if __name__ == "__main__":
    main()
