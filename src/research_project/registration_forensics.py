"""Registration and protocol-congruence helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd


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


def extract_allocation_ratio(text: str) -> str | None:
    """Extract allocation ratio pattern like 1:1 from text."""

    match = re.search(r"\b(\d+)\s*:\s*(\d+)\b", text)
    if not match:
        return None
    return f"{match.group(1)}:{match.group(2)}"


def first_page_with_phrase(page_texts: Sequence[str], phrase: str) -> int | None:
    """Return the first page index (1-based) containing a phrase."""

    needle = normalize_text(phrase)
    for index, text in enumerate(page_texts, start=1):
        if needle in normalize_text(text):
            return index
    return None


def first_page_with_any_phrase(page_texts: Sequence[str], phrases: Sequence[str]) -> int | None:
    """Return the first page index (1-based) containing any phrase."""

    for phrase in phrases:
        page = first_page_with_phrase(page_texts, phrase)
        if page is not None:
            return page
    return None


def derive_registration_claims(
    *,
    trial_id: str,
    report_page_texts: Sequence[str],
    protocol_page_texts: Sequence[str],
) -> pd.DataFrame:
    """Build claim-level congruence table for report versus protocol."""

    report_text = "\n".join(report_page_texts)
    protocol_text = "\n".join(protocol_page_texts)

    report_ids = extract_registry_ids(report_text)
    protocol_ids = extract_registry_ids(protocol_text)
    ratio_report = extract_allocation_ratio(report_text)
    ratio_protocol = extract_allocation_ratio(protocol_text)
    randomization_phrases = ["randomization", "randomisation", "randomly assigned"]
    blinding_phrases = ["blind", "blinded", "masked", "masking", "open-label"]

    claims = [
        {
            "trial_id": trial_id,
            "claim": "registry_id_overlap",
            "report_value": "|".join(report_ids),
            "protocol_value": "|".join(protocol_ids),
            "match_status": bool(set(report_ids).intersection(protocol_ids)),
            "evidence_page_report": first_page_with_any_phrase(
                report_page_texts, report_ids or protocol_ids
            ),
            "evidence_page_protocol": first_page_with_any_phrase(
                protocol_page_texts, protocol_ids or report_ids
            ),
            "extract_confidence": "medium",
        },
        {
            "trial_id": trial_id,
            "claim": "allocation_ratio",
            "report_value": ratio_report or "",
            "protocol_value": ratio_protocol or "",
            "match_status": ratio_report is not None and ratio_report == ratio_protocol,
            "evidence_page_report": first_page_with_phrase(report_page_texts, "1:1"),
            "evidence_page_protocol": first_page_with_phrase(protocol_page_texts, "1:1"),
            "extract_confidence": "medium",
        },
        {
            "trial_id": trial_id,
            "claim": "randomization_phrase",
            "report_value": "present"
            if first_page_with_any_phrase(report_page_texts, randomization_phrases) is not None
            else "missing",
            "protocol_value": "present"
            if first_page_with_any_phrase(protocol_page_texts, randomization_phrases) is not None
            else "missing",
            "match_status": (
                first_page_with_any_phrase(report_page_texts, randomization_phrases) is not None
                and first_page_with_any_phrase(protocol_page_texts, randomization_phrases)
                is not None
            ),
            "evidence_page_report": first_page_with_any_phrase(
                report_page_texts, randomization_phrases
            ),
            "evidence_page_protocol": first_page_with_any_phrase(
                protocol_page_texts, randomization_phrases
            ),
            "extract_confidence": "high",
        },
        {
            "trial_id": trial_id,
            "claim": "blinding_phrase",
            "report_value": "present"
            if first_page_with_any_phrase(report_page_texts, blinding_phrases) is not None
            else "missing",
            "protocol_value": "present"
            if first_page_with_any_phrase(protocol_page_texts, blinding_phrases) is not None
            else "missing",
            "match_status": (
                first_page_with_any_phrase(report_page_texts, blinding_phrases) is not None
                and first_page_with_any_phrase(protocol_page_texts, blinding_phrases) is not None
            ),
            "evidence_page_report": first_page_with_any_phrase(report_page_texts, blinding_phrases),
            "evidence_page_protocol": first_page_with_any_phrase(
                protocol_page_texts, blinding_phrases
            ),
            "extract_confidence": "medium",
        },
    ]

    return pd.DataFrame(claims)
