from __future__ import annotations

import hashlib

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.codex_source_build import validate_build_manifest


def build_manifest(root):
    """Invented build artifacts for validator tests, never runtime evidence."""
    from research_project.medical_review.codex_source_build import BUILD_COMMAND, PINNED_SOURCE

    binary = root / "candidate"
    binary.write_bytes(b"synthetic binary")
    artifacts = {}
    for name in (
        "original_lock",
        "normalized_lock",
        "normalization_patch",
        "native_patch",
        "toolchain",
        "build_log",
        "source_ledger",
    ):
        path = root / name
        path.write_bytes(name.encode())
        artifacts[name] = {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "schema_version": "medical_codex_source_build_v1",
        "classification": "locally_patched_assessment",
        "source": PINNED_SOURCE.copy(),
        "target": "aarch64-apple-darwin",
        "rustc_version": "rustc 1.95.0 (synthetic)",
        "cargo_version": "cargo 1.95.0 (synthetic)",
        "build_command": BUILD_COMMAND.copy(),
        "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "artifacts": artifacts,
    }
    path = root / "build-manifest.json"
    write_json(path, manifest)
    return path, manifest, binary


@pytest.mark.parametrize(
    "change",
    [
        "binary",
        "artifact",
        "escape",
        "symlink",
        "source",
        "command",
        "unknown",
        "repinned_lock",
        "repinned_patch",
    ],
)
def test_source_build_manifest_rejects_changed_or_uncontained_inputs(tmp_path, monkeypatch, change):
    # Real pin checks remain mandatory; synthetic hashes are substituted only here.
    path, manifest, binary = build_manifest(tmp_path)
    monkeypatch.setattr(
        "research_project.medical_review.codex_source_build.PINNED_ARTIFACTS",
        {
            name: manifest["artifacts"][name]["sha256"]
            for name in ("original_lock", "normalized_lock", "normalization_patch", "toolchain")
        },
    )
    reviewed_patch = tmp_path / "reviewed-native-patch"
    reviewed_patch.write_bytes((tmp_path / "native_patch").read_bytes())
    monkeypatch.setattr(
        "research_project.medical_review.codex_source_build.NATIVE_PATCH", reviewed_patch
    )
    assert validate_build_manifest(path, binary) == manifest
    if change == "binary":
        binary.write_bytes(b"changed")
    elif change == "artifact":
        (tmp_path / "native_patch").write_text("changed")
    elif change == "escape":
        manifest["artifacts"]["native_patch"]["path"] = "../native_patch"
    elif change == "symlink":
        (tmp_path / "link").symlink_to(tmp_path / "native_patch")
        manifest["artifacts"]["native_patch"]["path"] = "link"
    elif change == "source":
        manifest["source"]["commit"] = "0" * 40
    elif change in {"repinned_lock", "repinned_patch"}:
        name = "normalized_lock" if change == "repinned_lock" else "native_patch"
        (tmp_path / name).write_bytes(b"changed and rehashed")
        manifest["artifacts"][name]["sha256"] = hashlib.sha256(
            (tmp_path / name).read_bytes()
        ).hexdigest()
    elif change == "command":
        manifest["build_command"].remove("--locked")
    else:
        manifest["qualified"] = True
    write_json(path, manifest)
    with pytest.raises(ValueError, match="build"):
        validate_build_manifest(path, binary)
