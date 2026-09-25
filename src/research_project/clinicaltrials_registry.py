"""ClinicalTrials.gov registration audit helpers."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from calendar import monthrange
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from research_project.registration_forensics import extract_registry_ids, normalize_text

CLINICALTRIALS_API_BASE = "https://clinicaltrials.gov/api/v2"
NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", flags=re.IGNORECASE)

CURRENT_RECORD_COLUMNS = [
    "study_id",
    "registry_id",
    "registry_source",
    "official_title",
    "brief_title",
    "study_type",
    "overall_status",
    "start_date",
    "registered_start_date",
    "start_date_type",
    "actual_recruitment_start_date",
    "first_submitted_date",
    "study_first_posted_date",
    "primary_completion_date",
    "completion_date",
    "results_first_posted_date",
    "has_results",
    "enrollment_count",
    "enrollment_type",
    "allocation",
    "intervention_model",
    "masking",
    "primary_outcomes",
    "secondary_outcomes",
    "arms",
    "interventions",
    "references",
]

FETCH_METADATA_COLUMNS = [
    "study_id",
    "registry_id",
    "registry_id_source",
    "registry_url",
    "registry_current_source",
    "allow_network",
    "fetch_status",
    "fetch_message",
    "api_url",
    "fetched_at",
    "source_version",
    "source_sha256",
]

EXPANDED_CLAIM_COLUMNS = [
    "schema_version",
    "trial_id",
    "claim_id",
    "claim_category",
    "source",
    "report_value",
    "protocol_value",
    "registry_value",
    "match_status",
    "assessment_status",
    "severity",
    "notes",
    "page_ref",
    "registry_field",
    "screen_status",
    "report_evidence",
    "protocol_evidence",
    "report_negated",
    "protocol_negated",
    "population",
    "role",
]

HISTORY_STATUS_COLUMNS = [
    "history_status",
    "history_completeness",
    "chronology_status",
    "history_path_supplied",
    "history_sha256",
    "snapshots_supplied",
    "dated_snapshots",
    "undated_snapshots",
    "change_events_detected",
]

HISTORY_EVENT_COLUMNS = [
    "study_id",
    "registry_id",
    "event_id",
    "event_date",
    "registry_field",
    "old_value",
    "new_value",
    "change_type",
    "severity",
    "notes",
]

TRACKED_HISTORY_FIELDS = [
    "start_date",
    "primary_completion_date",
    "completion_date",
    "enrollment_count",
    "enrollment_type",
    "allocation",
    "intervention_model",
    "masking",
    "primary_outcomes",
    "secondary_outcomes",
    "arms",
    "interventions",
]


@dataclass(frozen=True)
class RegistryDateInterval:
    """Date interval for ClinicalTrials.gov dates with partial precision."""

    start: date
    end: date
    precision: str
    raw: str


class RegistryFetchResult:
    """Container for a current registry record and fetch metadata."""

    def __init__(
        self,
        record: dict[str, Any] | None,
        metadata: pd.DataFrame,
        raw_json: bytes | None = None,
    ) -> None:
        self.record = record
        self.metadata = metadata
        self.raw_json = raw_json


def _empty_current_record() -> pd.DataFrame:
    return pd.DataFrame(columns=CURRENT_RECORD_COLUMNS)


def _empty_fetch_metadata() -> pd.DataFrame:
    return pd.DataFrame(columns=FETCH_METADATA_COLUMNS)


def empty_expanded_claims() -> pd.DataFrame:
    """Return a schema-valid expanded registration claims table."""

    return pd.DataFrame(columns=EXPANDED_CLAIM_COLUMNS)


def empty_history_events() -> pd.DataFrame:
    """Return a schema-valid registry-history event table."""

    return pd.DataFrame(columns=HISTORY_EVENT_COLUMNS)


def _is_missing_scalar(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Mapping):
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, bool) else False


def _first_text(value: object) -> str:
    if _is_missing_scalar(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _get_path(record: Mapping[str, Any], path: Sequence[str], default: Any = "") -> Any:
    current: Any = record
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _date_from_struct(value: Any) -> str:
    if isinstance(value, Mapping):
        return _first_text(value.get("date"))
    return _first_text(value)


def _join_values(values: Sequence[object]) -> str:
    cleaned = [_first_text(value) for value in values if _first_text(value)]
    return " || ".join(cleaned)


def _outcome_text(outcomes: Any) -> str:
    if not isinstance(outcomes, Sequence) or isinstance(outcomes, (str, bytes)):
        return ""
    rendered: list[str] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        parts = [
            _first_text(outcome.get("measure")),
            _first_text(outcome.get("timeFrame")),
            _first_text(outcome.get("description")),
        ]
        rendered.append(" | ".join(part for part in parts if part))
    return _join_values(rendered)


def _arm_text(arms: Any) -> str:
    if not isinstance(arms, Sequence) or isinstance(arms, (str, bytes)):
        return ""
    rendered: list[str] = []
    for arm in arms:
        if not isinstance(arm, Mapping):
            continue
        rendered.append(
            " | ".join(
                part
                for part in [
                    _first_text(arm.get("label")),
                    _first_text(arm.get("type")),
                    _join_values(arm.get("interventionNames", [])),
                ]
                if part
            )
        )
    return _join_values(rendered)


def _intervention_text(interventions: Any) -> str:
    if not isinstance(interventions, Sequence) or isinstance(interventions, (str, bytes)):
        return ""
    rendered: list[str] = []
    for intervention in interventions:
        if not isinstance(intervention, Mapping):
            continue
        rendered.append(
            " | ".join(
                part
                for part in [
                    _first_text(intervention.get("name")),
                    _first_text(intervention.get("type")),
                    _first_text(intervention.get("description")),
                ]
                if part
            )
        )
    return _join_values(rendered)


def _reference_text(references: Any) -> str:
    if not isinstance(references, Sequence) or isinstance(references, (str, bytes)):
        return ""
    rendered: list[str] = []
    for reference in references:
        if not isinstance(reference, Mapping):
            continue
        rendered.append(
            " | ".join(
                part
                for part in [
                    _first_text(reference.get("pmid")),
                    _first_text(reference.get("type")),
                    _first_text(reference.get("citation")),
                ]
                if part
            )
        )
    return _join_values(rendered)


def extract_nct_ids(text: str) -> list[str]:
    """Extract NCT identifiers from free text."""

    return sorted({match.upper() for match in NCT_PATTERN.findall(text or "")})


def _normalize_registry_identifier(value: str | None) -> str:
    text = _first_text(value).upper()
    match = NCT_PATTERN.search(text)
    if match:
        return match.group(0).upper()
    return text


def resolve_registry_id(
    *,
    explicit_registry_id: str | None,
    registry_url: str | None,
    report_text: str,
    protocol_text: str,
) -> dict[str, str]:
    """Resolve the ClinicalTrials.gov ID to use, without silently choosing among multiples."""

    explicit = _normalize_registry_identifier(explicit_registry_id)
    if explicit.startswith("NCT"):
        return {
            "registry_id": explicit,
            "registry_id_source": "config_registry_id",
            "resolution_status": "resolved",
            "resolution_message": "Using explicit registry ID from config or CLI.",
        }

    url_ids = extract_nct_ids(registry_url or "")
    if len(url_ids) == 1:
        return {
            "registry_id": url_ids[0],
            "registry_id_source": "config_registry_url",
            "resolution_status": "resolved",
            "resolution_message": "Using NCT ID parsed from registry URL.",
        }
    if len(url_ids) > 1:
        return {
            "registry_id": "",
            "registry_id_source": "config_registry_url",
            "resolution_status": "ambiguous",
            "resolution_message": "Multiple NCT IDs found in registry URL.",
        }

    discovered = sorted(set(extract_nct_ids(report_text)).union(extract_nct_ids(protocol_text)))
    if len(discovered) == 1:
        return {
            "registry_id": discovered[0],
            "registry_id_source": "source_text",
            "resolution_status": "resolved",
            "resolution_message": "Using unique NCT ID parsed from report/protocol text.",
        }
    if len(discovered) > 1:
        return {
            "registry_id": "",
            "registry_id_source": "source_text",
            "resolution_status": "ambiguous",
            "resolution_message": "Multiple NCT IDs found in report/protocol text.",
        }

    other_ids = sorted(
        set(extract_registry_ids(report_text)).union(extract_registry_ids(protocol_text))
    )
    return {
        "registry_id": explicit or "",
        "registry_id_source": "not_found" if not other_ids else "non_clinicaltrials_registry",
        "resolution_status": "not_assessed",
        "resolution_message": "No ClinicalTrials.gov NCT ID found."
        if not other_ids
        else f"Only non-ClinicalTrials.gov registry IDs found: {'|'.join(other_ids)}.",
    }


def fetch_current_record(
    *,
    study_id: str,
    registry_id: str,
    registry_id_source: str,
    registry_url: str | None,
    current_json_path: Path | None,
    allow_network: bool,
    timeout_seconds: int = 30,
) -> RegistryFetchResult:
    """Load a ClinicalTrials.gov current record from local JSON or API v2."""

    fetched_at = datetime.now(tz=UTC).isoformat()
    api_url = f"{CLINICALTRIALS_API_BASE}/studies/{registry_id}" if registry_id else ""
    metadata = {
        "study_id": study_id,
        "registry_id": registry_id,
        "registry_id_source": registry_id_source,
        "registry_url": registry_url or "",
        "registry_current_source": str(current_json_path)
        if current_json_path
        else "clinicaltrials_api_v2",
        "allow_network": allow_network,
        "fetch_status": "not_assessed",
        "fetch_message": "No ClinicalTrials.gov NCT ID available.",
        "api_url": api_url,
        "fetched_at": fetched_at,
        "source_version": "not_available",
        "source_sha256": "",
    }

    if not registry_id.startswith("NCT"):
        return RegistryFetchResult(None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS))

    if current_json_path is not None:
        metadata["registry_current_source"] = str(current_json_path)
        metadata["source_version"] = "local_json_unverified_version"
        if not current_json_path.exists():
            metadata["fetch_status"] = "missing_local_json"
            metadata["fetch_message"] = f"Missing registry JSON: {current_json_path}"
            return RegistryFetchResult(
                None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS)
            )
        try:
            raw_record = current_json_path.read_bytes()
            record = json.loads(raw_record)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            metadata["fetch_status"] = "local_parse_failed"
            metadata["fetch_message"] = f"Could not read local registry JSON: {exc}"
            return RegistryFetchResult(
                None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS)
            )
        metadata["source_sha256"] = hashlib.sha256(raw_record).hexdigest()
        metadata["fetch_status"] = "loaded_local_json"
        metadata["fetch_message"] = "Loaded current registry record from local JSON."
        return RegistryFetchResult(
            record,
            pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS),
            raw_json=raw_record,
        )

    if not allow_network:
        metadata["fetch_status"] = "network_disabled"
        metadata["fetch_message"] = "Network fetch disabled and no local registry JSON supplied."
        return RegistryFetchResult(None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS))

    try:
        metadata["source_version"] = "ClinicalTrials.gov API v2"
        with urllib.request.urlopen(api_url, timeout=timeout_seconds) as response:
            raw_record = response.read()
            record = json.loads(raw_record)
    except urllib.error.HTTPError as exc:
        metadata["fetch_status"] = "record_not_found" if exc.code == 404 else "fetch_failed"
        if exc.code == 404:
            metadata["fetch_message"] = (
                f"ClinicalTrials.gov returned HTTP 404 for registry ID {registry_id}."
            )
        else:
            metadata["fetch_message"] = (
                f"ClinicalTrials.gov fetch failed: HTTP {exc.code}: {exc.reason}"
            )
        return RegistryFetchResult(None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        metadata["fetch_status"] = "fetch_failed"
        metadata["fetch_message"] = f"ClinicalTrials.gov fetch failed: {exc}"
        return RegistryFetchResult(None, pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS))

    metadata["fetch_status"] = "fetched_api_v2"
    metadata["source_sha256"] = hashlib.sha256(raw_record).hexdigest()
    metadata["fetch_message"] = "Fetched current registry record from ClinicalTrials.gov API v2."
    return RegistryFetchResult(
        record,
        pd.DataFrame([metadata], columns=FETCH_METADATA_COLUMNS),
        raw_json=raw_record,
    )


def normalize_current_record(
    *,
    study_id: str,
    record: Mapping[str, Any] | None,
    registry_source: str,
) -> pd.DataFrame:
    """Normalize a ClinicalTrials.gov current record into one stable row."""

    if not record:
        return _empty_current_record()

    protocol = record.get("protocolSection", {}) if isinstance(record, Mapping) else {}
    identification = _get_path(protocol, ["identificationModule"], {})
    status = _get_path(protocol, ["statusModule"], {})
    design = _get_path(protocol, ["designModule"], {})
    design_info = _get_path(design, ["designInfo"], {})
    masking_info = _get_path(design_info, ["maskingInfo"], {})
    enrollment = _get_path(design, ["enrollmentInfo"], {})
    outcomes = _get_path(protocol, ["outcomesModule"], {})
    arms_interventions = _get_path(protocol, ["armsInterventionsModule"], {})
    references = _get_path(protocol, ["referencesModule"], {})

    row = {
        "study_id": study_id,
        "registry_id": _first_text(_get_path(identification, ["nctId"])),
        "registry_source": registry_source,
        "official_title": _first_text(_get_path(identification, ["officialTitle"])),
        "brief_title": _first_text(_get_path(identification, ["briefTitle"])),
        "study_type": _first_text(_get_path(design, ["studyType"])),
        "overall_status": _first_text(_get_path(status, ["overallStatus"])),
        "start_date": _date_from_struct(_get_path(status, ["startDateStruct"])),
        "registered_start_date": _date_from_struct(_get_path(status, ["startDateStruct"])),
        "start_date_type": _first_text(_get_path(status, ["startDateStruct", "type"])),
        "actual_recruitment_start_date": (
            _date_from_struct(_get_path(status, ["startDateStruct"]))
            if _first_text(_get_path(status, ["startDateStruct", "type"])).upper() == "ACTUAL"
            else ""
        ),
        "first_submitted_date": _first_text(_get_path(status, ["studyFirstSubmitDate"])),
        "study_first_posted_date": _date_from_struct(
            _get_path(status, ["studyFirstPostDateStruct"])
        ),
        "primary_completion_date": _date_from_struct(
            _get_path(status, ["primaryCompletionDateStruct"])
        ),
        "completion_date": _date_from_struct(_get_path(status, ["completionDateStruct"])),
        "results_first_posted_date": _date_from_struct(
            _get_path(status, ["resultsFirstPostDateStruct"])
        ),
        "has_results": bool(record.get("hasResults", False)),
        "enrollment_count": _first_text(_get_path(enrollment, ["count"])),
        "enrollment_type": _first_text(_get_path(enrollment, ["type"])),
        "allocation": _first_text(_get_path(design_info, ["allocation"])),
        "intervention_model": _first_text(_get_path(design_info, ["interventionModel"])),
        "masking": _first_text(_get_path(masking_info, ["masking"])),
        "primary_outcomes": _outcome_text(_get_path(outcomes, ["primaryOutcomes"], [])),
        "secondary_outcomes": _outcome_text(_get_path(outcomes, ["secondaryOutcomes"], [])),
        "arms": _arm_text(_get_path(arms_interventions, ["armGroups"], [])),
        "interventions": _intervention_text(_get_path(arms_interventions, ["interventions"], [])),
        "references": _reference_text(_get_path(references, ["references"], [])),
    }
    return pd.DataFrame([row], columns=CURRENT_RECORD_COLUMNS)


def _parse_registry_date_interval(value: object) -> RegistryDateInterval | None:
    text = _first_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
        return RegistryDateInterval(start=parsed, end=parsed, precision="day", raw=text)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        parsed = datetime.strptime(text, "%Y-%m").date()
        last_day = monthrange(parsed.year, parsed.month)[1]
        return RegistryDateInterval(
            start=parsed,
            end=date(parsed.year, parsed.month, last_day),
            precision="month",
            raw=text,
        )
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        return RegistryDateInterval(
            start=date(year, 1, 1),
            end=date(year, 12, 31),
            precision="year",
            raw=text,
        )
    return None


def _partial_precision_note(*intervals: tuple[str, RegistryDateInterval | None]) -> str:
    partial = [
        f"{label}_precision={interval.precision}"
        for label, interval in intervals
        if interval is not None and interval.precision != "day"
    ]
    if not partial:
        return ""
    return " Partial date precision: " + "; ".join(partial) + "."


def _claim_row(
    *,
    trial_id: str,
    claim_id: str,
    claim_category: str,
    source: str,
    report_value: object = "",
    protocol_value: object = "",
    registry_value: object = "",
    match_status: bool | None = None,
    assessment_status: str | None = None,
    severity: str = "info",
    notes: str = "",
    page_ref: object = "",
    registry_field: str = "",
    screen_status: str = "",
    report_evidence: object = "",
    protocol_evidence: object = "",
    report_negated: object = pd.NA,
    protocol_negated: object = pd.NA,
    population: str = "",
    role: str = "",
) -> dict[str, object]:
    if assessment_status is None:
        if match_status is True:
            assessment_status = "match"
        elif match_status is False:
            assessment_status = "mismatch"
        else:
            assessment_status = "indeterminate"
    return {
        "schema_version": "registration_claims_v2",
        "trial_id": trial_id,
        "claim_id": claim_id,
        "claim_category": claim_category,
        "source": source,
        "report_value": _first_text(report_value),
        "protocol_value": _first_text(protocol_value),
        "registry_value": _first_text(registry_value),
        "match_status": match_status if match_status is not None else pd.NA,
        "assessment_status": assessment_status,
        "severity": severity,
        "notes": notes,
        "page_ref": _first_text(page_ref),
        "registry_field": registry_field,
        "screen_status": screen_status,
        "report_evidence": _first_text(report_evidence),
        "protocol_evidence": _first_text(protocol_evidence),
        "report_negated": report_negated,
        "protocol_negated": protocol_negated,
        "population": population,
        "role": role,
    }


def legacy_claims_to_expanded(legacy_claims: pd.DataFrame) -> pd.DataFrame:
    """Convert legacy report-vs-protocol claims to the expanded claim schema."""

    if legacy_claims.empty:
        return empty_expanded_claims()

    rows: list[dict[str, object]] = []
    for row in legacy_claims.to_dict("records"):
        raw_match_value = row.get("match_status")
        match_value = None if _is_missing_scalar(raw_match_value) else bool(raw_match_value)
        page_ref = "report_page={}; protocol_page={}".format(
            _first_text(row.get("evidence_page_report")),
            _first_text(row.get("evidence_page_protocol")),
        )
        rows.append(
            _claim_row(
                trial_id=_first_text(row.get("trial_id")),
                claim_id=_first_text(row.get("claim")),
                claim_category="report_protocol",
                source="report_vs_protocol",
                report_value=row.get("report_value", ""),
                protocol_value=row.get("protocol_value", ""),
                registry_value="",
                match_status=match_value,
                assessment_status=(
                    "indeterminate"
                    if match_value is None
                    else ("match" if match_value else "mismatch")
                ),
                severity="medium" if match_value is False else "info",
                notes="Legacy report/protocol congruence claim.",
                page_ref=page_ref,
                registry_field="",
                report_evidence=row.get("report_evidence", ""),
                protocol_evidence=row.get("protocol_evidence", ""),
                report_negated=row.get("report_negated", pd.NA),
                protocol_negated=row.get("protocol_negated", pd.NA),
                population=_first_text(row.get("population")),
                role=_first_text(row.get("role")),
            )
        )
    return pd.DataFrame(rows, columns=EXPANDED_CLAIM_COLUMNS)


def _contains_exact_or_token_overlap(text: str, target: str, *, min_overlap: float = 0.75) -> bool:
    normalized_text = normalize_text(text)
    normalized_target = normalize_text(target)
    if not normalized_target:
        return False
    if normalized_target in normalized_text:
        return True
    target_tokens = {
        token for token in re.findall(r"[a-z0-9]+", normalized_target) if len(token) > 3
    }
    text_tokens = {token for token in re.findall(r"[a-z0-9]+", normalized_text) if len(token) > 3}
    if not target_tokens:
        return False
    return len(target_tokens.intersection(text_tokens)) / len(target_tokens) >= min_overlap


def _extract_enrollment_candidates(text: str) -> list[str]:
    patterns = [
        r"\bn\s*=\s*(\d{1,6})\b",
        r"\b(\d{1,6})\s+(?:patients|participants|subjects|individuals)\b",
        r"\benroll(?:ed|ment)?\D{0,30}(\d{1,6})\b",
        r"\brandomi[sz]ed\D{0,30}(\d{1,6})\b",
    ]
    values: set[str] = set()
    for pattern in patterns:
        values.update(re.findall(pattern, text, flags=re.IGNORECASE))
    return sorted(values, key=lambda value: int(value))


def _publication_link_found(
    references: str, *, doi: str | None, pmid: str | None, url: str | None
) -> bool | None:
    if not any([doi, pmid, url]):
        return None
    normalized_refs = normalize_text(references)
    if doi and normalize_text(doi) in normalized_refs:
        return True
    if pmid and re.search(rf"\b{re.escape(_first_text(pmid))}\b", references):
        return True
    if url and normalize_text(url) in normalized_refs:
        return True
    return False


def derive_clinicaltrials_claims(
    *,
    trial_id: str,
    report_text: str,
    protocol_text: str,
    current_record: pd.DataFrame,
    fetch_metadata: pd.DataFrame,
    registry_resolution: Mapping[str, str],
    publication_doi: str | None = None,
    publication_pmid: str | None = None,
    publication_url: str | None = None,
    as_of_date: date | None = None,
) -> pd.DataFrame:
    """Derive conservative ClinicalTrials.gov screening claims."""

    rows: list[dict[str, object]] = []
    as_of = as_of_date or date.today()
    registry_id = _first_text(registry_resolution.get("registry_id"))
    resolution_message = _first_text(registry_resolution.get("resolution_message"))
    fetch_status = ""
    fetch_message = ""
    if not fetch_metadata.empty:
        fetch_status = _first_text(fetch_metadata.iloc[0].get("fetch_status"))
        fetch_message = _first_text(fetch_metadata.iloc[0].get("fetch_message"))

    if current_record.empty:
        status = "not_assessed"
        rows.append(
            _claim_row(
                trial_id=trial_id,
                claim_id="clinicaltrials_current_record_available",
                claim_category="registry_availability",
                source="clinicaltrials_api_v2",
                registry_value=registry_id,
                match_status=None,
                assessment_status=status,
                severity="info",
                notes=f"fetch_status={fetch_status or 'not_attempted'}; "
                f"{fetch_message or resolution_message}",
                registry_field="protocolSection",
            )
        )
        return pd.DataFrame(rows, columns=EXPANDED_CLAIM_COLUMNS)

    record = current_record.iloc[0].to_dict()
    combined_text = f"{report_text}\n{protocol_text}"
    registry_id = _first_text(record.get("registry_id")) or registry_id
    report_ids = extract_nct_ids(report_text)
    protocol_ids = extract_nct_ids(protocol_text)
    text_ids = sorted(set(report_ids).union(protocol_ids))
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_registry_id_consistency",
            claim_category="registry_current",
            source="report_protocol_registry",
            report_value="|".join(report_ids),
            protocol_value="|".join(protocol_ids),
            registry_value=registry_id,
            match_status=registry_id in text_ids if text_ids else None,
            assessment_status=None if text_ids else "indeterminate",
            severity="medium" if text_ids and registry_id not in text_ids else "info",
            notes="Compares NCT IDs extracted from source text with current registry record.",
            registry_field="identificationModule.nctId",
        )
    )

    start_date = _parse_registry_date_interval(
        record.get("registered_start_date") or record.get("start_date")
    )
    first_submitted = _parse_registry_date_interval(record.get("first_submitted_date"))
    prospective: bool | None = None
    if start_date and first_submitted:
        if first_submitted.end <= start_date.start:
            prospective = True
        elif first_submitted.start > start_date.end:
            prospective = False
    prospective_screen = (
        "prospective_timing_screen"
        if prospective is True
        else "potentially_retrospective_timing_screen"
        if prospective is False
        else "timing_indeterminate"
    )
    prospective_assessment = (
        "not_assessed" if start_date is None or first_submitted is None else "indeterminate"
    )
    prospective_note = "Compares first submission with registered start as a metadata screen; "
    prospective_note += "first-posted and actual recruitment dates are retained separately."
    prospective_note += _partial_precision_note(
        ("registered_start", start_date),
        ("first_submitted", first_submitted),
    )
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_prospective_registration",
            claim_category="registry_current",
            source="clinicaltrials_api_v2",
            registry_value="; ".join(
                [
                    f"first_submitted={record.get('first_submitted_date')}",
                    f"first_posted={record.get('study_first_posted_date')}",
                    "registered_start={}".format(
                        record.get("registered_start_date") or record.get("start_date")
                    ),
                    f"actual_recruitment_start={record.get('actual_recruitment_start_date')}",
                ]
            ),
            match_status=None,
            assessment_status=prospective_assessment,
            severity="info",
            notes=prospective_note,
            registry_field="statusModule.studyFirstSubmitDate|statusModule.studyFirstPostDateStruct|statusModule.startDateStruct",
        )
    )
    rows[-1]["screen_status"] = prospective_screen

    enrollment = _first_text(record.get("enrollment_count"))
    enrollment_candidates = _extract_enrollment_candidates(combined_text)
    enrollment_match = None
    enrollment_status = "indeterminate"
    notes = "No manuscript/protocol enrollment candidate was extracted."
    if enrollment and enrollment_candidates:
        enrollment_match = enrollment in enrollment_candidates
        enrollment_status = "match" if enrollment_match else "indeterminate"
        notes = (
            "Registry enrollment was found in source text."
            if enrollment_match
            else (
                "Registry enrollment was not found among extracted source-text candidates; "
                "not labeled mismatch because automatic enrollment extraction is broad."
            )
        )
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_enrollment_congruence",
            claim_category="registry_current",
            source="report_protocol_registry",
            report_value="|".join(enrollment_candidates),
            registry_value=f"{enrollment} ({record.get('enrollment_type')})" if enrollment else "",
            match_status=enrollment_match,
            assessment_status=enrollment_status,
            severity="info",
            notes=notes,
            registry_field="designModule.enrollmentInfo",
        )
    )

    for claim_id, field_name, label in [
        ("clinicaltrials_primary_outcome_congruence", "primary_outcomes", "primary outcomes"),
        ("clinicaltrials_secondary_outcome_congruence", "secondary_outcomes", "secondary outcomes"),
    ]:
        registry_value = _first_text(record.get(field_name))
        if not registry_value:
            match = None
            assessment = "not_assessed"
            notes = f"No registry {label} available in normalized record."
        else:
            first_measure = registry_value.split("|")[0].strip()
            match = _contains_exact_or_token_overlap(combined_text, first_measure)
            assessment = "match" if match else "indeterminate"
            notes = (
                f"First registry {label[:-1]} measure found in source text."
                if match
                else f"First registry {label[:-1]} measure not found by conservative text matching."
            )
        rows.append(
            _claim_row(
                trial_id=trial_id,
                claim_id=claim_id,
                claim_category="registry_current",
                source="report_protocol_registry",
                registry_value=registry_value,
                match_status=match,
                assessment_status=assessment,
                severity="info" if assessment != "indeterminate" else "medium",
                notes=notes,
                registry_field=f"outcomesModule.{field_name}",
            )
        )

    for claim_id, field_name, registry_field in [
        (
            "clinicaltrials_allocation_congruence",
            "allocation",
            "designModule.designInfo.allocation",
        ),
        ("clinicaltrials_masking_congruence", "masking", "designModule.designInfo.maskingInfo"),
        (
            "clinicaltrials_intervention_model_congruence",
            "intervention_model",
            "designModule.designInfo.interventionModel",
        ),
    ]:
        registry_value = _first_text(record.get(field_name))
        if not registry_value:
            match = None
            assessment = "not_assessed"
            notes = "Registry field unavailable."
        else:
            match = _contains_exact_or_token_overlap(combined_text, registry_value, min_overlap=1.0)
            assessment = "match" if match else "indeterminate"
            notes = (
                "Registry design term found in source text."
                if match
                else ("Registry design term was not found by conservative text matching.")
            )
        rows.append(
            _claim_row(
                trial_id=trial_id,
                claim_id=claim_id,
                claim_category="registry_current",
                source="report_protocol_registry",
                registry_value=registry_value,
                match_status=match,
                assessment_status=assessment,
                severity="info" if assessment != "indeterminate" else "medium",
                notes=notes,
                registry_field=registry_field,
            )
        )

    for claim_id, field_name, registry_field in [
        ("clinicaltrials_arms_congruence", "arms", "armsInterventionsModule.armGroups"),
        (
            "clinicaltrials_interventions_congruence",
            "interventions",
            "armsInterventionsModule.interventions",
        ),
    ]:
        registry_value = _first_text(record.get(field_name))
        if not registry_value:
            match = None
            assessment = "not_assessed"
            notes = "Registry field unavailable."
        else:
            first_label = registry_value.split("|")[0].strip()
            match = _contains_exact_or_token_overlap(combined_text, first_label)
            assessment = "match" if match else "indeterminate"
            notes = (
                "First registry label found in source text."
                if match
                else ("First registry label was not found by conservative text matching.")
            )
        rows.append(
            _claim_row(
                trial_id=trial_id,
                claim_id=claim_id,
                claim_category="registry_current",
                source="report_protocol_registry",
                registry_value=registry_value,
                match_status=match,
                assessment_status=assessment,
                severity="info" if assessment != "indeterminate" else "medium",
                notes=notes,
                registry_field=registry_field,
            )
        )

    has_results = bool(record.get("has_results")) or bool(
        _first_text(record.get("results_first_posted_date"))
    )
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_results_posted",
            claim_category="registry_current",
            source="clinicaltrials_api_v2",
            registry_value="; ".join(
                [
                    f"has_results={has_results}",
                    f"results_first_posted={record.get('results_first_posted_date')}",
                ]
            ),
            match_status=None,
            assessment_status="not_assessed",
            severity="info",
            notes=("Descriptive results-posting metadata; absence alone is not an assessment."),
            registry_field="hasResults|statusModule.resultsFirstPostDateStruct",
            screen_status="results_posted" if has_results else "results_not_detected",
        )
    )

    primary_completion = _parse_registry_date_interval(record.get("primary_completion_date"))
    overdue_screen = "not_assessed"
    overdue_note = (
        "Uses a 365-day metadata screen after primary completion when registry results are absent."
    )
    if has_results:
        overdue_screen = "results_posted"
        overdue_note = "Registry results are posted; overdue screen is not triggered."
    elif primary_completion is not None:
        earliest_due = primary_completion.start + timedelta(days=365)
        latest_due = primary_completion.end + timedelta(days=365)
        if as_of > latest_due:
            overdue_screen = "potentially_overdue"
        elif as_of <= earliest_due:
            overdue_screen = "not_yet_due"
        else:
            overdue_screen = "timing_indeterminate"
        overdue_note += _partial_precision_note(("primary_completion", primary_completion))
    elif record.get("primary_completion_date"):
        overdue_screen = "invalid_date"
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_results_overdue",
            claim_category="registry_current",
            source="clinicaltrials_api_v2",
            registry_value="; ".join(
                [
                    f"primary_completion={record.get('primary_completion_date')}",
                    f"as_of={as_of.isoformat()}",
                ]
            ),
            match_status=None,
            assessment_status=(
                "not_assessed"
                if overdue_screen in {"not_assessed", "invalid_date"}
                else "indeterminate"
            ),
            severity="info",
            notes=overdue_note,
            registry_field="statusModule.primaryCompletionDateStruct|hasResults",
        )
    )
    rows[-1]["screen_status"] = overdue_screen

    link_match = _publication_link_found(
        _first_text(record.get("references")),
        doi=publication_doi,
        pmid=publication_pmid,
        url=publication_url,
    )
    rows.append(
        _claim_row(
            trial_id=trial_id,
            claim_id="clinicaltrials_publication_linkage",
            claim_category="registry_current",
            source="clinicaltrials_api_v2",
            report_value="; ".join(
                part
                for part in [
                    f"doi={publication_doi}" if publication_doi else "",
                    f"pmid={publication_pmid}" if publication_pmid else "",
                    f"url={publication_url}" if publication_url else "",
                ]
                if part
            ),
            registry_value=record.get("references", ""),
            match_status=None,
            assessment_status="not_assessed" if link_match is None else "indeterminate",
            severity="info",
            notes=(
                "Metadata screen for whether supplied publication identifiers appear in "
                "registry references; non-detection does not establish absence or concern."
            ),
            registry_field="referencesModule.references",
        )
    )
    rows[-1]["screen_status"] = (
        "identifier_detected"
        if link_match is True
        else "not_detected"
        if link_match is False
        else "not_assessed"
    )

    if fetch_status:
        rows.append(
            _claim_row(
                trial_id=trial_id,
                claim_id="clinicaltrials_current_record_available",
                claim_category="registry_availability",
                source="clinicaltrials_api_v2",
                registry_value=registry_id,
                match_status=True,
                assessment_status="match",
                severity="info",
                notes=fetch_message,
                registry_field="protocolSection",
            )
        )

    return pd.DataFrame(rows, columns=EXPANDED_CLAIM_COLUMNS)


def _normalize_history_snapshots_from_json(
    *, study_id: str, registry_id: str, payload: Any
) -> pd.DataFrame:
    if isinstance(payload, Mapping):
        snapshots = payload.get("snapshots", [])
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        snapshots = payload
    else:
        snapshots = []

    rows: list[pd.DataFrame] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        snapshot_date = _first_text(
            snapshot.get("snapshot_date") or snapshot.get("version_date") or snapshot.get("date")
        )
        record = snapshot.get("record", snapshot)
        normalized = normalize_current_record(
            study_id=study_id,
            record=record if isinstance(record, Mapping) else None,
            registry_source="registry_history_local_json",
        )
        if normalized.empty:
            continue
        normalized["snapshot_date"] = snapshot_date
        normalized["registry_id"] = normalized["registry_id"].replace("", registry_id)
        rows.append(normalized)
    if not rows:
        return pd.DataFrame(columns=["snapshot_date", *CURRENT_RECORD_COLUMNS])
    return pd.concat(rows, ignore_index=True)


def _events_from_snapshot_rows(
    *, study_id: str, registry_id: str, snapshots: pd.DataFrame
) -> pd.DataFrame:
    if snapshots.empty or "snapshot_date" not in snapshots.columns:
        return empty_history_events()
    dated_rows = []
    for index, row in snapshots.iterrows():
        interval = _parse_registry_date_interval(row.get("snapshot_date"))
        if interval is not None:
            dated_rows.append((interval, index, row))
    dated_rows.sort(key=lambda item: (item[0].start, item[0].end))
    rows: list[dict[str, object]] = []
    for field in TRACKED_HISTORY_FIELDS:
        if field not in snapshots.columns:
            continue
        previous_value: str | None = None
        previous_date = ""
        previous_interval: RegistryDateInterval | None = None
        for current_interval, _, row in dated_rows:
            current_value = _first_text(row.get(field))
            current_date = _first_text(row.get("snapshot_date"))
            if previous_value is None:
                previous_value = current_value
                previous_date = current_date
                previous_interval = current_interval
                continue
            if previous_interval is not None and previous_interval.end >= current_interval.start:
                previous_value = current_value
                previous_date = current_date
                previous_interval = current_interval
                continue
            if current_value != previous_value:
                rows.append(
                    {
                        "study_id": study_id,
                        "registry_id": registry_id or _first_text(row.get("registry_id")),
                        "event_id": f"history_{len(rows) + 1:03d}",
                        "event_date": current_date,
                        "registry_field": field,
                        "old_value": previous_value,
                        "new_value": current_value,
                        "change_type": "value_changed",
                        "severity": "medium"
                        if field in {"primary_outcomes", "enrollment_count"}
                        else "info",
                        "notes": f"Changed after snapshot dated {previous_date}.",
                    }
                )
            previous_value = current_value
            previous_date = current_date
            previous_interval = current_interval
    if not rows:
        return empty_history_events()
    return pd.DataFrame(rows, columns=HISTORY_EVENT_COLUMNS)


def build_history_events(
    *, study_id: str, registry_id: str, history_path: Path | None
) -> pd.DataFrame:
    """Build dated registry-history change events from an optional local file."""

    if history_path is None or not history_path.exists():
        return empty_history_events()

    if history_path.suffix.lower() == ".json":
        try:
            with history_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return empty_history_events()
        snapshots = _normalize_history_snapshots_from_json(
            study_id=study_id, registry_id=registry_id, payload=payload
        )
        return _events_from_snapshot_rows(
            study_id=study_id, registry_id=registry_id, snapshots=snapshots
        )

    try:
        history = pd.read_csv(history_path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return empty_history_events()
    if {"snapshot_date", "registry_field", "registry_value"}.issubset(history.columns):
        rows: list[dict[str, object]] = []
        history = history.copy()
        history["_date_interval"] = history["snapshot_date"].map(_parse_registry_date_interval)
        history = history[history["_date_interval"].notna()].copy()
        history["_date_start"] = history["_date_interval"].map(lambda value: value.start)
        history["_date_end"] = history["_date_interval"].map(lambda value: value.end)
        for field, group in history.sort_values(["_date_start", "_date_end"]).groupby(
            "registry_field"
        ):
            previous_value: str | None = None
            previous_date = ""
            previous_interval: RegistryDateInterval | None = None
            for _, row in group.iterrows():
                current_value = _first_text(row.get("registry_value"))
                current_date = _first_text(row.get("snapshot_date"))
                current_interval = row.get("_date_interval")
                if previous_value is None:
                    previous_value = current_value
                    previous_date = current_date
                    previous_interval = current_interval
                    continue
                if (
                    previous_interval is not None
                    and previous_interval.end >= current_interval.start
                ):
                    previous_value = current_value
                    previous_date = current_date
                    previous_interval = current_interval
                    continue
                if current_value != previous_value:
                    rows.append(
                        {
                            "study_id": study_id,
                            "registry_id": registry_id,
                            "event_id": f"history_{len(rows) + 1:03d}",
                            "event_date": current_date,
                            "registry_field": field,
                            "old_value": previous_value,
                            "new_value": current_value,
                            "change_type": "value_changed",
                            "severity": "medium"
                            if field in {"primary_outcomes", "enrollment_count"}
                            else "info",
                            "notes": f"Changed after snapshot dated {previous_date}.",
                        }
                    )
                previous_value = current_value
                previous_date = current_date
                previous_interval = current_interval
        if not rows:
            return empty_history_events()
        return pd.DataFrame(rows, columns=HISTORY_EVENT_COLUMNS)

    return _events_from_snapshot_rows(study_id=study_id, registry_id=registry_id, snapshots=history)


def build_history_status(
    *, history_path: Path | None, events: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Report supplied history, usable dates, detected events, and source hash separately."""

    base: dict[str, object] = {
        "history_status": "not_supplied",
        "history_completeness": "unknown",
        "chronology_status": "not_assessed",
        "history_path_supplied": bool(history_path),
        "history_sha256": "",
        "snapshots_supplied": 0,
        "dated_snapshots": 0,
        "undated_snapshots": 0,
        "change_events_detected": len(events) if events is not None else 0,
    }
    if history_path is None:
        return pd.DataFrame([base], columns=HISTORY_STATUS_COLUMNS)
    if not history_path.exists():
        base["history_status"] = "missing_input"
        return pd.DataFrame([base], columns=HISTORY_STATUS_COLUMNS)
    try:
        raw = history_path.read_bytes()
        base["history_sha256"] = hashlib.sha256(raw).hexdigest()
        if history_path.suffix.lower() == ".json":
            payload = json.loads(raw)
            if isinstance(payload, Mapping):
                if "snapshots" not in payload or not isinstance(payload["snapshots"], list):
                    base["history_status"] = "invalid_structure"
                    return pd.DataFrame([base], columns=HISTORY_STATUS_COLUMNS)
                snapshots = payload["snapshots"]
            elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
                snapshots = payload
            else:
                snapshots = []
            dates = [
                _first_text(
                    item.get("snapshot_date") or item.get("version_date") or item.get("date")
                )
                for item in snapshots
                if isinstance(item, Mapping)
            ]
        else:
            history = pd.read_csv(history_path)
            required_long = {"snapshot_date", "registry_field", "registry_value"}
            wide_fields = set(TRACKED_HISTORY_FIELDS).intersection(history.columns)
            if "snapshot_date" not in history.columns or not (
                required_long.issubset(history.columns) or wide_fields
            ):
                base["history_status"] = "invalid_structure"
                return pd.DataFrame([base], columns=HISTORY_STATUS_COLUMNS)
            dates = [_first_text(value) for value in history["snapshot_date"].drop_duplicates()]
        parsed = [_parse_registry_date_interval(value) for value in dates]
        dated = sum(value is not None for value in parsed)
        undated = len(dates) - dated
        base["snapshots_supplied"] = len(dates)
        base["dated_snapshots"] = dated
        base["undated_snapshots"] = undated
        if not dates:
            base["history_status"] = "empty"
            base["chronology_status"] = "not_assessed"
        elif dated == 0:
            base["history_status"] = "unusable_undated"
            base["chronology_status"] = "not_assessed"
        elif undated:
            base["history_status"] = "partially_usable"
            base["chronology_status"] = "partially_assessed"
        else:
            base["history_status"] = "usable"
            ordered = sorted(
                (value for value in parsed if value is not None),
                key=lambda value: (value.start, value.end),
            )
            overlaps = any(
                left.end >= right.start for left, right in zip(ordered, ordered[1:], strict=False)
            )
            base["chronology_status"] = "ambiguous_overlap" if overlaps else "ordered"
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ):
        base["history_status"] = "parse_failed"
    return pd.DataFrame([base], columns=HISTORY_STATUS_COLUMNS)
