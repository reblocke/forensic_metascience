"""Registration and protocol-congruence helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd

CLAIM_COLUMNS = [
    "schema_version",
    "trial_id",
    "claim",
    "report_value",
    "protocol_value",
    "match_status",
    "assessment_status",
    "evidence_page_report",
    "evidence_page_protocol",
    "report_evidence",
    "protocol_evidence",
    "report_negated",
    "protocol_negated",
    "population",
    "role",
    "extract_confidence",
]


def normalize_text(value: str) -> str:
    """Normalize whitespace and lowercase text."""

    normalized = value or ""
    for old, new in {
        "\u00ad": "",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
    }.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip().lower()


def extract_registry_ids(text: str) -> list[str]:
    """Extract common trial registry identifiers from text."""

    patterns = [
        r"\bNCT\d{8}\b",
        r"\bISRCTN\d{8}\b",
        r"\bChiCTR[-_]?[A-Za-z0-9]+\b",
        r"\bEUCTR\d{4}-\d{6}-\d{2}\b",
    ]
    ids: set[str] = set()
    for pattern in patterns:
        ids.update(re.findall(pattern, text, flags=re.IGNORECASE))
    return sorted(identifier.upper() for identifier in ids)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", text) if part.strip()]


def _allocation_evidence(page_texts: Sequence[str]) -> tuple[str, int | None, str, bool | None]:
    ratio_re = re.compile(r"\b(\d{1,3})\s*:\s*(\d{1,3})\b")
    context_re = re.compile(r"\b(allocation|allocated|randomi[sz]ed|assigned|arms?|ratio)\b", re.I)
    for page, text in enumerate(page_texts, start=1):
        for sentence in _sentences(text):
            for match in ratio_re.finditer(sentence):
                nearby = sentence[max(0, match.start() - 24) : match.end() + 24]
                if not context_re.search(nearby):
                    continue
                negated = bool(
                    re.search(
                        r"\b(?:not|no|never|without)\b.{0,30}\b(?:allocation|ratio|randomi[sz]ed|allocated|assigned)\b",
                        sentence,
                        re.I,
                    )
                )
                return f"{match.group(1)}:{match.group(2)}", page, sentence, negated
    return "", None, "", None


def _claim_evidence(
    page_texts: Sequence[str],
    *,
    patterns: Sequence[tuple[str, str]],
) -> tuple[str, int | None, str, bool | None]:
    for page, text in enumerate(page_texts, start=1):
        for sentence in _sentences(text):
            for pattern, value in patterns:
                match = re.search(pattern, sentence, flags=re.IGNORECASE)
                if match:
                    prefix = sentence[max(0, match.start() - 35) : match.start()]
                    negated = value.startswith("not_") or bool(
                        re.search(
                            r"\b(?:not|no|never|without|neither)\b[^.!?;]{0,35}$", prefix, re.I
                        )
                    )
                    return value, page, sentence, negated
    return "", None, "", None


def _comparison(report_value: str, protocol_value: str) -> tuple[bool | None, str]:
    if not report_value or not protocol_value:
        return None, "indeterminate"
    matches = report_value == protocol_value
    return matches, "match" if matches else "mismatch"


def _row(
    *,
    trial_id: str,
    claim: str,
    report_value: str = "",
    protocol_value: str = "",
    report_page: int | None = None,
    protocol_page: int | None = None,
    report_evidence: str = "",
    protocol_evidence: str = "",
    report_negated: bool | None = None,
    protocol_negated: bool | None = None,
    population: str = "",
    role: str = "",
    extract_confidence: str = "medium",
) -> dict[str, object]:
    compared_report = report_value
    compared_protocol = protocol_value
    if claim == "blinding_role":
        if compared_report in {"open_label", "not_blinded"}:
            compared_report = "not_blinded"
        if compared_protocol in {"open_label", "not_blinded"}:
            compared_protocol = "not_blinded"
    match_status, assessment_status = _comparison(compared_report, compared_protocol)
    if report_negated is True or protocol_negated is True:
        match_status, assessment_status = None, "indeterminate"
    return {
        "schema_version": "registration_source_claims_v3",
        "trial_id": trial_id,
        "claim": claim,
        "report_value": report_value,
        "protocol_value": protocol_value,
        "match_status": match_status if match_status is not None else pd.NA,
        "assessment_status": assessment_status,
        "evidence_page_report": report_page if report_page is not None else pd.NA,
        "evidence_page_protocol": protocol_page if protocol_page is not None else pd.NA,
        "report_evidence": report_evidence,
        "protocol_evidence": protocol_evidence,
        "report_negated": report_negated if report_negated is not None else pd.NA,
        "protocol_negated": protocol_negated if protocol_negated is not None else pd.NA,
        "population": population,
        "role": role,
        "extract_confidence": extract_confidence,
    }


def derive_registration_claims(
    *,
    trial_id: str,
    report_page_texts: Sequence[str],
    protocol_page_texts: Sequence[str],
) -> pd.DataFrame:
    """Extract source-linked registration claims without treating absence as a negative."""

    report_text = "\n".join(report_page_texts)
    protocol_text = "\n".join(protocol_page_texts)
    report_ids, protocol_ids = (
        extract_registry_ids(report_text),
        extract_registry_ids(protocol_text),
    )
    report_ratio = _allocation_evidence(report_page_texts)
    protocol_ratio = _allocation_evidence(protocol_page_texts)
    rows = [
        _row(
            trial_id=trial_id,
            claim="registry_id_overlap",
            report_value="|".join(report_ids),
            protocol_value="|".join(protocol_ids),
            report_page=next(
                (i for i, t in enumerate(report_page_texts, 1) if extract_registry_ids(t)), None
            ),
            protocol_page=next(
                (i for i, t in enumerate(protocol_page_texts, 1) if extract_registry_ids(t)), None
            ),
            report_evidence=next((t for t in report_page_texts if extract_registry_ids(t)), ""),
            protocol_evidence=next((t for t in protocol_page_texts if extract_registry_ids(t)), ""),
            extract_confidence="high",
        ),
        _row(
            trial_id=trial_id,
            claim="allocation_ratio",
            report_value=report_ratio[0],
            protocol_value=protocol_ratio[0],
            report_page=report_ratio[1],
            protocol_page=protocol_ratio[1],
            report_evidence=report_ratio[2],
            protocol_evidence=protocol_ratio[2],
            report_negated=report_ratio[3],
            protocol_negated=protocol_ratio[3],
            population="trial participants",
            extract_confidence="medium",
        ),
    ]

    negated_randomization = (
        r"\b(?:no|without)\s+randomi[sz]ation\b"
        r"|\brandomi[sz]ation\s+(?:was\s+)?not\b"
        r"|\b(?:not|never)\s+(?:randomi[sz]ed|randomly assigned)\b"
    )
    random_patterns = [
        (negated_randomization, "not_randomized"),
        (r"\b(?:randomi[sz]ed|randomly assigned|randomi[sz]ation)\b", "randomized"),
    ]
    report_random = _claim_evidence(report_page_texts, patterns=random_patterns)
    protocol_random = _claim_evidence(protocol_page_texts, patterns=random_patterns)
    rows.append(
        _row(
            trial_id=trial_id,
            claim="randomization_phrase",
            report_value=report_random[0],
            protocol_value=protocol_random[0],
            report_page=report_random[1],
            protocol_page=protocol_random[1],
            report_evidence=report_random[2],
            protocol_evidence=protocol_random[2],
            report_negated=report_random[3],
            protocol_negated=protocol_random[3],
            population="trial participants",
            extract_confidence="medium",
        )
    )

    role_patterns = {
        "treatment": [
            (r"\bopen[- ]label(?:ed)?\b", "open_label"),
            (r"\b(?:treatment|intervention) (?:was )?not blinded\b", "not_blinded"),
            (r"\b(?:treatment|intervention) (?:was )?(?:blinded|masked)\b", "blinded"),
        ],
        "participants": [
            (r"\bparticipants? (?:were )?not (?:blinded|masked)\b", "not_blinded"),
            (r"\bparticipants? (?:were )?(?:blinded|masked)\b", "blinded"),
        ],
        "care_providers": [
            (
                r"\b(?:clinicians|care providers|investigators) (?:were )?not blinded\b",
                "not_blinded",
            ),
            (
                r"\b(?:clinicians|care providers|investigators) (?:were )?(?:blinded|masked)\b",
                "blinded",
            ),
        ],
        "outcome_assessors": [
            (r"\b(?:outcome assessors?|assessors?) (?:were )?not blinded\b", "not_blinded"),
            (r"\b(?:outcome assessors?|assessors?) (?:were )?(?:blinded|masked)\b", "blinded"),
        ],
    }
    for role, patterns in role_patterns.items():
        report_blind = _claim_evidence(report_page_texts, patterns=patterns)
        protocol_blind = _claim_evidence(protocol_page_texts, patterns=patterns)
        rows.append(
            _row(
                trial_id=trial_id,
                claim="blinding_role",
                report_value=report_blind[0],
                protocol_value=protocol_blind[0],
                report_page=report_blind[1],
                protocol_page=protocol_blind[1],
                report_evidence=report_blind[2],
                protocol_evidence=protocol_blind[2],
                report_negated=report_blind[3],
                protocol_negated=protocol_blind[3],
                population="trial participants",
                role=role,
                extract_confidence="medium",
            )
        )

    return pd.DataFrame(rows, columns=CLAIM_COLUMNS)
