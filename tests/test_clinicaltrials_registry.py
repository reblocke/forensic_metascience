from __future__ import annotations

import hashlib
import json
import urllib.error
from datetime import date

import pandas as pd
import pytest

from research_project.clinicaltrials_registry import (
    build_history_events,
    build_history_status,
    derive_clinicaltrials_claims,
    fetch_current_record,
    legacy_claims_to_expanded,
    normalize_current_record,
    resolve_registry_id,
)


def _registry_record(
    *,
    start_date: str = "2020-01-01",
    first_submitted: str = "2019-12-15",
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
                "studyFirstSubmitDate": first_submitted,
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
    assert result.metadata.iloc[0]["source_version"] == "local_json_unverified_version"
    assert (
        result.metadata.iloc[0]["source_sha256"]
        == hashlib.sha256(json_path.read_bytes()).hexdigest()
    )
    assert result.raw_json == json_path.read_bytes()
    assert current.iloc[0]["registry_id"] == "NCT12345678"
    assert current.iloc[0]["enrollment_count"] == "120"
    assert "Mortality at 30 days" in current.iloc[0]["primary_outcomes"]


def test_network_disabled_uses_no_transport_even_with_registry_id(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled registry networking must not call the transport.")

    monkeypatch.setattr(
        "research_project.clinicaltrials_registry.urllib.request.urlopen", forbidden
    )
    result = fetch_current_record(
        study_id="trial_x",
        registry_id="NCT12345678",
        registry_id_source="config_registry_id",
        registry_url="",
        current_json_path=None,
        allow_network=False,
    )

    assert result.record is None
    assert result.metadata.iloc[0]["fetch_status"] == "network_disabled"


def test_documented_registry_404_is_distinct_from_fetch_failure(monkeypatch) -> None:
    def not_found(*args, **kwargs):
        raise urllib.error.HTTPError("https://example.test", 404, "not found", {}, None)

    monkeypatch.setattr(
        "research_project.clinicaltrials_registry.urllib.request.urlopen", not_found
    )
    result = fetch_current_record(
        study_id="trial_x",
        registry_id="NCT12345678",
        registry_id_source="config_registry_id",
        registry_url="",
        current_json_path=None,
        allow_network=True,
    )

    assert result.record is None
    assert result.metadata.iloc[0]["fetch_status"] == "record_not_found"
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text="",
        protocol_text="",
        current_record=normalize_current_record(
            study_id="trial_x", record=None, registry_source=""
        ),
        fetch_metadata=result.metadata,
        registry_resolution={
            "registry_id": "NCT12345678",
            "resolution_status": "resolved",
            "resolution_message": "resolved",
        },
    )
    assert claims.iloc[0]["assessment_status"] == "not_assessed"
    assert "HTTP 404" in claims.iloc[0]["notes"]


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

    assert prospective["assessment_status"] == "indeterminate"
    assert prospective["screen_status"] == "prospective_timing_screen"
    assert overdue["assessment_status"] == "indeterminate"
    assert overdue["screen_status"] == "potentially_overdue"
    assert publication["assessment_status"] == "indeterminate"
    assert publication["screen_status"] == "identifier_detected"


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


def test_missing_history_file_is_distinct_from_change_events(tmp_path) -> None:
    events = build_history_events(
        study_id="trial_x",
        registry_id="NCT12345678",
        history_path=tmp_path / "missing_history.csv",
    )
    status = build_history_status(history_path=tmp_path / "missing_history.csv")

    assert events.empty
    assert status.iloc[0]["history_status"] == "missing_input"


def _registry_claims_for_dates(
    *,
    start_date: str = "2020-01-01",
    first_submitted: str = "2019-12-15",
    first_posted: str = "2019-12-15",
    primary_completion: str = "2020-06-01",
    as_of_date: date = date(2023, 1, 1),
) -> pd.DataFrame:
    current = normalize_current_record(
        study_id="trial_x",
        record=_registry_record(
            start_date=start_date,
            first_submitted=first_submitted,
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
        first_submitted="2020-04",
        first_posted="2020-06",
    )
    retrospective_claims = _registry_claims_for_dates(
        start_date="2020-04",
        first_submitted="2020-05",
        first_posted="2020-03",
    )

    prospective = prospective_claims[
        prospective_claims["claim_id"] == "clinicaltrials_prospective_registration"
    ].iloc[0]
    retrospective = retrospective_claims[
        retrospective_claims["claim_id"] == "clinicaltrials_prospective_registration"
    ].iloc[0]

    assert prospective["assessment_status"] == "indeterminate"
    assert prospective["screen_status"] == "prospective_timing_screen"
    assert retrospective["assessment_status"] == "indeterminate"
    assert retrospective["screen_status"] == "potentially_retrospective_timing_screen"


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
    assert overdue["assessment_status"] == "indeterminate"
    assert overdue["screen_status"] == "potentially_overdue"


def test_registry_date_fields_keep_submission_posting_and_actual_start_distinct() -> None:
    record = _registry_record()
    status = record["protocolSection"]["statusModule"]
    status["studyFirstSubmitDate"] = "2019-11-20"
    status["studyFirstPostDateStruct"] = {"date": "2019-12-15", "type": "ACTUAL"}
    status["startDateStruct"] = {"date": "2020-01", "type": "ESTIMATED"}

    current = normalize_current_record(
        study_id="trial_x", record=record, registry_source="fixture"
    ).iloc[0]

    assert current["first_submitted_date"] == "2019-11-20"
    assert current["study_first_posted_date"] == "2019-12-15"
    assert current["registered_start_date"] == "2020-01"
    assert current["actual_recruitment_start_date"] == ""
    assert current["start_date_type"] == "ESTIMATED"


def test_failed_fetch_is_availability_metadata_not_registry_absence(tmp_path) -> None:
    result = fetch_current_record(
        study_id="trial_x",
        registry_id="NCT12345678",
        registry_id_source="config_registry_id",
        registry_url="",
        current_json_path=tmp_path / "missing.json",
        allow_network=False,
    )
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text="",
        protocol_text="",
        current_record=normalize_current_record(
            study_id="trial_x", record=None, registry_source=""
        ),
        fetch_metadata=result.metadata,
        registry_resolution={
            "registry_id": "NCT12345678",
            "resolution_status": "resolved",
            "resolution_message": "resolved",
        },
    )

    availability = claims.iloc[0]
    assert availability["assessment_status"] == "not_assessed"
    assert availability["match_status"] is pd.NA or pd.isna(availability["match_status"])
    assert "missing_local_json" in availability["notes"]


def test_overdue_and_publication_linkage_are_metadata_screens() -> None:
    claims = _registry_claims_for_dates(as_of_date=date(2023, 1, 1))
    overdue = claims[claims["claim_id"] == "clinicaltrials_results_overdue"].iloc[0]
    publication = claims[claims["claim_id"] == "clinicaltrials_publication_linkage"].iloc[0]

    assert overdue["assessment_status"] == "indeterminate"
    assert "potentially_overdue" in overdue["screen_status"]
    assert publication["assessment_status"] == "not_assessed"
    assert publication["screen_status"] == "not_assessed"


@pytest.mark.parametrize(
    "report_text",
    [
        "This was a non-randomized study.",
        "This was a nonrandomized study.",
        "This study did not use randomized allocation.",
    ],
)
def test_negated_randomization_does_not_match_registry_claim(report_text: str) -> None:
    current_record = normalize_current_record(
        study_id="trial_x", record=_registry_record(), registry_source="fixture"
    )
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text=report_text,
        protocol_text="",
        current_record=current_record,
        fetch_metadata=pd.DataFrame(),
        registry_resolution={"registry_id": "NCT12345678"},
    )
    allocation = claims.loc[claims["claim_id"] == "clinicaltrials_allocation_congruence"].iloc[0]

    assert allocation["match_status"] is not True
    assert allocation["assessment_status"] == "indeterminate"


