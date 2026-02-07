"""Extract visual-forensics caption candidates from report PDF text."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.visual_forensics import (
    build_visual_checks,
    detect_caption_duplicates,
    detect_figure_numbering_gaps,
)


def _import_pdf_reader() -> object:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Missing PDF dependency. Install with: python3 -m pip install --user pypdf"
        ) from exc
    return PdfReader


def _extract_page_texts(pdf_reader_cls: object, pdf_path: Path) -> list[str]:
    reader = pdf_reader_cls(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.report.exists():
        raise FileNotFoundError(f"Missing report PDF: {args.report}")

    reader_cls = _import_pdf_reader()
    page_texts = _extract_page_texts(reader_cls, args.report)

    visual_checks = build_visual_checks(page_texts, args.study_id)
    duplicates = detect_caption_duplicates(visual_checks)
    gaps = detect_figure_numbering_gaps(visual_checks)

    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    checks_path = inputs_dir / "figure_captions.csv"
    duplicate_path = inputs_dir / "caption_duplicates.csv"
    metadata_path = metadata_dir / "visual_extract_metadata.csv"
    visual_checks.to_csv(checks_path, index=False)
    duplicates.to_csv(duplicate_path, index=False)
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "report_pdf": str(args.report),
                "n_figure_mentions": len(visual_checks),
                "n_duplicate_pairs": len(duplicates),
                "figure_number_gaps": "|".join(str(value) for value in gaps),
                "extract_confidence": "low",
            }
        ]
    ).to_csv(metadata_path, index=False)

    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=args.report.name,
        category="visual",
        extract_confidence="low",
        page_ref="figure_mentions",
        table_ref="figure_caption_text",
        analysis_ready=False,
    )

    print(f"Wrote {checks_path}")
    print(f"Wrote {duplicate_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
