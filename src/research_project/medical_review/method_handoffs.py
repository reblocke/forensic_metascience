"""Read-only links to existing, source-qualified R receipts and typed results."""

from __future__ import annotations

import csv
import io
import math
import re
from pathlib import Path
from typing import Any

from research_project.inspect_sr.adapters import (
    _evidence_id_list,
    _validate_method_receipt,
    map_candidate_result,
)
from research_project.medical_review.audit import (
    _proposal,
    _proposal_reference,
    recorded_artifact,
    validate_record_identity,
    validate_run_artifacts,
)
from research_project.medical_review.numeric import scoped_evidence_ids
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    content_hash,
    identity,
    parse_json,
    private_path,
)
from research_project.run_manifest import sha256_file

FIELDS = {
    "schema_version",
    "proposal_id",
    "numeric_run_reference",
    "receipt_artifact",
    "result_artifact",
    "method_id",
    "result_ids",
    "rationale",
}
NUMERIC_RUNS = PRIVATE_RUNS.parent


def _records(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Numerical handoff input exceeds the explicit 20 MiB file limit.")
    if path.suffix == ".json":
        rows = parse_json(raw)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Numerical handoff JSON must contain a list of records.")
        return rows
    if path.suffix != ".csv":
        raise ValueError("Numerical handoffs support existing JSON or CSV artifacts only.")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Numerical artifact has missing or duplicate CSV headers.")
    rows = list(reader)
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Numerical artifact has an inconsistent CSV row shape.")
        if row.get("schema_version") == "method_receipt_v4":
            for field in ("n_input", "n_eligible", "n_evaluated", "n_failed", "n_flagged"):
                value = row.get(field, "")
                if field == "n_flagged" and value in {"", "NA"}:
                    row[field] = None
                elif re.fullmatch(r"[0-9]+", value):
                    row[field] = int(value)
                else:
                    raise ValueError(
                        "Method receipt counts require nonnegative integers or nullable flags."
                    )
        elif row.get("schema_version") == "numeric_result_v2":
            for field in ("value_numeric", "p_value"):
                value = row.get(field, "")
                row[field] = None if value in {"", "NA"} else float(value)
                if row[field] is not None and not math.isfinite(row[field]):
                    raise ValueError("Numerical results require finite values or explicit null.")
            flag = row.get("anomaly_flag", "").lower()
            if flag not in {"", "na", "true", "t", "false", "f"}:
                raise ValueError("Numerical result anomaly flag must be boolean or null.")
            row["anomaly_flag"] = None if flag in {"", "na"} else flag in {"true", "t"}
    return rows


def build_method_handoff(
    repo: Path, dossier: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    """Bind an explicit existing run; never execute R or ingest proposed receipt objects."""
    if (
        not isinstance(request, dict)
        or set(request) != FIELDS
        or (request["schema_version"] != "medical_method_handoff_request_v1")
    ):
        raise ValueError("Unsupported numerical handoff request contract.")
    for field in (
        "numeric_run_reference",
        "receipt_artifact",
        "result_artifact",
        "method_id",
        "rationale",
    ):
        if not isinstance(request[field], str) or not request[field].strip():
            raise ValueError(
                "Numerical handoff requires explicit artifact/method/rationale references."
            )
    proposal = _proposal(dossier, request["proposal_id"])
    ids = request["result_ids"]
    if (
        not isinstance(ids, list)
        or any(not isinstance(x, str) or not x for x in ids)
        or len(set(ids)) != len(ids)
        or len(ids) > 256
    ):
        raise ValueError(
            "Numerical handoff result identities require a unique list of at most 256 references."
        )
    run = private_path(repo, Path(request["numeric_run_reference"]), NUMERIC_RUNS)
    manifest = validate_run_artifacts(repo, run, boundary=NUMERIC_RUNS)
    if "numeric" not in manifest["requested_categories"] or (
        manifest.get("stages", {}).get("numeric_methods", {}).get("status")
        not in {"completed", "failed"}
        or manifest["study_id"] != proposal["study_id"]
    ):
        raise ValueError(
            "Handoff requires a same-study existing numerical run "
            "with a terminal numeric_methods stage."
        )
    paths = {
        kind: recorded_artifact(repo, run, manifest, request[field], boundary=NUMERIC_RUNS)
        for kind, field in (("receipts", "receipt_artifact"), ("results", "result_artifact"))
    }
    receipts = [
        r for r in _records(paths["receipts"]) if r.get("method_id") == request["method_id"]
    ]
    if len(receipts) != 1 or receipts[0].get("run_id") != run.name:
        raise ValueError("Handoff needs one unambiguous same-run method receipt.")
    receipt = receipts[0]
    _validate_method_receipt(receipt)
    rows = _records(paths["results"])
    selected = []
    for result_id in ids:
        matches = [row for row in rows if row.get("result_id") == result_id]
        if (
            len(matches) != 1
            or matches[0].get("run_id") != run.name
            or (matches[0].get("method_id") != request["method_id"])
        ):
            raise ValueError("Handoff requires one exact same-run/same-method result per identity.")
        if matches[0].get("schema_version") != "numeric_result_v2":
            raise ValueError(
                "Numerical handoff results require the existing numeric_result_v2 contract."
            )
        selected.append(matches[0])
    known = scoped_evidence_ids(proposal, dossier["bundle"])
    evidence = [
        {**e, "extraction_method": e["parser"]["id"], "extraction_version": e["parser"]["version"]}
        for e in dossier["bundle"]["evidence"]
        if e["evidence_id"] in known
    ]
    results = []
    for row in selected:
        if request["method_id"] == "scrutiny_rounding_bias":
            mapped = []
            qualification = "blocked_method"
        elif not _evidence_id_list(row.get("input_evidence_ids")) or not row.get("source_locator"):
            mapped = []
            qualification = "unqualified_existing_result_reference"
        else:
            mapped = map_candidate_result(row, [receipt], evidence)
            qualification = (
                "qualified_existing_result_reference"
                if mapped
                else "unqualified_existing_result_reference"
            )
        results.append(
            {
                "result": row,
                "result_sha256": content_hash(row),
                "qualification": qualification,
                "existing_candidate_check_ids": [r["check_id"] for r in mapped],
                "new_candidate_written": False,
                "input_verification": "existing_method_input_contract_no_new_human_verification",
            }
        )
    relative_native = Path(receipt["output_reference"])
    if relative_native.is_absolute() or ".." in relative_native.parts or not relative_native.name:
        raise ValueError("Unsafe native method output reference.")
    native = private_path(repo, paths["receipts"].parent / relative_native, NUMERIC_RUNS)
    if run not in native.parents or not native.is_file():
        raise ValueError("Native method output must exist inside its original run.")
    native_reference = str(native.relative_to(run))
    native_registered = native_reference in {r["path"] for r in manifest["artifacts"]}
    record = {
        "schema_version": "medical_method_handoff_v1",
        "request": request,
        "proposal_id": proposal["proposal_id"],
        "original_proposal_sha256": content_hash(proposal),
        "original_proposal_run_reference": _proposal_reference(dossier, proposal["proposal_id"]),
        "bundle_sha256": content_hash(dossier["bundle"]),
        "numeric_run_reference": str(run.relative_to(repo)),
        "numeric_manifest_sha256": content_hash(manifest),
        "numeric_run_status": manifest["status"],
        "artifact_hashes": {kind: sha256_file(p) for kind, p in paths.items()},
        "native_output": {
            "reference": native_reference,
            "sha256": sha256_file(native),
            "binding": "existing_run_receipt" if native_registered else "captured_at_handoff",
        },
        "receipt": receipt,
        "receipt_sha256": content_hash(receipt),
        "results": results,
        "review_reassurance": False,
        "official_assessment": None,
    }
    if (
        content_hash(validate_run_artifacts(repo, run, boundary=NUMERIC_RUNS))
        != record["numeric_manifest_sha256"]
    ):
        raise ValueError("Numerical run changed during handoff.")
    return {**record, "handoff_id": identity("medicalhandoff", record)}


def validate_method_handoff(repo: Path, dossier: dict[str, Any], record: dict[str, Any]) -> None:
    validate_record_identity(record, "handoff_id", "medicalhandoff")
    if build_method_handoff(repo, dossier, record["request"]) != record:
        raise ValueError("Numerical handoff original result/receipt/source binding changed.")
