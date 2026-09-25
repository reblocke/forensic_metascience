"""Numeric integrity transforms for forensic meta-science checks."""

from __future__ import annotations

import math
import re
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation

import pandas as pd

SCRUTINY_CASE_COLUMNS = [
    "case_id",
    "trial_id",
    "source_pdf",
    "source_table",
    "source_page",
    "source_locator",
    "raw_value",
    "reported_decimals",
    "reported_p_raw",
    "reported_p_comparator",
    "variable",
    "level",
    "group",
    "n",
    "x_str",
    "sd_str",
    "digits_x",
    "digits_sd",
    "statistic_kind",
    "measurement_scale",
    "raw_or_adjusted",
    "weighting",
    "analysis_n",
    "imputation_status",
    "transformation_status",
    "granularity_transformation",
    "eligibility_evidence",
    "method_revision",
    "is_binary",
    "eligible_grim",
    "exclude_reason_grim",
    "eligible_grimmer",
    "exclude_reason_grimmer",
    "eligible_debit",
    "exclude_reason_debit",
    "exclude_reason",
]

SUMMARY_METADATA_COLUMNS = (
    "statistic_kind",
    "measurement_scale",
    "raw_or_adjusted",
    "weighting",
    "analysis_n",
    "imputation_status",
    "transformation_status",
    "granularity_transformation",
    "eligibility_evidence",
)
NUMERIC_METHOD_REVISION = "numeric_eligibility_precision_v3"


def compute_percent_from_count(
    count: int | float | None,
    n_group: int | float | None,
) -> float | None:
    """Compute percentage from a count and group size."""

    if count is None or n_group is None:
        return None
    if pd.isna(count) or pd.isna(n_group):
        return None
    count_value = _to_int(count)
    denominator = _to_int(n_group)
    if (
        count_value is None
        or denominator is None
        or count_value < 0
        or denominator <= 0
        or count_value > denominator
    ):
        return None
    return float(count_value) * 100.0 / float(denominator)


