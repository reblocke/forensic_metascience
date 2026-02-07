"""Helpers for maintaining a shared forensic manifest per study."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MANIFEST_COLUMNS = [
    "study_id",
    "source_pdf",
    "category",
    "extract_confidence",
    "page_ref",
    "table_ref",
    "analysis_ready",
]


def manifest_path(repo_root: Path, study_id: str) -> Path:
    """Return the canonical manifest path for a study."""

    return (
        repo_root
        / "data"
        / "processed"
        / "manifests"
        / study_id
        / "forensics_manifest.csv"
    )


def load_manifest(path: Path) -> pd.DataFrame:
    """Load an existing manifest, or create an empty one."""

    if not path.exists():
        return pd.DataFrame(columns=MANIFEST_COLUMNS)
    manifest = pd.read_csv(path)
    for column in MANIFEST_COLUMNS:
        if column not in manifest.columns:
            manifest[column] = None
    return manifest[MANIFEST_COLUMNS]


def upsert_manifest_row(
    path: Path,
    *,
    study_id: str,
    source_pdf: str,
    category: str,
    extract_confidence: str,
    page_ref: str,
    table_ref: str,
    analysis_ready: bool,
) -> pd.DataFrame:
    """Insert or update one category row in the study manifest."""

    manifest = load_manifest(path)
    row = pd.DataFrame(
        [
            {
                "study_id": study_id,
                "source_pdf": source_pdf,
                "category": category,
                "extract_confidence": extract_confidence,
                "page_ref": page_ref,
                "table_ref": table_ref,
                "analysis_ready": bool(analysis_ready),
            }
        ]
    )
    mask = (manifest["study_id"] == study_id) & (manifest["category"] == category)
    manifest = manifest.loc[~mask].copy()
    manifest = pd.concat([manifest, row], ignore_index=True)
    manifest = manifest.sort_values(["study_id", "category"], kind="stable")

    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(path, index=False)
    return manifest
