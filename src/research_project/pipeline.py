"""Deterministic data processing pipeline.

Convention:
- Reads from data/raw
- Writes to data/processed
- Avoids plotting. Diagnostics/plots belong in scripts/ or notebooks/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the pipeline.

    Keep config explicit and serializable.
    """

    input_csv: Path
    output_csv: Path


def run_pipeline(cfg: PipelineConfig) -> pd.DataFrame:
    """Run the processing pipeline.

    Parameters
    ----------
    cfg:
        PipelineConfig with input/output paths.

    Returns
    -------
    pd.DataFrame
        The processed dataset.
    """

    if not cfg.input_csv.exists():
        raise FileNotFoundError(f"Missing raw data file: {cfg.input_csv}")

    df = pd.read_csv(cfg.input_csv)

    # Example processing: normalize a numeric column if present.
    if "value" in df.columns:
        df = df.copy()
        df["value_z"] = (df["value"] - df["value"].mean()) / df["value"].std(ddof=0)

    cfg.output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.output_csv, index=False)
    return df


def default_config(repo_root: Path) -> PipelineConfig:
    """Create a default config rooted at the repository."""

    return PipelineConfig(
        input_csv=repo_root / "data" / "raw" / "sample.csv",
        output_csv=repo_root / "data" / "processed" / "sample_processed.csv",
    )