def assess_percent_compatibility(
    *,
    count: object,
    denominator: object,
    reported_percent: object,
    reported_decimals: object,
    denominator_role: str,
    weighting: str,
    rounding_convention: str,
) -> str:
    """Compare a count-derived percentage under explicit denominator and rounding rules."""

    count_value = _to_int(count)
    denominator_value = _to_int(denominator)
    decimals = _to_int(reported_decimals)
    try:
        reported = Decimal(str(reported_percent))
    except (InvalidOperation, ValueError):
        return "input_error"
    if (
        count_value is None
        or denominator_value is None
        or decimals is None
        or not reported.is_finite()
        or decimals < 0
    ):
        return "input_error"
    if count_value < 0 or denominator_value <= 0 or count_value > denominator_value:
        return "source_data_contradiction"
    if denominator_role not in {"randomized", "observed_at_timepoint", "analyzed", "other"}:
        return "indeterminate"
    if weighting != "unweighted":
        return "indeterminate"
    rounding_modes = {
        "nearest_half_up": ROUND_HALF_UP,
        "nearest_half_even": ROUND_HALF_EVEN,
        "truncate": ROUND_DOWN,
    }
    if rounding_convention not in rounding_modes:
        return "indeterminate"
    quantum = Decimal(1).scaleb(-decimals)
    implied = (Decimal(count_value) * Decimal(100) / Decimal(denominator_value)).quantize(
        quantum, rounding=rounding_modes[rounding_convention]
    )
    return "compatible" if implied == reported else "incompatible"


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

    categorical = table1_long[table1_long["var_type"] == "categorical_count_percent"].copy()
    for column, default in (
        ("raw_value", ""),
        ("raw_count", ""),
        ("reported_p_raw", ""),
        ("reported_p_comparator", ""),
        ("source_page", pd.NA),
        ("source_locator", ""),
    ):
        if column not in categorical:
            categorical[column] = default
    categorical = categorical.rename(columns={"value": "count", "percent": "reported_percent"})
    categorical["computed_percent"] = categorical.apply(
        lambda row: compute_percent_from_count(row["count"], row["n_group"]),
        axis=1,
    )
    categorical["abs_percent_delta"] = (
        categorical["reported_percent"] - categorical["computed_percent"]
    ).abs()
    categorical["legacy_abs_percent_delta"] = categorical["abs_percent_delta"]
    categorical["legacy_flag_percent_delta_0_2"] = categorical["abs_percent_delta"] >= 0.2
    if "reported_percent_raw" not in categorical:
        categorical["reported_percent_raw"] = categorical["reported_percent"].map(
            lambda value: "" if pd.isna(value) else str(value)
        )
    if "reported_percent_decimals" not in categorical:
        categorical["reported_percent_decimals"] = categorical["reported_percent_raw"].map(
            _digits_from_str
        )
    for column, default in (
        ("denominator_role", "unknown"),
        ("weighting", "unknown"),
        ("rounding_convention", "unknown"),
    ):
        if column not in categorical:
            categorical[column] = default
    categorical["compatibility_status"] = categorical.apply(
        lambda row: assess_percent_compatibility(
            count=row["count"],
            denominator=row["n_group"],
            reported_percent=row["reported_percent_raw"],
            reported_decimals=row["reported_percent_decimals"],
            denominator_role=row["denominator_role"],
            weighting=row["weighting"],
            rounding_convention=row["rounding_convention"],
        ),
        axis=1,
    )
    categorical["input_status"] = categorical.apply(
        lambda row: _count_input_status(row["count"], row["n_group"]), axis=1
    )
    return categorical[
        [
            "trial_id",
            "variable",
            "level",
            "group",
            "source_page",
            "source_locator",
            "raw_value",
            "raw_count",
            "n_group",
            "count",
            "reported_percent",
            "computed_percent",
            "abs_percent_delta",
            "legacy_abs_percent_delta",
            "legacy_flag_percent_delta_0_2",
            "reported_percent_raw",
            "reported_percent_decimals",
            "denominator_role",
            "weighting",
            "rounding_convention",
            "compatibility_status",
            "input_status",
            "reported_p",
            "reported_p_raw",
            "reported_p_comparator",
            "decimals",
        ]
    ]


def _count_input_status(count: object, denominator: object) -> str:
    count_value = _to_int(count)
    denominator_value = _to_int(denominator)
    if count_value is None or denominator_value is None:
        return "input_error"
    if count_value < 0 or denominator_value <= 0 or count_value > denominator_value:
        return "source_data_contradiction"
    return "ok"


