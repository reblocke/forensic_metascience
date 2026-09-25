"""Create immutable, run-scoped provenance manifests for forensic execution."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_MANIFEST_SCHEMA = "forensics_run_v1"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output_root(repo_root: Path, output_root: Path) -> Path:
    repo = repo_root.resolve()
    root_candidate = output_root if output_root.is_absolute() else repo / output_root
    root = root_candidate.resolve()
    if root != repo and repo not in root.parents:
        raise ValueError("Output root must be contained within the repository.")
    protected = [repo / "data" / "raw", repo / "config"]
    if any(root == path or path in root.parents for path in protected):
        raise ValueError("Output root cannot be inside source or configuration directories.")
    return root


def create_run(
    *,
    repo_root: Path,
    output_root: Path,
    study_id: str,
    categories: list[str],
    config_path: Path,
    input_paths: list[Path],
    required_input_paths: list[Path] | None = None,
    run_id: str | None = None,
) -> tuple[Path, Path]:
    """Create a fresh run directory and its initial manifest; refuse collisions."""
    repo = repo_root.resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", study_id):
        raise ValueError(f"Invalid study ID: {study_id!r}")
    root = validate_output_root(repo, output_root)
    selected_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", selected_run_id):
        raise ValueError(f"Invalid run ID: {selected_run_id!r}")
    study_root = root / study_id
    if study_root.exists() and (
        study_root.resolve() != study_root or root not in study_root.resolve().parents
    ):
        raise ValueError("Study output directory cannot resolve outside the output root.")
    run_root = study_root / selected_run_id
    resolved_run_root = run_root.resolve()
    if root not in resolved_run_root.parents:
        raise ValueError("Run destination must remain contained within the output root.")
    if run_root.exists():
        raise FileExistsError(f"Run destination already exists: {run_root}")
    run_root.mkdir(parents=True)
    (run_root / "processed").mkdir()
    (run_root / "reports").mkdir()
    required_inputs = {path.resolve() for path in (required_input_paths or [])}
    required_inputs.add(config_path.resolve())
    paths = list(dict.fromkeys([config_path, *input_paths]))
    fingerprints = []
    for path in paths:
        resolved = path.resolve()
        try:
            recorded_path = resolved.relative_to(repo).as_posix()
        except ValueError:
            recorded_path = str(resolved)
        fingerprints.append(
            {
                "path": recorded_path,
                "sha256": sha256_file(resolved),
                "available": resolved.is_file(),
                "required": resolved in required_inputs,
            }
        )
    manifest_path = run_root / "run_manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": RUN_MANIFEST_SCHEMA,
        "run_id": selected_run_id,
        "study_id": study_id,
        "repo_root": str(repo),
        "created_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "requested_categories": categories,
        "schema_versions": {
            "run_manifest": RUN_MANIFEST_SCHEMA,
            "numeric_method_receipt": "method_receipt_v1",
            "meta_evidence_coverage": "evidence_coverage_v1",
        },
        "method_versions": {"numeric": "numeric_eligibility_precision_v3"},
        "input_fingerprints": fingerprints,
        "stages": {},
        "artifacts": [],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return run_root, manifest_path


def update_run(
    manifest_path: Path,
    *,
    stage: str | None = None,
    status: str | None = None,
    error: str | None = None,
    artifact: str | None = None,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if stage is not None and status is not None:
        manifest["stages"][stage] = {"status": status, "updated_at": datetime.now(UTC).isoformat()}
    if status in {"completed", "failed"} and stage is None:
        manifest["status"] = status
        manifest["completed_at"] = datetime.now(UTC).isoformat()
    if error:
        manifest["error"] = error
    if artifact:
        artifact_path = Path(artifact).resolve()
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Cannot receipt missing run artifact: {artifact_path}")
        run_root = manifest_path.parent.resolve()
        try:
            recorded_path = artifact_path.relative_to(run_root).as_posix()
        except ValueError as exc:
            raise ValueError("Run artifacts must be inside their run directory.") from exc
        manifest["artifacts"].append(
            {
                "path": recorded_path,
                "sha256": sha256_file(artifact_path),
                "available": True,
            }
        )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
