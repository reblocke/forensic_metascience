"""Extract randomization metadata and baseline Table 1 rows from trial PDFs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from research_project.randomization import parse_table1_long


def _import_pdf_libraries() -> tuple[object, object]:
    try:
        import pdfplumber
        from pypdf import PdfReader
    except ImportError as exc:
        message = "Missing PDF dependencies. Run `uv sync` from the repo root."
        raise RuntimeError(message) from exc
    return pdfplumber, PdfReader


def _find_table1(
    pdfplumber_module: object,
    pdf_path: Path,
    *,
    table_label: str | None = None,
) -> tuple[int, list[list[str | None]]]:
    label = (table_label or "").lower()
    label_tokens = [token for token in re.split(r"\s+", label) if token]

    with pdfplumber_module.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").lower()
            if label_tokens and not all(token in page_text for token in label_tokens):
                continue
            candidate_table = None
            for table in page.extract_tables() or []:
                if not table:
                    continue
                if candidate_table is None and max(len(row) for row in table) >= 3:
                    candidate_table = table
                header_row = " ".join(str(cell or "") for cell in table[0]).lower()
                joined_table = " ".join(
                    " ".join(str(cell or "") for cell in row) for row in table[: min(len(table), 6)]
                ).lower()
                if label_tokens:
                    if all(token in joined_table for token in label_tokens):
                        return page_index, table
                    continue
                if "characteristics" in header_row or "baseline characteristics" in joined_table:
                    return page_index, table
            if label_tokens and candidate_table is not None:
                return page_index, candidate_table
    raise ValueError(f"Could not locate the baseline characteristics table in PDF: {pdf_path}")


def _extract_page_texts(pdf_reader_cls: object, pdf_path: Path) -> list[str]:
    reader = pdf_reader_cls(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def _first_page_with_phrase(page_texts: list[str], phrase: str) -> int | None:
    needle = phrase.lower()
    for page_index, text in enumerate(page_texts, start=1):
        if needle in text.lower():
            return page_index
    return None


def _sentence_with_phrase(page_texts: list[str], phrase: str) -> tuple[str, int | None]:
    needle = phrase.lower()
    for page_index, text in enumerate(page_texts, start=1):
        normalized = re.sub(r"\s+", " ", text)
        sentences = re.split(r"(?<=[.!?])\s+", normalized)
        for sentence in sentences:
            if needle in sentence.lower():
                return sentence.strip(), page_index
    return "", None


def _first_sentence_with_any_phrase(
    page_texts: list[str],
    phrases: list[str],
) -> tuple[str, int | None]:
    for phrase in phrases:
        sentence, page_index = _sentence_with_phrase(page_texts, phrase)
        if sentence:
            return sentence, page_index
    return "", None


def _derive_metadata(
    trial_id: str,
    table1_long: pd.DataFrame,
    report_page_texts: list[str],
    protocol_page_texts: list[str],
) -> pd.DataFrame:
    groups = list(dict.fromkeys(table1_long["group"].dropna().astype(str).tolist()))
    if len(groups) != 2:
        raise ValueError(f"Expected exactly 2 groups in baseline table, found: {groups}")
    arm_a_rows = table1_long[table1_long["group"] == groups[0]]
    arm_b_rows = table1_long[table1_long["group"] == groups[1]]
    n_a = int(arm_a_rows["n_group"].dropna().iloc[0])
    n_b = int(arm_b_rows["n_group"].dropna().iloc[0])

    method_text, report_methods_page = _first_sentence_with_any_phrase(
        report_page_texts,
        ["randomly assigned", "randomisation programme", "randomized in a 1:1 ratio"],
    )
    protocol_randomization_text, protocol_randomization_page = _first_sentence_with_any_phrase(
        protocol_page_texts,
        ["randomisation", "randomization", "allocation ratio"],
    )
    concealment_text, allocation_concealment_page = _first_sentence_with_any_phrase(
        report_page_texts + protocol_page_texts,
        ["web-based randomisation", "web-based randomization", "centrally controlled"],
    )
    stratification_text, _ = _first_sentence_with_any_phrase(
        protocol_page_texts,
        ["minimisation", "minimization", "stratified"],
    )
    blinding_text, _ = _first_sentence_with_any_phrase(
        report_page_texts + protocol_page_texts,
        ["open-label", "masked", "blinded", "not masked"],
    )

    allocation_ratio = "1:1" if n_a == n_b else f"{n_a}:{n_b}"

    metadata = pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "arm_a_label": groups[0],
                "arm_b_label": groups[1],
                "n_a": n_a,
                "n_b": n_b,
                "allocation_ratio": allocation_ratio,
                "randomization_method": method_text or protocol_randomization_text,
                "allocation_concealment": concealment_text,
                "stratification": stratification_text,
                "blinding": blinding_text,
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
    parser.add_argument("--baseline-pdf", type=Path, required=False)
    parser.add_argument("--baseline-table-label", type=str, required=False, default="")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trial-id", type=str, default="lungtime_c01_s41591_025_04181")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_pdf = args.report
    protocol_pdf = args.protocol
    baseline_pdf = args.baseline_pdf or report_pdf
    out_dir = args.out
    trial_id = args.trial_id

    if not report_pdf.exists():
        raise FileNotFoundError(f"Missing report PDF: {report_pdf}")
    if not protocol_pdf.exists():
        raise FileNotFoundError(f"Missing protocol PDF: {protocol_pdf}")
    if not baseline_pdf.exists():
        raise FileNotFoundError(f"Missing baseline PDF: {baseline_pdf}")

    pdfplumber_module, pdf_reader_cls = _import_pdf_libraries()
    source_page, table1 = _find_table1(
        pdfplumber_module,
        baseline_pdf,
        table_label=args.baseline_table_label,
    )
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