def build_scrutiny_input(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Create a lightweight scrutiny-oriented input table."""

    required = {"trial_id", "variable", "group", "n_group", "value", "decimals", "var_type"}
    missing = required.difference(table1_long.columns)
    if missing:
        raise ValueError(f"Missing required columns for scrutiny input: {sorted(missing)}")

    continuous = table1_long[table1_long["var_type"] == "continuous_median_range"].copy()
    continuous["item_label"] = continuous["variable"] + " [" + continuous["group"] + "]"
    continuous = continuous.rename(columns={"n_group": "n", "value": "x"})
    if "raw_statistic_value" in continuous:
        continuous["x"] = continuous["raw_statistic_value"].astype("string")
    else:
        continuous["x"] = pd.to_numeric(continuous["x"], errors="coerce")
    continuous["n"] = pd.to_numeric(continuous["n"], errors="coerce").astype("Int64")
    if "reported_decimals" in continuous:
        continuous["decimals"] = pd.to_numeric(
            continuous["reported_decimals"], errors="coerce"
        ).astype("Int64")
    else:
        continuous["decimals"] = (
            pd.to_numeric(continuous["decimals"], errors="coerce").fillna(0).astype(int)
        )
    continuous["statistic_kind"] = "median"
    continuous["measurement_scale"] = continuous.get("measurement_scale", "unknown")
    continuous["raw_or_adjusted"] = continuous.get("raw_or_adjusted", "unknown")
    continuous["weighting"] = continuous.get("weighting", "unknown")
    continuous["analysis_n"] = continuous.get("analysis_n", pd.NA)
    continuous["imputation_status"] = continuous.get("imputation_status", "unknown")
    continuous["transformation_status"] = continuous.get("transformation_status", "unknown")
    continuous["granularity_transformation"] = continuous.get("granularity_transformation", "")
    continuous["eligibility_evidence"] = continuous.get("eligibility_evidence", "")
    continuous["raw_value"] = continuous.get("raw_value", "")
    continuous["source_page"] = continuous.get("source_page", pd.NA)
    continuous["source_locator"] = continuous.get("source_locator", "")
    continuous["reported_decimals"] = continuous.get("reported_decimals", continuous["decimals"])
    continuous["reported_p_raw"] = continuous.get("reported_p_raw", "")
    continuous["reported_p_comparator"] = continuous.get("reported_p_comparator", "")
    return continuous[
        [
            "trial_id",
            "item_label",
            "n",
            "x",
            "decimals",
            "raw_value",
            "source_page",
            "source_locator",
            "reported_decimals",
            "reported_p_raw",
            "reported_p_comparator",
            *SUMMARY_METADATA_COLUMNS,
        ]
    ]


def build_statcheck_stub(table1_long: pd.DataFrame) -> pd.DataFrame:
    """Create a statcheck-style placeholder input from reported p-values."""

    required = {"trial_id", "variable", "reported_p"}
    missing = required.difference(table1_long.columns)
    if missing:
        raise ValueError(f"Missing required columns for statcheck input: {sorted(missing)}")

    columns = ["trial_id", "variable", "reported_p"]
    columns.extend(
        column for column in ("reported_p_raw", "reported_p_comparator") if column in table1_long
    )
    pvals = table1_long[columns].dropna(subset=["reported_p"]).copy()
    pvals = pvals.drop_duplicates()
    pvals["reported_p"] = pd.to_numeric(pvals["reported_p"], errors="coerce")
    pvals["input_status"] = pvals["reported_p"].map(
        lambda value: "source_value_out_of_range" if value < 0 or value > 1 else "ok"
    )
    if "reported_p_raw" not in pvals:
        pvals["reported_p_raw"] = pvals["reported_p"].map(str)
    if "reported_p_comparator" not in pvals:
        pvals["reported_p_comparator"] = "="
    return pvals.reset_index(drop=True)


def _to_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    numeric = _to_float(value)
    if numeric is None or not math.isfinite(numeric):
        return None
    if not numeric.is_integer():
        return None
    return int(numeric)


def _digits_from_str(value: str) -> int | None:
    if not isinstance(value, str):
        return None
    if not re.fullmatch(r"[+-]?\d+(?:\.\d*)?", value.strip()):
        return None
    if "." not in value:
        return 0
    return len(value.strip().split(".", maxsplit=1)[1])


def _format_numeric_string(value: object, digits: object) -> str:
    if value is None or pd.isna(value):
        return ""
    raw = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d*)?", raw):
        return ""
    declared_digits = _to_int(digits)
    observed_digits = _digits_from_str(raw)
    if declared_digits is not None and declared_digits != observed_digits:
        return ""
    return raw


def _parse_item_label(item_label: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\[(.*?)\]\s*$", str(item_label))
    if not match:
        return str(item_label), "unknown_group"
    return match.group(1).strip(), match.group(2).strip()


def _source_unit(variable: str, level: str, group: str) -> str:
    if level and level != "all":
        return f"{variable} / {level} [{group}]"
    return f"{variable} [{group}]"


def _metadata_value(row: pd.Series, column: str) -> str:
    value = row.get(column, "unknown")
    if pd.isna(value):
        return "unknown"
    text = str(value).strip().lower()
    return text or "unknown"


def _eligibility_reasons(
    *,
    x_str: str,
    sd_str: str,
    digits_x: int | None,
    n_value: int | None,
    digits_sd: int | None,
    metadata: dict[str, str],
) -> dict[str, str]:
    """Return method-specific reasons, failing closed when semantics are unknown."""

    base_reason = ""
    if not x_str or n_value is None or n_value <= 0:
        base_reason = "missing_x_or_valid_n"
    elif digits_x is None or digits_x != _digits_from_str(x_str):
        base_reason = "x_precision_unknown_or_inconsistent"
    elif metadata["statistic_kind"] != "arithmetic_mean":
        base_reason = "statistic_not_arithmetic_mean"
    elif metadata["measurement_scale"] not in {"integer_valued", "bernoulli"}:
        base_reason = "measurement_scale_not_documented_integer"
    elif metadata["raw_or_adjusted"] != "raw":
        base_reason = "summary_not_documented_raw"
    elif metadata["weighting"] != "unweighted":
        base_reason = "weighting_not_documented_unweighted"
    elif metadata["analysis_n"] == "unknown" or not metadata["analysis_n"].isdigit():
        base_reason = "analysis_n_unknown_or_invalid"
    elif int(metadata["analysis_n"]) != n_value:
        base_reason = "analysis_n_mismatch"
    elif metadata["eligibility_evidence"] in {"", "unknown"}:
        base_reason = "eligibility_evidence_missing"
    elif metadata["imputation_status"] != "not_imputed":
        base_reason = "imputation_status_not_documented_unimputed"
    elif metadata["transformation_status"] == "unknown":
        base_reason = "transformation_status_unknown"
    elif metadata["transformation_status"] not in {"none", "granularity_adjustment"}:
        base_reason = "summary_transformation_unsupported"
    elif metadata["transformation_status"] == "granularity_adjustment" and metadata[
        "granularity_transformation"
    ] in {"", "unknown"}:
        base_reason = "granularity_transformation_undocumented"

    grim_reason = base_reason
    grimmer_reason = base_reason
    debit_reason = base_reason
    if metadata["measurement_scale"] != "bernoulli":
        debit_reason = "measurement_scale_not_bernoulli"
    if not grim_reason and (
        not sd_str or digits_sd is None or digits_sd != _digits_from_str(sd_str)
    ):
        grimmer_reason = "missing_sd_or_precision"
        debit_reason = "missing_sd_or_precision"
    return {
        "exclude_reason_grim": grim_reason,
        "exclude_reason_grimmer": grimmer_reason,
        "exclude_reason_debit": debit_reason,
    }


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
            metadata = {column: _metadata_value(row, column) for column in SUMMARY_METADATA_COLUMNS}
            metadata["statistic_kind"] = "median"
            reasons = _eligibility_reasons(
                x_str=x_str,
                sd_str=sd_str,
                digits_x=digits_x,
                n_value=n_value,
                digits_sd=digits_sd,
                metadata=metadata,
            )
            eligible_grim = not reasons["exclude_reason_grim"]
            eligible_grimmer = not reasons["exclude_reason_grimmer"]
            eligible_debit = not reasons["exclude_reason_debit"]
            rows.append(
                {
                    "case_id": "",
                    "trial_id": str(row["trial_id"]),
                    "source_pdf": source_pdf,
                    "source_table": "table1_continuous_median_range",
                    "source_page": _to_int(row.get("source_page")),
                    "source_locator": str(row.get("source_locator", "")),
                    "raw_value": str(row.get("raw_value", "")),
                    "reported_decimals": _to_int(row.get("reported_decimals"))
                    if not pd.isna(row.get("reported_decimals", pd.NA))
                    else digits_x,
                    "reported_p_raw": str(row.get("reported_p_raw", "")),
                    "reported_p_comparator": str(row.get("reported_p_comparator", "")),
                    "variable": variable,
                    "level": "all",
                    "group": group or "unknown_group",
                    "n": n_value,
                    "x_str": x_str,
                    "sd_str": sd_str,
                    "digits_x": digits_x,
                    "digits_sd": digits_sd,
                    **metadata,
                    "method_revision": NUMERIC_METHOD_REVISION,
                    "is_binary": metadata["measurement_scale"] == "bernoulli",
                    "eligible_grim": eligible_grim,
                    **reasons,
                    "eligible_grimmer": eligible_grimmer,
                    "eligible_debit": eligible_debit,
                    "exclude_reason": next((reason for reason in reasons.values() if reason), ""),
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
            if "digits_x" not in row.index and x_str:
                digits_x = _digits_from_str(x_str)
            if "digits_sd" not in row.index and sd_str:
                digits_sd = _digits_from_str(sd_str)
            n_value = _to_int(row["n"])
            metadata = {column: _metadata_value(row, column) for column in SUMMARY_METADATA_COLUMNS}
            metadata["analysis_n"] = str(_to_int(row.get("analysis_n")) or "unknown")
            reasons = _eligibility_reasons(
                x_str=x_str,
                sd_str=sd_str,
                digits_x=digits_x,
                n_value=n_value,
                digits_sd=digits_sd,
                metadata=metadata,
            )
            eligible_grim = not reasons["exclude_reason_grim"]
            eligible_grimmer = not reasons["exclude_reason_grimmer"]
            eligible_debit = not reasons["exclude_reason_debit"]
            rows.append(
                {
                    "case_id": "",
                    "trial_id": str(row["trial_id"]),
                    "source_pdf": str(row["source_pdf"]),
                    "source_table": str(row["source_table"]),
                    "source_page": _to_int(row["source_page"]),
                    "source_locator": str(row.get("source_locator", "")),
                    "raw_value": str(row.get("raw_value", "")),
                    "reported_decimals": _to_int(row.get("reported_decimals"))
                    if not pd.isna(row.get("reported_decimals", pd.NA))
                    else digits_x,
                    "reported_p_raw": str(row.get("reported_p_raw", "")),
                    "reported_p_comparator": str(row.get("reported_p_comparator", "")),
                    "variable": str(row["variable"]),
                    "level": str(row["level"]) if not pd.isna(row["level"]) else "all",
                    "group": str(row["group"]),
                    "n": n_value,
                    "x_str": x_str,
                    "sd_str": sd_str,
                    "digits_x": digits_x,
                    "digits_sd": digits_sd,
                    **metadata,
                    "method_revision": NUMERIC_METHOD_REVISION,
                    "is_binary": metadata["measurement_scale"] == "bernoulli",
                    "eligible_grim": eligible_grim,
                    **reasons,
                    "eligible_grimmer": eligible_grimmer,
                    "eligible_debit": eligible_debit,
                    "exclude_reason": next((reason for reason in reasons.values() if reason), ""),
                }
            )

    scrutiny_cases = pd.DataFrame(rows, columns=SCRUTINY_CASE_COLUMNS)
    if scrutiny_cases.empty:
        return pd.DataFrame(columns=SCRUTINY_CASE_COLUMNS)

    scrutiny_cases = scrutiny_cases.reset_index(drop=True)
    scrutiny_cases["case_id"] = [f"case_{index + 1:04d}" for index in range(len(scrutiny_cases))]
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
        "source_locator",
        "raw_value",
        "reported_decimals",
        "reported_p_raw",
        "reported_p_comparator",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "digits_x",
        *SUMMARY_METADATA_COLUMNS,
        "method_revision",
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
        "source_locator",
        "raw_value",
        "reported_decimals",
        "reported_p_raw",
        "reported_p_comparator",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "sd",
        "digits_x",
        "digits_sd",
        *SUMMARY_METADATA_COLUMNS,
        "method_revision",
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
        "source_locator",
        "raw_value",
        "reported_decimals",
        "reported_p_raw",
        "reported_p_comparator",
        "variable",
        "level",
        "group",
        "n",
        "x",
        "sd",
        "digits_x",
        "digits_sd",
        *SUMMARY_METADATA_COLUMNS,
        "method_revision",
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
        "n_rounding_flags": int((numeric_table["compatibility_status"] == "incompatible").sum())
        if "compatibility_status" in numeric_table
        else 0,
        "median_abs_percent_delta": float(numeric_table["abs_percent_delta"].median()),
        "max_abs_percent_delta": float(numeric_table["abs_percent_delta"].max()),
        "n_reported_p": int(numeric_table["reported_p"].notna().sum()),
    }