def test_history_status_distinguishes_absent_undated_and_unchanged(tmp_path) -> None:
    absent = build_history_status(history_path=None)
    assert absent.iloc[0]["history_status"] == "not_supplied"

    undated_path = tmp_path / "undated.json"
    undated_path.write_text(
        json.dumps({"snapshots": [{"record": _registry_record()}]}), encoding="utf-8"
    )
    undated = build_history_status(history_path=undated_path)
    assert undated.iloc[0]["history_status"] == "unusable_undated"
    assert undated.iloc[0]["undated_snapshots"] == 1

    unchanged_path = tmp_path / "unchanged.json"
    snapshot = {"snapshot_date": "2020-01-01", "record": _registry_record()}
    unchanged_path.write_text(json.dumps({"snapshots": [snapshot, snapshot]}), encoding="utf-8")
    events = build_history_events(
        study_id="trial_x", registry_id="NCT12345678", history_path=unchanged_path
    )
    unchanged = build_history_status(history_path=unchanged_path, events=events)
    assert unchanged.iloc[0]["history_status"] == "usable"
    assert unchanged.iloc[0]["snapshots_supplied"] == 2
    assert unchanged.iloc[0]["change_events_detected"] == 0

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps({"error": "history unavailable"}), encoding="utf-8")
    invalid = build_history_status(history_path=invalid_path)
    assert invalid.iloc[0]["history_status"] == "invalid_structure"


