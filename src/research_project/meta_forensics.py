"""Meta-level aggregation across forensic categories."""

from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "randomization": 1.0,
    "numeric": 1.0,
    "registration": 0.8,
    "visual": 0.8,
    "transparency": 0.6,
}


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def build_category_scores(
    summary_tables: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    """Create normalized anomaly scores from category summary tables."""

    rows: list[dict[str, object]] = []

    if "randomization" in summary_tables and not summary_tables["randomization"].empty:
        randomization = summary_tables["randomization"].iloc[0]
        fisher = float(randomization.get("fisher_recalc", math.nan))
        score = 1.0 - _bounded(fisher if not math.isnan(fisher) else 0.5)
        rows.append(
            {
                "category": "randomization",
                "metric": "fisher_recalc",
                "raw_value": fisher,
                "anomaly_score": score,
            }
        )

    if "numeric" in summary_tables and not summary_tables["numeric"].empty:
        numeric = summary_tables["numeric"].iloc[0]
        delta = float(numeric.get("median_abs_percent_delta", math.nan))
        score = _bounded((delta if not math.isnan(delta) else 0.0) / 2.0)
        rows.append(
            {
                "category": "numeric",
                "metric": "median_abs_percent_delta",
                "raw_value": delta,
                "anomaly_score": score,
            }
        )

    if "registration" in summary_tables and not summary_tables["registration"].empty:
        registration = summary_tables["registration"].iloc[0]
        mismatch_rate = float(registration.get("mismatch_rate", math.nan))
        score = _bounded(mismatch_rate if not math.isnan(mismatch_rate) else 0.0)
        rows.append(
            {
                "category": "registration",
                "metric": "mismatch_rate",
                "raw_value": mismatch_rate,
                "anomaly_score": score,
            }
        )

    if "visual" in summary_tables and not summary_tables["visual"].empty:
        visual = summary_tables["visual"].iloc[0]
        duplicate_rate = float(visual.get("near_duplicate_rate", math.nan))
        score = _bounded(duplicate_rate if not math.isnan(duplicate_rate) else 0.0)
        rows.append(
            {
                "category": "visual",
                "metric": "near_duplicate_rate",
                "raw_value": duplicate_rate,
                "anomaly_score": score,
            }
        )

    if "transparency" in summary_tables and not summary_tables["transparency"].empty:
        transparency = summary_tables["transparency"].iloc[0]
        burden = float(transparency.get("transparency_evidence_burden", math.nan))
        score = _bounded(burden if not math.isnan(burden) else 0.0)
        rows.append(
            {
                "category": "transparency",
                "metric": "transparency_evidence_burden",
                "raw_value": burden,
                "anomaly_score": score,
            }
        )

    return pd.DataFrame(rows)


def compute_overall_meta_score(
    category_scores: pd.DataFrame,
    category_weights: Mapping[str, float] | None = None,
) -> dict[str, float | str]:
    """Compute weighted overall anomaly score and risk tier."""

    if category_scores.empty:
        return {
            "overall_score": math.nan,
            "risk_tier": "insufficient_data",
            "evidence_burden_score": math.nan,
            "review_priority": "insufficient_data",
        }

    weights = category_weights or DEFAULT_CATEGORY_WEIGHTS
    scores = []
    score_weights = []
    for _, row in category_scores.iterrows():
        category = str(row["category"])
        score = float(row["anomaly_score"])
        if math.isnan(score):
            continue
        weight = float(weights.get(category, 1.0))
        scores.append(score)
        score_weights.append(weight)

    if not scores:
        return {
            "overall_score": math.nan,
            "risk_tier": "insufficient_data",
            "evidence_burden_score": math.nan,
            "review_priority": "insufficient_data",
        }

    weighted = sum(scores[index] * score_weights[index] for index in range(len(scores)))
    total_weight = sum(score_weights)
    overall = weighted / total_weight if total_weight > 0 else math.nan

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
