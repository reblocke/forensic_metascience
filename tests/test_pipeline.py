from __future__ import annotations

from pathlib import Path

import pandas as pd

from research_project.pipeline import PipelineConfig, run_pipeline


def test_pipeline_writes_output_and_creates_zscore(tmp_path: Path) -> None:
    raw = tmp_path / "raw.csv"
    out = tmp_path / "processed.csv"

    pd.DataFrame(
        {
            "value": [0.0, 1.0, 2.0, 3.0],
            "label": ["a", "b", "c", "d"],
        }
    ).to_csv(raw, index=False)

    cfg = PipelineConfig(input_csv=raw, output_csv=out)
    df = run_pipeline(cfg)

    assert out.exists()
    assert "value_z" in df.columns
    # z-scoring should have mean ~= 0
    assert abs(df["value_z"].mean()) < 1e-9
