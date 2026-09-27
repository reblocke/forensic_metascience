#!/usr/bin/env python3
"""Local, offline command line for private INSPECT-SR review records."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_project.inspect_sr.adapters import (
    CHECK_ROUTES,
    build_candidate_dossier,
    map_candidate_result,
)
from research_project.inspect_sr.manual_evidence import validate_manual_evidence
from research_project.inspect_sr.records import (
    create_assessment,
    evidence_id,
    load_catalogue,
    source_version_id,
    stable_trial_id,
    validate_assessment,
)
from research_project.inspect_sr.reporting import build_report_model
from research_project.inspect_sr.review import (
    build_disagreement_table,
    create_adjudication_record,
    create_reviewer_submission,
    finalize_review,
    resolve_reviews,
)
from research_project.inspect_sr.snapshot import create_source_snapshot, validate_source_snapshot
from research_project.inspect_sr.synthesis_export import build_synthesis_export
from research_project.inspect_sr.validation import (
    validate_finalization,
    validate_reviewer_submission,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        records = frame.to_dict(orient="records")
        for record in records:
            if record.get("schema_version") == "method_receipt_v4":
                for field in ("n_input", "n_eligible", "n_evaluated", "n_failed"):
                    record[field] = _parse_receipt_count(record.get(field), field)
                record["n_flagged"] = _parse_receipt_count(
                    record.get("n_flagged"), "n_flagged", nullable=True
                )
        return records
    value = read_json(path)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Expected a JSON list of records in {path}.")
    return value


def _parse_receipt_count(value: Any, field: str, *, nullable: bool = False) -> int | None:
    if nullable and value in {"", "NA", None}:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Method receipt {field} count must be a nonnegative integer.")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        number = int(value)
    else:
        raise ValueError(f"Method receipt {field} count must be a nonnegative integer.")
    if number < 0:
        raise ValueError(f"Method receipt {field} count must be a nonnegative integer.")
    return number


def write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def private_root(path: Path) -> Path:
    root = path.resolve()
    allowed = (ROOT / "data" / "private" / "inspect_sr").resolve()
    if root != allowed and allowed not in root.parents:
        raise ValueError("INSPECT-SR human records must be stored beneath data/private/inspect_sr.")
    return root


def record_path(store: Path, folder: str, record_id: str, suffix: str = ".json") -> Path:
    for component in (folder, record_id):
        if not component or component in {".", ".."} or Path(component).name != component:
            raise ValueError("Private record path components must be simple identifiers.")
    root = private_root(store)
    destination = root / folder / f"{record_id}{suffix}"
    if root not in destination.resolve().parents:
        raise ValueError("Private record destination escapes the private store.")
    return destination


def new_report_output(report_dir: Path, filename: str) -> Path:
    report_root = report_dir.absolute()
    resolved_root = report_dir.resolve()
    private_root(resolved_root)
    if report_root != resolved_root:
        raise ValueError("Private report output directory cannot be a symlink.")
    if not filename or Path(filename).name != filename:
        raise ValueError("Private report output must be a simple filename.")
    destination = report_dir / filename
    resolved_destination = destination.resolve()
    if report_root not in resolved_destination.parents:
        raise ValueError("Private report output escapes its revision directory.")
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Private report output already exists or is redirected: {filename}.")
    return destination


def load_current_snapshot(store: Path, assessment: dict[str, Any], digest: str) -> dict[str, Any]:
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("A current source snapshot SHA-256 is required.")
    snapshot = read_json(record_path(store, "snapshots", digest))
    validate_source_snapshot(
        snapshot, assessment, snapshot["source_versions"], snapshot["evidence_records"]
    )
    if snapshot["source_snapshot_sha256"] != digest:
        raise ValueError("Stored source snapshot does not match its requested identity.")
    return snapshot


def stored_record(
    store: Path, folder: str, record: dict[str, Any], id_field: str
) -> dict[str, Any]:
    stored = read_json(record_path(store, folder, str(record[id_field])))
    if stored != record:
        raise ValueError(f"Referenced {folder} record differs from the private store.")
    return stored


def stored_review_chain(store: Path, finalization: dict[str, Any]) -> dict[str, Any]:
    stored_record(store, "finalizations", finalization, "finalization_id")
    assessment = read_json(record_path(store, "assessments", finalization["assessment_id"]))
    validate_assessment(assessment)
    snapshot = load_current_snapshot(store, assessment, finalization["source_snapshot_sha256"])
    adjudication = read_json(record_path(store, "adjudications", finalization["adjudication_id"]))
    if sorted(adjudication["reviewer_submission_ids"]) != sorted(
        finalization["reviewer_submission_ids"]
    ):
        raise ValueError("Adjudication and finalization reviewer references differ.")
    reviewers = [
        read_json(record_path(store, "reviewer-submissions", item))
        for item in adjudication["reviewer_submission_ids"]
    ]
    resolved = read_json(record_path(store, "resolved-reviews", finalization["review_record_id"]))
    if resolve_reviews(reviewers[0], reviewers[1], adjudication) != resolved:
        raise ValueError(
            "Stored resolved review differs from its human submissions and adjudication."
        )
    return {
        "assessment": assessment,
        "source_snapshot": snapshot,
        "source_versions": snapshot["source_versions"],
        "evidence_records": snapshot["evidence_records"],
        "candidate_dossier": {"coverage": [], "candidate_evidence": []},
        "reviewer_submissions": reviewers,
        "adjudication": adjudication,
    }


def command_snapshot(args: argparse.Namespace) -> None:
    assessment = read_json(args.assessment)
    snapshot = create_source_snapshot(
        assessment, read_records(args.source_versions), read_records(args.evidence)
    )
    store = private_root(args.store)
    write_exclusive(record_path(store, "snapshots", snapshot["source_snapshot_sha256"]), snapshot)
    print(snapshot["source_snapshot_sha256"])


def command_prepare(args: argparse.Namespace) -> None:
    catalogue = load_catalogue(args.catalogue)
    trial_id = stable_trial_id(args.trial_key)
    assessment = create_assessment(
        trial_id, str(catalogue["guidance_version"]), str(catalogue["guidance_sha256"])
    )
    store = private_root(args.store)
    write_exclusive(record_path(store, "assessments", assessment["assessment_id"]), assessment)
    print(assessment["assessment_id"])


def command_prepare_evidence(args: argparse.Namespace) -> None:
    if args.check_id not in CHECK_ROUTES:
        raise ValueError(f"Unknown INSPECT-SR check ID: {args.check_id}")
    source = args.source_file.resolve(strict=True)
    content_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    sourcever = source_version_id(args.source_id, content_hash)
    evidence = {
        "schema_version": "inspect_sr_evidence_v2",
        "record_type": "source_evidence",
        "source_id": args.source_id,
        "source_version_id": sourcever,
        "content_sha256": content_hash,
        "locator": args.locator,
        "raw_value": args.raw_value,
        "extraction_method": args.extraction_method,
        "extraction_version": args.extraction_version,
    }
    evidence["evidence_id"] = evidence_id(
        sourcever,
        args.locator,
        args.raw_value,
        args.extraction_method,
        args.extraction_version,
    )
    store = private_root(args.store)
    source_version = {
        "schema_version": "inspect_sr_source_version_v2",
        "record_type": "source_version",
        "source_id": args.source_id,
        "source_version_id": sourcever,
        "source_name": source.name,
        "source_path": str(source),
        "content_sha256": content_hash,
    }
    version_path = record_path(store, "source-versions-v2", sourcever)
    if version_path.exists():
        if read_json(version_path) != source_version:
            raise ValueError("Stored source-version identity conflicts with its content hash.")
    else:
        write_exclusive(version_path, source_version)
    evidence_path = record_path(store, "evidence", evidence["evidence_id"])
    if evidence_path.exists():
        if read_json(evidence_path) != evidence:
            raise ValueError("Stored evidence identity conflicts with its content.")
    else:
        write_exclusive(evidence_path, evidence)
    print(evidence["evidence_id"])


def command_manual_evidence(args: argparse.Namespace) -> None:
    record = validate_manual_evidence(read_json(args.record))
    version_path = record_path(
        private_root(args.store), "source-versions-v2", str(record["source_version_id"])
    )
    if not version_path.is_file():
        raise ValueError(
            "Manual evidence must reference a source version prepared in this private store."
        )
    version = read_json(version_path)
    if version.get("source_id") != record.get("source_id"):
        raise ValueError(
            "Manual evidence source identity does not match the stored source version."
        )
    write_exclusive(
        record_path(private_root(args.store), "manual-evidence", record["evidence_id"]), record
    )
    print(record["evidence_id"])


def command_submit(args: argparse.Namespace) -> None:
    assessment = read_json(args.assessment)
    validate_assessment(assessment)
    snapshot = load_current_snapshot(
        private_root(args.store), assessment, args.source_snapshot_sha256
    )
    available_ids = {item["evidence_id"] for item in snapshot["evidence_records"]}
    if any(set(row.get("evidence_ids", [])) - available_ids for row in read_json(args.checks)):
        raise ValueError("Reviewer submission references evidence outside the current snapshot.")
    submission = create_reviewer_submission(
        assessment,
        reviewer_id=args.reviewer_id,
        source_snapshot_sha256=args.source_snapshot_sha256,
        checks=read_json(args.checks),
        submission_revision=args.revision,
    )
    write_exclusive(
        record_path(private_root(args.store), "reviewer-submissions", submission["submission_id"]),
        submission,
    )
    print(submission["submission_id"])


def command_compare(args: argparse.Namespace) -> None:
    left, right = read_json(args.first), read_json(args.second)
    write_exclusive(private_root(args.output), build_disagreement_table(left, right))


def command_adjudicate(args: argparse.Namespace) -> None:
    first, second = read_json(args.first), read_json(args.second)
    store = private_root(args.store)
    stored_record(store, "reviewer-submissions", first, "submission_id")
    stored_record(store, "reviewer-submissions", second, "submission_id")
    assessment = read_json(record_path(store, "assessments", first["assessment_id"]))
    snapshot = load_current_snapshot(store, assessment, first["source_snapshot_sha256"])
    if second["source_snapshot_sha256"] != snapshot["source_snapshot_sha256"]:
        raise ValueError("Reviewers must use the same current source snapshot.")
    adjudication = create_adjudication_record(
        first,
        second,
        adjudicator_id=args.adjudicator_id,
        decisions=read_json(args.decisions),
    )
    resolved = resolve_reviews(first, second, adjudication)
    available_ids = {item["evidence_id"] for item in snapshot["evidence_records"]}
    if any(set(row["evidence_ids"]) - available_ids for row in resolved["checks"]):
        raise ValueError("Adjudication references evidence outside the current snapshot.")
    write_exclusive(
        record_path(store, "adjudications", adjudication["adjudication_id"]), adjudication
    )
    write_exclusive(
        record_path(store, "resolved-reviews", resolved["resolved_review_id"]), resolved
    )
    print(resolved["resolved_review_id"])


def command_finalize(args: argparse.Namespace) -> None:
    review = read_json(args.review)
    store = private_root(args.store)
    if review.get("record_type") != "resolved_human_review":
        raise ValueError("CLI finalization requires two reviewed submissions and adjudication.")
    stored_record(store, "resolved-reviews", review, "resolved_review_id")
    assessment = read_json(record_path(store, "assessments", review["assessment_id"]))
    snapshot = load_current_snapshot(store, assessment, review["source_snapshot_sha256"])
    adjudication = read_json(record_path(store, "adjudications", review["adjudication_id"]))
    reviewers = [
        read_json(record_path(store, "reviewer-submissions", item))
        for item in adjudication["reviewer_submission_ids"]
    ]
    if resolve_reviews(reviewers[0], reviewers[1], adjudication) != review:
        raise ValueError("Resolved review does not match its original human record chain.")
    available_ids = {item["evidence_id"] for item in snapshot["evidence_records"]}
    if not available_ids or any(
        set(row["evidence_ids"]) - available_ids for row in review["checks"]
    ):
        raise ValueError("Finalization requires current source evidence for every referenced ID.")
    finalization = finalize_review(
        review,
        read_json(args.judgments),
        early_stop=args.early_stop,
        early_stop_reason=args.early_stop_reason,
    )
    write_exclusive(
        record_path(store, "finalizations", finalization["finalization_id"]),
        finalization,
    )
    print(finalization["finalization_id"])


def command_candidate_map(args: argparse.Namespace) -> None:
    receipts = read_records(args.receipts)
    results = read_records(args.results)
    evidence = read_records(args.evidence)
    candidates = []
    unresolved = []
    for result in results:
        try:
            mapped = map_candidate_result(result, receipts, evidence)
        except ValueError as exc:
            if not any(
                marker in str(exc)
                for marker in (
                    "stable result ID and exact source locator",
                    "exact input evidence IDs",
                    "unavailable evidence IDs",
                    "lacks a source version",
                )
            ):
                raise
            mapped = []
            reason = str(exc)
        else:
            reason = "No current completed receipt with matching source evidence was found."
        candidates.extend(mapped)
        if not mapped:
            unresolved.append(
                {
                    "schema_version": "inspect_sr_unresolved_candidate_v1",
                    "result_id": result.get("result_id"),
                    "run_id": result.get("run_id"),
                    "method_id": result.get("method_id"),
                    "status": "unresolved",
                    "reason": reason,
                }
            )
    dossier = build_candidate_dossier(receipts, candidates)
    dossier.update(
        {
            "schema_version": "inspect_sr_candidate_dossier_v2",
            "unresolved_results": unresolved,
        }
    )
    write_exclusive(private_root(args.output), dossier)


def command_validate(args: argparse.Namespace) -> None:
    record = read_json(args.record)
    if args.kind == "assessment":
        validate_assessment(record)
    elif args.kind == "reviewer-submission":
        validate_reviewer_submission(record)
    elif args.kind == "finalization":
        chain = stored_review_chain(private_root(args.store), record)
        validate_finalization(
            record,
            current_source_snapshot_sha256=chain["source_snapshot"]["source_snapshot_sha256"],
        )
        model = build_report_model(
            assessment=chain["assessment"],
            catalogue=load_catalogue(args.catalogue),
            source_versions=chain["source_versions"],
            evidence_records=chain["evidence_records"],
            candidate_dossier=chain["candidate_dossier"],
            reviewer_submissions=chain["reviewer_submissions"],
            adjudication=chain["adjudication"],
            finalization=record,
            current_source_snapshot_sha256=chain["source_snapshot"]["source_snapshot_sha256"],
            source_snapshot=chain["source_snapshot"],
        )
        if not model["report_status"].startswith("FINALIZED"):
            raise ValueError("Finalization has no complete current review chain.")
    elif args.kind == "manual-evidence":
        validate_manual_evidence(record)
    elif args.kind == "catalogue":
        load_catalogue(args.record)
    elif args.kind == "candidate-dossier":
        if not isinstance(record.get("coverage"), list) or not isinstance(
            record.get("candidate_evidence"), list
        ):
            raise ValueError(
                "Candidate dossier must contain coverage and candidate_evidence lists."
            )
    print("valid")


def command_render(args: argparse.Namespace) -> None:
    store = private_root(args.store)
    assessment = read_json(args.assessment)
    snapshot = load_current_snapshot(store, assessment, args.source_snapshot_sha256)
    sources = read_records(args.source_versions)
    evidence = read_records(args.evidence)
    validate_source_snapshot(snapshot, assessment, sources, evidence)
    finalization = read_json(args.finalization) if args.finalization else None
    reviewers = [read_json(path) for path in args.reviewer_submission]
    adjudication = read_json(args.adjudication) if args.adjudication else None
    if finalization is not None:
        chain = stored_review_chain(store, finalization)
        if (
            chain["assessment"] != assessment
            or {item["submission_id"]: item for item in chain["reviewer_submissions"]}
            != {item["submission_id"]: item for item in reviewers}
            or chain["adjudication"] != adjudication
        ):
            raise ValueError("Finalized report inputs differ from their stored review chain.")
        reviewers = chain["reviewer_submissions"]
    model = build_report_model(
        assessment=assessment,
        catalogue=load_catalogue(args.catalogue),
        source_versions=sources,
        evidence_records=evidence,
        candidate_dossier=read_json(args.candidates),
        reviewer_submissions=reviewers,
        adjudication=adjudication,
        finalization=finalization,
        method_receipts=read_records(args.receipts),
        current_source_snapshot_sha256=args.source_snapshot_sha256,
        source_snapshot=snapshot,
    )
    report_dir = record_path(
        store / "reports", assessment["assessment_id"], args.revision, suffix=""
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    qmd = ROOT / "notebooks" / "inspect_sr_assessment.qmd"
    formats = ("html", "pdf") if args.format == "both" else (args.format,)
    expected_outputs = ["report-model.json", qmd.name] + [
        f"assessment.{output_format}" for output_format in formats
    ]
    for filename in expected_outputs:
        new_report_output(report_dir, filename)

    model_path = new_report_output(report_dir, "report-model.json")
    write_exclusive(model_path, model)
    copied_qmd = new_report_output(report_dir, qmd.name)
    with copied_qmd.open("xb") as destination, qmd.open("rb") as source:
        shutil.copyfileobj(source, destination)
    for output_format in formats:
        output_name = f"assessment.{output_format}"
        new_report_output(report_dir, output_name)
        env = {
            **os.environ,
            "INSPECT_SR_REPORT_JSON": str(model_path.resolve()),
        }
        with tempfile.TemporaryDirectory(prefix=".render-", dir=report_dir) as temporary:
            temporary_dir = Path(temporary)
            temporary_qmd = temporary_dir / qmd.name
            shutil.copy2(copied_qmd, temporary_qmd)
            subprocess.run(
                [
                    "quarto",
                    "render",
                    str(temporary_qmd),
                    "--to",
                    output_format,
                    "--output",
                    output_name,
                ],
                cwd=temporary_dir,
                env=env,
                check=True,
            )
            rendered = temporary_dir / output_name
            if not rendered.is_file() or rendered.is_symlink():
                raise RuntimeError(f"Quarto did not create a regular report: {output_name}")
            output_path = new_report_output(report_dir, output_name)
            with output_path.open("xb") as destination, rendered.open("rb") as source:
                shutil.copyfileobj(source, destination)
    print(report_dir)


def command_export(args: argparse.Namespace) -> None:
    store = private_root(args.store)
    finalizations = [read_json(path) for path in args.finalization]
    catalogue = load_catalogue(args.catalogue)
    contexts = {}
    for finalization in finalizations:
        chain = stored_review_chain(store, finalization)
        contexts[finalization["trial_id"]] = {**chain, "catalogue": catalogue}
    output = build_synthesis_export(
        finalizations,
        read_json(args.reports),
        read_json(args.comparisons),
        read_json(args.policy),
        guidance_sha256=args.guidance_sha256,
        current_source_snapshot_sha256_by_trial=read_json(args.current_sources),
        unresolved_policy=args.unresolved,
        policy_variant=args.policy_variant,
        public=args.public,
        public_trial_ids=args.trial_id or (),
        public_reviewed_by=args.reviewed_by,
        review_context_by_trial=contexts,
    )
    target = record_path(store, "exports", args.output.name, suffix="")
    if args.public:
        target = args.output.resolve()
        if private_root(args.store) in target.parents:
            raise ValueError("Public export destination cannot be inside the private review store.")
        payload_hash = hashlib.sha256(
            json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        approval = {
            "schema_version": "inspect_sr_public_export_approval_v1",
            "record_type": "private_public_export_approval",
            "reviewed_by": args.reviewed_by,
            "approved_at": datetime.now(UTC).isoformat(),
            "payload_sha256": payload_hash,
            "destination": str(target),
            "trial_ids": list(args.trial_id or ()),
        }
    if args.public:
        write_exclusive(
            record_path(store, "public-export-approvals", payload_hash),
            approval,
        )
    write_exclusive(target, output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare", help="Create a pending review from the pinned catalogue."
    )
    prepare.add_argument(
        "--catalogue", type=Path, default=ROOT / "config/inspect_sr/v1.1.2/catalogue.json"
    )
    prepare.add_argument("--trial-key", required=True, help="Stable local trial identity.")
    prepare.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    prepare.set_defaults(func=command_prepare)

    evidence = commands.add_parser(
        "prepare-evidence",
        help="Create source-versioned evidence from a local file and exact locator.",
    )
    evidence.add_argument("--source-file", type=Path, required=True)
    evidence.add_argument("--source-id", required=True)
    evidence.add_argument("--check-id", required=True)
    evidence.add_argument("--locator", required=True)
    evidence.add_argument("--raw-value", required=True)
    evidence.add_argument("--extraction-method", required=True)
    evidence.add_argument("--extraction-version", required=True)
    evidence.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    evidence.set_defaults(func=command_prepare_evidence)

    snapshot = commands.add_parser("snapshot", help="Pin current local sources and evidence.")
    snapshot.add_argument("--assessment", type=Path, required=True)
    snapshot.add_argument("--source-versions", type=Path, required=True)
    snapshot.add_argument("--evidence", type=Path, required=True)
    snapshot.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    snapshot.set_defaults(func=command_snapshot)

    manual = commands.add_parser(
        "manual-evidence", help="Validate and store one append-only human evidence record."
    )
    manual.add_argument("--record", type=Path, required=True)
    manual.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    manual.set_defaults(func=command_manual_evidence)

    submit = commands.add_parser("submit", help="Store an independent reviewer submission.")
    submit.add_argument("--assessment", type=Path, required=True)
    submit.add_argument("--reviewer-id", required=True)
    submit.add_argument("--source-snapshot-sha256", required=True)
    submit.add_argument("--checks", type=Path, required=True)
    submit.add_argument("--revision", type=int, default=1)
    submit.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    submit.set_defaults(func=command_submit)

    compare = commands.add_parser("compare", help="Create a read-only disagreement table.")
    compare.add_argument("--first", type=Path, required=True)
    compare.add_argument("--second", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.set_defaults(func=command_compare)

    adjudicate = commands.add_parser(
        "adjudicate", help="Store adjudication and resolved review records."
    )
    adjudicate.add_argument("--first", type=Path, required=True)
    adjudicate.add_argument("--second", type=Path, required=True)
    adjudicate.add_argument("--adjudicator-id", required=True)
    adjudicate.add_argument("--decisions", type=Path, required=True)
    adjudicate.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    adjudicate.set_defaults(func=command_adjudicate)

    finalize = commands.add_parser(
        "finalize", help="Finalize a resolved human review with explicit judgments."
    )
    finalize.add_argument("--review", type=Path, required=True)
    finalize.add_argument("--judgments", type=Path, required=True)
    finalize.add_argument("--early-stop", action="store_true")
    finalize.add_argument("--early-stop-reason", default="")
    finalize.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    finalize.set_defaults(func=command_finalize)

    candidates = commands.add_parser(
        "map-candidates", help="Map receipt-linked native results to candidate-only evidence."
    )
    candidates.add_argument("--receipts", type=Path, required=True)
    candidates.add_argument("--results", type=Path, required=True)
    candidates.add_argument("--evidence", type=Path, required=True)
    candidates.add_argument("--output", type=Path, required=True)
    candidates.set_defaults(func=command_candidate_map)

    validate = commands.add_parser("validate", help="Validate one versioned local record.")
    validate.add_argument(
        "--kind",
        choices=[
            "assessment",
            "reviewer-submission",
            "finalization",
            "manual-evidence",
            "catalogue",
            "candidate-dossier",
        ],
        required=True,
    )
    validate.add_argument("--record", type=Path, required=True)
    validate.add_argument("--source-snapshot-sha256")
    validate.add_argument(
        "--catalogue", type=Path, default=ROOT / "config/inspect_sr/v1.1.2/catalogue.json"
    )
    validate.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    validate.set_defaults(func=command_validate)

    render = commands.add_parser(
        "render", help="Build a private report model and render current-run HTML/PDF."
    )
    render.add_argument("--assessment", type=Path, required=True)
    render.add_argument(
        "--catalogue", type=Path, default=ROOT / "config/inspect_sr/v1.1.2/catalogue.json"
    )
    render.add_argument("--source-versions", type=Path, required=True)
    render.add_argument("--evidence", type=Path, required=True)
    render.add_argument("--candidates", type=Path, required=True)
    render.add_argument("--receipts", type=Path, required=True)
    render.add_argument("--reviewer-submission", type=Path, action="append", default=[])
    render.add_argument("--adjudication", type=Path)
    render.add_argument("--finalization", type=Path)
    render.add_argument("--source-snapshot-sha256", required=True)
    render.add_argument("--revision", required=True)
    render.add_argument("--format", choices=["html", "pdf", "both"], default="both")
    render.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    render.set_defaults(func=command_render)

    export = commands.add_parser("export", help="Create a policy-controlled synthesis export.")
    export.add_argument("--finalization", type=Path, action="append", required=True)
    export.add_argument("--reports", type=Path, required=True)
    export.add_argument("--comparisons", type=Path, required=True)
    export.add_argument("--policy", type=Path, required=True)
    export.add_argument("--guidance-sha256", required=True)
    export.add_argument(
        "--catalogue", type=Path, default=ROOT / "config/inspect_sr/v1.1.2/catalogue.json"
    )
    export.add_argument("--current-sources", type=Path, required=True)
    export.add_argument("--unresolved", choices=["block", "list"], required=True)
    export.add_argument("--policy-variant", choices=["primary", "sensitivity"], required=True)
    export.add_argument("--public", action="store_true")
    export.add_argument("--trial-id", action="append", default=[])
    export.add_argument("--reviewed-by")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--store", type=Path, default=ROOT / "data/private/inspect_sr")
    export.set_defaults(func=command_export)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"inspect_sr: {exc}\n")


if __name__ == "__main__":
    main()
