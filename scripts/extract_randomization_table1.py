"""Extract randomization metadata and baseline Table 1 rows from trial PDFs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.randomization import parse_table1_long


def _import_pdf_libraries() -> tuple[object, object]:
    try:
        import pdfplumber
        from pypdf import PdfReader
    except ImportError as exc:
        message = (
            "Missing PDF dependencies. Install with: "
            "python3 -m pip install --user pypdf pdfplumber"
        )
        raise RuntimeError(message) from exc
    return pdfplumber, PdfReader


def _find_table1(pdfplumber_module: object, report_pdf: Path) -> tuple[int, list[list[str | None]]]:
    with pdfplumber_module.open(report_pdf) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables() or []:
                if not table:
                    continue
                header_row = " ".join(str(cell or "") for cell in table[0]).lower()
                if (
                    "characteristics" in header_row
                    and "early tod group" in header_row
                    and "late tod group" in header_row
                ):
                    return page_index, table
    raise ValueError("Could not locate the baseline characteristics table in report PDF.")


def _extract_page_texts(pdf_reader_cls: object, pdf_path: Path) -> list[str]:
    reader = pdf_reader_cls(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def _first_page_with_phrase(page_texts: list[str], phrase: str) -> int | None:
    needle = phrase.lower()
    for page_index, text in enumerate(page_texts, start=1):
        if needle in text.lower():
            return page_index
    return None


def _derive_metadata(
    trial_id: str,
    table1_long: pd.DataFrame,
    report_page_texts: list[str],
    protocol_page_texts: list[str],
) -> pd.DataFrame:
    early_rows = table1_long[table1_long["group"] == "early_tod"]
    late_rows = table1_long[table1_long["group"] == "late_tod"]
    n_early = int(early_rows["n_group"].iloc[0])
    n_late = int(late_rows["n_group"].iloc[0])

    report_methods_page = _first_page_with_phrase(
        report_page_texts, "randomization was performed in a 1:1 ratio"
    )
    protocol_randomization_page = _first_page_with_phrase(
        protocol_page_texts, "3.2.3 randomization"
    )
    allocation_concealment_page = _first_page_with_phrase(
        protocol_page_texts, "opaque, sealed envelopes"
    )

    allocation_ratio = "1:1" if n_early == n_late else f"{n_early}:{n_late}"

    method_text = (
        "computer-generated random number table by independent statistician"
    )
    stratification = "none (without stratification)"
    concealment = "sequentially numbered, opaque, sealed envelopes"
    blinding = "open-label for treatment assignment; BIRC blinded for endpoint review"

    metadata = pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "arm_a_label": "early_tod",
                "arm_b_label": "late_tod",
                "n_a": n_early,
                "n_b": n_late,
                "allocation_ratio": allocation_ratio,
                "randomization_method": method_text,
                "allocation_concealment": concealment,
                "stratification": stratification,
                "blinding": blinding,
                "source_page_report": report_methods_page,
                "source_page_protocol": protocol_randomization_page,
                "source_page_concealment": allocation_concealment_page,
            }
        ]
    )
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trial-id", type=str, default="lungtime_c01_s41591_025_04181")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_pdf = args.report
    protocol_pdf = args.protocol
    out_dir = args.out
    trial_id = args.trial_id

    if not report_pdf.exists():
        raise FileNotFoundError(f"Missing report PDF: {report_pdf}")
    if not protocol_pdf.exists():
        raise FileNotFoundError(f"Missing protocol PDF: {protocol_pdf}")

    pdfplumber_module, pdf_reader_cls = _import_pdf_libraries()
    source_page, table1 = _find_table1(pdfplumber_module, report_pdf)
    table1_long = parse_table1_long(table=table1, trial_id=trial_id, source_page=source_page)

    report_page_texts = _extract_page_texts(pdf_reader_cls, report_pdf)
    protocol_page_texts = _extract_page_texts(pdf_reader_cls, protocol_pdf)
    metadata = _derive_metadata(
        trial_id=trial_id,
        table1_long=table1_long,
        report_page_texts=report_page_texts,
        protocol_page_texts=protocol_page_texts,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    table1_path = out_dir / "table1_long.csv"
    metadata_path = out_dir / "randomization_metadata.csv"
    table1_long.to_csv(table1_path, index=False)
    metadata.to_csv(metadata_path, index=False)

    print(f"Wrote {table1_path}")
    print(f"Wrote {metadata_path}")


if __name__ == "__main__":
    main()
