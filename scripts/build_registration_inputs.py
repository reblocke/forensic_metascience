"""Build registration congruence analysis inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from research_project.clinicaltrials_registry import (
    EXPANDED_CLAIM_COLUMNS,
    legacy_claims_to_expanded,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def _normalize_value(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def _read_claims(in_dir: Path) -> pd.DataFrame:
    expanded_path = in_dir / "inputs" / "registration_claims_expanded.csv"
    claims_path = in_dir / "inputs" / "registration_claims.csv"
    if expanded_path.exists():
        claims = pd.read_csv(expanded_path)
        for column in EXPANDED_CLAIM_COLUMNS:
            if column not in claims.columns:
                claims[column] = ""
        return claims[EXPANDED_CLAIM_COLUMNS]
    if claims_path.exists():
        return legacy_claims_to_expanded(pd.read_csv(claims_path))
    raise FileNotFoundError(f"Missing claims input: {expanded_path} or {claims_path}")


def _logical_or_na(value: object) -> bool | pd.NA:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes"}:
        return True
    if text in {"false", "f", "0", "no"}:
        return False
    return pd.NA


def main() -> None:
    args = parse_args()
    claims = _read_claims(args.in_dir)
    claims["claim"] = claims["claim_id"]
    claims["report_norm"] = claims["report_value"].map(_normalize_value)
    claims["protocol_norm"] = claims["protocol_value"].map(_normalize_value)
    claims["registry_norm"] = claims["registry_value"].map(_normalize_value)
    report_protocol_claim = claims["claim_category"] == "report_protocol"
    claims["is_missing_report"] = report_protocol_claim & (claims["report_norm"] == "")
    claims["is_missing_protocol"] = report_protocol_claim & (claims["protocol_norm"] == "")
    claims["is_missing_registry"] = claims["registry_norm"] == ""
    claims["match_status"] = claims["match_status"].map(_logical_or_na)
    claims["assessment_status"] = claims["assessment_status"].fillna("indeterminate")
    claims["assessed_flag"] = claims["assessment_status"].isin(["match", "mismatch"])
    claims["mismatch_flag"] = claims["assessment_status"] == "mismatch"

    inputs_dir = args.out_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = inputs_dir / "registration_checks_input.csv"
    claims.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
