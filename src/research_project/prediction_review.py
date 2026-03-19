"""Helpers for nonrandomized manuscript prediction-model review."""

from __future__ import annotations

import math
from itertools import zip_longest
from pathlib import Path

import pandas as pd

SUMMARY_TABLE_COLUMNS = [
    "study_id",
    "source_table",
    "source_page",
    "variable",
    "level",
    "measure_type",
    "group_label",
    "n_group",
    "count",
    "percent",
    "percent_digits",
    "mean",
    "sd",
    "median",
    "q1",
    "q3",
    "digits_x",
    "digits_sd",
    "p_reported",
]

TABLE3_COLUMNS = [
    "study_id",
    "source_table",
    "source_page",
    "cohort",
    "n_total",
    "n_events",
    "c_statistic",
    "c_stat_low",
    "c_stat_high",
    "sensitivity",
    "sensitivity_low",
    "sensitivity_high",
    "specificity",
    "specificity_low",
    "specificity_high",
    "ppv",
    "ppv_low",
    "ppv_high",
    "npv",
    "npv_low",
    "npv_high",
]

TABLEE2_COLUMNS = [
    "study_id",
    "source_table",
    "source_page",
    "group_id",
    "probability",
    "observed_outcomes",
    "expected_outcomes",
    "total_individuals",
]

FLOW_COLUMNS = [
    "study_id",
    "source_figure",
    "source_page",
    "stage",
    "count",
]

PAGE_TEXT_COLUMNS = ["study_id", "page_number", "page_text"]

_SUMMARY_MEASURE_TYPES = {
    "categorical_count_percent",
    "continuous_mean_sd",
    "continuous_median_iqr",
}


def extract_pdf_page_texts(pdf_path: Path) -> list[str]:
    """Extract page-level text from a PDF."""

    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing report PDF: {pdf_path}")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Missing PDF dependency for manuscript review extraction. "
            "Install with: python3 -m pip install --user pypdf"
        ) from exc

    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def build_page_text_frame(study_id: str, page_texts: list[str]) -> pd.DataFrame:
    """Create a page-text artifact frame."""

    rows = [
        {"study_id": study_id, "page_number": index + 1, "page_text": text}
        for index, text in enumerate(page_texts)
    ]
    return pd.DataFrame(rows, columns=PAGE_TEXT_COLUMNS)


def scaffold_summary_table(study_id: str, source_table: str, source_page: int) -> pd.DataFrame:
    """Create an empty summary-table scaffold."""

    return (
        pd.DataFrame(columns=SUMMARY_TABLE_COLUMNS)
        .assign(
            study_id=study_id,
            source_table=source_table,
            source_page=source_page,
        )
        .iloc[0:0]
    )


def scaffold_table3(study_id: str, source_page: int) -> pd.DataFrame:
    """Create an empty Table 3 scaffold."""

    return (
        pd.DataFrame(columns=TABLE3_COLUMNS)
        .assign(
            study_id=study_id,
            source_table="table3_discrimination_metrics",
            source_page=source_page,
        )
        .iloc[0:0]
    )


def scaffold_tablee2(study_id: str, source_page: int) -> pd.DataFrame:
    """Create an empty Table E2 scaffold."""

    return (
        pd.DataFrame(columns=TABLEE2_COLUMNS)
        .assign(
            study_id=study_id,
            source_table="tablee2_calibration_deciles",
            source_page=source_page,
        )
        .iloc[0:0]
    )


def scaffold_flow_counts(study_id: str, source_page: int) -> pd.DataFrame:
    """Create an empty flow-count scaffold."""

    return (
        pd.DataFrame(columns=FLOW_COLUMNS)
        .assign(
            study_id=study_id,
            source_figure="figure1_flow",
            source_page=source_page,
        )
        .iloc[0:0]
    )


