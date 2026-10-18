"""Version-2 citation identities and literal packet-span resolution."""

from __future__ import annotations

import copy
import hashlib

from research_project.medical_review.records import identity


def normalize_citations(review, generation_sha256):
    """Preserve content while separating finding-local citation IDs from source IDs."""
    result = copy.deepcopy(review)
    ledger = []
    findings = set()
    for finding in result["findings"]:
        fid = finding["id"]
        if not isinstance(fid, str) or not fid.strip() or fid in findings:
            raise ValueError("Duplicate finding ID or missing finding identity.")
        findings.add(fid)
        mapping = {}
        for obj in finding["source_objects"]:
            old = obj["id"]
            if not isinstance(old, str) or not old.strip() or old in mapping:
                raise ValueError("Duplicate source object ID in finding or missing identity.")
            new = identity(
                "codexcitation", {"generation": generation_sha256, "finding": fid, "id": old}
            )
            mapping[old] = new
            ledger.append(
                {
                    "finding_id": fid,
                    "original_id": old,
                    "derived_id": new,
                    "original": copy.deepcopy(obj),
                }
            )
            obj["id"] = new
        for link in finding["claim_evidence_links"]:
            if any(k not in mapping for k in link["source_object_ids"]):
                raise ValueError("Claim references an unknown source object.")
            link["source_object_ids"] = [mapping[k] for k in link["source_object_ids"]]
    return result, ledger


def resolve_citation(bundle, packet, obj, study, comparison):
    """Resolve one literal span; exact text is not semantic or human verification."""
    unresolved = {
        "source_object_id": obj["id"],
        "resolution": "unresolved",
        "evidence_id": None,
        "reason": "Missing, ambiguous or inexact packet unit/excerpt.",
    }
    candidates = [(s, u) for s in packet["sources"] for u in s.get("units", [])]
    by_id = [(s, u) for s, u in candidates if u["evidence_id"] == obj["id"]]
    if by_id:
        candidates = by_id
    elif obj.get("path") is None or not any(
        obj.get(k) is not None for k in ("section", "page", "page_label")
    ):
        return unresolved
    for key in ("section", "page", "page_label"):
        if obj.get(key) is not None:
            candidates = [(s, u) for s, u in candidates if u.get(key) == obj[key]]
    if obj.get("path") is not None:

        def matches(source):
            documents = [
                d
                for d in bundle["documents"]
                if d.get("source_version_id") == source.get("source_version_id")
            ]
            paths = [source["alias"], *[p for d in documents for p in d.get("upstream_paths", [])]]
            return obj["path"] in paths

        candidates = [(s, u) for s, u in candidates if matches(s)]
    if len(candidates) != 1:
        return unresolved
    source, unit = candidates[0]
    reports = [r for r in bundle["reports"] if study in r["study_ids"]]
    allowed = {r["report_id"] for r in reports}
    if comparison is not None:
        comparisons = [
            c
            for c in bundle.get("comparisons", [])
            if c["comparison_id"] == comparison and c["study_id"] == study
        ]
        if len(comparisons) != 1:
            raise ValueError("Unknown citation comparison scope.")
        if comparisons[0].get("report_ids"):
            allowed &= set(comparisons[0]["report_ids"])
    if not allowed.intersection(source["report_ids"]):
        raise ValueError("Codex citation refers to a different study/comparison scope.")
    if any(
        len(r["study_ids"]) > 1 and r.get("mapping_reviewed") is not True
        for r in reports
        if r["report_id"] in source["report_ids"]
    ):
        return {**unresolved, "reason": "Unreviewed multi-study report mapping."}
    # Packet v1 has no URL locator binding; do not silently ignore a supplied one.
    if obj.get("url") is not None:
        return {**unresolved, "reason": "URL locator is not bound in the prepared packet."}
    quote = obj.get("text_quote")
    text = unit["quote"]
    if not isinstance(quote, str) or not quote:
        return unresolved
    start = text.find(quote)
    if start < 0 or text.find(quote, start + 1) >= 0:
        return unresolved

    def digest(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    start_byte = len(text[:start].encode("utf-8"))
    return {
        "source_object_id": obj["id"],
        "resolution": "exact",
        "match_kind": "whole_unit" if quote == text else "exact_excerpt",
        "evidence_id": unit["evidence_id"],
        "source_version_id": source["source_version_id"],
        "source_sha256": source["sha256"],
        "unit_sha256": digest(text),
        "quote_sha256": digest(quote),
        "start_byte": start_byte,
        "end_byte": start_byte + len(quote.encode("utf-8")),
        "locator": unit["section"],
        "visual_inspected": False,
        "input_verification": "proposed_transcription",
        "reason": None,
    }
