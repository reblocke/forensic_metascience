from __future__ import annotations

import pandas as pd
import pytest

from research_project.visual_forensics import (
    empty_plot_digitized_values,
    scaffold_plot_digitization_targets,
    summarize_plot_digitization,
    validate_plot_digitization_targets,
    validate_plot_digitized_values,
)


def test_scaffold_plot_digitization_targets_validates() -> None:
    scaffold = scaffold_plot_digitization_targets("trial_x")
    validated = validate_plot_digitization_targets(scaffold)

    assert len(validated) == 1
    assert bool(validated.iloc[0]["include"]) is True
    assert validated.iloc[0]["x_scale"] == "linear"
    assert validated.iloc[0]["y_scale"] == "linear"


def test_invalid_target_scale_raises() -> None:
    scaffold = scaffold_plot_digitization_targets("trial_x")
    scaffold.loc[0, "x_scale"] = "log"

    with pytest.raises(ValueError, match="Invalid `x_scale`"):
        validate_plot_digitization_targets(scaffold)


def test_validate_plot_digitized_values_and_summary() -> None:
    values = pd.DataFrame(
        [
            {
                "study_id": "trial_x",
                "figure_id": "figure_01",
                "panel_id": "A",
                "series_id": "overall",
                "x_value": "1.5",
                "y_value": "0.82",
                "x_unit": "months",
                "y_unit": "survival_probability",
                "source_image": "data/raw/figures/trial_x/figure_01_panel_a.png",
                "digitizer": "tester",
                "digitized_at": "2026-02-07T10:00:00-0500",
                "extract_confidence": "",
            }
        ]
    )

    validated = validate_plot_digitized_values(values)
    summary = summarize_plot_digitization(validated)

    assert float(validated.iloc[0]["x_value"]) == 1.5
    assert float(validated.iloc[0]["y_value"]) == 0.82
    assert validated.iloc[0]["extract_confidence"] == "medium"
    assert summary["n_digitized_figures"] == 1
    assert summary["n_digitized_series"] == 1
    assert summary["n_digitized_points"] == 1
    assert bool(summary["digitization_ready"]) is True


def test_empty_plot_digitized_values_returns_header_and_false_ready() -> None:
    empty = empty_plot_digitized_values()
    validated = validate_plot_digitized_values(empty)
    summary = summarize_plot_digitization(validated)

    assert validated.empty
    assert summary["n_digitized_points"] == 0
    assert bool(summary["digitization_ready"]) is False


def test_non_numeric_digitized_value_raises() -> None:
    values = pd.DataFrame(
        [
            {
                "study_id": "trial_x",
                "figure_id": "figure_01",
                "panel_id": "A",
                "series_id": "overall",
                "x_value": "not_a_number",
                "y_value": "0.80",
                "x_unit": "months",
                "y_unit": "survival_probability",
                "source_image": "figure.png",
                "digitizer": "tester",
                "digitized_at": "2026-02-07T10:00:00-0500",
                "extract_confidence": "medium",
            }
        ]
    )

    with pytest.raises(ValueError, match="Non-numeric `x_value`"):
        validate_plot_digitized_values(values)
