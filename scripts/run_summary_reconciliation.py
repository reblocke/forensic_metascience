"""Execute source-bound, conditional R reconciliation without creating method receipts."""

from __future__ import annotations

import argparse
from pathlib import Path

from research_project.summary_reconciliation import run_reconciliation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_reconciliation(args.input, args.out, Path(__file__).resolve().parents[1])
    print(f"Reconciled {len(result['results'])} requests; candidate-only results in {args.out}")


if __name__ == "__main__":
    main()
