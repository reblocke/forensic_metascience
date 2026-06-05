"""Transparency and research-object helpers.

This module borrows the ScienceVerse/MetaCheck pattern of separating a
machine-readable research object from checks run against that object, while
keeping this repository's v1 implementation offline and dependency-light.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA_NAME = "forensic_metascience.research_object_lite"
SCHEMA_VERSION = "1.0.0"

SOURCE_COLUMNS = [
    "study_id",
    "source_type",
    "source_pdf",
    "source_path",
    "sha256",
    "n_pages",
]

PAGE_TEXT_COLUMNS = [
    "study_id",
    "source_type",
    "source_pdf",
    "page",
    "text_id",
    "text",
]

URL_COLUMNS = [
    "study_id",
    "source_pdf",
    "page",
    "text_id",
    "url",
    "url_type",
    "context",
]

OPEN_PRACTICE_COLUMNS = [
    "study_id",
    "practice",
    "is_open",
    "category",
    "location",
    "source_pdf",
    "page",
    "text_id",
    "evidence_text",
    "on_request",
    "extract_confidence",
]

REPOSITORY_COLUMNS = [
    "study_id",
    "repository_type",
    "url",
    "source_pdf",
    "page",
    "text_id",
    "context",
]

PREREGISTRATION_COLUMNS = [
    "study_id",
    "link_type",
    "url_or_id",
    "source_pdf",
    "page",
    "text_id",
    "context",
]

FIGURE_TABLE_COLUMNS = [
    "study_id",
    "mention_type",
    "label",
    "number",
    "source_pdf",
    "page",
    "text_id",
    "context",
]

TRANSPARENCY_CHECK_COLUMNS = [
    "study_id",
    "n_source_files",
    "n_pages",
    "n_urls",
    "n_repository_links",
    "n_preregistration_links",
    "n_availability_statements",
    "data_statement_detected",
    "code_statement_detected",
    "materials_statement_detected",
    "registration_statement_detected",
    "on_request_statement_detected",
    "n_figure_mentions",
    "n_table_mentions",
    "transparency_evidence_burden",
    "external_network_used",
    "llm_used",
    "metacheck_dependency_used",
]

URL_PATTERN = re.compile(r"https?://[^\s<>{}\[\]\"']+", flags=re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:)]}"

AVAILABILITY_PATTERN = re.compile(
    r"\b(availab\w*|access\w*|shar\w*|repository|archive|supplement\w*|"
    r"online|request|found|deposited|uploaded|download\w*)\b",
    flags=re.IGNORECASE,
)
ON_REQUEST_PATTERN = re.compile(r"\b(on|upon|by)\s+(reasonable\s+)?request\b", flags=re.IGNORECASE)
PRACTICE_PATTERNS = {
    "data": re.compile(
        r"\b(data|dataset|datasets|individual participant data|source data|raw data)\b",
        flags=re.IGNORECASE,
    ),
    "code": re.compile(
        r"\b(analysis code|statistical code|source code|computer code|code|scripts?)\b",
        flags=re.IGNORECASE,
    ),
    "materials": re.compile(
        r"\b(materials?|questionnaires?|instruments?|protocol|supplementary materials?)\b",
        flags=re.IGNORECASE,
    ),
    "registration": re.compile(
        r"\b(pre-?regist\w*|registered|registration|registry|clinicaltrials\.gov|"
        r"aspredicted|ISRCTN\d{8}|NCT\d{8})\b",
        flags=re.IGNORECASE,
    ),
}
REPOSITORY_DOMAINS = {
    "github": ("github.com",),
    "osf": ("osf.io", "osfstorage"),
    "zenodo": ("zenodo.org",),
    "researchbox": ("researchbox.org", "researchbox.com"),
    "figshare": ("figshare.com",),
    "dryad": ("datadryad.org", "dryad"),
    "dataverse": ("dataverse",),
}
PREREGISTRATION_DOMAINS = {
    "aspredicted": ("aspredicted.org",),
    "osf": ("osf.io",),
    "clinicaltrials": ("clinicaltrials.gov",),
    "isrctn": ("isrctn.com", "isrctn.org"),
    "chictr": ("chictr.org.cn", "chictr.org"),
    "euctr": ("clinicaltrialsregister.eu",),
}
REGISTRY_ID_PATTERN = re.compile(
    r"\b(NCT\d{8}|ISRCTN\d{8}|ChiCTR[-_]?[A-Za-z0-9]+|EUCTR\d{4}-\d{6}-\d{2})\b",
    flags=re.IGNORECASE,
)
FIGURE_TABLE_PATTERN = re.compile(
    r"\b(Fig(?:ure)?\.?|Table)\s*([0-9]+[A-Za-z]?)\b", flags=re.IGNORECASE
)
PDF_HYPHENATED_LINEBREAK_PATTERN = re.compile(r"(?<=\w)\s*-\s*(?:\r?\n|\r)\s*(?=\w)")
PDF_HYPHENATED_SPACE_PATTERN = re.compile(r"\b([A-Za-z]{2,})\s*-\s+([A-Za-z]{2,})\b")
SOFTWARE_USE_CONTEXT_PATTERN = re.compile(
    r"\b(data processing|statistical analyses?|figure generation|analyses were performed|"
    r"performed using)\b",
    flags=re.IGNORECASE,
)
SOFTWARE_TOOL_PATTERN = re.compile(
    r"\b(SPSS|Graph\s*Pad|GraphPad|Prism|SAS|Stata|MATLAB)\b|\bR\s*\(v?\d",
    flags=re.IGNORECASE,
)
AVAILABILITY_STATEMENT_BOILERPLATE_PATTERN = re.compile(
    r"\b(statements?\s+of\s+[^.!?]{0,120}\bavailability|"
    r"(data|code)\s+availability\s+statements?)\b",
    flags=re.IGNORECASE,
)


def normalize_text(value: object) -> str:
    """Normalize whitespace and common punctuation variants."""

    text = "" if value is None else str(value)
    for old, new in {
        "\u00ad": "",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
    }.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_detection_text(value: object) -> str:
    """Normalize text artifacts that can split evidence phrases across PDF line breaks."""

    text = "" if value is None else str(value)
    text = PDF_HYPHENATED_LINEBREAK_PATTERN.sub("", text)
    text = normalize_text(text)
    return PDF_HYPHENATED_SPACE_PATTERN.sub(r"\1\2", text)


def empty_sources() -> pd.DataFrame:
    return pd.DataFrame(columns=SOURCE_COLUMNS)


def empty_page_texts() -> pd.DataFrame:
    return pd.DataFrame(columns=PAGE_TEXT_COLUMNS)


def empty_urls() -> pd.DataFrame:
    return pd.DataFrame(columns=URL_COLUMNS)


def empty_open_practices() -> pd.DataFrame:
    return pd.DataFrame(columns=OPEN_PRACTICE_COLUMNS)


def empty_repository_links() -> pd.DataFrame:
    return pd.DataFrame(columns=REPOSITORY_COLUMNS)


def empty_preregistration_links() -> pd.DataFrame:
    return pd.DataFrame(columns=PREREGISTRATION_COLUMNS)


def empty_figure_table_mentions() -> pd.DataFrame:
    return pd.DataFrame(columns=FIGURE_TABLE_COLUMNS)


def empty_transparency_checks() -> pd.DataFrame:
    return pd.DataFrame(columns=TRANSPARENCY_CHECK_COLUMNS)


def file_sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a source file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_root(path: Path, repo_root: Path) -> str:
    """Return a repo-relative path when possible, otherwise the file name."""

    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return path.name


def build_source_record(
    *,
    study_id: str,
    source_type: str,
    source_path: Path,
    repo_root: Path,
    n_pages: int,
) -> dict[str, object]:
    """Build one source-file provenance row."""

    return {
        "study_id": study_id,
        "source_type": source_type,
        "source_pdf": source_path.name,
        "source_path": relative_to_root(source_path, repo_root),
        "sha256": file_sha256(source_path),
        "n_pages": n_pages,
    }


def build_page_text_table(
    *,
    study_id: str,
    source_type: str,
    source_pdf: str,
    page_texts: list[str],
    starting_text_id: int = 1,
) -> pd.DataFrame:
    """Create page-level text rows for one source document."""

    rows = []
    for offset, text in enumerate(page_texts):
        rows.append(
            {
                "study_id": study_id,
                "source_type": source_type,
                "source_pdf": source_pdf,
                "page": offset + 1,
                "text_id": starting_text_id + offset,
                "text": text or "",
            }
        )
    return pd.DataFrame(rows, columns=PAGE_TEXT_COLUMNS)


def _context(text: str, start: int, end: int, width: int = 160) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return normalize_text(text[left:right])


def _classify_url(url: str) -> str:
    lowered = url.lower()
    if _repository_type(url):
        return "repository"
    if _preregistration_type(url):
        return "preregistration_or_registry"
    if "doi.org" in lowered or "pubmed.ncbi.nlm.nih.gov" in lowered:
        return "publication_identifier"
    return "other"


def _repository_type(url: str) -> str | None:
    lowered = url.lower()
    for repository_type, domains in REPOSITORY_DOMAINS.items():
        if any(domain in lowered for domain in domains):
            return repository_type
    return None


def _preregistration_type(url: str) -> str | None:
    lowered = url.lower()
    for link_type, domains in PREREGISTRATION_DOMAINS.items():
        if any(domain in lowered for domain in domains):
            return link_type
    return None


def extract_urls(page_texts: pd.DataFrame) -> pd.DataFrame:
    """Extract URLs with page and context provenance."""

    if page_texts.empty:
        return empty_urls()

    rows: list[dict[str, object]] = []
    for _, row in page_texts.iterrows():
        text = str(row.get("text", ""))
        for match in URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
            rows.append(
                {
                    "study_id": row["study_id"],
                    "source_pdf": row["source_pdf"],
                    "page": row["page"],
                    "text_id": row["text_id"],
                    "url": url,
                    "url_type": _classify_url(url),
                    "context": _context(text, match.start(), match.end()),
                }
            )
    return pd.DataFrame(rows, columns=URL_COLUMNS).drop_duplicates(ignore_index=True)


def detect_repository_links(urls: pd.DataFrame) -> pd.DataFrame:
    """Classify detected URLs that point to known repository services."""

    if urls.empty:
        return empty_repository_links()

    rows = []
    for _, row in urls.iterrows():
        repository_type = _repository_type(str(row["url"]))
        if repository_type is None:
            continue
        rows.append(
            {
                "study_id": row["study_id"],
                "repository_type": repository_type,
                "url": row["url"],
                "source_pdf": row["source_pdf"],
                "page": row["page"],
                "text_id": row["text_id"],
                "context": row["context"],
            }
        )
    return pd.DataFrame(rows, columns=REPOSITORY_COLUMNS).drop_duplicates(ignore_index=True)


def detect_preregistration_links(page_texts: pd.DataFrame, urls: pd.DataFrame) -> pd.DataFrame:
    """Detect preregistration or trial-registry links and identifiers."""

    rows: list[dict[str, object]] = []
    if not urls.empty:
        for _, row in urls.iterrows():
            link_type = _preregistration_type(str(row["url"]))
            if link_type is None:
                continue
            rows.append(
                {
                    "study_id": row["study_id"],
                    "link_type": link_type,
                    "url_or_id": row["url"],
                    "source_pdf": row["source_pdf"],
                    "page": row["page"],
                    "text_id": row["text_id"],
                    "context": row["context"],
                }
            )

    if not page_texts.empty:
        for _, row in page_texts.iterrows():
            text = str(row.get("text", ""))
            for match in REGISTRY_ID_PATTERN.finditer(text):
                identifier = match.group(1).upper()
                if identifier.startswith("NCT"):
                    link_type = "clinicaltrials"
                elif identifier.startswith("ISRCTN"):
                    link_type = "isrctn"
                elif identifier.startswith("CHICTR"):
                    link_type = "chictr"
                else:
                    link_type = "euctr"
                rows.append(
                    {
                        "study_id": row["study_id"],
                        "link_type": link_type,
                        "url_or_id": identifier,
                        "source_pdf": row["source_pdf"],
                        "page": row["page"],
                        "text_id": row["text_id"],
                        "context": _context(text, match.start(), match.end()),
                    }
                )

    return pd.DataFrame(rows, columns=PREREGISTRATION_COLUMNS).drop_duplicates(ignore_index=True)


def _sentence_units(text: str) -> list[str]:
    text = _normalize_detection_text(text)
    rough_units = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [normalize_text(unit) for unit in rough_units if normalize_text(unit)]


def _location_from_text(text: str) -> str:
    match = URL_PATTERN.search(text)
    if match:
        return match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
    return ""


def _urls_in_text(text: str) -> list[str]:
    return [match.group(0).rstrip(TRAILING_URL_PUNCTUATION) for match in URL_PATTERN.finditer(text)]


def _has_repository_url(text: str) -> bool:
    return any(_repository_type(url) is not None for url in _urls_in_text(text))


def _has_publication_identifier_url(text: str) -> bool:
    return any(
        "doi.org" in url.lower() or "pubmed.ncbi.nlm.nih.gov" in url.lower()
        for url in _urls_in_text(text)
    )


def _is_software_use_statement(text: str) -> bool:
    return bool(SOFTWARE_USE_CONTEXT_PATTERN.search(text) and SOFTWARE_TOOL_PATTERN.search(text))


def _is_availability_statement_boilerplate(text: str) -> bool:
    return bool(
        AVAILABILITY_STATEMENT_BOILERPLATE_PATTERN.search(text)
        and _has_publication_identifier_url(text)
        and not _has_repository_url(text)
    )


def _has_practice_availability(text: str, practice: str) -> bool:
    if practice == "registration":
        return True
    if practice in {"data", "code"} and _is_software_use_statement(text):
        return False
    if practice == "code" and _is_availability_statement_boilerplate(text):
        return False
    if _has_repository_url(text):
        return True
    return bool(AVAILABILITY_PATTERN.search(text))


def _practice_category(text: str, location: str, on_request: bool) -> str:
    lowered = f"{text} {location}".lower()
    if on_request:
        return "upon request"
    if any(_repository_type(location) == key for key in REPOSITORY_DOMAINS):
        return "repository"
    if any(domain in lowered for domains in REPOSITORY_DOMAINS.values() for domain in domains):
        return "repository"
    if "supplement" in lowered:
        return "supplementary"
    if location:
        return "website"
    return "unknown"


def detect_open_practices(page_texts: pd.DataFrame) -> pd.DataFrame:
    """Detect open-practice evidence statements from page-level text."""

    if page_texts.empty:
        return empty_open_practices()

    rows: list[dict[str, object]] = []
    for _, row in page_texts.iterrows():
        for unit in _sentence_units(str(row.get("text", ""))):
            matched_practices = [
                practice
                for practice, pattern in PRACTICE_PATTERNS.items()
                if pattern.search(unit) and _has_practice_availability(unit, practice)
            ]
            if not matched_practices:
                continue

            on_request = bool(ON_REQUEST_PATTERN.search(unit))
            location = _location_from_text(unit)
            for practice in matched_practices:
                category = _practice_category(unit, location, on_request)
                is_open = not on_request and category in {"repository", "supplementary", "website"}
                rows.append(
                    {
                        "study_id": row["study_id"],
                        "practice": practice,
                        "is_open": bool(is_open),
                        "category": category,
                        "location": location,
                        "source_pdf": row["source_pdf"],
                        "page": row["page"],
                        "text_id": row["text_id"],
                        "evidence_text": unit,
                        "on_request": bool(on_request),
                        "extract_confidence": "medium" if location or on_request else "low",
                    }
                )

    return pd.DataFrame(rows, columns=OPEN_PRACTICE_COLUMNS).drop_duplicates(
        subset=["study_id", "practice", "source_pdf", "page", "evidence_text"],
        ignore_index=True,
    )


def detect_figure_table_mentions(page_texts: pd.DataFrame) -> pd.DataFrame:
    """Extract figure and table mentions for lightweight research-object metadata."""

    if page_texts.empty:
        return empty_figure_table_mentions()

    rows: list[dict[str, object]] = []
    for _, row in page_texts.iterrows():
        text = str(row.get("text", ""))
        for match in FIGURE_TABLE_PATTERN.finditer(text):
            raw_type = match.group(1).lower()
            mention_type = "figure" if raw_type.startswith("fig") else "table"
            number_text = match.group(2)
            number_match = re.match(r"(\d+)", number_text)
            rows.append(
                {
                    "study_id": row["study_id"],
                    "mention_type": mention_type,
                    "label": normalize_text(match.group(0)),
                    "number": int(number_match.group(1)) if number_match else None,
                    "source_pdf": row["source_pdf"],
                    "page": row["page"],
                    "text_id": row["text_id"],
                    "context": _context(text, match.start(), match.end(), width=80),
                }
            )
    return pd.DataFrame(rows, columns=FIGURE_TABLE_COLUMNS).drop_duplicates(ignore_index=True)


def _bool_practice(open_practices: pd.DataFrame, practice: str) -> bool:
    if open_practices.empty:
        return False
    return bool((open_practices["practice"] == practice).any())


def build_transparency_checks(
    *,
    study_id: str,
    sources: pd.DataFrame,
    urls: pd.DataFrame,
    repository_links: pd.DataFrame,
    preregistration_links: pd.DataFrame,
    open_practices: pd.DataFrame,
    figure_table_mentions: pd.DataFrame,
    external_network_used: bool = False,
    llm_used: bool = False,
    metacheck_dependency_used: bool = False,
) -> pd.DataFrame:
    """Summarize transparency evidence into one report-ready input row."""

    data_statement = _bool_practice(open_practices, "data")
    code_statement = _bool_practice(open_practices, "code")
    materials_statement = _bool_practice(open_practices, "materials")
    registration_statement = _bool_practice(open_practices, "registration") or (
        not preregistration_links.empty
    )
    on_request = bool(open_practices["on_request"].any()) if not open_practices.empty else False
    detected_practices = sum(
        [data_statement, code_statement, materials_statement, registration_statement]
    )
    missing_fraction = (4 - detected_practices) / 4
    request_penalty = 0.25 if on_request else 0.0
    evidence_burden = min(1.0, missing_fraction + request_penalty)

    if figure_table_mentions.empty:
        n_figures = 0
        n_tables = 0
    else:
        n_figures = int((figure_table_mentions["mention_type"] == "figure").sum())
        n_tables = int((figure_table_mentions["mention_type"] == "table").sum())

    checks = pd.DataFrame(
        [
            {
                "study_id": study_id,
                "n_source_files": len(sources),
                "n_pages": int(sources["n_pages"].sum()) if not sources.empty else 0,
                "n_urls": len(urls),
                "n_repository_links": len(repository_links),
                "n_preregistration_links": len(preregistration_links),
                "n_availability_statements": len(open_practices),
                "data_statement_detected": data_statement,
                "code_statement_detected": code_statement,
                "materials_statement_detected": materials_statement,
                "registration_statement_detected": registration_statement,
                "on_request_statement_detected": on_request,
                "n_figure_mentions": n_figures,
                "n_table_mentions": n_tables,
                "transparency_evidence_burden": evidence_burden,
                "external_network_used": bool(external_network_used),
                "llm_used": bool(llm_used),
                "metacheck_dependency_used": bool(metacheck_dependency_used),
            }
        ],
        columns=TRANSPARENCY_CHECK_COLUMNS,
    )
    return checks


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    subset = frame[[column for column in columns if column in frame.columns]].copy()
    return subset.where(pd.notna(subset), None).to_dict(orient="records")


def build_research_object_lite(
    *,
    study_id: str,
    study_title: str,
    trial_id: str,
    identifiers: dict[str, str],
    sources: pd.DataFrame,
    urls: pd.DataFrame,
    repository_links: pd.DataFrame,
    preregistration_links: pd.DataFrame,
    open_practices: pd.DataFrame,
    figure_table_mentions: pd.DataFrame,
    external_network_used: bool = False,
    llm_used: bool = False,
    metacheck_dependency_used: bool = False,
) -> dict[str, Any]:
    """Build a compact machine-readable research-object description."""

    checks = build_transparency_checks(
        study_id=study_id,
        sources=sources,
        urls=urls,
        repository_links=repository_links,
        preregistration_links=preregistration_links,
        open_practices=open_practices,
        figure_table_mentions=figure_table_mentions,
        external_network_used=external_network_used,
        llm_used=llm_used,
        metacheck_dependency_used=metacheck_dependency_used,
    )
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "study_id": study_id,
        "study_title": study_title,
        "trial_id": trial_id,
        "identifiers": {key: value for key, value in identifiers.items() if value},
        "sources": _records(sources, SOURCE_COLUMNS),
        "detected_urls": _records(urls, URL_COLUMNS),
        "repository_links": _records(repository_links, REPOSITORY_COLUMNS),
        "preregistration_links": _records(preregistration_links, PREREGISTRATION_COLUMNS),
        "open_practices": _records(open_practices, OPEN_PRACTICE_COLUMNS),
        "figure_table_mentions": _records(figure_table_mentions, FIGURE_TABLE_COLUMNS),
        "summary": _records(checks, TRANSPARENCY_CHECK_COLUMNS)[0],
        "provenance": {
            "adapter_inspiration": "ScienceVerse/MetaCheck research-object and module pattern",
            "external_network_used": bool(external_network_used),
            "llm_used": bool(llm_used),
            "metacheck_dependency_used": bool(metacheck_dependency_used),
            "offline_default": True,
        },
    }
