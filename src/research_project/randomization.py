"""Randomization-table extraction and forensic input builders."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class GroupInfo:
    """Parsed information from a group header cell."""

    label: str
    n: int


def clean_cell(value: object) -> str:
    """Normalize a PDF table cell into plain text."""

    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_variable_name(value: str) -> str:
    """Remove table-style suffixes from variable labels."""

    normalized = re.sub(r"\s*\(n,\s*%\)\s*$", "", value, flags=re.IGNORECASE)
    return normalized.strip()


def parse_group_header(header_cell: str) -> GroupInfo:
    """Parse arm label and sample size from a header cell."""

    cleaned = clean_cell(header_cell)
    n_match = re.search(r"n\s*=\s*(\d+)", cleaned, flags=re.IGNORECASE)
    if not n_match:
        raise ValueError(f"Could not parse group size from header: {cleaned!r}")
    label = re.sub(r"\(.*?\)", "", cleaned).strip()
    return GroupInfo(label=label, n=int(n_match.group(1)))


def parse_float(text: str) -> float | None:
    """Parse a float from text, returning None when unavailable."""

    cleaned = clean_cell(text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_count_percent(cell_value: str) -> tuple[int | None, float | None]:
    """Parse count and percentage from strings like '95 (90.5)'."""

    cleaned = clean_cell(cell_value).replace("%", "")
    match = re.search(r"(\d+)\s*\(([\d.]+)\)", cleaned)
    if not match:
        return None, None
    return int(match.group(1)), float(match.group(2))


def parse_median_range(cell_value: str) -> tuple[float | None, float | None, float | None]:
    """Parse median and range from strings like '61 (33-80)' or '61 (33–80)'."""

    cleaned = clean_cell(cell_value)
    cleaned = cleaned.replace("−", "-").replace("–", "-")
    pattern = (
        r"(-?\d+(?:\.\d+)?)\s*\(\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*\)"
    )
    match = re.search(pattern, cleaned)
    if not match:
        return None, None, None
    return float(match.group(1)), float(match.group(2)), float(match.group(3))


def infer_decimals(number_value: float | None) -> int | None:
    """Infer decimal precision from a numeric value."""

    if number_value is None:
        return None
    as_text = f"{number_value}"
    if "." not in as_text:
        return 0
    return len(as_text.split(".", maxsplit=1)[1].rstrip("0"))


def parse_table1_long(
    table: list[list[str | None]],
    trial_id: str,
    source_page: int,
) -> pd.DataFrame:
    """Parse a baseline characteristics table into canonical long format."""

    if not table:
        raise ValueError("Empty table cannot be parsed.")

    header = [clean_cell(value) for value in table[0]]
    if len(header) < 4:
        raise ValueError("Table must contain at least 4 columns.")

    group_early = parse_group_header(header[1])
    group_late = parse_group_header(header[2])

    rows: list[dict[str, object]] = []
    current_variable: str | None = None
    variable_order = 0
    level_order = 0
    variable_first_pval: dict[str, float] = {}

    for raw_row in table[1:]:
        row = [clean_cell(value) for value in raw_row[:4]]
        if len(row) < 4:
            row.extend([""] * (4 - len(row)))
        raw_label, value_early, value_late, p_value_text = row

        if not raw_label:
            continue

        normalized_variable = normalize_variable_name(raw_label)
        p_value = parse_float(p_value_text)

        is_variable_header = (value_early == "" and value_late == "")
        if is_variable_header:
            current_variable = normalized_variable
            variable_order += 1
            level_order = 0
            if p_value is not None:
                variable_first_pval[current_variable] = p_value
            continue

        if "age" in normalized_variable.lower() and current_variable is None:
            variable_name = normalized_variable
            variable_order += 1
            median_early, low_early, high_early = parse_median_range(value_early)
            median_late, low_late, high_late = parse_median_range(value_late)
            if p_value is not None:
                variable_first_pval[variable_name] = p_value

            rows.append(
                {
                    "trial_id": trial_id,
                    "variable": variable_name,
                    "level": "all",
                    "var_type": "continuous_median_range",
                    "group": "early_tod",
                    "n_group": group_early.n,
                    "value": median_early,
                    "sd": None,
                    "decimals": infer_decimals(median_early),
                    "percent": None,
                    "range_low": low_early,
                    "range_high": high_early,
                    "reported_p": p_value,
                    "extract_confidence": "high",
                    "source_page": source_page,
                    "variable_order": variable_order,
                    "level_order": 0,
                }
            )
            rows.append(
                {
                    "trial_id": trial_id,
                    "variable": variable_name,
                    "level": "all",
                    "var_type": "continuous_median_range",
                    "group": "late_tod",
                    "n_group": group_late.n,
                    "value": median_late,
                    "sd": None,
                    "decimals": infer_decimals(median_late),
                    "percent": None,
                    "range_low": low_late,
                    "range_high": high_late,
                    "reported_p": p_value,
                    "extract_confidence": "high",
                    "source_page": source_page,
                    "variable_order": variable_order,
                    "level_order": 0,
                }
            )
            continue

        if current_variable is None:
            current_variable = normalized_variable
            variable_order += 1
            level_order = 0

        level_order += 1
        count_early, percent_early = parse_count_percent(value_early)
        count_late, percent_late = parse_count_percent(value_late)

        if p_value is not None and current_variable not in variable_first_pval:
            variable_first_pval[current_variable] = p_value

        rows.append(
            {
                "trial_id": trial_id,
                "variable": current_variable,
                "level": raw_label,
                "var_type": "categorical_count_percent",
                "group": "early_tod",
                "n_group": group_early.n,
                "value": count_early,
                "sd": None,
                "decimals": 0,
                "percent": percent_early,
                "range_low": None,
                "range_high": None,
                "reported_p": p_value,
                "extract_confidence": "high",
                "source_page": source_page,
                "variable_order": variable_order,
                "level_order": level_order,
            }
        )
        rows.append(
            {
                "trial_id": trial_id,
                "variable": current_variable,
                "level": raw_label,
                "var_type": "categorical_count_percent",
                "group": "late_tod",
                "n_group": group_late.n,
                "value": count_late,
                "sd": None,
                "decimals": 0,
                "percent": percent_late,
                "range_low": None,
                "range_high": None,
                "reported_p": p_value,
                "extract_confidence": "high",
                "source_page": source_page,
                "variable_order": variable_order,
                "level_order": level_order,
            }
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        raise ValueError("No rows were parsed from Table 1.")

    for variable_name, first_p in variable_first_pval.items():
        variable_mask = dataframe["variable"] == variable_name
        missing_mask = variable_mask & dataframe["reported_p"].isna()
        dataframe.loc[missing_mask, "reported_p"] = first_p

    return dataframe


def chi_square_2x2_pvalue(a: int, b: int, c: int, d: int) -> float | None:
    """Compute two-sided Pearson chi-square p-value for a 2x2 table."""

    total = a + b + c + d
    denominator = (a + b) * (c + d) * (a + c) * (b + d)
    if total <= 0 or denominator == 0:
        return None
    chi2 = (total * (a * d - b * c) ** 2) / denominator
    return float(math.erfc(math.sqrt(chi2 / 2)))


def _ordered_unique(values: Iterable[object]) -> list[object]:
    """Return unique values preserving first-seen order."""

    seen: set[object] = set()
    ordered: list[object] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def build_simdistr_input(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Build a simdistr-compatible input table from parsed baseline rows."""

    categorical = table1_long[table1_long["var_type"] == "categorical_count_percent"].copy()
    if categorical.empty:
        raise ValueError("No categorical rows available for simdistr input.")

    rows: list[dict[str, object]] = []
    variable_ordered = _ordered_unique(categorical["variable"].tolist())

    for variable_name in variable_ordered:
        variable_rows = categorical[categorical["variable"] == variable_name].copy()
        levels = _ordered_unique(variable_rows["level"].tolist())
        selected_levels = levels[:1] if len(levels) == 2 else levels

        for level_name in selected_levels:
            level_rows = variable_rows[variable_rows["level"] == level_name]
            early_row = level_rows[level_rows["group"] == "early_tod"]
            late_row = level_rows[level_rows["group"] == "late_tod"]
            if early_row.empty or late_row.empty:
                continue

            early_series = early_row.iloc[0]
            late_series = late_row.iloc[0]

            n_early = int(early_series["n_group"])
            n_late = int(late_series["n_group"])
            count_early = int(early_series["value"])
            count_late = int(late_series["value"])
            p_chi2 = chi_square_2x2_pvalue(
                a=count_early,
                b=n_early - count_early,
                c=count_late,
                d=n_late - count_late,
            )

            rows.append(
                {
                    "1_category": variable_name,
                    "2_outcome": level_name,
                    "3_n_arm1": n_early,
                    "4_n_arm2": n_late,
                    "5_n_arm1_outcome": count_early,
                    "6_n_arm2_outcome": count_late,
                    "7_prop_arm1": count_early / n_early,
                    "8_prop_arm2": count_late / n_late,
                    "9_observed_pval": p_chi2,
                }
            )

    return pd.DataFrame(rows)


