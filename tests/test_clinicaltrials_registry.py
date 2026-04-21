from __future__ import annotations

import json
from datetime import date

import pandas as pd

from research_project.clinicaltrials_registry import (
    build_history_events,
    derive_clinicaltrials_claims,
    fetch_current_record,
    legacy_claims_to_expanded,
    normalize_current_record,
    resolve_registry_id,
)


def _registry_record(
    *,
    start_date: str = "2020-01-01",
    first_posted: str = "2019-12-15",
    primary_completion: str = "2020-06-01",
    has_results: bool = False,
) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345678",
                "briefTitle": "Example Trial",
                "officialTitle": "Example Randomized Trial",
            },
            "statusModule": {
                "overallStatus": "COMPLETED",
                "startDateStruct": {"date": start_date, "type": "ACTUAL"},
                "studyFirstPostDateStruct": {"date": first_posted, "type": "ACTUAL"},
                "primaryCompletionDateStruct": {"date": primary_completion, "type": "ACTUAL"},
                "completionDateStruct": {"date": "2020-07-01", "type": "ACTUAL"},
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "designInfo": {
                    "allocation": "RANDOMIZED",
                    "interventionModel": "PARALLEL",
                    "maskingInfo": {"masking": "SINGLE"},
                },
                "enrollmentInfo": {"count": 120, "type": "ACTUAL"},
            },
            "outcomesModule": {
                "primaryOutcomes": [{"measure": "Mortality at 30 days", "timeFrame": "30 days"}],
                "secondaryOutcomes": [
                    {"measure": "Hospital length of stay", "timeFrame": "Index admission"}
                ],
            },
            "armsInterventionsModule": {
                "armGroups": [{"label": "Antibiotic stewardship", "type": "EXPERIMENTAL"}],
                "interventions": [{"name": "Antibiotic stewardship", "type": "OTHER"}],
            },
            "referencesModule": {
                "references": [
                    {
                        "pmid": "98765432",
                        "type": "RESULT",
                        "citation": "Example Trial. doi: 10.1000/example.",
                    }
                ]
            },
        },
        "hasResults": has_results,
    }


def test_resolve_registry_id_precedence_and_ambiguity() -> None:
    explicit = resolve_registry_id(
        explicit_registry_id="https://clinicaltrials.gov/study/NCT12345678",
        registry_url="",
        report_text="NCT87654321",
        protocol_text="",
    )
    ambiguous = resolve_registry_id(
        explicit_registry_id="",
        registry_url="",
        report_text="NCT12345678 and NCT87654321",
        protocol_text="",
    )
    non_nct = resolve_registry_id(
        explicit_registry_id="",
        registry_url="",
        report_text="Registered as ISRCTN12345678.",
        protocol_text="",
    )

    assert explicit["registry_id"] == "NCT12345678"
    assert explicit["registry_id_source"] == "config_registry_id"
    assert ambiguous["resolution_status"] == "ambiguous"
    assert ambiguous["registry_id"] == ""
    assert non_nct["resolution_status"] == "not_assessed"
    assert non_nct["registry_id_source"] == "non_clinicaltrials_registry"


def test_fetch_local_and_normalize_current_record(tmp_path) -> None:
    json_path = tmp_path / "registry.json"
    json_path.write_text(json.dumps(_registry_record()), encoding="utf-8")

    result = fetch_current_record(
        study_id="trial_x",
        registry_id="NCT12345678",
        registry_id_source="config_registry_id",
        registry_url="",
        current_json_path=json_path,
        allow_network=False,
    )
    current = normalize_current_record(
        study_id="trial_x",
        record=result.record,
        registry_source="fixture",
    )

    assert result.metadata.iloc[0]["fetch_status"] == "loaded_local_json"
    assert current.iloc[0]["registry_id"] == "NCT12345678"
    assert current.iloc[0]["enrollment_count"] == "120"
    assert "Mortality at 30 days" in current.iloc[0]["primary_outcomes"]


