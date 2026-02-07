"""Extract protocol/registration congruence claims from trial PDFs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.registration_forensics import derive_registration_claims


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
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.report.exists():
        raise FileNotFoundError(f"Missing report PDF: {args.report}")
    if not args.protocol.exists():
        raise FileNotFoundError(f"Missing protocol PDF: {args.protocol}")

    pdf_reader_cls = _import_pdf_reader()
    report_texts = _extract_page_texts(pdf_reader_cls, args.report)
    protocol_texts = _extract_page_texts(pdf_reader_cls, args.protocol)

    claims = derive_registration_claims(
        trial_id=args.study_id,
        report_page_texts=report_texts,
        protocol_page_texts=protocol_texts,
    )

    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    claims_path = inputs_dir / "registration_claims.csv"
    metadata_path = metadata_dir / "registration_extract_metadata.csv"
    claims.to_csv(claims_path, index=False)
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "report_pdf": str(args.report),
                "protocol_pdf": str(args.protocol),
                "extract_confidence": "medium",
                "n_claims": len(claims),
            }
        ]
    ).to_csv(metadata_path, index=False)

    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=f"{args.report.name}|{args.protocol.name}",
        category="registration",
        extract_confidence="medium",
        page_ref="claim_level",
        table_ref="report_vs_protocol",
        analysis_ready=False,
    )

    print(f"Wrote {claims_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
