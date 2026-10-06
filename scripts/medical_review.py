#!/usr/bin/env python3
"""Optional offline medical review, verification and reporting; live backends stay blocked."""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Output-free help/planning includes avoiding incidental Python bytecode writes.
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_project.medical_review.audit import (
    consolidate_reviews,
    record_human_disposition,
    verify_review,
)
from research_project.medical_review.bundle import load_bundle
from research_project.medical_review.context import build_study_context
from research_project.medical_review.evaluation import (
    freeze_evaluation_plan,
    prepare_evaluation_plan,
)
from research_project.medical_review.evaluation_assessment import (
    prepare_assessment_packets,
    record_assessment,
)
from research_project.medical_review.evaluation_candidates import freeze_candidates
from research_project.medical_review.evaluation_packets import (
    DEFAULT_PACKET_BYTES,
    DEFAULT_TOTAL_BYTES,
    prepare_source_packets,
)
from research_project.medical_review.evaluation_reference import freeze_reference_ledger
from research_project.medical_review.evaluation_synthesis import (
    prepare_synthesis_packets,
    record_synthesis,
)
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.numeric_inputs import record_input_review
from research_project.medical_review.preflight import structural_preflight
from research_project.medical_review.records import (
    PRIVATE_SOURCES,
    UPSTREAM_SCHEMA_HASH,
    private_path,
    read_json,
)
from research_project.medical_review.reporting import render_review
from research_project.medical_review.routing import build_review_plan
from research_project.medical_review.runner import DEFAULT_LIMITS, run_review


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="operation", required=True)
    plan = commands.add_parser(
        "plan", help="Show requirements without writing files or calling models."
    )
    plan.add_argument("--bundle", required=True, type=Path)
    plan.add_argument(
        "--profile",
        action="append",
        choices=[
            "clinical_trial",
            "observational_rwd",
            "diagnostic_accuracy",
            "prediction_model",
            "systematic_review_meta_analysis",
            "protocol",
            "methods",
            "other",
        ],
    )
    plan.add_argument("--dry-run", action="store_true")
    plan.add_argument("--offline", action="store_true")
    importing = commands.add_parser(
        "import-reviewer", help="Losslessly import authorized local JSON."
    )
    importing.add_argument("--bundle", required=True, type=Path)
    importing.add_argument("--input", required=True, type=Path)
    importing.add_argument("--upstream-schema-sha256", default=UPSTREAM_SCHEMA_HASH)
    importing.add_argument(
        "--upstream-commit", help="Operator-declared generating revision, if known."
    )
    importing.add_argument("--output-root", type=Path)
    importing.add_argument("--offline", action="store_true")
    importing.add_argument("--profile", action="append")
    running = commands.add_parser(
        "run", help="Replay local output; record blocked requests for unqualified live backends."
    )
    running.add_argument("--bundle", required=True, type=Path)
    running.add_argument("--backend", required=True, help="Only replay is supported for execution.")
    running.add_argument(
        "--input", type=Path, help="Already-authorized local Reviewer JSON for replay."
    )
    running.add_argument("--profile", action="append")
    running.add_argument("--offline", action="store_true")
    running.add_argument("--allow-llm", action="store_true")
    running.add_argument("--allow-web-search", action="store_true")
    running.add_argument("--provider")
    running.add_argument("--model")
    running.add_argument("--authorization", type=Path)
    running.add_argument("--resume", type=Path, help="Prior attempt; exact dependencies required.")
    running.add_argument("--output-root", type=Path)
    for field, default in DEFAULT_LIMITS.items():
        running.add_argument(
            "--" + field.replace("_", "-"),
            default=default,
            type=float if field == "max_duration_seconds" else int,
        )
    verifying = commands.add_parser(
        "verify", help="Append an offline counterevidence/arithmetic pass."
    )
    verifying.add_argument("--run", required=True, type=Path)
    verifying.add_argument("--input", required=True, type=Path)
    deciding = commands.add_parser(
        "decide", help="Record an explicit operator-attested human decision."
    )
    deciding.add_argument("--run", required=True, type=Path)
    deciding.add_argument("--input", required=True, type=Path)
    combining = commands.add_parser(
        "consolidate", help="Link compatible explicit review runs, retaining every original."
    )
    combining.add_argument("--run", required=True, action="append", type=Path)
    inputs = commands.add_parser(
        "verify-inputs", help="Record explicit numeric source-semantic review."
    )
    inputs.add_argument("--run", required=True, type=Path)
    inputs.add_argument("--input", required=True, type=Path)
    rendering = commands.add_parser(
        "render", help="Write a private Markdown report; Quarto is opt-in."
    )
    rendering.add_argument("--run", required=True, type=Path)
    rendering.add_argument("--output-root", type=Path)
    rendering.add_argument("--html", action="store_true")
    rendering.add_argument("--pdf", action="store_true")
    evaluation = commands.add_parser(
        "evaluation-plan", help="Validate a private paired evaluation plan; freeze is explicit."
    )
    evaluation.add_argument("--input", required=True, type=Path)
    evaluation.add_argument("--freeze", action="store_true")
    reference = commands.add_parser(
        "evaluation-reference", help="Freeze a private operator-attested source reference ledger."
    )
    reference.add_argument("--plan-run", required=True, type=Path)
    reference.add_argument("--input", required=True, type=Path)
    packets = commands.add_parser(
        "evaluation-packets", help="Stage local read-only source packets; no live execution."
    )
    packets.add_argument("--reference-run", required=True, type=Path)
    packets.add_argument("--repetitions", type=int, default=1)
    packets.add_argument("--max-packet-bytes", type=int, default=DEFAULT_PACKET_BYTES)
    packets.add_argument("--max-total-bytes", type=int, default=DEFAULT_TOTAL_BYTES)
    candidates = commands.add_parser(
        "evaluation-candidates",
        help="Import supplied offline candidate outputs; no live execution.",
    )
    candidates.add_argument("--packets-run", required=True, type=Path)
    candidates.add_argument("--input", required=True, type=Path)
    blind = commands.add_parser(
        "evaluation-blind", help="Prepare private source packets for human assessment."
    )
    blind.add_argument("--candidates-run", required=True, type=Path)
    assess = commands.add_parser(
        "evaluation-assess", help="Record explicit private human candidate judgments."
    )
    assess.add_argument("--packets-run", required=True, type=Path)
    assess.add_argument("--input", required=True, type=Path)
    synthesis_packets = commands.add_parser(
        "evaluation-synthesis-packets", help="Prepare private stage-paired human packets."
    )
    synthesis_packets.add_argument("--assessment-run", required=True, type=Path)
    synthesis = commands.add_parser(
        "evaluation-synthesis", help="Record explicit private synthesis memberships and judgments."
    )
    synthesis.add_argument("--packets-run", required=True, type=Path)
    synthesis.add_argument("--input", required=True, type=Path)
    return cli


