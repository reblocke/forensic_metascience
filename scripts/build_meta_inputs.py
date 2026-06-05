"""Build meta-level forensic score inputs from category summaries."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.meta_forensics import build_category_scores, compute_overall_meta_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def _to_summary_table(raw: pd.DataFrame, category: str) -> pd.DataFrame:
    subset = raw[raw["category"] == category].copy()
    if subset.empty:
        return pd.DataFrame()
    metrics = {row["metric"]: row["value"] for _, row in subset.iterrows()}
    return pd.DataFrame([metrics])


def main() -> None:
    args = parse_args()
    raw_path = args.in_dir / "inputs" / "category_summaries_raw.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing meta raw summaries: {raw_path}")

    raw = pd.read_csv(raw_path)
    for column in ("metric", "value", "category"):
        if column not in raw.columns:
            raise ValueError(f"Missing required column {column!r} in {raw_path}")

    summary_tables = {
        category: _to_summary_table(raw, category)
        for category in ("randomization", "numeric", "registration", "visual", "transparency")
    }
    category_scores = build_category_scores(summary_tables)
    overall = compute_overall_meta_score(category_scores)

    inputs_dir = args.out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    scores_path = inputs_dir / "meta_category_scores.csv"
    overall_path = inputs_dir / "meta_overall_seed.csv"
    category_scores.to_csv(scores_path, index=False)
    pd.DataFrame([overall]).to_csv(overall_path, index=False)

    print(f"Wrote {scores_path}")
    print(f"Wrote {overall_path}")


if __name__ == "__main__":
    main()