def build_csf_input(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Build a one-vs-rest table for CSF/STALT-oriented analyses."""

    categorical = table1_long[table1_long["var_type"] == "categorical_count_percent"].copy()
    if categorical.empty:
        raise ValueError("No categorical rows available for CSF input.")

    rows: list[dict[str, object]] = []
    variable_ordered = _ordered_unique(categorical["variable"].tolist())

    for variable_name in variable_ordered:
        variable_rows = categorical[categorical["variable"] == variable_name].copy()
        levels = _ordered_unique(variable_rows["level"].tolist())
        selected_levels = levels[:1] if len(levels) == 2 else levels
        if variable_rows["reported_p"].notna().any():
            reported_p = variable_rows["reported_p"].dropna().iloc[0]
        else:
            reported_p = None

        for level_name in selected_levels:
            level_rows = variable_rows[variable_rows["level"] == level_name]
            early_row = level_rows[level_rows["group"] == "early_tod"]
            late_row = level_rows[level_rows["group"] == "late_tod"]
            if early_row.empty or late_row.empty:
                continue

            early_series = early_row.iloc[0]
            late_series = late_row.iloc[0]
            n_early = int(early_series["n_group"])
            n_late = int(late_series["n_group"])
            count_early = int(early_series["value"])
            count_late = int(late_series["value"])

            rows.append(
                {
                    "trial_id": early_series["trial_id"],
                    "variable": variable_name,
                    "level": level_name,
                    "n_arm1": n_early,
                    "n_arm2": n_late,
                    "count_arm1": count_early,
                    "count_arm2": count_late,
                    "prop_arm1": count_early / n_early,
                    "prop_arm2": count_late / n_late,
                    "reported_p": reported_p,
                    "row_chisq_p": chi_square_2x2_pvalue(
                        a=count_early,
                        b=n_early - count_early,
                        c=count_late,
                        d=n_late - count_late,
                    ),
                    "one_vs_rest": True,
                }
            )

    return pd.DataFrame(rows)