def _require_columns(frame: pd.DataFrame, required: list[str], context: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns for {context}: {missing}")


def _normalize_text_column(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()


def _round_half_up(value: float) -> int:
    return int(math.floor(float(value) + 0.5))


def _parse_digits(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip()
    if "." not in text:
        return 0
    return len(text.split(".", maxsplit=1)[1].rstrip("0"))


def _format_numeric(value: object, digits: object) -> str:
    if value is None or pd.isna(value):
        return ""
    digits_int = int(digits) if digits is not None and not pd.isna(digits) else 0
    return f"{float(value):.{max(digits_int, 0)}f}"


def validate_summary_table(frame: pd.DataFrame, context: str) -> pd.DataFrame:
    """Validate one long-format summary table transcription."""

    _require_columns(frame, SUMMARY_TABLE_COLUMNS, context)
    normalized = frame[SUMMARY_TABLE_COLUMNS].copy()
    _normalize_text_column(
        normalized,
        ["study_id", "source_table", "variable", "level", "measure_type", "group_label"],
    )

    numeric_columns = [
        "source_page",
        "n_group",
        "count",
        "percent",
        "percent_digits",
        "mean",
        "sd",
        "median",
        "q1",
        "q3",
        "digits_x",
        "digits_sd",
        "p_reported",
    ]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if normalized["study_id"].eq("").any():
        raise ValueError(f"Empty `study_id` in {context}")
    if normalized["variable"].eq("").any():
        raise ValueError(f"Empty `variable` in {context}")
    if normalized["group_label"].eq("").any():
        raise ValueError(f"Empty `group_label` in {context}")

    invalid_types = normalized.loc[~normalized["measure_type"].isin(_SUMMARY_MEASURE_TYPES)]
    if not invalid_types.empty:
        bad = invalid_types.iloc[0]
        raise ValueError(
            f"Invalid `measure_type` in {context} for `{bad['variable']}`: {bad['measure_type']!r}"
        )

    for row in normalized.itertuples(index=False):
        if pd.isna(row.n_group) or int(row.n_group) <= 0:
            raise ValueError(
                f"Invalid `n_group` in {context} for `{row.variable}` / `{row.group_label}`"
            )
        if row.measure_type == "categorical_count_percent":
            if pd.isna(row.count) or pd.isna(row.percent):
                raise ValueError(
                    f"Missing count/percent in {context} for `{row.variable}` / `{row.group_label}`"
                )
        elif row.measure_type == "continuous_mean_sd":
            if pd.isna(row.mean) or pd.isna(row.sd):
                raise ValueError(
                    f"Missing mean/sd in {context} for `{row.variable}` / `{row.group_label}`"
                )
        elif row.measure_type == "continuous_median_iqr":
            if pd.isna(row.median) or pd.isna(row.q1) or pd.isna(row.q3):
                raise ValueError(
                    f"Missing median/IQR in {context} for `{row.variable}` / `{row.group_label}`"
                )

    return normalized


def validate_table3(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate Table 3 discrimination metrics."""

    _require_columns(frame, TABLE3_COLUMNS, "table3")
    normalized = frame[TABLE3_COLUMNS].copy()
    _normalize_text_column(normalized, ["study_id", "source_table", "cohort"])

    numeric_columns = [
        column for column in TABLE3_COLUMNS if column not in {"study_id", "source_table", "cohort"}
    ]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if normalized["cohort"].eq("").any():
        raise ValueError("Empty `cohort` in table3")
    return normalized


def validate_tablee2(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate Table E2 calibration deciles."""

    _require_columns(frame, TABLEE2_COLUMNS, "tablee2")
    normalized = frame[TABLEE2_COLUMNS].copy()
    _normalize_text_column(normalized, ["study_id", "source_table"])
    for column in [
        "source_page",
        "group_id",
        "probability",
        "observed_outcomes",
        "expected_outcomes",
        "total_individuals",
    ]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if normalized["group_id"].isna().any():
        raise ValueError("Missing `group_id` in tablee2")
    if normalized["group_id"].duplicated().any():
        raise ValueError("Duplicate `group_id` values in tablee2")
    return normalized.sort_values("group_id", kind="stable").reset_index(drop=True)


def validate_flow_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate flow-count transcription rows."""

    _require_columns(frame, FLOW_COLUMNS, "flow_counts")
    normalized = frame[FLOW_COLUMNS].copy()
    _normalize_text_column(normalized, ["study_id", "source_figure", "stage"])
    for column in ["source_page", "count"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if normalized["stage"].eq("").any():
        raise ValueError("Empty `stage` in flow_counts")
    if normalized["stage"].duplicated().any():
        raise ValueError("Duplicate `stage` rows in flow_counts")
    if normalized["count"].isna().any():
        raise ValueError("Missing `count` in flow_counts")
    return normalized


def build_numeric_table_from_summary_rows(summary_rows: pd.DataFrame) -> pd.DataFrame:
    """Build numeric consistency inputs from long-format summary rows."""

    numeric_rows = summary_rows[summary_rows["measure_type"] == "categorical_count_percent"].copy()
    if numeric_rows.empty:
        return pd.DataFrame(
            columns=[
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
        )

    numeric_rows["computed_percent"] = numeric_rows["count"] / numeric_rows["n_group"] * 100.0
    numeric_rows["abs_percent_delta"] = (
        numeric_rows["percent"] - numeric_rows["computed_percent"]
    ).abs()
    numeric_rows["flag_percent_delta_0_2"] = numeric_rows["abs_percent_delta"] >= 0.2
    numeric_rows["level"] = numeric_rows["level"].replace("", "all")

    return numeric_rows.rename(
        columns={
            "study_id": "trial_id",
            "group_label": "group",
            "percent": "reported_percent",
            "percent_digits": "decimals",
        }
    )[
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
            "p_reported",
            "decimals",
        ]
    ].rename(columns={"p_reported": "reported_p"})


def build_statcheck_stub_from_summary_rows(summary_rows: pd.DataFrame) -> pd.DataFrame:
    """Create a simple statcheck metadata stub from reported p-values."""

    stub = summary_rows[["study_id", "variable", "p_reported"]].dropna().drop_duplicates().copy()
    if stub.empty:
        return pd.DataFrame(columns=["trial_id", "variable", "reported_p"])
    return stub.rename(columns={"study_id": "trial_id", "p_reported": "reported_p"}).reset_index(
        drop=True
    )


def build_numeric_summary_long_from_summary_rows(
    summary_rows: pd.DataFrame, *, source_pdf: str
) -> pd.DataFrame:
    """Create mean/SD scrutiny candidates from long-format summary rows."""

    subset = summary_rows[summary_rows["measure_type"] == "continuous_mean_sd"].copy()
    if subset.empty:
        return pd.DataFrame(
            columns=[
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
            ]
        )

    subset["digits_x"] = subset["digits_x"].fillna(0).astype(int)
    subset["digits_sd"] = subset["digits_sd"].fillna(0).astype(int)
    subset["x_str"] = [
        _format_numeric(value, digits)
        for value, digits in zip_longest(subset["mean"], subset["digits_x"], fillvalue=None)
    ]
    subset["sd_str"] = [
        _format_numeric(value, digits)
        for value, digits in zip_longest(subset["sd"], subset["digits_sd"], fillvalue=None)
    ]
    subset["level"] = subset["level"].replace("", "all")

    return subset.rename(
        columns={
            "study_id": "trial_id",
            "group_label": "group",
            "n_group": "n",
        }
    )[
        [
            "trial_id",
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
        ]
    ].assign(source_pdf=source_pdf)[
        [
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
        ]
    ]


def search_confusion_matrices(
    *,
    n_total: int,
    n_events: int,
    sensitivity: float,
    specificity: float,
    ppv: float,
    npv: float,
) -> pd.DataFrame:
    """Search integer confusion matrices compatible with rounded summary metrics."""

    nonevents = n_total - n_events
    rows: list[dict[str, float | int | bool]] = []
    for true_positive in range(n_events + 1):
        false_negative = n_events - true_positive
        for true_negative in range(nonevents + 1):
            false_positive = nonevents - true_negative
            if true_positive + false_positive == 0:
                continue
            if true_negative + false_negative == 0:
                continue

            sens_calc = true_positive / n_events * 100.0
            spec_calc = true_negative / nonevents * 100.0
            ppv_calc = true_positive / (true_positive + false_positive) * 100.0
            npv_calc = true_negative / (true_negative + false_negative) * 100.0
            exact_match = (
                _round_half_up(sens_calc) == _round_half_up(sensitivity)
                and _round_half_up(spec_calc) == _round_half_up(specificity)
                and _round_half_up(ppv_calc) == _round_half_up(ppv)
                and _round_half_up(npv_calc) == _round_half_up(npv)
            )
            rows.append(
                {
                    "tp": true_positive,
                    "fp": false_positive,
                    "tn": true_negative,
                    "fn": false_negative,
                    "sensitivity_calc": sens_calc,
                    "specificity_calc": spec_calc,
                    "ppv_calc": ppv_calc,
                    "npv_calc": npv_calc,
                    "sensitivity_abs_delta": abs(sens_calc - sensitivity),
                    "specificity_abs_delta": abs(spec_calc - specificity),
                    "ppv_abs_delta": abs(ppv_calc - ppv),
                    "npv_abs_delta": abs(npv_calc - npv),
                    "total_abs_delta": abs(sens_calc - sensitivity)
                    + abs(spec_calc - specificity)
                    + abs(ppv_calc - ppv)
                    + abs(npv_calc - npv),
                    "exact_rounded_match": exact_match,
                }
            )
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["exact_rounded_match", "total_abs_delta", "tp", "tn"],
        ascending=[False, True, False, False],
        kind="stable",
    ).reset_index(drop=True)


def summarize_calibration_deciles(
    deciles: pd.DataFrame, *, expected_n_total: int, expected_n_events: int
) -> pd.DataFrame:
    """Summarize displayed calibration-decile totals."""

    total_individuals_sum = int(deciles["total_individuals"].sum())
    observed_outcomes_sum = int(deciles["observed_outcomes"].sum())
    expected_outcomes_sum = float(deciles["expected_outcomes"].sum())

    return pd.DataFrame(
        [
            {
                "n_groups": int(len(deciles)),
                "total_individuals_sum": total_individuals_sum,
                "expected_total_individuals": int(expected_n_total),
                "total_individuals_delta": total_individuals_sum - int(expected_n_total),
                "observed_outcomes_sum": observed_outcomes_sum,
                "expected_observed_outcomes": int(expected_n_events),
                "observed_outcomes_delta": observed_outcomes_sum - int(expected_n_events),
                "displayed_expected_outcomes_sum": expected_outcomes_sum,
                "displayed_expected_minus_observed": expected_outcomes_sum
                - float(observed_outcomes_sum),
            }
        ]
    )


def reconcile_flow_counts(flow_counts: pd.DataFrame) -> pd.DataFrame:
    """Run arithmetic checks across the manuscript flow diagram counts."""

    counts = {row["stage"]: int(row["count"]) for _, row in flow_counts.iterrows()}
    excluded_reason_total = sum(
        count
        for stage, count in counts.items()
        if stage.startswith("excluded_") and stage != "excluded_from_analysis"
    )

    def get(stage: str) -> int | None:
        return counts.get(stage)

    def make_row(
        check_name: str,
        left: int | None,
        right: int | None,
        note: str,
    ) -> dict[str, object]:
        if left is None or right is None:
            return {
                "check_name": check_name,
                "left_value": left,
                "right_value": right,
                "delta": None,
                "pass_flag": False,
                "note": f"Missing stage count(s): {note}",
            }
        delta = int(left) - int(right)
        return {
            "check_name": check_name,
            "left_value": int(left),
            "right_value": int(right),
            "delta": delta,
            "pass_flag": delta == 0,
            "note": note,
        }

    rows = [
        make_row(
            "assessed_equals_did_not_meet_plus_eligible",
            get("assessed_for_eligibility"),
            (get("did_not_meet_eligibility_criteria") or 0) + (get("eligible") or 0)
            if get("did_not_meet_eligibility_criteria") is not None and get("eligible") is not None
            else None,
            "assessed = did_not_meet + eligible",
        ),
        make_row(
            "approached_equals_enrolled_plus_declined",
            get("approached"),
            (get("enrolled") or 0) + (get("declined_consent") or 0)
            if get("enrolled") is not None and get("declined_consent") is not None
            else None,
            "approached = enrolled + declined",
        ),
        make_row(
            "enrolled_equals_included_plus_excluded",
            get("enrolled"),
            (get("included_in_analysis") or 0) + (get("excluded_from_analysis") or 0)
            if get("included_in_analysis") is not None and get("excluded_from_analysis") is not None
            else None,
            "enrolled = included + excluded",
        ),
        make_row(
            "excluded_equals_listed_reasons",
            get("excluded_from_analysis"),
            excluded_reason_total if excluded_reason_total > 0 else None,
            "excluded = listed exclusion reasons",
        ),
    ]

    if get("eligible") is not None and get("approached") is not None:
        rows.append(
            {
                "check_name": "eligible_minus_approached_gap",
                "left_value": int(get("eligible")),
                "right_value": int(get("approached")),
                "delta": int(get("eligible")) - int(get("approached")),
                "pass_flag": int(get("eligible")) - int(get("approached")) == 0,
                "note": "eligible - approached (nonzero can reflect undocumented non-approach)",
            }
        )

    return pd.DataFrame(rows)
