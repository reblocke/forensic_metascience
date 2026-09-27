from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from research_project.inspect_sr.records import source_version_id
from research_project.numeric_integrity import (
    attach_source_evidence,
    build_scrutiny_cases,
    build_scrutiny_debit_input,
    build_scrutiny_duplicate_input,
    build_scrutiny_grim_input,
    build_scrutiny_grimmer_input,
    build_scrutiny_rounding_bias_input,
)


def write_numeric_method_fixture(
    input_dir: Path,
    *,
    trial_id: str = "synthetic_native",
    source_version: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    input_dir.mkdir(parents=True)

    def write_numeric_csv(frame: pd.DataFrame, name: str) -> None:
        frame = frame.copy()
        for column in (
            "x",
            "sd",
            "x_str",
            "sd_str",
            "raw_value",
            "raw_count",
            "reported_percent_raw",
            "reported_p",
            "reported_p_raw",
            "reported_p_comparator",
        ):
            if column not in frame:
                frame[column] = pd.NA
        frame.to_csv(input_dir / name, index=False)

    summary = pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "source_id": "synthetic-report",
                "source_pdf": "synthetic.pdf",
                "source_table": "synthetic_table",
                "source_page": 1,
                "source_locator": f"table1:row{i}",
                "raw_value": f"{x} (SD {sd})",
                "reported_decimals": 2,
                "reported_p_raw": "P=.50",
                "reported_p_comparator": "=",
                "variable": "synthetic mean",
                "level": "all",
                "group": f"arm_{i}",
                "n": 4,
                "analysis_n": 4,
                "x_str": x,
                "sd_str": sd,
                "digits_x": 2,
                "digits_sd": 2,
                "statistic_kind": "arithmetic_mean",
                "measurement_scale": "bernoulli",
                "raw_or_adjusted": "raw",
                "weighting": "unweighted",
                "imputation_status": "not_imputed",
                "transformation_status": "none",
                "granularity_transformation": "",
                "eligibility_evidence": "Synthetic fixture explicitly declares raw count mean.",
            }
            for i, x, sd in ((1, "0.25", "0.50"), (2, "0.26", "0.51"))
        ]
    )
    cases = build_scrutiny_cases(pd.DataFrame(), summary, source_pdf="synthetic.pdf")
    if source_version is None:
        source_path = input_dir.parent / "synthetic.pdf"
        source_path.write_text(
            "Synthetic table: row 1 mean 0.25 SD 0.50; row 2 mean 0.26 SD 0.51.\n",
            encoding="utf-8",
        )
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        source_version = {
            "source_id": "synthetic-report",
            "source_name": "synthetic.pdf",
            "source_version_id": source_version_id("synthetic-report", source_hash),
            "content_sha256": source_hash,
        }
    cases, evidence_records = attach_source_evidence(cases, [source_version])
    write_numeric_csv(cases, "scrutiny_cases.csv")
    write_numeric_csv(build_scrutiny_grim_input(cases), "scrutiny_grim_input.csv")
    write_numeric_csv(build_scrutiny_grimmer_input(cases), "scrutiny_grimmer_input.csv")
    write_numeric_csv(build_scrutiny_debit_input(cases), "scrutiny_debit_input.csv")
    write_numeric_csv(build_scrutiny_duplicate_input(cases), "scrutiny_duplicates_input.csv")
    write_numeric_csv(build_scrutiny_rounding_bias_input(cases), "scrutiny_rounding_bias_input.csv")

    numeric_checks = pd.DataFrame(
        [
            {
                "trial_id": trial_id,
                "variable": "synthetic mean",
                "level": "all",
                "group": "arm_1",
                "source_unit": "synthetic:table1:row1",
                "abs_percent_delta": 0.0,
                "legacy_abs_percent_delta": 0.0,
                "compatibility_status": "compatible",
                "reported_percent": 25.0,
                "computed_percent": 25.0,
                "reported_p": 0.5,
            }
        ]
    )
    write_numeric_csv(numeric_checks, "numeric_checks_input.csv")
    write_numeric_csv(pd.DataFrame(columns=["trial_id", "source_unit"]), "statcheck_input.csv")
    write_numeric_csv(
        pd.DataFrame(
            columns=[
                "trial_id",
                "variable",
                "level",
                "group_a",
                "group_b",
                "percent_a",
                "percent_b",
                "abs_percent_between_arms",
            ]
        ),
        "rsprite2_input.csv",
    )
    (input_dir / "statcheck_text.txt").write_text(
        "The synthetic test reported t(28) = 2.20, p = .036.", encoding="utf-8"
    )
    return evidence_records
