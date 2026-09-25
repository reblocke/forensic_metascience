#!/usr/bin/env python3
"""Initialize and update a fresh forensic run manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from research_project.run_manifest import create_run, update_run, validate_output_root


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--repo-root", type=Path, required=True)
    init.add_argument("--output-root", type=Path, required=True)
    init.add_argument("--study-id", required=True)
    init.add_argument("--categories", default="")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--input", action="append", type=Path, default=[])
    init.add_argument("--required-input", action="append", type=Path, default=[])
    init.add_argument("--run-id")
    update = commands.add_parser("update")
    update.add_argument("--manifest", type=Path, required=True)
    update.add_argument("--stage")
    update.add_argument("--status", choices=["running", "completed", "failed"])
    update.add_argument("--error")
    update.add_argument("--artifact")
    validate = commands.add_parser("validate-output")
    validate.add_argument("--repo-root", type=Path, required=True)
    validate.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "init":
        run_root, _ = create_run(
            repo_root=args.repo_root,
            output_root=args.output_root,
            study_id=args.study_id,
            categories=[value for value in args.categories.split(",") if value],
            config_path=args.config,
            input_paths=args.input,
            required_input_paths=args.required_input,
            run_id=args.run_id,
        )
        print(run_root)
    elif args.command == "update":
        if args.status is None:
            parser.error("update requires --status")
        update_run(
            args.manifest,
            stage=args.stage,
            status=args.status,
            error=args.error,
            artifact=args.artifact,
        )
    else:
        print(validate_output_root(args.repo_root, args.output_root))


if __name__ == "__main__":
    main()
