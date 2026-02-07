"""Mark a category as analysis-ready in the shared forensics manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from research_project.forensics_manifest import manifest_path, upsert_manifest_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-id", type=str, required=True)
    parser.add_argument("--category", type=str, required=True)
    parser.add_argument("--source-pdf", type=str, required=True)
    parser.add_argument("--extract-confidence", type=str, default="medium")
    parser.add_argument("--page-ref", type=str, default="n/a")
    parser.add_argument("--table-ref", type=str, default="n/a")
    parser.add_argument("--ready", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=args.source_pdf,
        category=args.category,
        extract_confidence=args.extract_confidence,
        page_ref=args.page_ref,
        table_ref=args.table_ref,
        analysis_ready=args.ready,
    )
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
