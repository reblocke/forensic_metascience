"""Build package-specific randomization anomaly inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.randomization import build_csf_input, build_simdistr_input


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="table1_long", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    table1_long_path = args.table1_long
    out_dir = args.out

    if not table1_long_path.exists():
        raise FileNotFoundError(f"Missing table1_long input file: {table1_long_path}")

    table1_long = pd.read_csv(table1_long_path)
    simdistr_df = build_simdistr_input(table1_long)
    csf_df = build_csf_input(table1_long)

    out_dir.mkdir(parents=True, exist_ok=True)
    simdistr_path = out_dir / "simdistr_input.csv"
    csf_path = out_dir / "csf_input.csv"
    simdistr_df.to_csv(simdistr_path, index=False)
    csf_df.to_csv(csf_path, index=False)

    print(f"Wrote {simdistr_path}")
    print(f"Wrote {csf_path}")


if __name__ == "__main__":
    main()
