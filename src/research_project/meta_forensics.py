"""Evidence coverage and isolated legacy aggregation for forensic categories."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import pandas as pd

META_CATEGORIES = ("randomization", "numeric", "registration", "visual", "transparency")
LEGACY_SCHEMA_VERSION = "legacy_composite_v1"


def build_evidence_coverage(
    raw_summaries: pd.DataFrame,
    category_status: pd.DataFrame | None = None,
    requested_categories: Sequence[str] = META_CATEGORIES,
) -> pd.DataFrame:
    """Summarize category-report coverage without imputing values or scoring."""
    required = {"category", "metric", "value"}
    missing = required - set(raw_summaries.columns)
    if missing:
        raise ValueError(f"Missing category-summary columns: {sorted(missing)}")

    status_by_category: dict[str, dict[str, object]] = {}
    if category_status is not None and not category_status.empty:
        for row in category_status.to_dict(orient="records"):
            status_by_category[str(row["category"])] = row

    rows: list[dict[str, object]] = []
    metadata_metrics = {"study_id", "trial_id", "source_file", "source_pdf"}
    for category in requested_categories:
        subset = raw_summaries[raw_summaries["category"].astype(str) == category]
        report_exists = bool(subset.shape[0])
        status = status_by_category.get(category, {})
        category_requested = status.get("requested", True)
        category_requested = bool(category_requested) if pd.notna(category_requested) else False
        available = status.get("report_available", report_exists)
        report_exists = bool(available) if pd.notna(available) else False
        metric_rows = subset[~subset["metric"].astype(str).isin(metadata_metrics)]
        values = metric_rows["value"]
        n_assessed = int(values.notna().sum())
        evaluation_units_value = status.get("n_evaluation_units", 0)
        n_evaluation_units = (
            int(evaluation_units_value)
            if pd.notna(evaluation_units_value) and str(evaluation_units_value).strip()
            else 0
        )
        source_files = sorted(
            str(value)
            for value in subset.get("source_file", pd.Series(dtype=str)).dropna().unique()
        )
        source = status.get("source_file")
        if source is not None and pd.notna(source) and str(source) and source not in source_files:
            source_files.append(str(source))
        rows.append(
            {
                "schema_version": "evidence_coverage_v2",
                "category": category,
                "requested": category_requested,
                "assessed": category_requested and n_evaluation_units > 0,
                "unavailable": category_requested and n_evaluation_units == 0,
                "failed": status.get("failed", pd.NA),
                "unsupported": status.get("unsupported", pd.NA),
                "report_available": report_exists,
                "n_metrics_assessed": n_assessed,
                "n_metrics_missing": int(len(values) - n_assessed),
                "n_evaluation_units": n_evaluation_units,
                "source_file": ";".join(source_files),
            }
        )
    return pd.DataFrame(rows)


def build_legacy_category_scores(
    summary_tables: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Reproduce the retired composite contribution formula for audit only."""
    rows: list[dict[str, object]] = []
    metric_specs = {
        "randomization": (
            "fisher_recalc",
            lambda value: 1.0 - _bounded(value if not math.isnan(value) else 0.5),
        ),
        "numeric": (
            "median_abs_percent_delta",
            lambda value: _bounded((value if not math.isnan(value) else 0.0) / 2.0),
        ),
        "registration": (
            "mismatch_rate",
            lambda value: _bounded(value if not math.isnan(value) else 0.0),
        ),
        "visual": (
            "near_duplicate_rate",
            lambda value: _bounded(value if not math.isnan(value) else 0.0),
        ),
        "transparency": (
            "transparency_evidence_burden",
            lambda value: _bounded(value if not math.isnan(value) else 0.0),
        ),
    }
    for category, (metric, transform) in metric_specs.items():
        table = summary_tables.get(category)
        if table is None or table.empty:
            continue
        value = float(table.iloc[0].get(metric, math.nan))
        rows.append(
            {
                "category": category,
                "metric": metric,
                "raw_value": value,
                "anomaly_score": transform(value),
            }
        )
    return pd.DataFrame(rows)


def compute_legacy_overall_meta_score(
    category_scores: pd.DataFrame,
    category_weights: Mapping[str, float] | None = None,
) -> dict[str, float | str]:
    """Reproduce the retired weighted tier; call only in explicit legacy mode."""
    if category_scores.empty:
        return {
            "overall_score": math.nan,
            "risk_tier": "insufficient_data",
            "evidence_burden_score": math.nan,
            "review_priority": "insufficient_data",
        }
    weights = category_weights or {
        "randomization": 1.0,
        "numeric": 1.0,
        "registration": 0.8,
        "visual": 0.8,
        "transparency": 0.6,
    }
    valid = [
        (float(row["anomaly_score"]), float(weights.get(str(row["category"]), 1.0)))
        for _, row in category_scores.iterrows()
        if not math.isnan(float(row["anomaly_score"]))
    ]
    if not valid:
        tier = "insufficient_data"
        overall = math.nan
    else:
        denominator = sum(weight for _, weight in valid)
        overall = (
            sum(score * weight for score, weight in valid) / denominator
            if denominator > 0
            else math.nan
        )
        if math.isnan(overall):
            tier = "insufficient_data"
        elif overall < 0.20:
            tier = "low"
        elif overall < 0.45:
            tier = "moderate"
        else:
            tier = "high"
    return {
        "overall_score": overall,
        "risk_tier": tier,
        "evidence_burden_score": overall,
        "review_priority": tier,
    }


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
