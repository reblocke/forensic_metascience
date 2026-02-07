"""Numeric integrity transforms for forensic meta-science checks."""

from __future__ import annotations

import math
import re

import pandas as pd

SCRUTINY_CASE_COLUMNS = [
    "case_id",
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
    "is_binary",
    "eligible_grim",
    "eligible_grimmer",
    "eligible_debit",
    "exclude_reason",
]


def compute_percent_from_count(
    count: int | float | None,
    n_group: int | float | None,
) -> float | None:
    """Compute percentage from a count and group size."""

    if count is None or n_group in (None, 0):
        return None
    if pd.isna(count) or pd.isna(n_group):
        return None
    return float(count) * 100.0 / float(n_group)


def build_numeric_table(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Build numeric integrity table from baseline Table 1 long data."""

    required = {
        "trial_id",
        "variable",
        "level",
        "group",
        "n_group",
        "value",
        "percent",
        "decimals",
        "reported_p",
        "var_type",
    }
    missing = required.difference(table1_long.columns)
    if missing:
        raise ValueError(f"Missing required columns for numeric integrity: {sorted(missing)}")

    categorical = table1_long[
        table1_long["var_type"] == "categorical_count_percent"
    ].copy()
    categorical = categorical.rename(columns={"value": "count", "percent": "reported_percent"})
    categorical["computed_percent"] = categorical.apply(
        lambda row: compute_percent_from_count(row["count"], row["n_group"]),
        axis=1,
    )
    categorical["abs_percent_delta"] = (
        categorical["reported_percent"] - categorical["computed_percent"]
    ).abs()
    categorical["flag_percent_delta_0_2"] = categorical["abs_percent_delta"] >= 0.2
    return categorical[
        [
            "trial_id",
            "variable",
            "level",
            "group",
            "n_group",
            "count",
            "reported_percent",
            "computed_percent",
            "abs_percent_delta",
            "flag_percent_delta_0_2",
            "reported_p",
            "decimals",
        ]
    ]


def build_scrutiny_input(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Create a lightweight scrutiny-oriented input table."""

    required = {"trial_id", "variable", "group", "n_group", "value", "decimals", "var_type"}
    missing = required.difference(table1_long.columns)
    if missing:
        raise ValueError(f"Missing required columns for scrutiny input: {sorted(missing)}")

    continuous = table1_long[table1_long["var_type"] == "continuous_median_range"].copy()
    continuous["item_label"] = continuous["variable"] + " [" + continuous["group"] + "]"
    continuous = continuous.rename(columns={"n_group": "n", "value": "x"})
    continuous["x"] = pd.to_numeric(continuous["x"], errors="coerce")
    continuous["n"] = pd.to_numeric(continuous["n"], errors="coerce").astype("Int64")
    continuous["decimals"] = (
        pd.to_numeric(continuous["decimals"], errors="coerce").fillna(0).astype(int)
    )
    return continuous[["trial_id", "item_label", "n", "x", "decimals"]]


def build_statcheck_stub(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Create a statcheck-style placeholder input from reported p-values."""

    required = {"trial_id", "variable", "reported_p"}
    missing = required.difference(table1_long.columns)
    if missing:
        raise ValueError(f"Missing required columns for statcheck input: {sorted(missing)}")

    pvals = table1_long[["trial_id", "variable", "reported_p"]].dropna().copy()
    pvals = pvals.drop_duplicates()
    pvals["reported_p"] = pd.to_numeric(pvals["reported_p"], errors="coerce")
    pvals["reported_p"] = pvals["reported_p"].clip(lower=0.0, upper=1.0)
    return pvals.reset_index(drop=True)


def _to_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    numeric = _to_float(value)
    if numeric is None or not math.isfinite(numeric):
        return None
    return int(round(numeric))


def _digits_from_str(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.split(".", maxsplit=1)[1].rstrip("0"))


def _format_numeric_string(value: object, digits: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return ""
    digits_int = _to_int(digits)
    if digits_int is None:
        return str(numeric)
    return f"{numeric:.{max(digits_int, 0)}f}"


def _parse_item_label(item_label: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\[(.*?)\]\s*$", str(item_label))
    if not match:
        return str(item_label), "unknown_group"
    return match.group(1).strip(), match.group(2).strip()


def _source_unit(variable: str, level: str, group: str) -> str:
    if level and level != "all":
        return f"{variable} / {level} [{group}]"
    return f"{variable} [{group}]"


def _exclude_reason(
    *,
    eligible_grim: bool,
    eligible_grimmer: bool,
    eligible_debit: bool,
) -> str:
    if not eligible_grim:
        return "missing_x_or_n"
    if not eligible_grimmer:
        return "missing_sd"
    if not eligible_debit:
        return "not_binary"
    return ""


def build_scrutiny_cases(
    scrutiny_input: pd.DataFrame,
    numeric_summary_long: pd.DataFrame,
    *,
    source_pdf: str = "",
) -> pd.DataFrame:
    """Build canonical scrutiny-case rows for method-specific execution."""

    rows: list[dict[str, object]] = []

    if not scrutiny_input.empty:
        required_scrutiny = {"trial_id", "item_label", "n", "x", "decimals"}
        missing_scrutiny = required_scrutiny.difference(scrutiny_input.columns)
        if missing_scrutiny:
            raise ValueError(
                "Missing columns for scrutiny cases from scrutiny_input: "
                f"{sorted(missing_scrutiny)}"
            )
        for _, row in scrutiny_input.iterrows():
            variable, group = _parse_item_label(str(row["item_label"]))
            n_value = _to_int(row["n"])
            digits_x = _to_int(row["decimals"])
            x_str = _format_numeric_string(row["x"], digits_x)
            sd_str = ""
            digits_sd = None
            x_numeric = _to_float(x_str)
            sd_numeric = _to_float(sd_str)
            is_binary = (
                x_numeric is not None
                and sd_numeric is not None
                and 0.0 <= x_numeric <= 1.0
                and 0.0 <= sd_numeric <= 1.0
            )
            eligible_grim = bool(x_str and n_value is not None and n_value > 0)
            eligible_grimmer = bool(eligible_grim and sd_str)
            eligible_debit = bool(eligible_grimmer and is_binary)
            rows.append(
                {
                    "case_id": "",
                    "trial_id": str(row["trial_id"]),
                    "source_pdf": source_pdf,
                    "source_table": "table1_continuous_median_range",
                    "source_page": None,
                    "variable": variable,
                    "level": "all",
                    "group": group or "unknown_group",
                    "n": n_value,
                    "x_str": x_str,
                    "sd_str": sd_str,
                    "digits_x": digits_x,
                    "digits_sd": digits_sd,
                    "is_binary": is_binary,
                    "eligible_grim": eligible_grim,
                    "eligible_grimmer": eligible_grimmer,
                    "eligible_debit": eligible_debit,
                    "exclude_reason": _exclude_reason(
                        eligible_grim=eligible_grim,
                        eligible_grimmer=eligible_grimmer,
                        eligible_debit=eligible_debit,
                    ),
                }
            )

    if not numeric_summary_long.empty:
        required_summary = {
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
        }
        missing_summary = required_summary.difference(numeric_summary_long.columns)
        if missing_summary:
            raise ValueError(
                "Missing columns for scrutiny cases from numeric_summary_long: "
                f"{sorted(missing_summary)}"
            )
        for _, row in numeric_summary_long.iterrows():
            x_str = str(row["x_str"]) if not pd.isna(row["x_str"]) else ""
            sd_str = str(row["sd_str"]) if not pd.isna(row["sd_str"]) else ""
            digits_x = _to_int(row["digits_x"])
            digits_sd = _to_int(row["digits_sd"])
            if digits_x is None and x_str:
                digits_x = _digits_from_str(x_str)
            if digits_sd is None and sd_str:
                digits_sd = _digits_from_str(sd_str)
            n_value = _to_int(row["n"])
            x_numeric = _to_float(x_str)
            sd_numeric = _to_float(sd_str)
            is_binary = (
                x_numeric is not None
                and sd_numeric is not None
                and 0.0 <= x_numeric <= 1.0
                and 0.0 <= sd_numeric <= 1.0
            )
            eligible_grim = bool(x_str and n_value is not None and n_value > 0)
            eligible_grimmer = bool(
                eligible_grim and sd_str and digits_sd is not None and digits_sd >= 0
            )
            eligible_debit = bool(eligible_grimmer and is_binary)
            rows.append(
                {
                    "case_id": "",
                    "trial_id": str(row["trial_id"]),
                    "source_pdf": str(row["source_pdf"]),
                    "source_table": str(row["source_table"]),
                    "source_page": _to_int(row["source_page"]),
                    "variable": str(row["variable"]),
                    "level": str(row["level"]) if not pd.isna(row["level"]) else "all",
                    "group": str(row["group"]),
                    "n": n_value,
                    "x_str": x_str,
                    "sd_str": sd_str,
                    "digits_x": digits_x,
                    "digits_sd": digits_sd,
                    "is_binary": is_binary,
                    "eligible_grim": eligible_grim,
                    "eligible_grimmer": eligible_grimmer,
                    "eligible_debit": eligible_debit,
                    "exclude_reason": _exclude_reason(
                        eligible_grim=eligible_grim,
                        eligible_grimmer=eligible_grimmer,
                        eligible_debit=eligible_debit,
                    ),
                }
            )

    scrutiny_cases = pd.DataFrame(rows, columns=SCRUTINY_CASE_COLUMNS)
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=SCRUTINY_CASE_COLUMNS)

    scrutiny_cases = scrutiny_cases.reset_index(drop=True)
    scrutiny_cases["case_id"] = [
        f"case_{index + 1:04d}" for index in range(len(scrutiny_cases))
    ]
    scrutiny_cases["source_pdf"] = scrutiny_cases["source_pdf"].fillna(source_pdf)
    scrutiny_cases["level"] = scrutiny_cases["level"].replace("", "all")
    return scrutiny_cases[SCRUTINY_CASE_COLUMNS]


def build_scrutiny_grim_input(scrutiny_cases: pd.DataFrame) -> pd.DataFrame:
    """Build GRIM-ready input from canonical scrutiny cases."""

    columns = [
        "case_id",
        "trial_id",
        "source_unit",
        "source_pdf",
        "source_table",
        "source_page",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "digits_x",
    ]
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=columns)
    subset = scrutiny_cases[scrutiny_cases["eligible_grim"]].copy()
    if subset.empty:
        return pd.DataFrame(columns=columns)
    subset["source_unit"] = subset.apply(
        lambda row: _source_unit(str(row["variable"]), str(row["level"]), str(row["group"])),
        axis=1,
    )
    subset = subset.rename(columns={"x_str": "x"})
    return subset[columns]


def build_scrutiny_grimmer_input(scrutiny_cases: pd.DataFrame) -> pd.DataFrame:
    """Build GRIMMER-ready input from canonical scrutiny cases."""

    columns = [
        "case_id",
        "trial_id",
        "source_unit",
        "source_pdf",
        "source_table",
        "source_page",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "sd",
        "digits_x",
        "digits_sd",
    ]
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=columns)
    subset = scrutiny_cases[scrutiny_cases["eligible_grimmer"]].copy()
    if subset.empty:
        return pd.DataFrame(columns=columns)
    subset["source_unit"] = subset.apply(
        lambda row: _source_unit(str(row["variable"]), str(row["level"]), str(row["group"])),
        axis=1,
    )
    subset = subset.rename(columns={"x_str": "x", "sd_str": "sd"})
    return subset[columns]


def build_scrutiny_debit_input(scrutiny_cases: pd.DataFrame) -> pd.DataFrame:
    """Build DEBIT-ready input from canonical scrutiny cases."""

    columns = [
        "case_id",
        "trial_id",
        "source_unit",
        "source_pdf",
        "source_table",
        "source_page",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "sd",
        "digits_x",
        "digits_sd",
    ]
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=columns)
    subset = scrutiny_cases[scrutiny_cases["eligible_debit"]].copy()
    if subset.empty:
        return pd.DataFrame(columns=columns)
    subset["source_unit"] = subset.apply(
        lambda row: _source_unit(str(row["variable"]), str(row["level"]), str(row["group"])),
        axis=1,
    )
    subset = subset.rename(columns={"x_str": "x", "sd_str": "sd"})
    return subset[columns]


def build_scrutiny_duplicate_input(scrutiny_cases: pd.DataFrame) -> pd.DataFrame:
    """Build duplication-check input from canonical scrutiny cases."""

    columns = [
        "case_id",
        "trial_id",
        "source_unit",
        "variable",
        "level",
        "group",
        "x",
        "sd",
        "n",
    ]
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=columns)
    subset = scrutiny_cases.copy()
    subset["source_unit"] = subset.apply(
        lambda row: _source_unit(str(row["variable"]), str(row["level"]), str(row["group"])),
        axis=1,
    )
    subset = subset.rename(columns={"x_str": "x", "sd_str": "sd"})
    subset = subset[(subset["x"] != "") | (subset["sd"] != "")]
    if subset.empty:
        return pd.DataFrame(columns=columns)
    return subset[columns]


def build_scrutiny_rounding_bias_input(scrutiny_cases: pd.DataFrame) -> pd.DataFrame:
    """Build rounding-bias input from canonical scrutiny cases."""

    columns = [
        "case_id",
        "trial_id",
        "source_unit",
        "x",
        "digits_x",
    ]
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=columns)
    subset = scrutiny_cases.copy()
    subset["source_unit"] = subset.apply(
        lambda row: _source_unit(str(row["variable"]), str(row["level"]), str(row["group"])),
        axis=1,
    )
    subset = subset.rename(columns={"x_str": "x"})
    subset = subset[(subset["x"] != "") & subset["digits_x"].notna()]
    if subset.empty:
        return pd.DataFrame(columns=columns)
    return subset[columns]


def build_rsprite2_stub(numeric_table: pd.DataFrame) -> pd.DataFrame:
    """Build a simple proportion-difference table as an rsprite2-ready stub."""

    required = {
        "trial_id",
        "variable",
        "level",
        "group",
        "reported_percent",
    }
    missing = required.difference(numeric_table.columns)
    if missing:
        raise ValueError(f"Missing required columns for rsprite2 stub: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    grouped = numeric_table.groupby(["trial_id", "variable", "level"], as_index=False)
    for _, subset in grouped:
        if len(subset) < 2:
            continue
        arms = subset.sort_values("group")
        row_a = arms.iloc[0]
        row_b = arms.iloc[1]
        diff = abs(float(row_a["reported_percent"]) - float(row_b["reported_percent"]))
        rows.append(
            {
                "trial_id": row_a["trial_id"],
                "variable": row_a["variable"],
                "level": row_a["level"],
                "group_a": row_a["group"],
                "group_b": row_b["group"],
                "percent_a": row_a["reported_percent"],
                "percent_b": row_b["reported_percent"],
                "abs_percent_between_arms": diff,
            }
        )
    return pd.DataFrame(rows)


def summarize_numeric_flags(numeric_table: pd.DataFrame) -> dict[str, float | int]:
    """Summarize numeric integrity flags for report-level aggregation."""

    if numeric_table.empty:
        return {
            "n_rows": 0,
            "n_rounding_flags": 0,
            "median_abs_percent_delta": math.nan,
            "max_abs_percent_delta": math.nan,
            "n_reported_p": 0,
        }

    return {
        "n_rows": int(len(numeric_table)),
        "n_rounding_flags": int(numeric_table["flag_percent_delta_0_2"].sum()),
        "median_abs_percent_delta": float(numeric_table["abs_percent_delta"].median()),
        "max_abs_percent_delta": float(numeric_table["abs_percent_delta"].max()),
        "n_reported_p": int(numeric_table["reported_p"].notna().sum()),
    }
