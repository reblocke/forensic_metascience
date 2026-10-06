"""Output-free, deterministic medical routing; model-assisted routing requires a live receipt."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from research_project.medical_review.context import validate_study_context
from research_project.medical_review.records import content_hash, identity, read_json


def build_review_plan(
    bundle: dict[str, Any], context: dict[str, Any], profiles: list[str] | None, repo_root: Path
) -> dict[str, Any]:
    validate_study_context(context, bundle)
    catalogue = read_json(repo_root / "config/medical_review/check_catalogue.json")
    guidance = read_json(repo_root / "config/medical_review/guidance_registry.json")
    if (
        catalogue.get("schema_version") != "medical_check_catalogue_v1"
        or guidance.get("schema_version") != "medical_guidance_registry_v1"
    ):
        raise ValueError("Unsupported medical catalogue/guidance registry.")
    _validate_prompt_sources(repo_root, catalogue)
    all_profiles = catalogue["supported_profiles"]
    requested = list(
        dict.fromkeys(
            [
                *(profiles or []),
                *[p for c in bundle.get("comparisons", []) for p in c.get("profile_ids", [])],
            ]
        )
    )
    if not set(requested) <= set(catalogue["recognized_routes"]):
        raise ValueError("Unknown medical profile route.")
    unresolved = not requested or "other" in requested
    selected = list(all_profiles) if unresolved else [p for p in requested if p in all_profiles]
    unsupported = [
        p for p in requested if p in {"systematic_review_meta_analysis", "methods", "other"}
    ]
    protocol = "protocol" in requested
    if protocol and not selected:
        selected = list(all_profiles)
        unresolved = True
    enabled = []
    for pack in guidance["packs"]:
        if pack.get("approved") is True and pack.get("available") is True:
            # Approved guidance loading needs immutable, reviewed source bytes, not flags alone.
            raise ValueError(
                "Guidance activation requires verified sources, not approval flags alone."
            )
    checks = []
    overrides = {
        (row["check_id"], row["study_id"], row.get("comparison_id")): row
        for row in bundle.get("planned_checks", [])
    }
    used_overrides = set()
    for study in bundle["studies"]:
        reports = {r["report_id"] for r in bundle["reports"] if study["study_id"] in r["study_ids"]}
        comparisons = [
            row for row in bundle.get("comparisons", []) if row["study_id"] == study["study_id"]
        ] or [{"comparison_id": None}]
        for comparison in comparisons:
            comparison_id = comparison["comparison_id"]
            scope_profiles = comparison.get("profile_ids", selected)
            scope_unresolved = unresolved or (
                comparison_id is not None and not comparison.get("profile_ids")
            )
            if "other" in scope_profiles:
                scope_unresolved = True
                scope_profiles = list(all_profiles)
            scope_reports = reports
            if comparison.get("report_ids"):
                scope_reports = reports.intersection(comparison["report_ids"])
            sources = [
                d for d in bundle["documents"] if scope_reports.intersection(d["report_ids"])
            ]
            supplied_roles = {d["role"] for d in sources if d["availability"] == "supplied"}
            for rule in catalogue["checks"]:
                if rule["module"] != "core" and not set(rule["profiles"]).intersection(
                    scope_profiles
                ):
                    continue
                key = (rule["check_id"], study["study_id"], comparison_id)
                override_key = (
                    key if key in overrides else (rule["check_id"], study["study_id"], None)
                )
                override = overrides.get(override_key)
                gaps = [
                    roles
                    for roles in rule["required_source_role_groups"]
                    if not supplied_roles.intersection(roles)
                ]
                applicability = (
                    "unknown" if scope_unresolved or rule["conditional"] else "applicable"
                )
                rationale = (
                    "Unresolved design uses a conservative profile union."
                    if scope_unresolved
                    else "Operator-selected profile scope."
                )
                if override:
                    used_overrides.add(override_key)
                    applicability, rationale = override["applicability"], override["rationale"]
                    if scope_unresolved and applicability == "applicable":
                        applicability = "unknown"
                        rationale += " Comparison design remains unresolved."
                checks.append(
                    {
                        "check_id": rule["check_id"],
                        "study_id": study["study_id"],
                        "comparison_id": comparison_id,
                        "reviewer": rule["reviewer"],
                        "applicability": applicability,
                        "rationale": rationale,
                        "required_source_role_groups": rule["required_source_role_groups"],
                        "required_source_gaps": gaps,
                        "source_version_ids": [d.get("source_version_id") for d in sources],
                        "verification_available": not gaps,
                        "execution": "not_requested",
                        "assessment": "cannot_verify" if gaps else "not_assessed",
                        "question": rule["question"],
                        "safeguard": rule["safeguard"],
                        "review_stage": "protocol" if protocol else "report",
                        "stage_scope_reason": (
                            "Review the planned approach; observed results are not required."
                            if protocol
                            else "Review the reported study and its source limitations."
                        ),
                        "guideline_claims_enabled": False,
                        "execution_permissions": {"allow_llm": False, "allow_web_search": False},
                    }
                )
    scope_keys = {(r["check_id"], r["study_id"], r["comparison_id"]) for r in checks}
    if len(scope_keys) != len(checks):
        raise ValueError("Duplicate planned medical check scope.")
    if set(overrides) - used_overrides:
        raise ValueError("A planned check is absent from the selected catalogue/profile scope.")
    record = {
        "schema_version": "medical_review_plan_v1",
        "bundle_sha256": content_hash(bundle),
        "context_sha256": content_hash(context),
        "catalogue_sha256": content_hash(catalogue),
        "guidance_sha256": content_hash(guidance),
        "prompt_sources": [
            catalogue["prompt_provenance"]["shared"],
            *catalogue["prompt_provenance"]["modules"],
        ],
        "selected_profiles": selected,
        "requested_profiles": requested,
        "unsupported_profiles": unsupported,
        "routing_status": "unresolved" if unresolved else "operator_scoped",
        "guidance_status": "unavailable",
        "enabled_guideline_claims": enabled,
        "checks": checks,
        "model_calls": 0,
        "full_coverage": False,
        "limitations": [
            "Planning does not establish inspected coverage or medical capability.",
            "Unsupported profiles and source requirements remain explicit.",
        ],
    }
    return {**record, "plan_id": identity("medicalplan", record)}


def _validate_prompt_sources(repo_root: Path, catalogue: dict[str, Any]) -> None:
    """Bind plans to the exact reviewed prompts; do not accept hashes as unchecked metadata."""
    provenance = catalogue.get("prompt_provenance", {})
    shared, modules = provenance.get("shared"), provenance.get("modules")
    if not isinstance(shared, dict) or not isinstance(modules, list):
        raise ValueError("Missing medical prompt provenance.")
    root = repo_root.resolve()
    paths = set()
    for source in [shared, *modules]:
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise ValueError("Invalid medical prompt provenance.")
        relative = Path(source["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parent != Path("prompts/medical_review")
            or relative in paths
        ):
            raise ValueError("Unsafe or duplicate medical prompt path.")
        path = root / relative
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
            raise ValueError("Symlink medical prompt path refused.")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source.get(
            "sha256"
        ):
            raise ValueError("Medical prompt hash mismatch.")
        paths.add(relative)
    expected = {
        Path(f"prompts/medical_review/{rule['module']}.txt") for rule in catalogue["checks"]
    }
    if not expected <= paths:
        raise ValueError("Missing medical module prompt provenance.")
