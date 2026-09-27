from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from research_project.clinicaltrials_registry import legacy_claims_to_expanded
from research_project.registration_forensics import derive_registration_claims


def test_allocation_ratio_requires_allocation_context_and_preserves_source_evidence() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["At 12:30, participants were randomized in a 2:1 allocation ratio."],
        protocol_page_texts=["The protocol says participants were randomized 2:1."],
    )

    ratio = claims[claims["claim"] == "allocation_ratio"].iloc[0]
    assert ratio["match_status"] is True
    assert ratio["report_value"] == "2:1"
    assert (
        ratio["report_evidence"]
        == "At 12:30, participants were randomized in a 2:1 allocation ratio."
    )
    assert ratio["evidence_page_report"] == 1
    assert ratio["report_negated"] is False


def test_time_colon_is_not_an_allocation_ratio_and_missing_is_not_mismatch() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["The infusion began at 12:30."],
        protocol_page_texts=["Allocation was not reported."],
    )

    ratio = claims[claims["claim"] == "allocation_ratio"].iloc[0]
    assert ratio["match_status"] is None or str(ratio["match_status"]) == "<NA>"
    assert ratio["report_value"] == ""
    assert ratio["assessment_status"] == "indeterminate"


def test_explicitly_negated_ratio_retains_the_quote_without_assessing_it() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["Participants were not randomized in a 2:1 ratio."],
        protocol_page_texts=["Participants were randomized in a 2:1 ratio."],
    )

    ratio = claims[claims["claim"] == "allocation_ratio"].iloc[0]
    assert ratio["report_value"] == ratio["protocol_value"] == "2:1"
    assert ratio["report_negated"] is True
    assert ratio["assessment_status"] == "indeterminate"
    assert ratio["report_evidence"] == "Participants were not randomized in a 2:1 ratio."


def test_explicit_negation_and_role_specific_masking_are_not_collapsed() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["Treatment was open-label; outcome assessors were blinded."],
        protocol_page_texts=[
            "Treatment was not blinded; participants and clinicians were not blinded."
        ],
    )

    randomization = claims[claims["claim"] == "randomization_phrase"].iloc[0]
    treatment = claims[(claims["claim"] == "blinding_role") & (claims["role"] == "treatment")].iloc[
        0
    ]
    outcome = claims[
        (claims["claim"] == "blinding_role") & (claims["role"] == "outcome_assessors")
    ].iloc[0]

    assert randomization["assessment_status"] == "indeterminate"
    assert treatment["report_value"] == "open_label"
    assert treatment["protocol_value"] == "not_blinded"
    assert treatment["assessment_status"] == "indeterminate"
    assert outcome["report_value"] == "blinded"
    assert outcome["protocol_value"] == ""
    assert outcome["assessment_status"] == "indeterminate"
    assert outcome["report_evidence"] == "outcome assessors were blinded."
    assert outcome["role"] == "outcome_assessors"


def test_expanded_claim_conversion_preserves_structured_evidence() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["Treatment was open-label."],
        protocol_page_texts=["Treatment was not blinded."],
    )
    expanded = legacy_claims_to_expanded(claims)
    treatment = expanded[
        (expanded["claim_id"] == "blinding_role") & (expanded["role"] == "treatment")
    ].iloc[0]

    assert treatment["schema_version"] == "registration_claims_v4"
    assert treatment["report_evidence"] == "Treatment was open-label."
    assert treatment["protocol_evidence"] == "Treatment was not blinded."
    assert treatment["report_negated"] is False
    assert treatment["population"] == "trial participants"
    assert treatment["role"] == "treatment"


def test_negated_blinding_claim_does_not_match_positive_claim() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["The study was not open-label."],
        protocol_page_texts=["The study was open-label."],
    )
    treatment = claims[(claims["claim"] == "blinding_role") & (claims["role"] == "treatment")].iloc[
        0
    ]
    assert treatment["report_value"] == "open_label"
    assert treatment["report_negated"] is True
    assert treatment["assessment_status"] == "indeterminate"


@pytest.mark.parametrize(
    "negative_claim",
    [
        "The study was non-randomized.",
        "The study used quasi-randomised allocation.",
        "The study was non–randomised.",
    ],
)
def test_non_and_quasi_randomized_wording_does_not_match_randomized(
    negative_claim: str,
) -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=[negative_claim],
        protocol_page_texts=["Participants were randomized."],
    )
    row = claims.loc[claims["claim"] == "randomization_phrase"].iloc[0]
    assert row["report_value"] == "not_randomized"
    assert row["match_status"] is pd.NA or pd.isna(row["match_status"])
    assert row["assessment_status"] == "indeterminate"


def test_conflicting_randomization_context_remains_indeterminate() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["Participants were randomized. Participants were not randomized."],
        protocol_page_texts=["Participants were randomized."],
    )
    row = claims.loc[claims["claim"] == "randomization_phrase"].iloc[0]
    assert row["assessment_status"] == "indeterminate"


def test_multiple_registry_mentions_remain_indeterminate_without_index_mapping() -> None:
    claims = derive_registration_claims(
        trial_id="trial_x",
        report_page_texts=["Registry IDs NCT12345678 and ISRCTN12345678."],
        protocol_page_texts=["Registry NCT12345678."],
    )
    row = claims.loc[claims["claim"] == "registry_id_overlap"].iloc[0]
    assert row["schema_version"] == "registration_source_claims_v4"
    assert row["assessment_status"] == "indeterminate"
    assert pd.isna(row["match_status"])


def test_registration_input_builder_keeps_unassessed_mismatch_flag_missing(tmp_path) -> None:
    input_dir = tmp_path / "input"
    (input_dir / "inputs").mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "schema_version": "registration_claims_v3",
                "trial_id": "trial_x",
                "claim_id": "one",
                "claim_category": "registry_current",
                "assessment_status": "indeterminate",
                "match_status": "",
            },
            {
                "schema_version": "registration_claims_v3",
                "trial_id": "trial_x",
                "claim_id": "two",
                "claim_category": "report_protocol",
                "assessment_status": "match",
                "match_status": "true",
            },
            {
                "schema_version": "registration_claims_v3",
                "trial_id": "trial_x",
                "claim_id": "three",
                "claim_category": "report_protocol",
                "assessment_status": "mismatch",
                "match_status": "false",
            },
        ]
    ).to_csv(input_dir / "inputs" / "registration_claims_expanded.csv", index=False)
    output_dir = tmp_path / "output"
    script = Path(__file__).parents[1] / "scripts" / "build_registration_inputs.py"
    subprocess.run(
        [sys.executable, str(script), "--in", str(input_dir), "--out", str(output_dir)],
        check=True,
    )

    results = pd.read_csv(output_dir / "inputs" / "registration_checks_input.csv")
    mismatch_flags = results.set_index("claim_id")["mismatch_flag"]
    assert pd.isna(mismatch_flags["one"])
    assert mismatch_flags["two"] == 0
    assert mismatch_flags["three"] == 1


def test_registration_extractor_requires_explicit_network_opt_in(monkeypatch) -> None:
    script = Path(__file__).parents[1] / "scripts" / "extract_registration.py"
    spec = importlib.util.spec_from_file_location("extract_registration_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_registration.py",
            "--report",
            "report.pdf",
            "--protocol",
            "protocol.pdf",
            "--out",
            "out",
        ],
    )

    args = module.parse_args()
    assert args.allow_network is False
