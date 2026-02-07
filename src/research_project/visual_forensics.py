"""Text-driven visual-forensics helpers for figure checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import pandas as pd

PLOT_DIGITIZATION_TARGET_COLUMNS = [
    "study_id",
    "figure_id",
    "panel_id",
    "image_path",
    "plot_type",
    "x_unit",
    "y_unit",
    "x_scale",
    "y_scale",
    "target_series",
    "include",
]

PLOT_DIGITIZED_VALUE_COLUMNS = [
    "study_id",
    "figure_id",
    "panel_id",
    "series_id",
    "x_value",
    "y_value",
    "x_unit",
    "y_unit",
    "source_image",
    "digitizer",
    "digitized_at",
    "extract_confidence",
]

_ALLOWED_SCALE_VALUES = {"linear", "log10", "log2", "ln"}
_TRUE_VALUES = {"true", "1", "yes", "y"}
_FALSE_VALUES = {"false", "0", "no", "n"}


@dataclass(frozen=True)
class CaptionRecord:
    """One figure-caption mention extracted from PDF text."""

    figure_label: str
    figure_number: int | None
    caption: str
    page: int


def normalize_caption(text: str) -> str:
    """Normalize caption text for near-duplicate checks."""

    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    cleaned = re.sub(r"^figure\s*\d+[:.\-]?\s*", "", cleaned)
    return cleaned


def extract_figure_captions(page_texts: list[str]) -> list[CaptionRecord]:
    """Extract candidate figure captions from page-level text."""

    records: list[CaptionRecord] = []
    pattern = re.compile(r"(Figure\s*\d+[A-Za-z]?)[:.\-]?\s*([^\n]{8,200})", flags=re.IGNORECASE)

    for page_index, page_text in enumerate(page_texts, start=1):
        for match in pattern.finditer(page_text):
            label = match.group(1).strip()
            number_match = re.search(r"(\d+)", label)
            figure_number = int(number_match.group(1)) if number_match else None
            caption = match.group(2).strip()
            records.append(
                CaptionRecord(
                    figure_label=label,
                    figure_number=figure_number,
                    caption=caption,
                    page=page_index,
                )
            )
    return records


def build_visual_checks(page_texts: list[str], trial_id: str) -> pd.DataFrame:
    """Build row-level visual checks from extracted captions."""

    columns = [
        "trial_id",
        "figure_label",
        "figure_number",
        "caption",
        "caption_norm",
        "page",
    ]
    rows = []
    for record in extract_figure_captions(page_texts):
        rows.append(
            {
                "trial_id": trial_id,
                "figure_label": record.figure_label,
                "figure_number": record.figure_number,
                "caption": record.caption,
                "caption_norm": normalize_caption(record.caption),
                "page": record.page,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def detect_caption_duplicates(
    visual_checks: pd.DataFrame, similarity_threshold: float = 0.9
) -> pd.DataFrame:
    """Detect near-duplicate caption text pairs."""

    if visual_checks.empty:
        return pd.DataFrame(
            columns=[
                "trial_id",
                "figure_label_a",
                "figure_label_b",
                "similarity",
                "flag_near_duplicate",
            ]
        )

    rows: list[dict[str, object]] = []
    subset = visual_checks.reset_index(drop=True)
    for left_index in range(len(subset)):
        for right_index in range(left_index + 1, len(subset)):
            left = subset.iloc[left_index]
            right = subset.iloc[right_index]
            similarity = SequenceMatcher(
                None,
                str(left["caption_norm"]),
                str(right["caption_norm"]),
            ).ratio()
            if similarity < similarity_threshold:
                continue
            rows.append(
                {
                    "trial_id": left["trial_id"],
                    "figure_label_a": left["figure_label"],
                    "figure_label_b": right["figure_label"],
                    "similarity": similarity,
                    "flag_near_duplicate": True,
                }
            )
    return pd.DataFrame(rows)


def detect_figure_numbering_gaps(visual_checks: pd.DataFrame) -> list[int]:
    """Return missing figure numbers between min/max observed labels."""

    if visual_checks.empty or visual_checks["figure_number"].dropna().empty:
        return []
    numbers = sorted(set(int(value) for value in visual_checks["figure_number"].dropna()))
    full = set(range(min(numbers), max(numbers) + 1))
    return sorted(full.difference(numbers))


def _require_columns(frame: pd.DataFrame, required_columns: list[str], context: str) -> None:
    missing = sorted(set(required_columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns for {context}: {missing}")


def _coerce_bool(value: object, *, field: str, row_number: int) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean for `{field}` at row {row_number}: {value!r}")


def scaffold_plot_digitization_targets(study_id: str) -> pd.DataFrame:
    """Create a one-row starter manifest for pilot plot digitization."""

    return pd.DataFrame(
        [
            {
                "study_id": study_id,
                "figure_id": "figure_01",
                "panel_id": "A",
                "image_path": f"data/raw/figures/{study_id}/figure_01_panel_a.png",
                "plot_type": "survival_curve",
                "x_unit": "months",
                "y_unit": "survival_probability",
                "x_scale": "linear",
                "y_scale": "linear",
                "target_series": "overall",
                "include": True,
            }
        ],
        columns=PLOT_DIGITIZATION_TARGET_COLUMNS,
    )


def validate_plot_digitization_targets(targets: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize plot-digitization target manifest rows."""

    if targets.empty:
        return pd.DataFrame(columns=PLOT_DIGITIZATION_TARGET_COLUMNS)
    _require_columns(targets, PLOT_DIGITIZATION_TARGET_COLUMNS, "plot digitization targets")
    normalized = targets[PLOT_DIGITIZATION_TARGET_COLUMNS].copy()

    text_columns = [
        "study_id",
        "figure_id",
        "panel_id",
        "image_path",
        "plot_type",
        "x_unit",
        "y_unit",
        "x_scale",
        "y_scale",
        "target_series",
    ]
    for column in text_columns:
        normalized[column] = normalized[column].fillna("").astype(str).str.strip()
        empty_rows = normalized.index[normalized[column] == ""].tolist()
        if empty_rows:
            first_row = int(empty_rows[0]) + 1
            raise ValueError(f"Empty value in `{column}` at row {first_row}")

    normalized["x_scale"] = normalized["x_scale"].str.lower()
    normalized["y_scale"] = normalized["y_scale"].str.lower()
    invalid_x = normalized.loc[~normalized["x_scale"].isin(_ALLOWED_SCALE_VALUES)]
    invalid_y = normalized.loc[~normalized["y_scale"].isin(_ALLOWED_SCALE_VALUES)]
    if not invalid_x.empty:
        row_num = int(invalid_x.index[0]) + 1
        value = invalid_x["x_scale"].iloc[0]
        raise ValueError(f"Invalid `x_scale` at row {row_num}: {value!r}")
    if not invalid_y.empty:
        row_num = int(invalid_y.index[0]) + 1
        value = invalid_y["y_scale"].iloc[0]
        raise ValueError(f"Invalid `y_scale` at row {row_num}: {value!r}")

    normalized["include"] = [
        _coerce_bool(value, field="include", row_number=index + 1)
        for index, value in enumerate(normalized["include"].tolist())
    ]
    return normalized[PLOT_DIGITIZATION_TARGET_COLUMNS]


