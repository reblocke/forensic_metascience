"""Extract category summaries for meta-level forensic aggregation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row

SUMMARY_PATHS = {
    "randomization": "reports/randomization/lungtime/pooled_pvalues.csv",
    "numeric": "reports/numeric/lungtime/numeric_summary.csv",
    "registration": "reports/registration/lungtime/registration_summary.csv",
    "visual": "reports/visual/lungtime/visual_summary.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[dict[str, object]] = []
    found_categories: list[str] = []

    for category, relative in SUMMARY_PATHS.items():
        path = args.repo_root / relative
        if not path.exists():
            continue
        summary = pd.read_csv(path)
        if summary.empty:
            continue
        found_categories.append(category)
        row = summary.iloc[0].to_dict()
        for metric, value in row.items():
            rows.append(
                {
                    "study_id": args.study_id,
                    "category": category,
                    "metric": metric,
                    "value": value,
                    "source_file": str(path),
                }
            )

    raw = pd.DataFrame(rows)
    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    raw_path = inputs_dir / "category_summaries_raw.csv"
    metadata_path = metadata_dir / "meta_extract_metadata.csv"
    raw.to_csv(raw_path, index=False)
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "n_categories_found": len(found_categories),
                "categories_found": "|".join(found_categories),
            }
        ]
    ).to_csv(metadata_path, index=False)

    manifest = manifest_path(args.repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf="derived_from_category_reports",
        category="meta",
        extract_confidence="medium",
        page_ref="n/a",
        table_ref="category_summary_tables",
        analysis_ready=False,
    )

    print(f"Wrote {raw_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
