"""Trusted local importer worker, never an arbitrary model/tool/code executor."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from research_project.medical_review.importer import IncompleteImportError, import_reviewer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--profile", action="append")
    parser.add_argument("--recover-incomplete", action="store_true")
    args = parser.parse_args()
    try:
        try:
            run = import_reviewer(args.repo_root, args.bundle, args.input, profiles=args.profile)
        except IncompleteImportError:
            if not args.recover_incomplete:
                raise
            run = import_reviewer(
                args.repo_root,
                args.bundle,
                args.input,
                profiles=args.profile,
                attempt_suffix=uuid.uuid4().hex[:8],
            )
        print(run)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"replay-import: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
