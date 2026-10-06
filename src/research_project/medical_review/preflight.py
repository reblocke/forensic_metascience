"""Deterministic extraction diagnostics, explicitly separate from source fidelity."""

from __future__ import annotations

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from research_project.medical_review.records import PRIVATE_SOURCES, content_hash, private_path


def structural_preflight(repo_root: Path, bundle: dict[str, Any]) -> dict[str, Any]:
    """Inspect authorized source bytes; unsupported structure stays unverifiable."""
    sources = []
    for doc in bundle["documents"]:
        record = {
            "source_id": doc["source_id"],
            "source_version_id": doc.get("source_version_id"),
            "availability": doc["availability"],
            "pages": [],
            "page_count": None,
            "pages_with_text": None,
            "extracted_units": None,
            "visual_inspection": "not_performed",
            "source_fidelity_verified": False,
            "manuscript_defect": None,
            "properties": {
                "page_coverage": "unverified",
                "reading_order": "unsupported",
                "table_structure": "unsupported",
                "signs_units_formulas": "unverified",
                "cross_references": "unverified",
            },
            "limitations": [],
        }
        if doc["availability"] != "supplied":
            record.update(extraction_status="unavailable", parser=None)
            sources.append(record)
            continue
        if doc.get("permissions", {}).get("local_processing") is not True:
            raise ValueError("Structural preflight lacks local-processing permission.")
        path = private_path(repo_root, Path(doc["path"]), PRIVATE_SOURCES / bundle["study_id"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
            raise ValueError("Preflight source hash mismatch.")
        try:
            if path.suffix.lower() == ".pdf":
                from pypdf import PdfReader

                reader = PdfReader(path)
                pages = [
                    {"page_index": i, "text": page.extract_text() or ""}
                    for i, page in enumerate(reader.pages)
                ]
                parser = {"id": "pypdf", "version": version("pypdf")}
            elif path.suffix.lower() in {".txt", ".md"}:
                pages = [{"page_index": None, "text": path.read_text(encoding="utf-8")}]
                parser = {"id": "utf8_text", "version": "1"}
            else:
                record.update(extraction_status="unsupported", parser=None)
                record["limitations"].append("No approved extractor for this source format.")
                sources.append(record)
                continue
        except Exception as error:
            record.update(extraction_status="failed", parser=None)
            record["limitations"].append(f"Extraction failed: {type(error).__name__}")
            sources.append(record)
            continue
        with_text = sum(bool(page["text"].strip()) for page in pages)
        record.update(
            pages=pages,
            page_count=len(pages) if path.suffix.lower() == ".pdf" else None,
            pages_with_text=with_text if path.suffix.lower() == ".pdf" else None,
            extracted_units=len(pages),
            parser=parser,
            extraction_status="completed" if pages and with_text == len(pages) else "partial",
        )
        record["properties"]["page_coverage"] = (
            "enumerated_pdf_pages" if path.suffix.lower() == ".pdf" else "text_file_only"
        )
        record["limitations"].append(
            "Extraction does not verify images, tables, signs, units or reading order."
        )
        if with_text != len(pages) or not pages:
            record["limitations"].append("Empty/unreadable pages constrain downstream review.")
        record["parsed_sha256"] = content_hash(pages)
        sources.append(record)
    return {
        "schema_version": "medical_parser_preflight_v1",
        "bundle_sha256": content_hash(bundle),
        "sources": sources,
        "model_assessment": None,
    }
