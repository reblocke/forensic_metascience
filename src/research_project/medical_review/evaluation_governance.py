"""Human-supplied threshold definitions and write-once, recoverable unblinding."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation import _exact, _identifier
from research_project.medical_review.evaluation_assessment import _write
from research_project.medical_review.evaluation_candidates import _snapshot
from research_project.medical_review.evaluation_packets import _json_bytes
from research_project.medical_review.evaluation_reference import _text, load_reference_ledger
from research_project.medical_review.evaluation_synthesis import (
    _code_sources as synthesis_code_sources,
)
from research_project.medical_review.evaluation_synthesis import load_synthesis
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    PRIVATE_SOURCES,
    content_hash,
    identity,
    parse_json,
    private_path,
    read_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

DOMAINS = (
    "important_issue_coverage",
    "serious_false_allegations",
    "traceability",
    "human_verification_burden",
)
PERSON_FIELDS = {
    "human_identity",
    "domain_qualifications",
    "date",
    "conditions_not_previously_unblinded",
    "rationale",
}
CRITERION_FIELDS = {
    "criterion_id",
    "domain",
    "metric_definition",
    "unit",
    "denominator",
    "aggregation",
    "scope_description",
    "direction",
    "threshold_value",
    "rationale",
}
RAW = "generated/medical_evaluation/raw/governance_input.json"
RECEIPT = "generated/medical_evaluation/release_receipt.json"


def _code_sources() -> dict[str, Path]:
    return {**synthesis_code_sources(), "evaluation_governance.py": Path(__file__)}


def _person(person: Any, *, approval: bool = False) -> datetime:
    _exact(person, PERSON_FIELDS | ({"decision"} if approval else set()), "governance human")
    for field in PERSON_FIELDS - {"conditions_not_previously_unblinded"}:
        _text(person[field], field)
    if person["conditions_not_previously_unblinded"] is not True:
        raise ValueError("Human must explicitly attest conditions were not previously unblinded.")
    if approval and person["decision"] != "approved":
        raise ValueError("Threshold decision must be explicitly approved or absent.")
    date = datetime.fromisoformat(person["date"])
    if date.utcoffset() is None:
        raise ValueError("Governance dates require an explicit timezone.")
    return date


def validate_thresholds(reference: dict[str, Any], data: Any) -> dict[str, Any]:
    """Preserve supplied scientific definitions; never choose or interpret cutoffs."""
    _exact(
        data, {"schema_version", "reference_record_id", "criteria", "approval"}, "threshold input"
    )
    if (
        data["schema_version"] != "medical_evaluation_threshold_input_v1"
        or data["reference_record_id"] != reference["ledger"]["ledger_id"]
    ):
        raise ValueError("Threshold schema/reference identity mismatch.")
    criteria = data["criteria"]
    if not isinstance(criteria, list) or len(criteria) > 128:
        raise ValueError("Threshold criteria require an explicit list of at most 128 entries.")
    identifiers, domains = set(), set()
    for row in criteria:
        _exact(row, CRITERION_FIELDS, "threshold criterion")
        _identifier(row["criterion_id"], "criterion_id")
        if row["criterion_id"] in identifiers or row["domain"] not in DOMAINS:
            raise ValueError("Duplicate criterion or unsupported threshold domain.")
        identifiers.add(row["criterion_id"])
        domains.add(row["domain"])
        for field in CRITERION_FIELDS - {"threshold_value", "criterion_id", "domain", "direction"}:
            _text(row[field], field)
        if row["direction"] not in {"at_least", "at_most"}:
            raise ValueError("Threshold direction must be explicit.")
        value = row["threshold_value"]
        if value is not None and (
            type(value) not in {int, float} or (type(value) is float and not math.isfinite(value))
        ):
            raise ValueError("Threshold value must be finite numeric data or unknown (null).")
    approval = data["approval"]
    if approval is not None:
        _person(approval, approval=True)
        if domains != set(DOMAINS) or any(r["threshold_value"] is None for r in criteria):
            raise ValueError("Approval requires all four domains and explicit numeric cutoffs.")
    record = {
        "schema_version": "medical_evaluation_thresholds_v1",
        "record_type": "operator_attested_human_thresholds",
        "reference_record_id": reference["ledger"]["ledger_id"],
        "plan_id": reference["plan"]["plan_id"],
        "evaluation_id": reference["plan"]["evaluation_id"],
        "original": copy.deepcopy(data),
        "criteria": copy.deepcopy(criteria),
        "approval": copy.deepcopy(approval),
        "approval_status": "approved" if approval is not None else "pending",
        "credentials_and_prior_blinding": "operator_attested_not_authenticated",
        "metric_interpretation": "human_defined_not_automatically_evaluated",
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("evaluationthresholds", record)
    _json_bytes(record)
    return record


def _marker(repo: Path, record: dict[str, Any]) -> Path:
    return private_path(
        repo,
        PRIVATE_SOURCES
        / record["evaluation_id"]
        / "evaluation/governance/unblinded"
        / (record["plan_id"] + ".json"),
        PRIVATE_SOURCES,
    )


@contextmanager
def _plan_lock(repo: Path, record: dict[str, Any]):
    path = private_path(repo, _marker(repo, record).with_suffix(".lock"), PRIVATE_SOURCES)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Retain the lock file: deleting it can split waiting processes across inodes.
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _reference(synthesis: dict[str, Any]) -> dict[str, Any]:
    return synthesis["packets"]["assessment"]["packets"]["candidates"]["packets"]["reference"]


def validate_unblinding(thresholds: dict[str, Any], synthesis: dict[str, Any], data: Any):
    _exact(
        data,
        {"schema_version", "threshold_record_id", "synthesis_record_id", "operator"},
        "unblinding input",
    )
    threshold = thresholds["thresholds"]
    source = _reference(synthesis)
    if threshold["approval_status"] != "approved":
        raise ValueError("Unblinding requires explicitly approved thresholds.")
    if (
        data["schema_version"] != "medical_evaluation_unblinding_input_v1"
        or data["threshold_record_id"] != threshold["record_id"]
        or data["synthesis_record_id"] != synthesis["synthesis"]["record_id"]
        or threshold["reference_record_id"] != source["ledger"]["ledger_id"]
        or threshold["plan_id"] != source["plan"]["plan_id"]
    ):
        raise ValueError("Unblinding schema/threshold/synthesis/reference lineage mismatch.")
    date = _person(data["operator"])
    if date < datetime.fromisoformat(
        threshold["approval"]["date"]
    ) or date < datetime.fromisoformat(synthesis["synthesis"]["adjudication"]["date"]):
        raise ValueError("Unblinding cannot precede threshold approval or source adjudication.")
    packets = synthesis["packets"]["packets"]
    record = {
        "schema_version": "medical_evaluation_unblinding_v1",
        "record_type": "operator_attested_condition_release",
        "evaluation_id": threshold["evaluation_id"],
        "plan_id": threshold["plan_id"],
        "reference_record_id": threshold["reference_record_id"],
        "threshold_record_id": threshold["record_id"],
        "synthesis_record_id": synthesis["synthesis"]["record_id"],
        "original": copy.deepcopy(data),
        "condition_map": [
            {k: v[k] for k in ("view_id", "packet_id", "case_id", "condition_id", "track")}
            for v in packets["views"]
        ],
        "item_map": [
            {
                k: v[k]
                for k in (
                    "item_id",
                    "candidate_id",
                    "view_id",
                    "packet_id",
                    "case_id",
                    "attempt_id",
                    "stage",
                )
            }
            for v in packets["items"]
        ],
        "credentials_and_prior_blinding": "operator_attested_not_authenticated",
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("evaluationunblinding", record)
    _json_bytes(record)
    return record


def _start(
    repo: Path,
    parents: list[Path],
    stage: str,
    record: dict[str, Any],
    raw: bytes,
    *,
    recovery: str | None = None,
):
    code_sources = _code_sources()
    code = {k: p.read_bytes() for k, p in code_sources.items()}
    parent_refs = {str(p.relative_to(repo)): sha256_file(p / "run_manifest.json") for p in parents}
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=record["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=parents[0] / "run_manifest.json",
        input_paths=[p / "run_manifest.json" for p in parents],
        settings={
            "medical_evaluation_governance_stage": stage,
            "parent_refs": parent_refs,
            "record_sha256": content_hash(record),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "recovery_of_run_reference": recovery,
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    return run, manifest, parent_refs, code_sources, code


def _archive(run: Path, manifest: Path, raw: bytes, code: dict[str, bytes]) -> None:
    _write(run, manifest, RAW, raw)
    for name, value in code.items():
        _write(run, manifest, "generated/medical_evaluation/code/" + name, value)


def _bookends(
    repo: Path,
    source: Path,
    raw: bytes,
    parents: dict[str, str],
    code_sources: dict[str, Path],
    code: dict[str, bytes],
) -> None:
    if (
        _snapshot(source) != raw
        or any(
            sha256_file(private_path(repo, Path(p), PRIVATE_RUNS) / "run_manifest.json") != h
            for p, h in parents.items()
        )
        or any(code_sources[k].read_bytes() != v for k, v in code.items())
    ):
        raise ValueError("Governance input/parent/code changed while recording.")


def freeze_thresholds(repo_root: Path, reference_run: Path, input_path: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, reference_run, PRIVATE_RUNS)
    reference = load_reference_ledger(repo, parent)
    source = private_path(
        repo, input_path, PRIVATE_SOURCES / reference["plan"]["evaluation_id"] / "evaluation"
    )
    raw = _snapshot(source)
    data = parse_json(raw)
    record = validate_thresholds(reference, data)
    with _plan_lock(repo, record):
        marker = _marker(repo, record)
        if record["approval_status"] == "approved" and marker.exists():
            raise ValueError("Cannot approve thresholds after this plan is already unblinded.")
        run, manifest, parents, code_sources, code = _start(
            repo, [parent], "thresholds", record, raw
        )
        try:
            _archive(run, manifest, raw, code)
            _bookends(repo, source, raw, parents, code_sources, code)
            if validate_thresholds(load_reference_ledger(repo, parent), data) != record:
                raise ValueError("Threshold source/semantic binding changed.")
            if record["approval_status"] == "approved" and marker.exists():
                raise ValueError("Cannot approve thresholds after this plan is already unblinded.")
            _write(
                run, manifest, "processed/medical_evaluation/thresholds.json", _json_bytes(record)
            )
            update_run(manifest, stage="thresholds", status="completed")
            update_run(manifest, status="completed")
        except Exception as error:
            update_run(manifest, status="failed", error=str(error))
            raise
        return run


def _bindings(repo: Path, run: Path, manifest: dict[str, Any]):
    settings = manifest["effective_settings"]
    expected = hashlib.sha256(
        json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if (
        manifest["schema_version"] != "forensics_run_v3"
        or manifest["run_id"] != run.name
        or manifest["effective_settings_sha256"] != expected
    ):
        raise ValueError("Governance manifest identity/settings changed.")
    parents = []
    for reference, digest in settings["parent_refs"].items():
        parent = private_path(repo, Path(reference), PRIVATE_RUNS)
        if sha256_file(parent / "run_manifest.json") != digest:
            raise ValueError("Governance parent manifest changed.")
        parents.append(parent)

    def artifact(reference):
        path = recorded_artifact(repo, run, manifest, reference)
        receipts = [r for r in manifest["artifacts"] if r["path"] == reference]
        if len(receipts) != 1 or sha256_file(path) != receipts[0]["sha256"]:
            raise ValueError("Governance archive receipt changed.")
        return path

    raw = _snapshot(artifact(RAW))
    code = {
        k: sha256_file(artifact("generated/medical_evaluation/code/" + k)) for k in _code_sources()
    }
    if (
        hashlib.sha256(raw).hexdigest() != settings["raw_sha256"]
        or content_hash(code) != settings["code_sha256"]
    ):
        raise ValueError("Governance raw/code archive binding changed.")
    return settings, parents, raw, artifact


def _load(repo: Path, run: Path, stage: str):
    manifest = validate_run_artifacts(repo, run)
    settings, parents, raw, _ = _bindings(repo, run, manifest)
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_governance_stage") != stage
    ):
        raise ValueError("Governance stage is not successfully completed.")
    record = read_json(
        recorded_artifact(repo, run, manifest, f"processed/medical_evaluation/{stage}.json")
    )
    if content_hash(record) != settings["record_sha256"]:
        raise ValueError("Governance record identity changed.")
    return manifest, parents, raw, record


def load_thresholds(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest, parents, raw, record = _load(repo, run, "thresholds")
    if len(parents) != 1:
        raise ValueError("Thresholds require exactly one frozen reference parent.")
    reference = load_reference_ledger(repo, parents[0])
    if validate_thresholds(reference, parse_json(raw)) != record:
        raise ValueError("Threshold reference/semantic binding changed.")
    return {"run_root": run, "manifest": manifest, "reference": reference, "thresholds": record}


def _publish(path: Path, raw: bytes) -> None:
    """Atomically publish complete bytes once, including when storage spans mounts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".unblinding-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o444)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _receipt(repo: Path, marker: Path, record: dict[str, Any], raw: bytes):
    receipt_raw = _snapshot(marker)
    receipt = parse_json(receipt_raw)
    _exact(
        receipt,
        {"schema_version", "record", "original_run_reference", "raw_sha256", "code_sha256"},
        "release receipt",
    )
    if (
        receipt["schema_version"] != "medical_evaluation_unblinding_receipt_v1"
        or receipt["record"] != record
        or receipt["raw_sha256"] != hashlib.sha256(raw).hexdigest()
    ):
        raise ValueError("Existing immutable release has a different request or lineage.")
    reference = receipt["original_run_reference"]
    if not isinstance(reference, str) or Path(reference).is_absolute():
        raise ValueError("Release origin requires a repo-relative private run.")
    origin = private_path(repo, Path(reference), PRIVATE_RUNS)
    manifest = read_json(origin / "run_manifest.json")
    # A crash may leave the original run nonterminal. Validate its already-written
    # archives without changing its manifest or pretending its process completed.
    settings, parents, archived_raw, artifact = _bindings(repo, origin, manifest)
    if (
        settings["medical_evaluation_governance_stage"] != "unblinding"
        or settings["recovery_of_run_reference"] is not None
        or settings["record_sha256"] != content_hash(record)
        or settings["code_sha256"] != receipt["code_sha256"]
        or archived_raw != raw
        or _snapshot(artifact(RECEIPT)) != receipt_raw
        or len(parents) != 2
    ):
        raise ValueError("Original release raw/code/receipt/parent binding changed.")
    # Resolve parents by their stage rather than relying on JSON object ordering.
    threshold_parent = next(
        (
            p
            for p in parents
            if read_json(p / "run_manifest.json")["effective_settings"].get(
                "medical_evaluation_governance_stage"
            )
            == "thresholds"
        ),
        None,
    )
    if threshold_parent is None:
        raise ValueError("Original release lacks its approved threshold parent.")
    synthesis_parent = next(p for p in parents if p != threshold_parent)
    if (
        validate_unblinding(
            load_thresholds(repo, threshold_parent),
            load_synthesis(repo, synthesis_parent),
            parse_json(raw),
        )
        != record
    ):
        raise ValueError("Original release source/semantic binding changed.")
    return receipt_raw, origin, manifest


