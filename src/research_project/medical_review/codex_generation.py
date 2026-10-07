"""Validate generated proposals and derive a scoped reading layer without rewriting imports."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from research_project.medical_review.bundle import resolve_source_object
from research_project.medical_review.codex_backend import MODEL
from research_project.medical_review.importer import validate_upstream
from research_project.medical_review.records import UPSTREAM_SCHEMA_HASH, content_hash, read_json

GENERATION_SCHEMA = "medical_codex_generation_v1"


def output_schema(repo: Path) -> dict[str, Any]:
    """Reuse the exact pinned output vocabulary; no human or qualified-result fields."""
    upstream = read_json(repo / "config/medical_review/upstream/reviewer_output.schema.json")
    review = {k: v for k, v in upstream.items() if k not in {"$schema", "$id", "$defs"}}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [GENERATION_SCHEMA]},
            "review": review,
            "associations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "finding_id": {"type": "string"},
                        "study_id": {"type": "string"},
                        "comparison_id": {"type": ["string", "null"]},
                        "check_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["finding_id", "study_id", "comparison_id", "check_ids"],
                },
            },
        },
        "required": ["schema_version", "review", "associations"],
        "$defs": upstream.get("$defs", {}),
    }


def validate_generation(
    repo: Path,
    envelope: Any,
    bundle: dict[str, Any],
    packet: dict[str, Any],
) -> None:
    if (
        not isinstance(envelope, dict)
        or set(envelope) != {"schema_version", "review", "associations"}
        or envelope["schema_version"] != GENERATION_SCHEMA
    ):
        raise ValueError("Unsupported Codex generation envelope; authority fields refused.")
    review = envelope["review"]
    validate_upstream(review, repo, UPSTREAM_SCHEMA_HASH)
    if review["paper_id"] != bundle.get("upstream_paper_id"):
        raise ValueError("Codex generation paper identity mismatch.")
    associations = envelope["associations"]
    findings = {f["id"]: f for f in review["findings"]}
    if not isinstance(associations, list) or any(not isinstance(a, dict) for a in associations):
        raise ValueError("Codex finding associations must be explicit records.")
    if len(associations) != len(findings) or {a.get("finding_id") for a in associations} != set(
        findings
    ):
        raise ValueError("Codex finding associations must account for each finding exactly once.")
    scopes = {(c["study_id"], c.get("comparison_id"), c["check_id"]) for c in packet["checks"]}
    studies = {s["study_id"] for s in bundle["studies"]}
    comparisons = {(c["study_id"], c["comparison_id"]) for c in bundle.get("comparisons", [])}
    for association in associations:
        if set(association) != {"finding_id", "study_id", "comparison_id", "check_ids"}:
            raise ValueError("Unsupported Codex association fields.")
        study, comparison, checks = [
            association[k] for k in ("study_id", "comparison_id", "check_ids")
        ]
        if study not in studies or (
            comparison is not None and (study, comparison) not in comparisons
        ):
            raise ValueError("Codex finding has an unknown study/comparison scope.")
        if (
            not isinstance(checks, list)
            or any(not isinstance(c, str) or (study, comparison, c) not in scopes for c in checks)
            or len(checks) != len(set(checks))
        ):
            raise ValueError("Codex finding check scope does not match the prepared packet.")
        allowed_reports = {r["report_id"] for r in bundle["reports"] if study in r["study_ids"]}
        if comparison is not None:
            row = next(c for c in bundle["comparisons"] if c["comparison_id"] == comparison)
            if row.get("report_ids"):
                allowed_reports &= set(row["report_ids"])
        aliases = {s["alias"]: s for s in packet["sources"]}
        for obj in findings[association["finding_id"]]["source_objects"]:
            source = aliases.get(obj.get("path"))
            if source is not None and not set(source["report_ids"]).intersection(allowed_reports):
                raise ValueError("Codex citation refers to a different study/comparison scope.")
            # Inexact, unknown or ambiguous anchors remain explicit unresolved proposals.


def derived_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    """Namespace model-local finding identities; original envelope remains byte-exact."""
    review = copy.deepcopy(envelope["review"])
    prefix = "codex-" + content_hash(envelope)[:24] + "-"
    for finding in review["findings"]:
        finding["id"] = prefix + finding["id"]
    return review


def reading_proposals(
    proposals: list[dict[str, Any]],
    envelope: dict[str, Any],
    bundle: dict[str, Any],
    packet: dict[str, Any],
    *,
    envelope_sha256: str,
    packet_sha256: str,
    runtime: dict[str, Any],
) -> list[dict[str, Any]]:
    """A new overlay bound to the original import; historical proposals stay unchanged."""
    prefix = "codex-" + content_hash(envelope)[:24] + "-"
    associations = {prefix + a["finding_id"]: a for a in envelope["associations"]}
    indexed_ids = {u["evidence_id"] for s in packet["sources"] for u in s["units"]}
    result = copy.deepcopy(proposals)
    for proposal in result:
        association = associations[proposal["original_finding_id"]]
        proposal["study_id"] = association["study_id"]
        proposal["comparison_id"] = association["comparison_id"]
        proposal["check_ids"] = association["check_ids"]
        proposal["report_ids"] = [
            r["report_id"] for r in bundle["reports"] if association["study_id"] in r["study_ids"]
        ]
        if association["comparison_id"] is not None:
            comparison = next(
                c
                for c in bundle["comparisons"]
                if c["comparison_id"] == association["comparison_id"]
            )
            if comparison.get("report_ids"):
                proposal["report_ids"] = comparison["report_ids"]
        proposal["origin"] = {
            **proposal["origin"],
            "type": "codex_reading",
            "backend": "codex_cli",
            "model": runtime.get("effective_model"),
            "requested_model": MODEL,
            "reasoning": "max",
            "prompt_sha256": packet_sha256,
            "generation_sha256": envelope_sha256,
            "output_upstream_revision": None,
        }
        proposal["evidence_links"] = []
        for obj in proposal["original"]["source_objects"]:
            link = resolve_source_object(bundle, obj)
            if link.get("evidence_id") not in indexed_ids:
                link = {
                    "source_object_id": obj["id"],
                    "resolution": "unresolved",
                    "evidence_id": None,
                    "reason": "Citation is not an exact, unique prepared packet unit.",
                }
            proposal["evidence_links"].append(link)
    return result


def observed_metadata(events: Path) -> dict[str, Any]:
    """CLI events do not establish provider request count, cost or effective model identity."""
    usage = None
    import json

    for line in events.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return {
        "effective_model": None,
        "model_calls": None,
        "token_usage": usage,
        "cost_estimate": None,
        "search_activity": [],
        "provider_fallbacks": [],
    }