def test_malformed_history_date_is_parse_failed_without_synthetic_events(tmp_path) -> None:
    history_path = tmp_path / "malformed-date.json"
    history_path.write_text(
        json.dumps({"snapshots": [{"snapshot_date": "2026-02-30", "record": _registry_record()}]}),
        encoding="utf-8",
    )
    status = build_history_status(history_path=history_path).iloc[0]
    events = build_history_events(
        study_id="trial_x", registry_id="NCT12345678", history_path=history_path
    )
    assert status["history_status"] == "parse_failed"
    assert events.empty


def test_registry_design_matching_rejects_negated_randomization() -> None:
    current = normalize_current_record(
        study_id="trial_x", record=_registry_record(), registry_source="fixture"
    )
    claims = derive_clinicaltrials_claims(
        trial_id="trial_x",
        report_text="Patients were not randomized.",
        protocol_text="",
        current_record=current,
        fetch_metadata=pd.DataFrame([{"fetch_status": "loaded_local_json"}]),
        registry_resolution={"registry_id": "NCT12345678", "resolution_message": "fixture"},
    )
    allocation = claims[claims["claim_id"] == "clinicaltrials_allocation_congruence"].iloc[0]
    assert allocation["assessment_status"] == "indeterminate"


def test_history_orders_dates_chronologically_and_rejects_undated_rows(tmp_path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "snapshot_date": "2020-10-01",
                        "record": _registry_record(start_date="2020-10-01"),
                    },
                    {
                        "snapshot_date": "2020-02-01",
                        "record": _registry_record(start_date="2020-02-01"),
                    },
                    {"record": _registry_record(start_date="2020-01-01")},
                ]
            }
        ),
        encoding="utf-8",
    )

    events = build_history_events(
        study_id="trial_x", registry_id="NCT12345678", history_path=history_path
    )
    status = build_history_status(history_path=history_path, events=events).iloc[0]

    start_events = events[events["registry_field"] == "start_date"]
    assert list(start_events["event_date"]) == ["2020-10-01"]
    assert start_events.iloc[0]["old_value"] == "2020-02-01"
    assert status["undated_snapshots"] == 1
    assert status["history_status"] == "partially_usable"


def test_history_overlapping_partial_dates_do_not_create_ordered_change(tmp_path) -> None:
    history_path = tmp_path / "overlapping.json"
    history_path.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "snapshot_date": "2020-02",
                        "record": _registry_record(start_date="2020-02-01"),
                    },
                    {
                        "snapshot_date": "2020-02-15",
                        "record": _registry_record(start_date="2020-02-15"),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    events = build_history_events(
        study_id="trial_x", registry_id="NCT12345678", history_path=history_path
    )
    status = build_history_status(history_path=history_path, events=events).iloc[0]
    start_events = events[events["registry_field"] == "start_date"]

    assert start_events.empty
    assert status["history_status"] == "usable"
    assert status["history_completeness"] == "unknown"
    assert status["chronology_status"] == "ambiguous_overlap"