def main() -> int:
    cli = parser()
    args = cli.parse_args()
    try:
        if args.operation == "plan":
            path = args.bundle if args.bundle.is_absolute() else ROOT / args.bundle
            if not path.exists():
                result = {
                    "status": "incomplete",
                    "reason": "Source bundle is absent.",
                    "profiles": args.profile or [],
                    "model_calls": 0,
                    "files_written": 0,
                }
            else:
                bundle, digest = load_bundle(ROOT, path)
                context = build_study_context(bundle, bundle.get("context_fields"))
                review_plan = build_review_plan(
                    bundle, context, args.profile or bundle.get("profile_ids"), ROOT
                )
                preflight = structural_preflight(ROOT, bundle)
                result = {
                    "status": "incomplete",
                    "reason": "Scope planned; gaps and unexecuted checks remain explicit.",
                    "study_id": bundle["study_id"],
                    "bundle_sha256": digest,
                    "profiles": args.profile or [],
                    "model_calls": 0,
                    "files_written": 0,
                    "review_plan": review_plan,
                    "study_context": context,
                    "parser_preflight": {
                        **preflight,
                        "sources": [
                            {key: value for key, value in source.items() if key != "pages"}
                            for source in preflight["sources"]
                        ],
                    },
                }
            print(json.dumps(result, sort_keys=True))
        elif args.operation == "import-reviewer":
            run = import_reviewer(
                ROOT,
                args.bundle,
                args.input,
                schema_sha256=args.upstream_schema_sha256,
                output_root=args.output_root,
                generating_revision=args.upstream_commit,
                profiles=args.profile,
            )
            print(run)
        elif args.operation == "run":
            run = run_review(
                ROOT,
                args.bundle,
                backend=args.backend,
                input_path=args.input,
                offline=args.offline or not args.allow_llm,
                allow_llm=args.allow_llm,
                allow_web_search=args.allow_web_search,
                authorization_path=args.authorization,
                provider=args.provider,
                model=args.model,
                profiles=args.profile,
                resume_run=args.resume,
                output_root=args.output_root,
                limits={field: getattr(args, field) for field in DEFAULT_LIMITS},
            )
            result = read_json(run / "generated/medical_review/attempt_result.json")
            print(json.dumps({"run_root": str(run), "status": result["status"]}, sort_keys=True))
            return 0 if result["status"] == "completed" else 3
        elif args.operation == "verify":
            print(verify_review(ROOT, args.run, args.input))
        elif args.operation == "consolidate":
            print(consolidate_reviews(ROOT, args.run))
        elif args.operation == "decide":
            path = private_path(ROOT, args.input, PRIVATE_SOURCES)
            print(record_human_disposition(ROOT, args.run, read_json(path)))
        elif args.operation == "verify-inputs":
            path = private_path(ROOT, args.input, PRIVATE_SOURCES)
            print(record_input_review(ROOT, args.run, read_json(path)))
        elif args.operation == "render":
            print(
                render_review(
                    ROOT, args.run, output_root=args.output_root, html=args.html, pdf=args.pdf
                )
            )
        elif args.operation == "evaluation-plan":
            if args.freeze:
                print(freeze_evaluation_plan(ROOT, args.input))
            else:
                path = private_path(ROOT, args.input, PRIVATE_SOURCES)
                data = read_json(path)
                plan = prepare_evaluation_plan(ROOT, data)
                private_path(ROOT, path, PRIVATE_SOURCES / data["evaluation_id"] / "evaluation")
                print(json.dumps(plan, sort_keys=True))
        elif args.operation == "evaluation-reference":
            print(freeze_reference_ledger(ROOT, args.plan_run, args.input))
        elif args.operation == "evaluation-packets":
            print(
                prepare_source_packets(
                    ROOT,
                    args.reference_run,
                    repetitions=args.repetitions,
                    max_packet_bytes=args.max_packet_bytes,
                    max_total_bytes=args.max_total_bytes,
                )
            )
        elif args.operation == "evaluation-candidates":
            print(freeze_candidates(ROOT, args.packets_run, args.input))
        elif args.operation == "evaluation-blind":
            print(prepare_assessment_packets(ROOT, args.candidates_run))
        elif args.operation == "evaluation-assess":
            print(record_assessment(ROOT, args.packets_run, args.input))
        elif args.operation == "evaluation-synthesis-packets":
            print(prepare_synthesis_packets(ROOT, args.assessment_run))
        elif args.operation == "evaluation-synthesis":
            print(record_synthesis(ROOT, args.packets_run, args.input))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        cli.exit(2, f"medical-review: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
