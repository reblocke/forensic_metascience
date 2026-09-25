"""Extract category summaries for meta-level forensic aggregation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row

SUMMARY_FILES = {
    "randomization": "pooled_pvalues.csv",
    "numeric": "numeric_summary.csv",
    "registration": "registration_summary.csv",
    "visual": "visual_summary.csv",
    "transparency": "transparency_summary.csv",
}
CANDIDATE_FILES = {
    "randomization": ("row_level_results.csv", "flagged_p_delta_0_05", None),
    "numeric": ("numeric_standardized_results.csv", "anomaly_flag", None),
    "registration": ("registration_row_results.csv", "mismatch_flag", "assessed_flag"),
    "visual": ("visual_summary.csv", "numbering_gap_flag", None),
}


def _truthy(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _candidate_records(
    path: Path, category: str, flag_column: str, assessed_column: str | None
) -> list[dict[str, object]]:
    if not path.exists():
        return []
    table = pd.read_csv(path)
    if flag_column not in table.columns:
        return []
    mask = _truthy(table[flag_column])
    if assessed_column and assessed_column in table.columns:
        mask &= _truthy(table[assessed_column])
    records: list[dict[str, object]] = []
    for _, row in table.loc[mask].iterrows():
        source_unit = next(
            (
                row[column]
                for column in ("source_unit", "source_page", "source_table", "claim_id", "case_id")
                if column in table.columns and pd.notna(row[column]) and str(row[column]).strip()
            ),
            path.name,
        )
        records.append(
            {
                "category": category,
                "source_file": str(path),
                "source_unit": str(source_unit),
                "method": str(row.get("method", category)),
                "metric": flag_column,
                "value_numeric": row.get("value_numeric", row.get(flag_column)),
                "details": json.dumps(row.to_dict(), default=str, sort_keys=True),
                "candidate_status": "screening_signal",
            }
        )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--requested-categories",
        default=",".join(SUMMARY_FILES),
        help="Comma-separated category outputs from this run; defaults to all meta categories.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[dict[str, object]] = []
    found_categories: list[str] = []
    coverage_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    requested_categories = {
        value.strip() for value in args.requested_categories.split(",") if value.strip()
    }
    unknown = requested_categories - set(SUMMARY_FILES)
    if unknown:
        raise ValueError(f"Unknown requested meta categories: {sorted(unknown)}")

    for category, filename in SUMMARY_FILES.items():
        path = args.repo_root / "reports" / category / args.study_id / filename
        requested = category in requested_categories
        summary = pd.read_csv(path) if requested and path.exists() else pd.DataFrame()
        report_available: bool | None = (
            bool(path.exists() and not summary.empty) if requested else None
        )
        if report_available:
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
        coverage_rows.append(
            {
                "category": category,
                "requested": requested,
                "report_available": report_available,
                "failed": pd.NA,
                "unsupported": pd.NA,
                "source_file": str(path),
            }
        )
        if requested and category in CANDIDATE_FILES:
            result_name, flag_column, assessed_column = CANDIDATE_FILES[category]
            candidate_rows.extend(
                _candidate_records(
                    path.parent / result_name, category, flag_column, assessed_column
                )
            )

    raw = pd.DataFrame(rows)
    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    raw_path = inputs_dir / "category_summaries_v2_raw.csv"
    metadata_path = metadata_dir / "meta_extract_metadata_v2.csv"
    coverage_path = inputs_dir / "category_coverage_v1_raw.csv"
    candidate_path = inputs_dir / "candidate_concerns_v1_raw.csv"
    raw.to_csv(raw_path, index=False)
    pd.DataFrame(coverage_rows).to_csv(coverage_path, index=False)
    pd.DataFrame(
        candidate_rows,
        columns=[
            "category",
            "source_file",
            "source_unit",
            "method",
            "metric",
            "value_numeric",
            "details",
            "candidate_status",
        ],
    ).to_csv(candidate_path, index=False)
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
    print(f"Wrote {coverage_path}")
    print(f"Wrote {candidate_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
