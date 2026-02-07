"""Make cheap, high-signal diagnostic plots.

Goal: catch obvious data misreads early.

Writes PNGs to the output directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    args.outdir.mkdir(parents=True, exist_ok=True)

    # Basic numeric column histograms
    numeric = df.select_dtypes(include="number").columns.tolist()
    for col in numeric:
        plt.figure()
        df[col].hist(bins=30)
        plt.title(f"Histogram: {col}")
        plt.xlabel(col)
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(args.outdir / f"hist_{col}.png", dpi=150)
        plt.close()

    # Pair plot surrogate: scatter of first two numeric columns
    if len(numeric) >= 2:
        x, y = numeric[0], numeric[1]
        plt.figure()
        plt.scatter(df[x], df[y], s=12)
        plt.title(f"Scatter: {x} vs {y}")
        plt.xlabel(x)
        plt.ylabel(y)
        plt.tight_layout()
        plt.savefig(args.outdir / f"scatter_{x}_vs_{y}.png", dpi=150)
        plt.close()


if __name__ == "__main__":
    main()
