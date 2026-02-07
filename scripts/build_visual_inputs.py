"""Build visual-forensics rule-based input table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from research_project.visual_forensics import (
    detect_figure_numbering_gaps,
    empty_plot_digitized_values,
    summarize_plot_digitization,
    validate_plot_digitized_values,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    caption_path = args.in_dir / "inputs" / "figure_captions.csv"
    duplicate_path = args.in_dir / "inputs" / "caption_duplicates.csv"
    digitized_path = args.in_dir / "inputs" / "plot_digitized_values.csv"
    if not caption_path.exists():
        raise FileNotFoundError(f"Missing figure captions input: {caption_path}")
    if not duplicate_path.exists():
        raise FileNotFoundError(f"Missing caption duplicate input: {duplicate_path}")

    try:
        captions = pd.read_csv(caption_path)
    except EmptyDataError:
        captions = pd.DataFrame(
            columns=["trial_id", "figure_label", "figure_number", "caption", "caption_norm", "page"]
        )
    try:
        duplicates = pd.read_csv(duplicate_path)
    except EmptyDataError:
        duplicates = pd.DataFrame(
            columns=[
                "trial_id",
                "figure_label_a",
                "figure_label_b",
                "similarity",
                "flag_near_duplicate",
            ]
        )
    if digitized_path.exists():
        try:
            digitized_values = pd.read_csv(digitized_path)
        except EmptyDataError:
            digitized_values = empty_plot_digitized_values()
    else:
        digitized_values = empty_plot_digitized_values()
    digitized_values = validate_plot_digitized_values(digitized_values)
    digitization_summary = summarize_plot_digitization(digitized_values)

    gaps = detect_figure_numbering_gaps(captions)
    gaps_text = "|".join(str(gap) for gap in gaps)
    if not captions.empty:
        trial_id = captions["trial_id"].iloc[0]
    elif not digitized_values.empty:
        trial_id = digitized_values["study_id"].iloc[0]
    else:
        trial_id = "lungtime"
    checks = pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "n_figure_mentions": len(captions),
                "n_duplicate_pairs": len(duplicates),
                "n_numbering_gaps": len(gaps),
                "numbering_gaps": gaps_text,
                "n_digitized_figures": digitization_summary["n_digitized_figures"],
                "n_digitized_series": digitization_summary["n_digitized_series"],
                "n_digitized_points": digitization_summary["n_digitized_points"],
                "digitization_ready": digitization_summary["digitization_ready"],
            }
        ]
    )

    inputs_dir = args.out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    checks_path = inputs_dir / "visual_checks_input.csv"
    digitized_ready_path = inputs_dir / "plot_digitized_values.csv"
    checks.to_csv(checks_path, index=False)
    digitized_values.to_csv(digitized_ready_path, index=False)
    print(f"Wrote {checks_path}")
    print(f"Wrote {digitized_ready_path}")


if __name__ == "__main__":
    main()
