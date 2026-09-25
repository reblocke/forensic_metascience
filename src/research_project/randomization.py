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


def normalize_group_key(value: str) -> str:
    """Normalize an arm label into a stable snake_case key."""

    cleaned = clean_cell(value)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"\b(group|arm)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return key or "group"


def parse_group_header(header_cell: str) -> GroupInfo:
    """Parse arm label and sample size from a header cell."""

    cleaned = clean_cell(header_cell)
    n_match = re.search(r"n\s*=\s*([^\s)]+)", cleaned, flags=re.IGNORECASE)
    if not n_match:
        raise ValueError(f"Could not parse group size from header: {cleaned!r}")
    try:
        n_value = float(n_match.group(1))
    except ValueError as exc:
        raise ValueError(f"Invalid group size in header: {cleaned!r}") from exc
    if not math.isfinite(n_value) or n_value <= 0 or not n_value.is_integer():
        raise ValueError(f"Group size must be a finite positive integer: {cleaned!r}")
    label = re.sub(r"\(.*?\)", "", cleaned)
    label = re.sub(r"\b(group|arm)\b", "", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+", " ", label).strip()
    return GroupInfo(label=label, n=int(n_value))


def parse_float(text: str) -> float | None:
    """Parse a float from text, returning None when unavailable."""

    cleaned = clean_cell(text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_p_value(text: str) -> tuple[float | None, str, str]:
    """Parse a P value while preserving its printed comparator and text."""

    raw = clean_cell(text)
    if not raw:
        return None, raw, ""
    match = re.fullmatch(
        r"[Pp]?\s*(<=|>=|<|>|=)?\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        raw,
    )
    if not match:
        return None, raw, ""
    return float(match.group(2)), raw, match.group(1) or "="


def _printed_decimals(value: str) -> int | None:
    match = re.search(r"(?<!\w)[+-]?\d+\.(\d+)", value)
    if match:
        return len(match.group(1))
    return 0 if re.search(r"(?<!\w)[+-]?\d+", value) else None


def _count_percent_raw(value: str) -> tuple[str, str]:
    match = re.fullmatch(
        r"\s*(-?\d+)\s*(?:/\s*\d+)?\s*\(\s*([+-]?\d+(?:\.\d+)?)\s*%?\s*\)\s*",
        value,
    )
    return (match.group(1), match.group(2)) if match else ("", "")


def parse_count_percent(cell_value: str) -> tuple[int | None, float | None]:
    """Parse count and percentage from strings like '95 (90.5)'."""

    count, percent, _ = parse_count_percent_denominator(cell_value)
    return count, percent


def parse_count_percent_denominator(
    cell_value: str,
) -> tuple[int | None, float | None, int | None]:
    """Parse count, percentage, and denominator from common baseline cell formats."""

    cleaned = clean_cell(cell_value).replace("%", "")
    cleaned = cleaned.replace("·", ".")

    match = re.fullmatch(r"\s*(-?\d+)\s*/\s*(\d+)\s*\(([^)]+)\)\s*", cleaned)
    if match:
        percent_text = match.group(3).strip()
        percent = None if "<" in percent_text else parse_float(percent_text)
        return int(match.group(1)), percent, int(match.group(2))

    match = re.fullmatch(r"\s*(-?\d+)\s*\(([^)]+)\)\s*", cleaned)
    if match:
        percent_text = match.group(2).strip()
        percent = None if "<" in percent_text else parse_float(percent_text)
        return int(match.group(1)), percent, None

    if re.fullmatch(r"-?\d+", cleaned):
        return int(cleaned), None, None

    return None, None, None


def parse_median_range(cell_value: str) -> tuple[float | None, float | None, float | None]:
    """Parse median and spread from strings like '61 (33-80)' or '72 [57, 82]'."""

    cleaned = clean_cell(cell_value)
    cleaned = cleaned.replace("−", "-").replace("–", "-").replace("·", ".")
    pattern = (
        r"(-?\d+(?:\.\d+)?)\s*[\(\[]\s*(-?\d+(?:\.\d+)?)\s*[-,]\s*"
        r"(-?\d+(?:\.\d+)?)\s*[\)\]]"
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


def _build_continuous_row(
    *,
    trial_id: str,
    variable_name: str,
    group_key: str,
    n_group: int,
    value: float | None,
    low: float | None,
    high: float | None,
    reported_p: float | None,
    reported_p_raw: str,
    reported_p_comparator: str,
    raw_value: str,
    source_page: int,
    variable_order: int,
) -> dict[str, object]:
    return {
        "trial_id": trial_id,
        "variable": variable_name,
        "level": "all",
        "var_type": "continuous_median_range",
        "group": group_key,
        "n_group": n_group,
        "value": value,
        "raw_value": raw_value,
        "raw_statistic_value": re.search(r"[+-]?\d+(?:\.\d+)?", raw_value).group(0)
        if re.search(r"[+-]?\d+(?:\.\d+)?", raw_value)
        else "",
        "reported_decimals": _printed_decimals(
            re.search(r"[+-]?\d+(?:\.\d+)?", raw_value).group(0)
            if re.search(r"[+-]?\d+(?:\.\d+)?", raw_value)
            else ""
        ),
        "sd": None,
        "decimals": infer_decimals(value),
        "percent": None,
        "range_low": low,
        "range_high": high,
        "reported_p": reported_p,
        "reported_p_raw": reported_p_raw,
        "reported_p_comparator": reported_p_comparator,
        "extract_confidence": "high",
        "source_page": source_page,
        "source_locator": f"table1:page={source_page}:row={variable_order}:group={group_key}",
        "variable_order": variable_order,
        "level_order": 0,
    }


def _build_categorical_row(
    *,
    trial_id: str,
    variable_name: str,
    level_name: str,
    group_key: str,
    n_group: int,
    count: int | None,
    percent: float | None,
    reported_p: float | None,
    reported_p_raw: str,
    reported_p_comparator: str,
    raw_value: str,
    source_page: int,
    variable_order: int,
    level_order: int,
) -> dict[str, object]:
    raw_count, raw_percent = _count_percent_raw(raw_value)
    return {
        "trial_id": trial_id,
        "variable": variable_name,
        "level": level_name,
        "var_type": "categorical_count_percent",
        "group": group_key,
        "n_group": n_group,
        "value": count,
        "raw_value": raw_value,
        "raw_count": raw_count,
        "sd": None,
        "decimals": _printed_decimals(_count_percent_raw(raw_value)[0]),
        "percent": percent,
        "reported_percent_raw": raw_percent,
        "reported_percent_decimals": _printed_decimals(raw_percent),
        "denominator_role": "unknown",
        "weighting": "unknown",
        "rounding_convention": "unknown",
        "range_low": None,
        "range_high": None,
        "reported_p": reported_p,
        "reported_p_raw": reported_p_raw,
        "reported_p_comparator": reported_p_comparator,
        "extract_confidence": "high",
        "source_page": source_page,
        "source_locator": (
            f"table1:page={source_page}:row={variable_order}:level={level_order}:group={group_key}"
        ),
        "variable_order": variable_order,
        "level_order": level_order,
    }


def _parse_standard_table1(
    *,
    table: list[list[str | None]],
    trial_id: str,
    source_page: int,
) -> pd.DataFrame:
    """Parse the original 4-column baseline-table layout."""

    header = [clean_cell(value) for value in table[0]]
    if len(header) < 4:
        raise ValueError("Table must contain at least 4 columns.")

    group_a = parse_group_header(header[1])
    group_b = parse_group_header(header[2])
    group_a_key = normalize_group_key(group_a.label)
    group_b_key = normalize_group_key(group_b.label)

    rows: list[dict[str, object]] = []
    current_variable: str | None = None
    variable_order = 0
    level_order = 0
    variable_first_pval: dict[str, tuple[float, str, str]] = {}

    for raw_row in table[1:]:
        row = [clean_cell(value) for value in raw_row[:4]]
        if len(row) < 4:
            row.extend([""] * (4 - len(row)))
        raw_label, value_a, value_b, p_value_text = row

        if not raw_label:
            continue

        normalized_variable = normalize_variable_name(raw_label)
        p_value, p_value_raw, p_value_comparator = parse_p_value(p_value_text)

        is_variable_header = value_a == "" and value_b == ""
        if is_variable_header:
            current_variable = normalized_variable
            variable_order += 1
            level_order = 0
            if p_value is not None:
                variable_first_pval[current_variable] = (
                    p_value,
                    p_value_raw,
                    p_value_comparator,
                )
            continue

        if "age" in normalized_variable.lower() and current_variable is None:
            variable_name = normalized_variable
            variable_order += 1
            median_a, low_a, high_a = parse_median_range(value_a)
            median_b, low_b, high_b = parse_median_range(value_b)
            if p_value is not None:
                variable_first_pval[variable_name] = (
                    p_value,
                    p_value_raw,
                    p_value_comparator,
                )

            rows.append(
                _build_continuous_row(
                    trial_id=trial_id,
                    variable_name=variable_name,
                    group_key=group_a_key,
                    n_group=group_a.n,
                    value=median_a,
                    low=low_a,
                    high=high_a,
                    reported_p=p_value,
                    reported_p_raw=p_value_raw,
                    reported_p_comparator=p_value_comparator,
                    raw_value=value_a,
                    source_page=source_page,
                    variable_order=variable_order,
                )
            )
            rows.append(
                _build_continuous_row(
                    trial_id=trial_id,
                    variable_name=variable_name,
                    group_key=group_b_key,
                    n_group=group_b.n,
                    value=median_b,
                    low=low_b,
                    high=high_b,
                    reported_p=p_value,
                    reported_p_raw=p_value_raw,
                    reported_p_comparator=p_value_comparator,
                    raw_value=value_b,
                    source_page=source_page,
                    variable_order=variable_order,
                )
            )
            continue

        if current_variable is None:
            current_variable = normalized_variable
            variable_order += 1
            level_order = 0

        level_order += 1
        count_a, percent_a, denom_a = parse_count_percent_denominator(value_a)
        count_b, percent_b, denom_b = parse_count_percent_denominator(value_b)

        if p_value is not None and current_variable not in variable_first_pval:
            variable_first_pval[current_variable] = (
                p_value,
                p_value_raw,
                p_value_comparator,
            )

        rows.append(
            _build_categorical_row(
                trial_id=trial_id,
                variable_name=current_variable,
                level_name=raw_label,
                group_key=group_a_key,
                n_group=denom_a if denom_a is not None else group_a.n,
                count=count_a,
                percent=percent_a,
                reported_p=p_value,
                reported_p_raw=p_value_raw,
                reported_p_comparator=p_value_comparator,
                raw_value=value_a,
                source_page=source_page,
                variable_order=variable_order,
                level_order=level_order,
            )
        )
        rows.append(
            _build_categorical_row(
                trial_id=trial_id,
                variable_name=current_variable,
                level_name=raw_label,
                group_key=group_b_key,
                n_group=denom_b if denom_b is not None else group_b.n,
                count=count_b,
                percent=percent_b,
                reported_p=p_value,
                reported_p_raw=p_value_raw,
                reported_p_comparator=p_value_comparator,
                raw_value=value_b,
                source_page=source_page,
                variable_order=variable_order,
                level_order=level_order,
            )
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        raise ValueError("No rows were parsed from Table 1.")

    for variable_name, first_p in variable_first_pval.items():
        variable_mask = dataframe["variable"] == variable_name
        missing_mask = variable_mask & dataframe["reported_p"].isna()
        dataframe.loc[missing_mask, "reported_p"] = first_p[0]
        dataframe.loc[missing_mask, "reported_p_raw"] = first_p[1]
        dataframe.loc[missing_mask, "reported_p_comparator"] = first_p[2]

    return dataframe


def _parse_hierarchical_baseline_table(
    *,
    table: list[list[str | None]],
    trial_id: str,
    source_page: int,
) -> pd.DataFrame:
    """Parse supplement-style baseline tables with variable and level columns."""

    header = [clean_cell(value) for value in table[0]]
    if len(header) < 4:
        raise ValueError("Hierarchical baseline table must contain at least 4 columns.")

    group_a_label = clean_cell(header[-2])
    group_b_label = clean_cell(header[-1])
    group_a_key = normalize_group_key(group_a_label)
    group_b_key = normalize_group_key(group_b_label)

    group_a_n = None
    group_b_n = None
    if len(table) > 1:
        n_row = [clean_cell(value) for value in table[1][:4]]
        if clean_cell(n_row[0]).lower() == "n":
            count_a, _, _ = parse_count_percent_denominator(n_row[-2])
            count_b, _, _ = parse_count_percent_denominator(n_row[-1])
            group_a_n = count_a
            group_b_n = count_b

    rows: list[dict[str, object]] = []
    current_variable: str | None = None
    variable_order = 0
    level_order = 0

    for raw_row in table[1:]:
        row = [clean_cell(value) for value in raw_row[:4]]
        if len(row) < 4:
            row.extend([""] * (4 - len(row)))
        raw_variable, raw_level, value_a, value_b = row

        if not any([raw_variable, raw_level, value_a, value_b]):
            continue
        if clean_cell(raw_variable).lower() == "n":
            continue

        if raw_variable:
            current_variable = normalize_variable_name(raw_variable)
            variable_order += 1
            level_order = 0

        if current_variable is None or value_a == "" or value_b == "":
            continue

        level_text = clean_cell(raw_level)
        if level_text.lower().startswith("median"):
            median_a, low_a, high_a = parse_median_range(value_a)
            median_b, low_b, high_b = parse_median_range(value_b)
            rows.append(
                _build_continuous_row(
                    trial_id=trial_id,
                    variable_name=current_variable,
                    group_key=group_a_key,
                    n_group=group_a_n if group_a_n is not None else 0,
                    value=median_a,
                    low=low_a,
                    high=high_a,
                    reported_p=None,
                    reported_p_raw="",
                    reported_p_comparator="",
                    raw_value=value_a,
                    source_page=source_page,
                    variable_order=variable_order,
                )
            )
            rows.append(
                _build_continuous_row(
                    trial_id=trial_id,
                    variable_name=current_variable,
                    group_key=group_b_key,
                    n_group=group_b_n if group_b_n is not None else 0,
                    value=median_b,
                    low=low_b,
                    high=high_b,
                    reported_p=None,
                    reported_p_raw="",
                    reported_p_comparator="",
                    raw_value=value_b,
                    source_page=source_page,
                    variable_order=variable_order,
                )
            )
            continue

        level_order += 1
        count_a, percent_a, denom_a = parse_count_percent_denominator(value_a)
        count_b, percent_b, denom_b = parse_count_percent_denominator(value_b)
        if count_a is None and count_b is None:
            continue
        rows.append(
            _build_categorical_row(
                trial_id=trial_id,
                variable_name=current_variable,
                level_name=level_text or "all",
                group_key=group_a_key,
                n_group=(
                    denom_a if denom_a is not None else group_a_n if group_a_n is not None else 0
                ),
                count=count_a,
                percent=percent_a,
                reported_p=None,
                reported_p_raw="",
                reported_p_comparator="",
                raw_value=value_a,
                source_page=source_page,
                variable_order=variable_order,
                level_order=level_order,
            )
        )
        rows.append(
            _build_categorical_row(
                trial_id=trial_id,
                variable_name=current_variable,
                level_name=level_text or "all",
                group_key=group_b_key,
                n_group=(
                    denom_b if denom_b is not None else group_b_n if group_b_n is not None else 0
                ),
                count=count_b,
                percent=percent_b,
                reported_p=None,
                reported_p_raw="",
                reported_p_comparator="",
                raw_value=value_b,
                source_page=source_page,
                variable_order=variable_order,
                level_order=level_order,
            )
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        raise ValueError("No rows were parsed from hierarchical baseline table.")
    return dataframe


def parse_table1_long(
    table: list[list[str | None]],
    trial_id: str,
    source_page: int,
) -> pd.DataFrame:
    """Parse a baseline characteristics table into canonical long format."""

    if not table:
        raise ValueError("Empty table cannot be parsed.")

    header = [clean_cell(value) for value in table[0]]
    if len(header) >= 4 and header[0] == "" and header[1] == "" and header[2] and header[3]:
        return _parse_hierarchical_baseline_table(
            table=table,
            trial_id=trial_id,
            source_page=source_page,
        )

    return _parse_standard_table1(
        table=table,
        trial_id=trial_id,
        source_page=source_page,
    )


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


def _group_pair(table1_long: pd.DataFrame) -> tuple[str, str]:
    groups = _ordered_unique(table1_long["group"].dropna().tolist())
    if len(groups) != 2:
        raise ValueError(f"Expected exactly 2 trial arms, found {groups}")
    return str(groups[0]), str(groups[1])


def _validated_count_and_denominator(count: object, denominator: object) -> tuple[int, int] | None:
    """Return exact nonnegative count and positive denominator, or reject the row."""

    try:
        count_value = float(count)
        denominator_value = float(denominator)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(count_value) or not math.isfinite(denominator_value):
        return None
    if not count_value.is_integer() or not denominator_value.is_integer():
        return None
    count_int = int(count_value)
    denominator_int = int(denominator_value)
    if count_int < 0 or denominator_int <= 0 or count_int > denominator_int:
        return None
    return count_int, denominator_int


def build_simdistr_input(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Build a simdistr-compatible input table from parsed baseline rows."""

    categorical = table1_long[table1_long["var_type"] == "categorical_count_percent"].copy()
    if categorical.empty:
        raise ValueError("No categorical rows available for simdistr input.")
    group_a, group_b = _group_pair(categorical)

    rows: list[dict[str, object]] = []
    variable_ordered = _ordered_unique(categorical["variable"].tolist())

    for variable_name in variable_ordered:
        variable_rows = categorical[categorical["variable"] == variable_name].copy()
        levels = _ordered_unique(variable_rows["level"].tolist())
        selected_levels = levels[:1] if len(levels) == 2 else levels

        for level_name in selected_levels:
            level_rows = variable_rows[variable_rows["level"] == level_name]
            arm_a_row = level_rows[level_rows["group"] == group_a]
            arm_b_row = level_rows[level_rows["group"] == group_b]
            if arm_a_row.empty or arm_b_row.empty:
                continue

            arm_a_series = arm_a_row.iloc[0]
            arm_b_series = arm_b_row.iloc[0]

            arm_a_counts = _validated_count_and_denominator(
                arm_a_series["value"], arm_a_series["n_group"]
            )
            arm_b_counts = _validated_count_and_denominator(
                arm_b_series["value"], arm_b_series["n_group"]
            )
            if arm_a_counts is None or arm_b_counts is None:
                continue
            count_early, n_early = arm_a_counts
            count_late, n_late = arm_b_counts
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
    group_a, group_b = _group_pair(categorical)

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
            arm_a_row = level_rows[level_rows["group"] == group_a]
            arm_b_row = level_rows[level_rows["group"] == group_b]
            if arm_a_row.empty or arm_b_row.empty:
                continue

            arm_a_series = arm_a_row.iloc[0]
            arm_b_series = arm_b_row.iloc[0]
            arm_a_counts = _validated_count_and_denominator(
                arm_a_series["value"], arm_a_series["n_group"]
            )
            arm_b_counts = _validated_count_and_denominator(
                arm_b_series["value"], arm_b_series["n_group"]
            )
            if arm_a_counts is None or arm_b_counts is None:
                continue
            count_early, n_early = arm_a_counts
            count_late, n_late = arm_b_counts

            rows.append(
                {
                    "trial_id": arm_a_series["trial_id"],
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
