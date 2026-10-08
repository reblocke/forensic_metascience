"""Record a completed isolated source build; never install or authorize its runtime."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

from research_project.medical_review.codex_source_build import (
    BUILD_COMMAND,
    NATIVE_PATCH,
    PINNED_SOURCE,
    validate_build_manifest,
)
from research_project.medical_review.records import PRIVATE_SOURCES, private_path, write_json

REPO = Path(__file__).resolve().parents[2]


def git(source: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(source), *args])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "original", "executable", "build-log", "output", "rustc", "cargo"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for source in (args.source, args.original):
        if git(source, "rev-parse", "HEAD").decode().strip() != PINNED_SOURCE["commit"]:
            raise ValueError("Source build must use the pinned upstream commit.")
        if git(source, "ls-files", "--others", "--exclude-standard").strip():
            raise ValueError("Source build has untracked source inputs.")
    if git(args.original, "status", "--porcelain").strip():
        raise ValueError("Original source checkout must remain unchanged.")
    native_diff = git(
        args.source, "diff", "--no-ext-diff", "--binary", "--", ".", ":(exclude)codex-rs/Cargo.lock"
    )
    if native_diff != NATIVE_PATCH.read_bytes():
        raise ValueError("Source changes do not match the reviewed native-tool patch.")
    output = private_path(REPO, args.output, PRIVATE_SOURCES / "runtime_candidates")
    output.mkdir()  # Write once; new attempts require a fresh output directory.
    inputs = {
        "original_lock": args.original / "codex-rs/Cargo.lock",
        "normalized_lock": args.source / "codex-rs/Cargo.lock",
        "normalization_patch": Path(__file__).parent / "workspace-versions.patch",
        "native_patch": NATIVE_PATCH,
        "toolchain": args.original / "codex-rs/rust-toolchain.toml",
        "build_log": args.build_log,
    }
    ledger = {}
    for relative in git(args.source, "diff", "--name-only").decode().splitlines():
        path = args.source / relative
        ledger[relative] = {
            "original_sha256": hashlib.sha256((args.original / relative).read_bytes()).hexdigest(),
            "built_source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    write_json(output / "source_ledger", ledger)
    artifacts = {
        "source_ledger": {
            "path": "source_ledger",
            "sha256": hashlib.sha256((output / "source_ledger").read_bytes()).hexdigest(),
        }
    }
    for name, source in inputs.items():
        shutil.copyfile(source, output / name)
        artifacts[name] = {
            "path": name,
            "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": "medical_codex_source_build_v1",
        "classification": "locally_patched_assessment",
        "source": PINNED_SOURCE.copy(),
        "target": "aarch64-apple-darwin",
        "rustc_version": subprocess.check_output([str(args.rustc), "--version"], text=True).strip(),
        "cargo_version": subprocess.check_output([str(args.cargo), "--version"], text=True).strip(),
        "build_command": BUILD_COMMAND.copy(),
        "executable_sha256": hashlib.sha256(args.executable.read_bytes()).hexdigest(),
        "artifacts": artifacts,
    }
    path = output / "build-manifest.json"
    write_json(path, manifest)
    validate_build_manifest(path, args.executable)
    print(path)


if __name__ == "__main__":
    main()
