"""Dependency-light validators and stable identities for INSPECT-SR records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CATALOGUE_SCHEMA = "inspect_sr_catalogue_v1"
ASSESSMENT_SCHEMA = "inspect_sr_assessment_v1"
CHECK_RESPONSES = {"Yes", "No", "Unclear", "Not Applicable"}
CHECK_STATES = {"pending", "assessed", "not_assessed_early_stop"}
EXPECTED_CHECK_IDS = tuple(
    [f"1.{number}" for number in range(1, 4)]
    + [f"2.{number}" for number in range(1, 6)]
    + [f"3.{number}" for number in range(1, 3)]
    + [f"4.{number}" for number in range(1, 12)]
)
GUIDANCE_COMMIT = "a349c4f1ddd9d232dfc2632938aad31382a9a770"


def _canonical_hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_canonical_hash(value)}"


def stable_trial_id(local_identity: str) -> str:
    """Return a stable local trial ID; no registry ID is required."""
    identity = local_identity.strip()
    if not identity:
        raise ValueError("A nonempty local trial identity is required.")
    return _stable_id("trial", identity)


def stable_report_id(persistent_identifier: str, *, local_key: str | None = None) -> str:
    """Use a persistent publication ID or a caller-supplied stable local key."""
    identifier = persistent_identifier.strip().lower()
    if identifier.startswith("https://doi.org/"):
        identifier = identifier.removeprefix("https://doi.org/")
    elif identifier.startswith("http://doi.org/"):
        identifier = identifier.removeprefix("http://doi.org/")
    if not identifier:
        identifier = (local_key or "").strip()
    if not identifier:
        raise ValueError("A persistent report identifier or stable local_key is required.")
    return _stable_id("report", identifier)


def source_version_id(source_id: str, content_sha256: str) -> str:
    if not source_id.strip() or not re.fullmatch(r"[a-f0-9]{64}", content_sha256):
        raise ValueError("Source version requires a source ID and a lowercase SHA-256 hash.")
    return _stable_id("sourcever", {"source_id": source_id, "sha256": content_sha256})


def evidence_id(
    source_version: str,
    locator: str,
    raw_value: str,
    extraction_method: str,
    extraction_version: str,
) -> str:
    """Hash source version, locator, exact value, and parser identity, never row order."""
    if not all(
        value.strip() for value in (source_version, locator, extraction_method, extraction_version)
    ):
        raise ValueError(
            "Evidence identity requires source version, locator, and parser provenance."
        )
    return _stable_id(
        "evidence",
        {
            "source_version_id": source_version,
            "locator": locator.strip(),
            "raw_value": raw_value,
            "extraction_method": extraction_method.strip(),
            "extraction_version": extraction_version.strip(),
        },
    )


def link_report_to_trial(
    trial_id: str, report_id: str, *, reviewed: bool, multi_trial_report: bool
) -> dict[str, str | bool]:
    if not trial_id or not report_id:
        raise ValueError("Report-to-trial links require both persistent IDs.")
    if multi_trial_report and not reviewed:
        raise ValueError("A multi-trial report requires a reviewed mapping.")
    return {
        "link_id": _stable_id("trialreport", {"trial_id": trial_id, "report_id": report_id}),
        "trial_id": trial_id,
        "report_id": report_id,
        "reviewed_mapping": reviewed,
    }


def verify_guidance_snapshot(snapshot_dir: Path) -> list[str]:
    """Return hash/identity errors for the pinned upstream guidance files."""
    retrieval_path = snapshot_dir / "retrieval.json"
    if not retrieval_path.is_file():
        return [f"Missing retrieval receipt: {retrieval_path}"]
    receipt = json.loads(retrieval_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    checksum_path = snapshot_dir / "SHA256SUMS"
    if not checksum_path.is_file():
        errors.append(f"Missing snapshot checksum manifest: {checksum_path}")
    else:
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            expected, separator, relative = line.partition("  ")
            relative = relative.removeprefix("./")
            source_path = (snapshot_dir / relative).resolve()
            if not separator or snapshot_dir.resolve() not in source_path.parents:
                errors.append(f"Invalid snapshot checksum entry: {line}")
                continue
            if not source_path.is_file():
                errors.append(f"Missing checksummed snapshot file: {relative}")
            elif hashlib.sha256(source_path.read_bytes()).hexdigest() != expected:
                errors.append(f"Snapshot checksum mismatch: {relative}")
    if receipt.get("commit") != GUIDANCE_COMMIT:
        errors.append("Guidance commit does not match the selected immutable revision.")
    for item in receipt.get("files", []):
        path = snapshot_dir / item["path"]
        if not path.is_file():
            errors.append(f"Missing guidance source file: {item['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            errors.append(f"Guidance source hash mismatch: {item['path']}")
    return errors


def load_catalogue(path: Path) -> dict[str, Any]:
    errors = verify_guidance_snapshot(path.parent)
    if errors:
        raise ValueError("Invalid pinned guidance snapshot: " + "; ".join(errors))
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    validate_catalogue(catalogue)
    receipt = json.loads((path.parent / "retrieval.json").read_text(encoding="utf-8"))
    guidance_hash = _canonical_hash(
        {
            "commit": receipt["commit"],
            "files": [(item["path"], item["sha256"]) for item in receipt["files"]],
        }
    )
    if catalogue.get("guidance_sha256") != guidance_hash:
        raise ValueError("Catalogue guidance hash does not match its immutable source receipt.")
    return catalogue


def validate_catalogue(catalogue: dict[str, Any]) -> None:
    if catalogue.get("schema_version") != CATALOGUE_SCHEMA:
        raise ValueError("Unsupported INSPECT-SR catalogue schema.")
    if catalogue.get("guidance_commit") != GUIDANCE_COMMIT:
        raise ValueError("Catalogue does not reference the pinned guidance commit.")
    checks = catalogue.get("checks")
    if not isinstance(checks, list):
        raise ValueError("Catalogue checks must be a list.")
    identifiers = [item.get("check_id") for item in checks if isinstance(item, dict)]
    if len(identifiers) != len(checks) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Catalogue contains malformed or duplicate check IDs.")
    if tuple(identifiers) != EXPECTED_CHECK_IDS:
        raise ValueError("Catalogue must contain all 21 official IDs in canonical order.")
    for item in checks:
        check_id = item["check_id"]
        if item.get("domain_id") != check_id.split(".", maxsplit=1)[0]:
            raise ValueError(f"Check {check_id} has an inconsistent domain membership.")
        if not item.get("official_wording") or not item.get("source_path"):
            raise ValueError(f"Check {check_id} is missing its official wording or source.")
        if not item.get("source_sha256") or not item.get("source_url"):
            raise ValueError(f"Check {check_id} is missing source provenance.")


def create_assessment(trial_id: str, guidance_version: str, guidance_sha256: str) -> dict[str, Any]:
    if not trial_id or not guidance_version or not guidance_sha256:
        raise ValueError("Trial identity and guidance version/hash are required.")
    assessment_id = _stable_id(
        "assessment",
        {
            "trial_id": trial_id,
            "guidance_version": guidance_version,
            "guidance_sha256": guidance_sha256,
        },
    )
    checks = [
        {
            "check_id": check_id,
            "workflow_status": "pending",
            "response": None,
            "rationale": None,
            "evidence_ids": [],
        }
        for check_id in EXPECTED_CHECK_IDS
    ]
    assessment = {
        "schema_version": ASSESSMENT_SCHEMA,
        "method_revision": "inspect_sr_record_model_v1",
        "assessment_id": assessment_id,
        "trial_id": trial_id,
        "guidance_version": guidance_version,
        "guidance_sha256": guidance_sha256,
        "created_at": datetime.now(UTC).isoformat(),
        "review_revision": 1,
        "workflow_status": "in_progress",
        "checks": checks,
    }
    validate_assessment(assessment)
    return assessment


def validate_assessment(assessment: dict[str, Any]) -> None:
    if assessment.get("schema_version") != ASSESSMENT_SCHEMA:
        raise ValueError("Unsupported INSPECT-SR assessment schema.")
    checks = assessment.get("checks")
    if not isinstance(checks, list) or [item.get("check_id") for item in checks] != list(
        EXPECTED_CHECK_IDS
    ):
        raise ValueError("Assessment must contain all 21 checks exactly once in canonical order.")
    for item in checks:
        status, response = item.get("workflow_status"), item.get("response")
        if status not in CHECK_STATES:
            raise ValueError(f"Invalid workflow status for check {item['check_id']}.")
        if response is not None and response not in CHECK_RESPONSES:
            raise ValueError(f"Invalid human response for check {item['check_id']}.")
        if status == "pending" and response is not None:
            raise ValueError("Pending checks must have null responses.")
        if status == "assessed" and response is None:
            raise ValueError("Assessed checks require a response, including Unclear if needed.")
        if status == "not_assessed_early_stop" and response is not None:
            raise ValueError("Early-stopped checks keep null responses.")


def new_assessment_for_guidance(
    previous: dict[str, Any],
    guidance_version: str,
    guidance_sha256: str,
    *,
    explicit_review: bool = False,
) -> dict[str, Any]:
    if not explicit_review:
        raise ValueError("Guidance migration requires explicit review.")
    revised = create_assessment(previous["trial_id"], guidance_version, guidance_sha256)
    revised["review_revision"] = int(previous.get("review_revision", 1)) + 1
    revised["supersedes_assessment_id"] = previous["assessment_id"]
    revised["migration_status"] = "new_guidance_requires_review"
    return revised


def write_json_exclusive(path: Path, record: dict[str, Any]) -> None:
    """Create a JSON record once; never overwrite a human-authored record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
