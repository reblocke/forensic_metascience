#!/usr/bin/env python3
"""Local, offline command line for private INSPECT-SR review records."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
from research_project.inspect_sr.synthesis_export import build_synthesis_export
from research_project.inspect_sr.validation import (
    validate_finalization,
    validate_reviewer_submission,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
        return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")
    value = read_json(path)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Expected a JSON list of records in {path}.")
    return value


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
    return private_root(store) / folder / f"{record_id}{suffix}"


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
        "schema_version": "inspect_sr_source_version_v1",
        "record_type": "source_version",
        "source_id": args.source_id,
        "source_version_id": sourcever,
        "source_name": source.name,
        "content_sha256": content_hash,
    }
    version_path = record_path(store, "source-versions", sourcever)
    if version_path.exists():
        if read_json(version_path) != source_version:
            raise ValueError("Stored source-version identity conflicts with its content hash.")
    else:
        write_exclusive(version_path, source_version)
    write_exclusive(record_path(store, "evidence", evidence["evidence_id"]), evidence)
    print(evidence["evidence_id"])


def command_manual_evidence(args: argparse.Namespace) -> None:
    record = validate_manual_evidence(read_json(args.record))
    version_path = record_path(
        private_root(args.store), "source-versions", str(record["source_version_id"])
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
    adjudication = create_adjudication_record(
        first,
        second,
        adjudicator_id=args.adjudicator_id,
        decisions=read_json(args.decisions),
    )
    resolved = resolve_reviews(first, second, adjudication)
    store = private_root(args.store)
    write_exclusive(
        record_path(store, "adjudications", adjudication["adjudication_id"]), adjudication
    )
    write_exclusive(
        record_path(store, "resolved-reviews", resolved["resolved_review_id"]), resolved
    )
    print(resolved["resolved_review_id"])


def command_finalize(args: argparse.Namespace) -> None:
    review = read_json(args.review)
    finalization = finalize_review(
        review,
        read_json(args.judgments),
        early_stop=args.early_stop,
        early_stop_reason=args.early_stop_reason,
    )
    write_exclusive(
        record_path(private_root(args.store), "finalizations", finalization["finalization_id"]),
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
        if not args.source_snapshot_sha256:
            raise ValueError("Finalization validation requires the current source snapshot hash.")
        validate_finalization(record, current_source_snapshot_sha256=args.source_snapshot_sha256)
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
    model = build_report_model(
        assessment=assessment,
        catalogue=load_catalogue(args.catalogue),
        source_versions=read_records(args.source_versions),
        evidence_records=read_records(args.evidence),
        candidate_dossier=read_json(args.candidates),
        reviewer_submissions=[read_json(path) for path in args.reviewer_submission],
        adjudication=read_json(args.adjudication) if args.adjudication else None,
        finalization=read_json(args.finalization) if args.finalization else None,
        method_receipts=read_records(args.receipts),
        current_source_snapshot_sha256=args.source_snapshot_sha256,
    )
    report_dir = store / "reports" / assessment["assessment_id"] / args.revision
    model_path = report_dir / "report-model.json"
    write_exclusive(model_path, model)
    qmd = ROOT / "notebooks" / "inspect_sr_assessment.qmd"
    copied_qmd = report_dir / qmd.name
    report_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(qmd, copied_qmd)
    formats = ("html", "pdf") if args.format == "both" else (args.format,)
    for output_format in formats:
        output_name = f"assessment.{output_format}"
        env = {
            **os.environ,
            "INSPECT_SR_REPORT_JSON": str(model_path.resolve()),
        }
        subprocess.run(
            ["quarto", "render", str(copied_qmd), "--to", output_format, "--output", output_name],
            cwd=report_dir,
            env=env,
            check=True,
        )
        if not (report_dir / output_name).is_file():
            raise RuntimeError(f"Quarto did not create the expected report: {output_name}")
    print(report_dir)


def command_export(args: argparse.Namespace) -> None:
    output = build_synthesis_export(
        [read_json(path) for path in args.finalization],
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
    )
    target = private_root(args.store) / "exports" / args.output.name
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
    write_exclusive(target, output)
    if args.public:
        write_exclusive(
            private_root(args.store) / "public-export-approvals" / f"{payload_hash}.json",
            approval,
        )


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