def test_clinicaltrials_claims_include_prospective_and_overdue_flags() -> None:
    current = normalize_current_record(
        study_id="trial_x",
        record=_registry_record(first_posted="2020-02-01", has_results=False),
        registry_source="fixture",
    )
    metadata = pd.DataFrame(
        [
            {
                "fetch_status": "loaded_local_json",
                "fetch_message": "fixture",
                "registry_current_source": "fixture",
            }
        ]
    )
    resolution = {
        "registry_id": "NCT12345678",
        "registry_id_source": "source_text",
        "resolution_status": "resolved",
        "resolution_message": "resolved",
    }
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text=(
            "Trial NCT12345678 randomized 120 participants. Mortality at 30 days was the "
            "primary outcome. Antibiotic stewardship was tested in a parallel design."
        ),
        protocol_text="Single masked trial with hospital length of stay as a secondary outcome.",
        current_record=current,
        fetch_metadata=metadata,
        registry_resolution=resolution,
        publication_doi="10.1000/example",
        as_of_date=date(2023, 1, 1),
    )

    prospective = claims[claims["claim_id"] == "clinicaltrials_prospective_registration"].iloc[0]
    overdue = claims[claims["claim_id"] == "clinicaltrials_results_overdue"].iloc[0]
    publication = claims[claims["claim_id"] == "clinicaltrials_publication_linkage"].iloc[0]

    assert prospective["assessment_status"] == "mismatch"
    assert overdue["assessment_status"] == "mismatch"
    assert publication["assessment_status"] == "match"


def test_clinicaltrials_no_registry_outputs_not_assessed_claim() -> None:
    resolution = resolve_registry_id(
        explicit_registry_id="",
        registry_url="",
        report_text="No registry is reported.",
        protocol_text="No registry is reported.",
    )
    result = fetch_current_record(
        study_id="trial_x",
        registry_id=resolution["registry_id"],
        registry_id_source=resolution["registry_id_source"],
        registry_url="",
        current_json_path=None,
        allow_network=False,
    )
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text="No registry is reported.",
        protocol_text="No registry is reported.",
        current_record=normalize_current_record(
            study_id="trial_x",
            record=result.record,
            registry_source="",
        ),
        fetch_metadata=result.metadata,
        registry_resolution=resolution,
    )

    assert len(claims) == 1
    assert claims.iloc[0]["claim_id"] == "clinicaltrials_current_record_available"
    assert claims.iloc[0]["assessment_status"] == "not_assessed"


def test_history_events_from_normalized_csv(tmp_path) -> None:
    history_path = tmp_path / "history.csv"
    pd.DataFrame(
        [
            {
                "snapshot_date": "2020-01-01",
                "registry_field": "enrollment_count",
                "registry_value": "100",
            },
            {
                "snapshot_date": "2020-02-01",
                "registry_field": "enrollment_count",
                "registry_value": "120",
            },
            {
                "snapshot_date": "2020-02-01",
                "registry_field": "masking",
                "registry_value": "SINGLE",
            },
        ]
    ).to_csv(history_path, index=False)

    events = build_history_events(
        study_id="trial_x",
        registry_id="NCT12345678",
        history_path=history_path,
    )

    assert len(events) == 1
    assert events.iloc[0]["registry_field"] == "enrollment_count"
    assert events.iloc[0]["old_value"] == "100"
    assert events.iloc[0]["new_value"] == "120"


def test_missing_values_do_not_become_literal_nan_in_expanded_claims() -> None:
    legacy = pd.DataFrame(
        [
            {
                "trial_id": "trial_x",
                "claim": "registry_id_overlap",
                "report_value": "NCT12345678",
                "protocol_value": pd.NA,
                "match_status": False,
                "evidence_page_report": 1,
                "evidence_page_protocol": pd.NA,
            }
        ]
    )

    expanded = legacy_claims_to_expanded(legacy)

    assert expanded.iloc[0]["protocol_value"] == ""
    assert "nan" not in expanded.iloc[0]["page_ref"].lower()


