"""Build meta-level evidence coverage, or isolated legacy score inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.meta_forensics import (
    META_CATEGORIES,
    build_evidence_coverage,
    build_legacy_category_scores,
    compute_legacy_overall_meta_score,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    parser.add_argument(
        "--legacy-reproduction",
        action="store_true",
        help="Reproduce the retired composite formula under an isolated legacy/ directory.",
    )
    return parser.parse_args()


def _to_summary_table(raw: pd.DataFrame, category: str) -> pd.DataFrame:
    subset = raw[raw["category"] == category].copy()
    if subset.empty:
        return pd.DataFrame()
    metrics = {row["metric"]: row["value"] for _, row in subset.iterrows()}
    return pd.DataFrame([metrics])


def main() -> None:
    args = parse_args()
    if args.legacy_reproduction:
        legacy_raw_path = args.in_dir / "inputs" / "category_summaries_raw.csv"
        versioned_raw_path = args.in_dir / "inputs" / "category_summaries_v2_raw.csv"
        raw_path = legacy_raw_path if legacy_raw_path.exists() else versioned_raw_path
    else:
        raw_path = args.in_dir / "inputs" / "category_summaries_v2_raw.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing meta raw summaries: {raw_path}")

    raw = pd.read_csv(raw_path)
    for column in ("metric", "value", "category"):
        if column not in raw.columns:
            raise ValueError(f"Missing required column {column!r} in {raw_path}")

    inputs_dir = args.out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    if args.legacy_reproduction:
        legacy_dir = inputs_dir / "legacy"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        summary_tables = {
            category: _to_summary_table(raw, category) for category in META_CATEGORIES
        }
        category_scores = build_legacy_category_scores(summary_tables)
        overall = compute_legacy_overall_meta_score(category_scores)
        scores_path = legacy_dir / "meta_category_scores.csv"
        overall_path = legacy_dir / "meta_overall_seed.csv"
        category_scores.to_csv(scores_path, index=False)
        pd.DataFrame([overall]).to_csv(overall_path, index=False)
        pd.DataFrame(
            [
                {
                    "schema_version": "legacy_composite_v1",
                    "label": "NOT_INSPECT",
                    "legacy_only": True,
                    "source_file": str(raw_path),
                }
            ]
        ).to_csv(legacy_dir / "meta_legacy_provenance.csv", index=False)
        print(f"Wrote isolated legacy inputs under {legacy_dir}")
        return

    status_path = args.in_dir / "inputs" / "category_coverage_v2_raw.csv"
    category_status = pd.read_csv(status_path) if status_path.exists() else None
    coverage = build_evidence_coverage(raw, category_status=category_status)
    candidate_path = args.in_dir / "inputs" / "candidate_concerns_v1_raw.csv"
    concerns = (
        pd.read_csv(candidate_path)
        if candidate_path.exists()
        else pd.DataFrame(
            columns=[
                "category",
                "source_file",
                "source_unit",
                "method",
                "metric",
                "value_numeric",
                "details",
                "candidate_status",
            ]
        )
    )
    coverage_path = inputs_dir / "meta_evidence_coverage_v2.csv"
    concerns_path = inputs_dir / "meta_candidate_concerns_v1.csv"
    coverage.to_csv(coverage_path, index=False)
    concerns.to_csv(concerns_path, index=False)
    print(f"Wrote {coverage_path}")
    print(f"Wrote {concerns_path}")


if __name__ == "__main__":
    main()
