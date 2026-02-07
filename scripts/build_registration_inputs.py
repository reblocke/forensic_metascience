"""Build registration congruence analysis inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def _normalize_value(value: object) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def main() -> None:
    args = parse_args()
    claims_path = args.in_dir / "inputs" / "registration_claims.csv"
    if not claims_path.exists():
        raise FileNotFoundError(f"Missing claims input: {claims_path}")

    claims = pd.read_csv(claims_path)
    claims["report_norm"] = claims["report_value"].map(_normalize_value)
    claims["protocol_norm"] = claims["protocol_value"].map(_normalize_value)
    claims["is_missing_report"] = claims["report_norm"] == ""
    claims["is_missing_protocol"] = claims["protocol_norm"] == ""
    claims["match_status"] = claims["match_status"].fillna(False).astype(bool)
    claims["mismatch_flag"] = ~claims["match_status"]

    inputs_dir = args.out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = inputs_dir / "registration_checks_input.csv"
    claims.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
