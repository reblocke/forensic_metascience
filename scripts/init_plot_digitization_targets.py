"""Initialize or validate pilot plot-digitization targets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from research_project.visual_forensics import (
    scaffold_plot_digitization_targets,
    validate_plot_digitization_targets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--out-root", type=Path, required=True)
    return parser.parse_args()


def _load_existing_targets(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def main() -> None:
    args = parse_args()
    study_id = args.study_id
    target_dir = args.out_root / study_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "plot_digitization_targets.csv"

    if target_path.exists():
        targets = _load_existing_targets(target_path)
        validated = validate_plot_digitization_targets(targets)
        validated.to_csv(target_path, index=False)
        print(f"Validated {target_path}")
        return

    scaffold = scaffold_plot_digitization_targets(study_id)
    scaffold.to_csv(target_path, index=False)
    print(f"Wrote {target_path}")


if __name__ == "__main__":
    main()
