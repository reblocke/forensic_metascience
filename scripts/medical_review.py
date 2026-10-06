#!/usr/bin/env python3
"""Optional offline medical-review planning and upstream import."""

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

from research_project.medical_review.bundle import load_bundle
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.records import UPSTREAM_SCHEMA_HASH


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
        choices=["clinical_trial", "observational_rwd", "diagnostic_accuracy", "prediction_model"],
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
                result = {
                    "status": "incomplete",
                    "reason": "Medical profile planning awaits WP2.",
                    "study_id": bundle["study_id"],
                    "bundle_sha256": digest,
                    "profiles": args.profile or [],
                    "model_calls": 0,
                    "files_written": 0,
                }
            print(json.dumps(result, sort_keys=True))
        else:
            run = import_reviewer(
                ROOT,
                args.bundle,
                args.input,
                schema_sha256=args.upstream_schema_sha256,
                output_root=args.output_root,
                generating_revision=args.upstream_commit,
            )
            print(run)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        cli.exit(2, f"medical-review: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
