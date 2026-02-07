"""Extract mean/SD summary candidates from report tables for numeric forensics."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from research_project.randomization import clean_cell, normalize_variable_name, parse_group_header

SUMMARY_COLUMNS = [
    "trial_id",
    "source_pdf",
    "source_table",
    "source_page",
    "variable",
    "level",
    "group",
    "n",
    "x_str",
    "sd_str",
    "digits_x",
    "digits_sd",
    "extract_confidence",
]

_MEAN_SD_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*\(\s*(-?\d+(?:\.\d+)?)\s*\)\s*$")
_KEYWORDS_MEAN_SD = ("mean", "sd", "std", "standard deviation", "deviation")


def _import_pdfplumber() -> object | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    return pdfplumber


def _decimals_from_str(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.split(".", maxsplit=1)[1].rstrip("0"))


def _group_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    normalized = re.sub(r"_group$", "", normalized)
    return normalized or "group"


def _looks_like_count_percent(x_value: float, sd_value: float, n_group: int) -> bool:
    if n_group <= 0:
        return False
    if not float(x_value).is_integer():
        return False
    if x_value < 0 or x_value > n_group:
        return False
    if sd_value < 0 or sd_value > 100:
        return False
    expected_percent = (x_value / n_group) * 100.0
    return abs(expected_percent - sd_value) <= 1.25


def _parse_mean_sd_cell(cell_value: str, n_group: int) -> tuple[str, str, int, int] | None:
    cleaned = clean_cell(cell_value).replace("−", "-").replace("–", "-")
    match = _MEAN_SD_PATTERN.match(cleaned)
    if not match:
        return None
    x_str = match.group(1)
    sd_str = match.group(2)
    x_value = float(x_str)
    sd_value = float(sd_str)
    if _looks_like_count_percent(x_value, sd_value, n_group=n_group):
        return None
    return x_str, sd_str, _decimals_from_str(x_str), _decimals_from_str(sd_str)


def _extract_group_columns(header_row: list[str]) -> list[tuple[int, str, int]]:
    group_columns: list[tuple[int, str, int]] = []
    for index, cell in enumerate(header_row):
        try:
            group_info = parse_group_header(cell)
        except ValueError:
            continue
        group_columns.append((index, _group_slug(group_info.label), group_info.n))
    return group_columns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--trial-id", type=str, default="lungtime_c01_s41591_025_04181")
    parser.add_argument("--source-pdf", type=str, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.report.exists():
        raise FileNotFoundError(f"Missing report PDF: {args.report}")

    out_inputs_dir = args.out / "inputs"
    out_inputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_inputs_dir / "numeric_summary_long.csv"

    pdfplumber = _import_pdfplumber()
    if pdfplumber is None:
        pd.DataFrame(columns=SUMMARY_COLUMNS).to_csv(output_path, index=False)
        print(
            "pdfplumber is not installed; wrote header-only numeric summary table.",
            file=sys.stderr,
        )
        print(f"Wrote {output_path}")
        return

    rows: list[dict[str, object]] = []

    with pdfplumber.open(args.report) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                if not table:
                    continue
                header_row = [clean_cell(value) for value in table[0]]
                group_columns = _extract_group_columns(header_row)
                if not group_columns:
                    continue

                table_text = " ".join(header_row).lower()
                table_has_mean_sd = all(keyword in table_text for keyword in ("mean", "sd"))
                source_table = f"page_{page_index}_table_{table_index}"
                current_variable: str | None = None
                current_level = "all"

                for raw_row in table[1:]:
                    row = [clean_cell(value) for value in raw_row]
                    if not row:
                        continue

                    label = row[0] if row else ""
                    if label:
                        normalized_label = normalize_variable_name(label)
                        group_cells = [
                            clean_cell(row[column_index]) if column_index < len(row) else ""
                            for column_index, _, _ in group_columns
                        ]
                        has_any_value = any(group_cells)
                        has_mean_sd_like = any(
                            _parse_mean_sd_cell(group_cells[idx], n_group=n_group) is not None
                            for idx, (_, _, n_group) in enumerate(group_columns)
                        )
                        if not has_any_value:
                            current_variable = normalized_label
                            current_level = "all"
                        elif has_mean_sd_like:
                            keyword_hit = any(
                                keyword in normalized_label.lower() for keyword in _KEYWORDS_MEAN_SD
                            )
                            if keyword_hit or current_variable is None:
                                current_variable = normalized_label
                                current_level = "all"
                            elif normalized_label != current_variable:
                                current_level = label
                        else:
                            if current_variable is None:
                                current_variable = normalized_label
                            elif normalized_label != current_variable:
                                current_level = label

                    variable_name = current_variable or normalize_variable_name(label) or "unknown"
                    level_name = current_level or "all"

                    for column_index, group_key, n_group in group_columns:
                        if column_index >= len(row):
                            continue
                        parsed = _parse_mean_sd_cell(row[column_index], n_group=n_group)
                        if parsed is None:
                            continue
                        x_str, sd_str, digits_x, digits_sd = parsed

                        keyword_hit = any(
                            keyword in variable_name.lower() for keyword in _KEYWORDS_MEAN_SD
                        )
                        if not keyword_hit and not table_has_mean_sd:
                            continue

                        rows.append(
                            {
                                "trial_id": args.trial_id,
                                "source_pdf": args.source_pdf,
                                "source_table": source_table,
                                "source_page": page_index,
                                "variable": variable_name,
                                "level": level_name,
                                "group": group_key,
                                "n": n_group,
                                "x_str": x_str,
                                "sd_str": sd_str,
                                "digits_x": digits_x,
                                "digits_sd": digits_sd,
                                "extract_confidence": "medium",
                            }
                        )

    summary_long = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    summary_long.to_csv(output_path, index=False)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