def test_blank_history_values_do_not_create_false_change_events(tmp_path) -> None:
    history_path = tmp_path / "history_blank.csv"
    pd.DataFrame(
        [
            {
                "snapshot_date": "2020-01-01",
                "registry_field": "masking",
                "registry_value": "",
            },
            {
                "snapshot_date": "2020-02-01",
                "registry_field": "masking",
                "registry_value": "",
            },
        ]
    ).to_csv(history_path, index=False)

    events = build_history_events(
        study_id="trial_x",
        registry_id="NCT12345678",
        history_path=history_path,
    )

    assert events.empty


def test_missing_history_file_is_not_counted_as_major_change(tmp_path) -> None:
    events = build_history_events(
        study_id="trial_x",
        registry_id="NCT12345678",
        history_path=tmp_path / "missing_history.csv",
    )

    assert len(events) == 1
    assert events.iloc[0]["change_type"] == "missing_input"
    assert events.iloc[0]["severity"] == "info"


def _registry_claims_for_dates(
    *,
    start_date: str = "2020-01-01",
    first_posted: str = "2019-12-15",
    primary_completion: str = "2020-06-01",
    as_of_date: date = date(2023, 1, 1),
) -> pd.DataFrame:
    current = normalize_current_record(
        study_id="trial_x",
        record=_registry_record(
            start_date=start_date,
            first_posted=first_posted,
            primary_completion=primary_completion,
            has_results=False,
        ),
        registry_source="fixture",
    )
    return derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text="Trial NCT12345678 randomized 120 participants.",
        protocol_text="Protocol text.",
        current_record=current,
        fetch_metadata=pd.DataFrame(),
        registry_resolution={
            "registry_id": "NCT12345678",
            "registry_id_source": "source_text",
            "resolution_status": "resolved",
            "resolution_message": "resolved",
        },
        as_of_date=as_of_date,
    )


def test_partial_same_month_registration_dates_are_indeterminate() -> None:
    claims = _registry_claims_for_dates(
        start_date="2020-04",
        first_posted="2020-04-30",
    )

    prospective = claims[claims["claim_id"] == "clinicaltrials_prospective_registration"].iloc[0]

    assert prospective["assessment_status"] == "indeterminate"
    assert "start_precision=month" in prospective["notes"]


def test_non_overlapping_partial_registration_dates_classify_when_justified() -> None:
    prospective_claims = _registry_claims_for_dates(
        start_date="2020-05",
        first_posted="2020-04",
    )
    retrospective_claims = _registry_claims_for_dates(
        start_date="2020-04",
        first_posted="2020-05",
    )

    prospective = prospective_claims[
        prospective_claims["claim_id"] == "clinicaltrials_prospective_registration"
    ].iloc[0]
    retrospective = retrospective_claims[
        retrospective_claims["claim_id"] == "clinicaltrials_prospective_registration"
    ].iloc[0]

    assert prospective["assessment_status"] == "match"
    assert retrospective["assessment_status"] == "mismatch"


def test_partial_primary_completion_overdue_is_conservative() -> None:
    indeterminate_claims = _registry_claims_for_dates(
        primary_completion="2020-06",
        as_of_date=date(2021, 6, 15),
    )
    overdue_claims = _registry_claims_for_dates(
        primary_completion="2020-06",
        as_of_date=date(2021, 7, 1),
    )

    indeterminate = indeterminate_claims[
        indeterminate_claims["claim_id"] == "clinicaltrials_results_overdue"
    ].iloc[0]
    overdue = overdue_claims[overdue_claims["claim_id"] == "clinicaltrials_results_overdue"].iloc[0]

    assert indeterminate["assessment_status"] == "indeterminate"
    assert "primary_completion_precision=month" in indeterminate["notes"]
    assert overdue["assessment_status"] == "mismatch"