def _recovery_marker(repo: Path, record: dict[str, Any]) -> Path:
    marker = _marker(repo, record)
    return private_path(repo, marker.with_name(marker.stem + ".recovery.json"), PRIVATE_SOURCES)


def _recovered_run(repo: Path, path: Path, receipt_raw: bytes, record: dict[str, Any]) -> Path:
    raw = _snapshot(path)
    pointer = parse_json(raw)
    _exact(pointer, {"schema_version", "release_sha256", "run_reference"}, "recovery receipt")
    if (
        pointer["schema_version"] != "medical_evaluation_recovery_receipt_v1"
        or pointer["release_sha256"] != hashlib.sha256(receipt_raw).hexdigest()
        or not isinstance(pointer["run_reference"], str)
        or Path(pointer["run_reference"]).is_absolute()
    ):
        raise ValueError("Recovery receipt does not bind this immutable release.")
    run = private_path(repo, Path(pointer["run_reference"]), PRIVATE_RUNS)
    loaded = load_unblinding(repo, run)
    archived = recorded_artifact(
        repo, run, loaded["manifest"], "generated/medical_evaluation/recovery_receipt.json"
    )
    if (
        loaded["unblinding"] != record
        or loaded["manifest"]["effective_settings"]["recovery_of_run_reference"] is None
        or _snapshot(archived) != raw
    ):
        raise ValueError("Recovery run/record/archive binding changed.")
    return run