def empty_plot_digitized_values() -> pd.DataFrame:
    """Create an empty schema-valid frame for digitized plot points."""

    return pd.DataFrame(columns=PLOT_DIGITIZED_VALUE_COLUMNS)


def validate_plot_digitized_values(values: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize digitized plot points."""

    if values.empty:
        return empty_plot_digitized_values()
    _require_columns(values, PLOT_DIGITIZED_VALUE_COLUMNS, "plot digitized values")
    normalized = values[PLOT_DIGITIZED_VALUE_COLUMNS].copy()

    for column in ["x_value", "y_value"]:
        original = normalized[column]
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        invalid = normalized.index[normalized[column].isna() & original.notna()].tolist()
        if invalid:
            first_row = int(invalid[0]) + 1
            bad_value = original.iloc[invalid[0]]
            raise ValueError(f"Non-numeric `{column}` at row {first_row}: {bad_value!r}")

    text_columns = [
        "study_id",
        "figure_id",
        "panel_id",
        "series_id",
        "x_unit",
        "y_unit",
        "source_image",
        "digitizer",
        "digitized_at",
        "extract_confidence",
    ]
    for column in text_columns:
        normalized[column] = normalized[column].fillna("").astype(str).str.strip()

    normalized.loc[normalized["extract_confidence"] == "", "extract_confidence"] = "medium"
    return normalized[PLOT_DIGITIZED_VALUE_COLUMNS]


def summarize_plot_digitization(values: pd.DataFrame) -> dict[str, int | bool]:
    """Summarize digitization coverage for report-level metrics."""

    normalized = validate_plot_digitized_values(values)
    if normalized.empty:
        return {
            "n_digitized_figures": 0,
            "n_digitized_series": 0,
            "n_digitized_points": 0,
            "digitization_ready": False,
        }

    n_figures = int(normalized["figure_id"].replace("", pd.NA).dropna().nunique())
    n_series = int(normalized["series_id"].replace("", pd.NA).dropna().nunique())
    n_points = int(len(normalized))
    return {
        "n_digitized_figures": n_figures,
        "n_digitized_series": n_series,
        "n_digitized_points": n_points,
        "digitization_ready": n_points > 0,
    }
