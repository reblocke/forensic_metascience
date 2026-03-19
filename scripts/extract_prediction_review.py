"""Extract manuscript-review text artifacts and scaffold transcription templates."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.prediction_review import (
    build_page_text_frame,
    extract_pdf_page_texts,
    scaffold_flow_counts,
    scaffold_summary_table,
    scaffold_table3,
    scaffold_tablee2,
    validate_flow_counts,
    validate_summary_table,
    validate_table3,
    validate_tablee2,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--study-id", type=str, required=True)
    parser.add_argument("--review-type", type=str, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def write_template_if_missing(path: Path, frame: pd.DataFrame) -> None:
    """Write a scaffold file if it does not already exist."""

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def validate_if_present(path: Path, validator: callable) -> None:
    """Validate an existing transcription file."""

    if not path.exists():
        return
    frame = pd.read_csv(path)
    validator(frame)


def main() -> None:
    args = parse_args()
    if args.review_type != "prediction_validation":
        raise ValueError(f"Unsupported review type: {args.review_type}")

    page_texts = extract_pdf_page_texts(args.report)
    full_text = "\n".join(page_texts)

    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    full_text_path = inputs_dir / "manuscript_text.txt"
    page_texts_path = inputs_dir / "page_texts.csv"
    table1_path = inputs_dir / "table1_baseline_summary.csv"
    table2_path = inputs_dir / "table2_baseline_by_outcome.csv"
    table3_path = inputs_dir / "table3_discrimination_metrics.csv"
    tablee2_path = inputs_dir / "tablee2_calibration_deciles.csv"
    tablee3_path = inputs_dir / "tablee3_correct_classification.csv"
    flow_path = inputs_dir / "flow_counts.csv"
    metadata_path = metadata_dir / "prediction_review_extract_metadata.csv"

    full_text_path.write_text(full_text, encoding="utf-8")
    build_page_text_frame(args.study_id, page_texts).to_csv(page_texts_path, index=False)

    write_template_if_missing(
        table1_path,
        scaffold_summary_table(args.study_id, "table1_baseline_summary", 22),
    )
    write_template_if_missing(
        table2_path,
        scaffold_summary_table(args.study_id, "table2_baseline_by_outcome", 23),
    )
    write_template_if_missing(table3_path, scaffold_table3(args.study_id, 24))
    write_template_if_missing(tablee2_path, scaffold_tablee2(args.study_id, 31))
    write_template_if_missing(
        tablee3_path,
        scaffold_summary_table(args.study_id, "tablee3_correct_classification", 32),
    )
    write_template_if_missing(flow_path, scaffold_flow_counts(args.study_id, 25))

    validate_if_present(table1_path, lambda frame: validate_summary_table(frame, "table1"))
    validate_if_present(table2_path, lambda frame: validate_summary_table(frame, "table2"))
    validate_if_present(table3_path, validate_table3)
    validate_if_present(tablee2_path, validate_tablee2)
    validate_if_present(tablee3_path, lambda frame: validate_summary_table(frame, "tablee3"))
    validate_if_present(flow_path, validate_flow_counts)

    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "review_type": args.review_type,
                "report_pdf": str(args.report),
                "source_pdf": args.report.name,
                "n_pages": len(page_texts),
                "extract_confidence": "medium",
                "table2_template": str(table2_path),
                "table3_template": str(table3_path),
                "tablee2_template": str(tablee2_path),
            }
        ]
    ).to_csv(metadata_path, index=False)

    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=args.report.name,
        category="review_prediction_validation",
        extract_confidence="medium",
        page_ref="table2|table3|tablee2|figure1",
        table_ref="prediction_validation_review",
        analysis_ready=False,
    )

    print(f"Wrote {full_text_path}")
    print(f"Wrote {page_texts_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