def record_unblinding(
    repo_root: Path, thresholds_run: Path, synthesis_run: Path, input_path: Path
) -> Path:
    repo = repo_root.resolve()
    thresholds = load_thresholds(repo, thresholds_run)
    synthesis = load_synthesis(repo, synthesis_run)
    source = private_path(
        repo, input_path, PRIVATE_SOURCES / thresholds["thresholds"]["evaluation_id"] / "evaluation"
    )
    raw = _snapshot(source)
    data = parse_json(raw)
    record = validate_unblinding(thresholds, synthesis, data)
    with _plan_lock(repo, record):
        marker = _marker(repo, record)
        receipt_raw, recovery = None, None
        if marker.exists():
            receipt_raw, origin, original_manifest = _receipt(repo, marker, record, raw)
            if original_manifest["status"] == "completed":
                load_unblinding(repo, origin)
                return origin
            recovery_marker = _recovery_marker(repo, record)
            if recovery_marker.exists():
                return _recovered_run(repo, recovery_marker, receipt_raw, record)
            recovery = str(origin.relative_to(repo))
        parents = [thresholds["run_root"], synthesis["run_root"]]
        run, manifest, parent_refs, code_sources, code = _start(
            repo, parents, "unblinding", record, raw, recovery=recovery
        )
        try:
            _archive(run, manifest, raw, code)
            if receipt_raw is None:
                receipt_raw = _json_bytes(
                    {
                        "schema_version": "medical_evaluation_unblinding_receipt_v1",
                        "record": record,
                        "original_run_reference": str(run.relative_to(repo)),
                        "raw_sha256": hashlib.sha256(raw).hexdigest(),
                        "code_sha256": content_hash(
                            {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
                        ),
                    }
                )
            _write(run, manifest, RECEIPT, receipt_raw)
            recovery_raw = None
            if recovery is not None:
                recovery_raw = _json_bytes(
                    {
                        "schema_version": "medical_evaluation_recovery_receipt_v1",
                        "release_sha256": hashlib.sha256(receipt_raw).hexdigest(),
                        "run_reference": str(run.relative_to(repo)),
                    }
                )
                _write(
                    run,
                    manifest,
                    "generated/medical_evaluation/recovery_receipt.json",
                    recovery_raw,
                )
            _bookends(repo, source, raw, parent_refs, code_sources, code)
            if (
                validate_unblinding(
                    load_thresholds(repo, parents[0]), load_synthesis(repo, parents[1]), data
                )
                != record
            ):
                raise ValueError("Unblinding source/semantic binding changed.")
            if recovery is None:
                _publish(marker, receipt_raw)
            elif _receipt(repo, marker, record, raw)[0] != receipt_raw:
                raise ValueError("Immutable release changed during recovery.")
            _write(
                run, manifest, "processed/medical_evaluation/unblinding.json", _json_bytes(record)
            )
            update_run(manifest, stage="unblinding", status="completed")
            update_run(manifest, status="completed")
            if recovery_raw is not None:
                _publish(_recovery_marker(repo, record), recovery_raw)
        except Exception as error:
            update_run(manifest, status="failed", error=str(error))
            raise
        return run


def load_unblinding(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest, parents, raw, record = _load(repo, run, "unblinding")
    if len(parents) != 2:
        raise ValueError("Unblinding requires exact threshold and synthesis parents.")
    threshold_parent = next(
        (
            p
            for p in parents
            if read_json(p / "run_manifest.json")["effective_settings"].get(
                "medical_evaluation_governance_stage"
            )
            == "thresholds"
        ),
        None,
    )
    if threshold_parent is None:
        raise ValueError("Unblinding approved thresholds are missing.")
    thresholds = load_thresholds(repo, threshold_parent)
    synthesis = load_synthesis(repo, next(p for p in parents if p != threshold_parent))
    if validate_unblinding(thresholds, synthesis, parse_json(raw)) != record:
        raise ValueError("Unblinding source/semantic binding changed.")
    receipt_raw, origin, _ = _receipt(repo, _marker(repo, record), record, raw)
    if _snapshot(recorded_artifact(repo, run, manifest, RECEIPT)) != receipt_raw:
        raise ValueError("Unblinding archived release receipt changed.")
    expected_recovery = None if run == origin else str(origin.relative_to(repo))
    if manifest["effective_settings"]["recovery_of_run_reference"] != expected_recovery:
        raise ValueError("Unblinding recovery origin changed.")
    return {
        "run_root": run,
        "manifest": manifest,
        "thresholds": thresholds,
        "synthesis": synthesis,
        "unblinding": record,
    }
