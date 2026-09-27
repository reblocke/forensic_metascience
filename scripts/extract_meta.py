"""Extract category summaries for meta-level forensic aggregation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row

SUMMARY_FILES = {
    "randomization": "pooled_descriptive_v2.csv",
    "numeric": "numeric_summary.csv",
    "registration": "registration_summary.csv",
    "visual": "visual_summary.csv",
    "transparency": "transparency_summary.csv",
}
CANDIDATE_FILES = {
    "randomization": ("row_level_results_v2.csv", "flagged_p_delta_0_05", None),
    "numeric": ("numeric_standardized_results.csv", "anomaly_flag", None),
    "registration": ("registration_row_results.csv", "mismatch_flag", "assessed_flag"),
    "visual": ("visual_summary.csv", "numbering_gap_flag", None),
}
LEGACY_SUMMARY_FILES = {**SUMMARY_FILES, "randomization": "pooled_pvalues.csv"}
LEGACY_CANDIDATE_FILES = {
    **CANDIDATE_FILES,
    "randomization": ("row_level_results.csv", "flagged_p_delta_0_05", None),
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


def _receipt_evaluation_units(category_root: Path, category: str) -> int:
    receipt_names = {
        "numeric": "numeric_method_receipts.csv",
    }
    receipt_name = receipt_names.get(category)
    if receipt_name is None:
        return 0
    path = category_root / receipt_name
    if not path.is_file():
        return 0
    receipt = pd.read_csv(path)
    required = {"execution", "n_evaluated"}
    if not required.issubset(receipt.columns):
        raise ValueError(f"Malformed method receipt {path}; required {sorted(required)}.")
    evaluated = pd.to_numeric(receipt["n_evaluated"], errors="coerce")
    states = receipt["execution"].astype(str)
    if evaluated.isna().any() or (evaluated < 0).any():
        raise ValueError(f"Invalid evaluation counts in method receipt {path}.")
    return int(evaluated[states.isin(["completed", "partial"])].sum())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reports-root", type=Path, default=None)
    parser.add_argument("--run-manifest", type=Path, default=None)
    parser.add_argument(
        "--legacy-layout",
        action="store_true",
        help="Read historical reports/<category>/<study_id>/ outputs explicitly.",
    )
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
    summary_files = LEGACY_SUMMARY_FILES if args.legacy_layout else SUMMARY_FILES
    candidate_files = LEGACY_CANDIDATE_FILES if args.legacy_layout else CANDIDATE_FILES
    unknown = requested_categories - set(summary_files)
    if unknown:
        raise ValueError(f"Unknown requested meta categories: {sorted(unknown)}")
    reports_root = args.reports_root or args.repo_root / "reports"
    if args.legacy_layout and args.run_manifest:
        raise ValueError("Legacy report layout cannot be combined with a run manifest.")
    run_manifest = None
    if args.run_manifest:
        run_manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        if run_manifest.get("study_id") != args.study_id:
            raise ValueError("Run manifest study_id does not match requested study.")
        if run_manifest.get("schema_version") != "forensics_run_v3":
            raise ValueError("Unsupported or missing run manifest schema.")
        if run_manifest.get("status") != "running":
            raise ValueError("Meta extraction requires an active run manifest.")
        run_categories = set(run_manifest.get("requested_categories", [])) - {"meta"}
        if requested_categories != run_categories:
            raise ValueError("Requested meta categories do not match the active run manifest.")
        for fingerprint in run_manifest.get("input_fingerprints", []):
            file_path = (
                args.repo_root / fingerprint["path"]
                if not Path(fingerprint["path"]).is_absolute()
                else Path(fingerprint["path"])
            )
            currently_available = file_path.is_file()
            if currently_available != fingerprint["available"]:
                raise ValueError(f"Run input availability changed before aggregation: {file_path}")
            if fingerprint["available"] and _sha256(file_path) != fingerprint["sha256"]:
                raise ValueError(f"Run input changed before aggregation: {file_path}")
        expected_root = (args.run_manifest.resolve().parent / "reports").resolve()
        if reports_root.resolve() != expected_root:
            raise ValueError("Meta extraction reports root must belong to the active run.")

    for category, filename in summary_files.items():
        category_root = reports_root / category
        if args.legacy_layout:
            category_root /= args.study_id
        path = category_root / filename
        requested = category in requested_categories
        if run_manifest is not None and requested:
            stage_name = f"{category}_methods"
            stage = run_manifest.get("stages", {}).get(stage_name, {})
            if stage.get("status") != "completed":
                raise ValueError(f"Requested category {category!r} has no completed run receipt.")
            artifact_rel = f"reports/{category}/{filename}"
            artifact = next(
                (
                    item
                    for item in run_manifest.get("artifacts", [])
                    if item.get("path") == artifact_rel
                ),
                None,
            )
            if not artifact or not artifact.get("available"):
                raise ValueError(
                    f"Requested category {category!r} lacks artifact receipt {artifact_rel}."
                )
            if not path.is_file() or _sha256(path) != artifact.get("sha256"):
                raise ValueError(f"Requested category artifact changed after completion: {path}")
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
                "n_evaluation_units": (
                    _receipt_evaluation_units(category_root, category) if requested else 0
                ),
                "source_file": str(path),
            }
        )
        if requested and category in candidate_files:
            result_name, flag_column, assessed_column = candidate_files[category]
            candidate_rows.extend(
                _candidate_records(
                    category_root / result_name, category, flag_column, assessed_column
                )
            )

    raw = pd.DataFrame(rows, columns=["study_id", "category", "metric", "value", "source_file"])
    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    raw_path = inputs_dir / "category_summaries_v2_raw.csv"
    metadata_path = metadata_dir / "meta_extract_metadata_v2.csv"
    coverage_path = inputs_dir / "category_coverage_v2_raw.csv"
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
    if args.run_manifest is None:
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
    if args.run_manifest is not None:
        print(f"Run receipt: {args.run_manifest}")
    else:
        print(f"Updated {manifest}")


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
