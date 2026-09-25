from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from research_project.pipeline import PipelineConfig, run_pipeline
from research_project.run_manifest import create_run, update_run, validate_output_root


def test_forensics_pipeline_help_and_dry_run_are_output_free(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/run_pipeline.sh"
    help_result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert help_result.returncode == 0
    assert "--dry-run" in help_result.stdout
    assert "--offline" in help_result.stdout

    dry_run_root = repo_root / "data/processed/forensics_dry_run_test"
    assert not dry_run_root.exists()
    dry_run = subprocess.run(
        [
            "bash",
            str(script),
            "--study-id",
            "lungtime",
            "--forensics",
            "numeric",
            "--allow-network",
            "--offline",
            "--dry-run",
            "--output-root",
            str(dry_run_root),
        ],
        capture_output=True,
        text=True,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "simdistr inference: not selected" in dry_run.stdout
    assert "Quarto: not selected" in dry_run.stdout
    assert not dry_run_root.exists()


def test_run_manifest_is_fresh_hashes_inputs_and_refuses_collision(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    config = tmp_path / "study.sh"
    source.write_bytes(b"first source bytes")
    config.write_text("STUDY_ID='demo'\n", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    destination = root / "runs"
    run_a, manifest_a = create_run(
        repo_root=root,
        output_root=destination,
        study_id="demo",
        categories=["numeric"],
        config_path=config,
        input_paths=[source],
        run_id="run-a",
    )
    first_manifest = json.loads(manifest_a.read_text(encoding="utf-8"))
    source.write_bytes(b"changed source bytes")
    _, manifest_b = create_run(
        repo_root=root,
        output_root=destination,
        study_id="demo",
        categories=["numeric"],
        config_path=config,
        input_paths=[source],
        run_id="run-b",
    )
    second_manifest = json.loads(manifest_b.read_text(encoding="utf-8"))

    first_hash = next(
        x["sha256"]
        for x in first_manifest["input_fingerprints"]
        if x["path"].endswith("source.pdf")
    )
    second_hash = next(
        x["sha256"]
        for x in second_manifest["input_fingerprints"]
        if x["path"].endswith("source.pdf")
    )
    assert first_hash != second_hash
    assert (run_a / "processed").is_dir()
    assert (run_a / "reports").is_dir()
    try:
        create_run(
            repo_root=root,
            output_root=destination,
            study_id="demo",
            categories=["numeric"],
            config_path=config,
            input_paths=[source],
            run_id="run-a",
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("A completed run destination must not be replaced.")

    artifact = run_a / "reports/numeric.csv"
    artifact.write_text("synthetic output", encoding="utf-8")
    update_run(manifest_a, stage="numeric", status="completed", artifact=str(artifact))
    update_run(manifest_a, status="completed")
    finished = json.loads(manifest_a.read_text(encoding="utf-8"))
    assert finished["status"] == "completed"
    assert finished["stages"]["numeric"]["status"] == "completed"
    assert finished["artifacts"][0]["path"] == "reports/numeric.csv"
    assert finished["artifacts"][0]["available"]
    assert finished["artifacts"][0]["sha256"]
    try:
        validate_output_root(root, tmp_path / "outside")
    except ValueError:
        pass
    else:
        raise AssertionError("Output roots outside the repository must be rejected.")


def test_meta_rejects_inputs_that_appear_after_run_initialization(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source = tmp_path / "late-source.pdf"
    config = tmp_path / "study.sh"
    config.write_text("STUDY_ID='demo'\n", encoding="utf-8")
    run_root, manifest_path = create_run(
        repo_root=repo_root,
        output_root=repo_root / "data/processed/forensics_manifest_test",
        study_id="demo",
        categories=["meta"],
        config_path=config,
        input_paths=[source],
        run_id="appeared-input",
    )
    source.write_bytes(b"created during the run")
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts/extract_meta.py"),
            "--study-id",
            "demo",
            "--repo-root",
            str(repo_root),
            "--out",
            str(run_root / "processed/meta"),
            "--reports-root",
            str(run_root / "reports"),
            "--run-manifest",
            str(manifest_path),
            "--requested-categories",
            "",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(project_root / "src")},
    )
    assert result.returncode != 0
    assert "input availability changed" in result.stderr


def test_private_review_help_and_dry_run_need_only_the_report(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/run_manuscript_review.sh"
    help_result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert help_result.returncode == 0
    assert "--dry-run" in help_result.stdout

    dry_root = repo_root / "data/processed/private_review_dry_run_test"
    assert not dry_root.exists()
    result = subprocess.run(
        [
            "bash",
            str(script),
            "--study-id",
            "private_x",
            "--report",
            "missing.pdf",
            "--review-type",
            "prediction_validation",
            "--dry-run",
            "--offline",
            "--output-root",
            str(dry_root),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Required source:" in result.stdout
    assert not dry_root.exists()


def test_plot_digitizer_uses_run_scoped_targets_and_working_directory() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pipeline = (repo_root / "scripts/run_pipeline.sh").read_text(encoding="utf-8")
    assert 'DIGITIZE_TARGET_ROOT="$VISUAL_DATA_DIR/inputs/plot_digitization_targets"' in pipeline
    assert 'cp "$SOURCE_DIGITIZE_TARGETS" "$DIGITIZE_TARGETS"' in pipeline
    assert (
        'DIGITIZE_PROJECT_DIR="$RUN_ROOT/generated/plot_digitization/$STUDY_ID/metaDigitise"'
        in pipeline
    )
    assert '--out-root "$DIGITIZE_TARGET_ROOT"' in pipeline
    assert (
        'SOURCE_DIGITIZE_TARGETS="$FIGURE_RAW_ROOT/$STUDY_ID/plot_digitization_targets.csv"'
        in pipeline
    )


def test_pipeline_writes_output_and_creates_zscore(tmp_path: Path) -> None:
    raw = tmp_path / "raw.csv"
    out = tmp_path / "processed.csv"

    pd.DataFrame(
        {
            "value": [0.0, 1.0, 2.0, 3.0],
            "label": ["a", "b", "c", "d"],
        }
    ).to_csv(raw, index=False)

    cfg = PipelineConfig(input_csv=raw, output_csv=out)
    df = run_pipeline(cfg)

    assert out.exists()
    assert "value_z" in df.columns
    # z-scoring should have mean ~= 0
    assert abs(df["value_z"].mean()) < 1e-9
