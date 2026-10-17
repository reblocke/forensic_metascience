"""Source validation and execution for conditional R summary reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from research_project.inspect_sr.records import evidence_id, source_version_id
from research_project.source_tables import read_docx_tables, read_html_tables

SCOPE_FIELDS = (
    "population",
    "timepoint",
    "orientation",
    "predictor_coding",
    "adjustment",
    "weighting",
    "estimator",
    "se_method",
    "ci_method",
    "test_method",
)
CHECKS = {
    "or_margins",
    "wald_bound",
    "wald_consistency",
    "binary_contrast",
    "exact_contingency",
    "sum",
    "percentage",
}


def bind_evidence(source: dict, locator: str, raw_value: str) -> dict:
    """Identify a proposed transcription without asserting human verification."""
    version = source_version_id(source["source_id"], source["sha256"])
    return {
        "source_id": source["source_id"],
        "source_version_id": version,
        "locator": locator,
        "raw_value": raw_value,
        "evidence_id": evidence_id(version, locator, raw_value, "summary_reconciliation", "1"),
        "input_verification": "proposed_transcription",
    }


def _source_value(source: dict, path: Path, locator: str) -> str:
    if source["format"] == "text":
        match = re.fullmatch(r"line=(\d+)", locator)
        if not match or int(match[1]) < 1:
            raise ValueError("Invalid text evidence locator")
        return path.read_text(encoding="utf-8").splitlines()[int(match[1]) - 1]
    if source["format"] == "html":
        tables = read_html_tables(path.read_text(encoding="utf-8"))
    elif source["format"] == "docx":
        tables = read_docx_tables(path)
    else:
        raise ValueError("Unsupported evidence source format")
    match = re.fullmatch(r"(.+):row=(\d+)(?::column=(\d+))?", locator)
    if not match or int(match[2]) < 1 or (match[3] and int(match[3]) < 1):
        raise ValueError("Invalid table evidence locator")
    row = tables[match[1]][int(match[2]) - 1]
    return row[int(match[3]) - 1] if match[3] else " | ".join(row)


def validate_requests(path: Path, repo_root: Path) -> dict:
    """Recheck source bytes and locators; semantic assumptions remain proposals."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != "summary_reconciliation_v1":
        raise ValueError("Unsupported reconciliation schema")
    root = repo_root.resolve()
    sources = {}
    for source in spec["sources"]:
        source_path = (root / source["path"]).resolve()
        if root not in source_path.parents or not source_path.is_file():
            raise ValueError("Source must be a repository-contained file")
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Source hash mismatch")
        if source["source_id"] in sources:
            raise ValueError("Duplicate source identity")
        sources[source["source_id"]] = (source, source_path)
    ids = set()
    if not spec["requests"]:
        raise ValueError("At least one reconciliation request is required")
    for request in spec["requests"]:
        rid = request["request_id"]
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError("Invalid or repeated request identity")
        ids.add(rid)
        if request["check"] not in CHECKS:
            raise ValueError("Unsupported requested check")
        if request.get("assumption_status") not in {"declared", "conditional", "unknown"}:
            raise ValueError("Explicit assumption status required")
        if any(not isinstance(request.get(key), str) or not request[key] for key in SCOPE_FIELDS):
            raise ValueError("All scope and method declarations are required; use unknown")
        if not request.get("evidence"):
            raise ValueError("Source evidence is required")
        for item in request["evidence"]:
            source, source_path = sources[item["source_id"]]
            expected = bind_evidence(source, item["locator"], item["raw_value"])
            if any(item.get(key) != value for key, value in expected.items()):
                raise ValueError("Changed evidence identity or verification status")
            if _source_value(source, source_path, item["locator"]) != item["raw_value"]:
                raise ValueError("Evidence does not match source locator")
    return spec


def run_reconciliation(input_path: Path, output_dir: Path, repo_root: Path) -> dict:
    """Run base-R calculations once and retain independent execution provenance."""
    root = repo_root.resolve()
    output = output_dir.resolve()
    if root / "data" / "processed" not in output.parents:
        raise ValueError("Reconciliation output must be under repository data/processed")
    if output.exists():
        raise FileExistsError("Reconciliation output already exists")
    original = input_path.read_bytes()
    spec = validate_requests(input_path, root)
    if input_path.read_bytes() != original:
        raise ValueError("Request bytes changed during validation")
    output.mkdir(parents=True)
    snapshot = output / "requests.json"
    snapshot.write_bytes(original)
    code_paths = [
        root / "R/summary_reconciliation.R",
        root / "scripts/run_summary_reconciliation.R",
        Path(__file__),
        root / "src/research_project/source_tables.py",
    ]
    command = [
        "Rscript",
        "--vanilla",
        "scripts/run_summary_reconciliation.R",
        "--input",
        str(snapshot),
        "--out",
        str(output),
    ]
    provenance = {
        "schema_version": "summary_reconciliation_execution_v1",
        "qualification": "candidate_only",
        "human_judgments_created": 0,
        "started_at": datetime.now(UTC).isoformat(),
        "command": command,
        "input_sha256": hashlib.sha256(original).hexdigest(),
        "sources": spec["sources"],
        "code_hashes": {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in code_paths
        },
        "status": "running",
    }
    receipt = output / "run_provenance.json"
    receipt.write_text(json.dumps(provenance, indent=2) + "\n")
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
        (output / "stdout.txt").write_text(result.stdout)
        (output / "stderr.txt").write_text(result.stderr)
        provenance["returncode"] = result.returncode
        result.check_returncode()
        if input_path.read_bytes() != original:
            raise ValueError("Request bytes changed during execution")
        validate_requests(snapshot, root)
        if any(
            hashlib.sha256((root / name).read_bytes()).hexdigest() != digest
            for name, digest in provenance["code_hashes"].items()
        ):
            raise ValueError("Implementation changed during execution")
        provenance["status"] = "completed"
        return json.loads((output / "reconciliation_results.json").read_text())
    except Exception as exc:
        provenance["status"] = "failed"
        provenance["error"] = str(exc)
        raise
    finally:
        provenance["finished_at"] = datetime.now(UTC).isoformat()
        provenance["output_hashes"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file() and p != receipt
        }
        receipt.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
