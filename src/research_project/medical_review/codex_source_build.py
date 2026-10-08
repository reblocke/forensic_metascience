"""Strict provenance binding for an isolated, assessment-only source-built CLI."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from research_project.medical_review.records import read_json

PINNED_SOURCE = {
    "url": "https://github.com/openai/codex.git",
    "tag": "rust-v0.161.0",
    "commit": "979011409de0a60b52f179721948e65531d26144",
}
PINNED_ARTIFACTS = {
    "original_lock": "3206e2fdb53a3498758ce2f2972f19fae26beb261befd65cc0eb9e02efe23d52",
    "normalized_lock": "4e43cd81ed341c32bde170917f38c3e79702cbc69d1f96744ab1e09f9e80a601",
    "normalization_patch": "9b2995d1b406de9526a4db5b1360c872eaa459bbb5dea1bd2412f560befd36bc",
    "toolchain": "570656042681cfd8795403a455baf9a33035331a07db0645e866bbcea89a3d64",
}
BUILD_COMMAND = [
    "cargo",
    "build",
    "--offline",
    "--locked",
    "--release",
    "-p",
    "codex-cli",
    "--bin",
    "codex",
]
NATIVE_PATCH = Path(__file__).resolve().parents[3] / "tools/codex-no-tools/native-tools.patch"
BUILD_ARTIFACTS = {*PINNED_ARTIFACTS, "native_patch", "build_log", "source_ledger"}


def validate_build_manifest(path: Path, executable: Path) -> dict:
    """Verify retained inputs and executable; this never grants execution eligibility."""
    manifest = read_json(path)
    expected = {
        "schema_version",
        "classification",
        "source",
        "target",
        "rustc_version",
        "cargo_version",
        "build_command",
        "executable_sha256",
        "artifacts",
    }
    try:
        if (
            set(manifest) != expected
            or manifest["schema_version"] != "medical_codex_source_build_v1"
            or manifest["classification"] != "locally_patched_assessment"
            or manifest["source"] != PINNED_SOURCE
            or manifest["target"] != "aarch64-apple-darwin"
            or not manifest["rustc_version"].startswith("rustc 1.95.0 ")
            or not manifest["cargo_version"].startswith("cargo 1.95.0 ")
            or manifest["build_command"] != BUILD_COMMAND
            or set(manifest["artifacts"]) != BUILD_ARTIFACTS
            or manifest["executable_sha256"] != hashlib.sha256(executable.read_bytes()).hexdigest()
        ):
            raise ValueError("Codex source build identity is unsupported or changed.")
        root = path.parent.resolve(strict=True)
        for name, record in manifest["artifacts"].items():
            relative = Path(record["path"])
            artifact = root / relative
            if (
                set(record) != {"path", "sha256"}
                or relative.is_absolute()
                or ".." in relative.parts
                or not relative.parts
                or any(part.is_symlink() for part in [artifact, *artifact.parents] if part != root)
                or root not in artifact.resolve(strict=True).parents
                or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                or hashlib.sha256(artifact.read_bytes()).hexdigest() != record["sha256"]
                or name in PINNED_ARTIFACTS
                and record["sha256"] != PINNED_ARTIFACTS[name]
                or name == "native_patch"
                and record["sha256"] != hashlib.sha256(NATIVE_PATCH.read_bytes()).hexdigest()
            ):
                raise ValueError("Codex source build artifacts are uncontained or changed.")
    except (KeyError, TypeError, AttributeError, OSError) as error:
        raise ValueError("Codex source build evidence is invalid.") from error
    return manifest
