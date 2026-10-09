"""Deterministic offline citation indexing and an allowlisted medical reading packet."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from research_project.inspect_sr.records import evidence_id
from research_project.medical_review.bundle import load_bundle, validate_bundle
from research_project.medical_review.codex_backend import INSTRUCTIONS, MODEL, execution_policy
from research_project.medical_review.codex_generation import output_schema
from research_project.medical_review.codex_qualification import validate_qualification
from research_project.medical_review.context import build_study_context
from research_project.medical_review.evaluation_packets import _source_path
from research_project.medical_review.preflight import structural_preflight
from research_project.medical_review.records import (
    PRIVATE_SOURCES,
    content_hash,
    private_path,
    read_json,
    write_json,
)
from research_project.medical_review.routing import build_review_plan


def _encoded(packet: dict[str, Any]) -> bytes:
    return (json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def _prompt_bytes(repo: Path, raw: bytes) -> int:
    # Bound the packet, explicit instructions, output contract and qualified CLI
    # context together. Never use a byte budget as a token-context guarantee.
    return (
        len(
            json.dumps(
                {
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": raw.decode("utf-8"),
                                }
                            ],
                        }
                    ],
                    "text": {
                        "format": {
                            "name": "codex_output_schema",
                            "schema": output_schema(repo),
                            "strict": True,
                            "type": "json_schema",
                        },
                        "verbosity": "low",
                    },
                },
                ensure_ascii=False,
            ).encode()
        )
        + len(INSTRUCTIONS.encode())
        + execution_policy()["max_runtime_context_bytes"]
    )


def _expected_sources(bundle, preflight):
    """Reconstruct the complete source allowlist from source bytes, not packet claims."""
    result = []
    for position, (doc, parsed) in enumerate(
        zip(bundle["documents"], preflight["sources"], strict=True)
    ):
        alias = f"source-{position + 1:04d}"
        entry = {
            "alias": alias,
            **{
                k: doc.get(k)
                for k in (
                    "source_id",
                    "source_version_id",
                    "sha256",
                    "role",
                    "availability",
                    "report_ids",
                )
            },
            "extraction_status": parsed["extraction_status"],
            "parser": parsed["parser"],
            "limitations": parsed["limitations"],
            "units": [],
        }
        for page in parsed["pages"]:
            page_index, text = page["page_index"], page["text"]
            for unit_index, offset in enumerate(range(0, len(text), 1000)):
                quote = text[offset : offset + 1000]
                if not quote.strip():
                    continue
                parser = parsed["parser"]
                locator = f"page_index={page_index};characters={offset}:{offset + len(quote)}"
                page_name = page_index if page_index is not None else "text"
                entry["units"].append(
                    {
                        "evidence_id": evidence_id(
                            doc["source_version_id"],
                            locator,
                            quote,
                            parser["id"],
                            parser["version"],
                        ),
                        "quote": quote,
                        "page": page_index + 1 if page_index is not None else None,
                        "page_label": None,
                        "section": f"{alias}:page-{page_name}:unit-{unit_index + 1}",
                    }
                )
        result.append(entry)
    return result


def prepare_packet(
    repo: Path,
    bundle_path: Path,
    *,
    qualification: Path | None,
    profiles: list[str] | None = None,
    max_source_bytes: int | None = None,
) -> dict[str, Path]:
    """Preserve the original, index new unverified anchors and never call a provider.

    A missing qualification is only useful for synthetic/offline packet tests. The
    CLI requires a successful qualification and live execution rechecks it.
    """
    bundle, digest = load_bundle(repo, bundle_path)
    if bundle.get("codex_packet"):
        raise ValueError("Prepare from an original source bundle, not an already indexed revision.")
    receipt = validate_qualification(repo, qualification) if qualification else None
    policy = execution_policy()
    maximum = policy["max_source_bytes"] if max_source_bytes is None else max_source_bytes
    if type(maximum) is not int or not 0 < maximum <= policy["max_source_bytes"]:
        raise ValueError("Invalid source-byte limit.")
    sources = [d for d in bundle["documents"] if d["availability"] == "supplied"]
    paths = [_source_path(repo, {"bundle": bundle}, d) for d in sources]
    if sum(p.stat().st_size for p in paths) > maximum:
        raise ValueError("Codex source-byte limit exceeded before extraction.")
    preflight = structural_preflight(repo, bundle)
    # Applicability remains an operator planning hint; annotations never enter the packet.
    context = build_study_context(bundle, bundle.get("context_fields"))
    plan = build_review_plan(bundle, context, profiles or bundle.get("profile_ids"), repo)
    key = content_hash(
        {
            "bundle": digest,
            "preflight": content_hash(preflight),
            "plan": content_hash(plan),
            "policy": policy,
            "qualification": receipt["receipt_sha256"] if receipt else None,
            "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )
    root = private_path(
        repo, PRIVATE_SOURCES / bundle["study_id"] / "codex_packets" / key, PRIVATE_SOURCES
    )
    result = {
        "bundle": root / "bundle.json",
        "packet": root / "packet.json",
        "authorization_template": root / "authorization.template.json",
    }
    if root.exists():
        validate_packet(repo, result["bundle"])
        return result
    root.mkdir(parents=True)
    indexed = copy.deepcopy(bundle)
    indexed["revision"] += 1
    indexed["profile_ids"] = plan["requested_profiles"]
    packet_sources = _expected_sources(indexed, preflight)
    for position, (doc, parsed) in enumerate(
        zip(indexed["documents"], preflight["sources"], strict=True)
    ):
        alias = f"source-{position + 1:04d}"
        if doc["availability"] != "supplied":
            continue
        doc["upstream_paths"] = [*doc.get("upstream_paths", []), alias]
        for page in parsed["pages"]:
            page_index, text = page["page_index"], page["text"]
            parsed_path = (
                root
                / "extracted"
                / f"{alias}-{page_index if page_index is not None else 'text'}.txt"
            )
            parsed_path.parent.mkdir(exist_ok=True)
            with parsed_path.open("x", encoding="utf-8") as stream:
                stream.write(text)
            parsed_hash = hashlib.sha256(parsed_path.read_bytes()).hexdigest()
            # Exact bounded text slices preserve every character without asserting
            # paragraph/table semantics. Whole units must be quoted by the model.
            for unit_index, offset in enumerate(range(0, len(text), 1000)):
                quote = text[offset : offset + 1000]
                if not quote.strip():
                    continue
                page_name = page_index if page_index is not None else "text"
                section = f"{alias}:page-{page_name}:unit-{unit_index + 1}"
                locator = f"page_index={page_index};characters={offset}:{offset + len(quote)}"
                parser = parsed["parser"]
                anchor = {
                    "evidence_id": evidence_id(
                        doc["source_version_id"], locator, quote, parser["id"], parser["version"]
                    ),
                    "source_version_id": doc["source_version_id"],
                    "locator": locator,
                    "raw_value": quote,
                    "parser": parser,
                    "parsed_path": parsed_path.relative_to(repo).as_posix(),
                    "parsed_sha256": parsed_hash,
                    "page_index": page_index,
                    "upstream_page": page_index + 1 if page_index is not None else None,
                    "page_label": None,
                    "section": section,
                    "visual_inspected": False,
                    "source_semantics_verified": False,
                }
                indexed["evidence"].append(anchor)
    catalogue = {
        c["check_id"]: c
        for c in read_json(repo / "config/medical_review/check_catalogue.json")["checks"]
    }
    packet = {
        "schema_version": "medical_codex_packet_v1",
        "paper_id": bundle.get("upstream_paper_id"),
        "studies": [{"study_id": s["study_id"]} for s in bundle["studies"]],
        "reports": [
            {"report_id": r["report_id"], "study_ids": r["study_ids"]} for r in bundle["reports"]
        ],
        "comparisons": [
            {k: c.get(k) for k in ("comparison_id", "study_id", "report_ids")}
            for c in bundle.get("comparisons", [])
        ],
        "checks": [
            {
                "check_id": c["check_id"],
                "study_id": c["study_id"],
                "comparison_id": c["comparison_id"],
                "question": catalogue[c["check_id"]]["question"],
                "safeguard": catalogue[c["check_id"]]["safeguard"],
            }
            for c in plan["checks"]
            if c["check_id"] in catalogue
        ],
        "routing": {
            "requested_profiles": plan["requested_profiles"],
            "selected_profiles": plan["selected_profiles"],
            "unsupported_profiles": plan["unsupported_profiles"],
            "routing_status": plan["routing_status"],
        },
        "sources": packet_sources,
        "guidance_status": "unavailable_no_guideline_specific_claims",
        "limitations": [
            "Source semantics and visual fidelity are unverified.",
            "Page numbers are one-based physical PDF pages; text units have no invented page.",
            "Tables, figures, reading order and extraction may be incomplete.",
            "Empty findings never establish completed coverage.",
        ],
    }
    raw = _encoded(packet)
    if _prompt_bytes(repo, raw) > policy["max_prompt_bytes"]:
        raise ValueError(
            "Complete Codex packet prompt exceeds byte limit; no truncation permitted."
        )
    with result["packet"].open("xb") as stream:
        stream.write(raw)
    indexed["codex_packet"] = {
        "schema_version": "medical_codex_packet_binding_v1",
        "parent_bundle_sha256": digest,
        "packet_path": result["packet"].relative_to(repo).as_posix(),
        "packet_sha256": hashlib.sha256(raw).hexdigest(),
        "policy_sha256": content_hash(policy),
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "qualification_sha256": receipt["receipt_sha256"] if receipt else None,
    }
    indexed_hash = validate_bundle(repo, indexed)
    write_json(result["bundle"], indexed)
    write_json(
        result["authorization_template"],
        {
            "schema_version": "medical_source_authorization_v2",
            "bundle_sha256": indexed_hash,
            "sources": [
                {
                    "source_version_id": d["source_version_id"],
                    "sha256": d["sha256"],
                    "classification": d["permissions"]["classification"],
                }
                for d in sources
            ],
            "provider": "openai",
            "backend": "codex_cli",
            "model": MODEL,
            "purposes": ["medical_review"],
            "tools": [],
            "allow_web_search": False,
            "packet_sha256": indexed["codex_packet"]["packet_sha256"],
            "execution_policy_sha256": content_hash(policy),
            "valid_from": None,
            "valid_until": None,
            "approver": None,
            "rationale": None,
        },
    )
    return result


def validate_packet(repo: Path, bundle_path: Path) -> dict[str, Any]:
    bundle, _ = load_bundle(repo, bundle_path)
    binding = bundle.get("codex_packet", {})
    if binding.get("schema_version") != "medical_codex_packet_binding_v1" or binding.get(
        "policy_sha256"
    ) != content_hash(execution_policy()):
        raise ValueError("Unsupported or changed Codex packet policy.")
    if binding.get("builder_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("Codex packet builder changed; prepare a new original-bundle revision.")
    path = private_path(repo, Path(binding["packet_path"]), PRIVATE_SOURCES / bundle["study_id"])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding["packet_sha256"]:
        raise ValueError("Codex packet bytes changed.")
    packet = read_json(path)
    if packet.get("schema_version") != "medical_codex_packet_v1" or packet.get(
        "paper_id"
    ) != bundle.get("upstream_paper_id"):
        raise ValueError("Codex packet identity mismatch.")
    plan = build_review_plan(
        bundle,
        build_study_context(bundle, bundle.get("context_fields")),
        bundle.get("profile_ids"),
        repo,
    )
    catalogue = {
        c["check_id"]: c
        for c in read_json(repo / "config/medical_review/check_catalogue.json")["checks"]
    }
    expected_checks = [
        {
            "check_id": c["check_id"],
            "study_id": c["study_id"],
            "comparison_id": c["comparison_id"],
            "question": catalogue[c["check_id"]]["question"],
            "safeguard": catalogue[c["check_id"]]["safeguard"],
        }
        for c in plan["checks"]
        if c["check_id"] in catalogue
    ]
    for doc in bundle["documents"]:
        if doc["availability"] == "supplied":
            _source_path(repo, {"bundle": bundle}, doc)
    expected_sources = _expected_sources(bundle, structural_preflight(repo, bundle))
    if (
        set(packet)
        != {
            "schema_version",
            "paper_id",
            "studies",
            "reports",
            "comparisons",
            "checks",
            "routing",
            "sources",
            "guidance_status",
            "limitations",
        }
        or packet["checks"] != expected_checks
        or packet["sources"] != expected_sources
        or packet["studies"] != [{"study_id": s["study_id"]} for s in bundle["studies"]]
        or packet["reports"]
        != [{"report_id": r["report_id"], "study_ids": r["study_ids"]} for r in bundle["reports"]]
        or packet["comparisons"]
        != [
            {k: c.get(k) for k in ("comparison_id", "study_id", "report_ids")}
            for c in bundle.get("comparisons", [])
        ]
        or packet["routing"]
        != {
            k: plan[k]
            for k in (
                "requested_profiles",
                "selected_profiles",
                "unsupported_profiles",
                "routing_status",
            )
        }
    ):
        raise ValueError("Codex packet allowlist, source units or scope changed.")
    if _prompt_bytes(repo, raw) > execution_policy()["max_prompt_bytes"]:
        raise ValueError("Codex packet prompt byte limit exceeded.")
    return {"bundle": bundle, "packet": packet, "raw": raw}
