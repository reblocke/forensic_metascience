from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

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
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "fixture@example.test"], check=True
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
    tracked_code = root / "src" / "fixture.py"
    tracked_code.parent.mkdir()
    tracked_code.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "src/fixture.py"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "fixture base"], check=True, capture_output=True
    )
    destination = root / "runs"
    run_a, manifest_a = create_run(
        repo_root=root,
        output_root=destination,
        study_id="demo",
        categories=["numeric"],
        config_path=config,
        input_paths=[source],
        settings={"network_allowed": False, "render_reports": False},
        run_id="run-a",
    )
    first_manifest = json.loads(manifest_a.read_text(encoding="utf-8"))
    assert first_manifest["schema_version"] == "forensics_run_v3"
    assert first_manifest["effective_settings"] == {
        "network_allowed": False,
        "render_reports": False,
    }
    assert first_manifest["effective_settings_sha256"]
    assert "code_revision" in first_manifest
    assert first_manifest["working_tree_dirty"] is False
    assert len(first_manifest["working_tree_diff_sha256"]) == 64
    tracked_code.write_text("VALUE = 2\n", encoding="utf-8")
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
    assert second_manifest["working_tree_dirty"] is True
    assert second_manifest["working_tree_diff_sha256"] != first_manifest["working_tree_diff_sha256"]

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


def test_run_manifest_cli_accepts_artifact_only_update(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    root.mkdir()
    config = tmp_path / "study.sh"
    config.write_text("STUDY_ID='demo'\n", encoding="utf-8")
    run_root, manifest = create_run(
        repo_root=root,
        output_root=root / "runs",
        study_id="demo",
        categories=["numeric"],
        config_path=config,
        input_paths=[],
        run_id="artifact-only",
    )
    artifact = run_root / "processed/output.csv"
    artifact.write_text("ok\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/forensics_run.py"),
            "update",
            "--manifest",
            str(manifest),
            "--artifact",
            str(artifact),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
    )
    assert result.returncode == 0, result.stderr
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    assert recorded["status"] == "running"
    assert recorded["artifacts"][0]["path"] == "processed/output.csv"


def test_terminal_run_manifest_rejects_later_mutations(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    config = tmp_path / "study.sh"
    config.write_text("STUDY_ID='demo'\n", encoding="utf-8")
    run_root, manifest = create_run(
        repo_root=root,
        output_root=root / "runs",
        study_id="demo",
        categories=["numeric"],
        config_path=config,
        input_paths=[],
        run_id="terminal",
    )
    update_run(manifest, status="completed")
    artifact = run_root / "late.csv"
    artifact.write_text("late\n", encoding="utf-8")
    with pytest.raises(ValueError, match="terminal"):
        update_run(manifest, artifact=str(artifact))


def test_meta_aggregates_versioned_randomization_producer_outputs(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = tmp_path / "study.sh"
    config.write_text("STUDY_ID='demo'\n", encoding="utf-8")
    run_root, manifest = create_run(
        repo_root=repo_root,
        output_root=repo_root / "runs",
        study_id="demo",
        categories=["randomization"],
        config_path=config,
        input_paths=[],
        run_id="meta-v2",
    )
    report_dir = run_root / "reports/randomization"
    report_dir.mkdir()
    summary = report_dir / "pooled_descriptive_v2.csv"
    pd.DataFrame([{"trial_id": "demo", "n_rows_recalc": 2, "status": "descriptive_only"}]).to_csv(
        summary, index=False
    )
    candidates = report_dir / "row_level_results_v2.csv"
    pd.DataFrame([{"flagged_p_delta_0_05": True, "source_table": "Table 1"}]).to_csv(
        candidates, index=False
    )
    update_run(manifest, artifact=str(summary))
    update_run(manifest, artifact=str(candidates))
    update_run(manifest, stage="randomization_methods", status="completed")
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
            str(manifest),
            "--requested-categories",
            "randomization",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(project_root / "src")},
    )
    assert result.returncode == 0, result.stderr
    summaries = pd.read_csv(run_root / "processed/meta/inputs/category_summaries_v2_raw.csv")
    coverage = pd.read_csv(run_root / "processed/meta/inputs/category_coverage_v2_raw.csv")
    concerns = pd.read_csv(run_root / "processed/meta/inputs/candidate_concerns_v1_raw.csv")
    assert "descriptive_only" in set(summaries["value"].astype(str))
    assert bool(coverage.loc[coverage["category"] == "randomization", "report_available"].item())
    assert concerns.loc[0, "source_unit"] == "Table 1"


@pytest.mark.report_integration
def test_randomization_report_renders_only_current_run_inputs(tmp_path: Path) -> None:
    quarto = shutil.which("quarto")
    if quarto is None:
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Quarto is required by FORENSICS_REQUIRE_REPORT_INTEGRATION=1")
        pytest.skip("Quarto is unavailable; report integration remains unverified.")
    project_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    (repo_root / "notebooks").mkdir(parents=True)
    (repo_root / "reports/randomization/demo").mkdir(parents=True)
    notebook = repo_root / "notebooks/lungtime_randomization_audit.qmd"
    shutil.copyfile(project_root / "notebooks/lungtime_randomization_audit.qmd", notebook)
    current_reports = repo_root / "reports/runs/run-b/randomization"
    current_reports.mkdir(parents=True)
    processed = repo_root / "data/processed/runs/run-b"
    processed.mkdir(parents=True)

    def write_csv(directory: Path, name: str, row: dict[str, object]) -> None:
        pd.DataFrame([row]).to_csv(directory / name, index=False)

    for directory, marker in [
        (repo_root / "reports/randomization/demo", "RUN_A_STALE"),
        (current_reports, "RUN_B_CURRENT"),
    ]:
        write_csv(
            directory,
            "row_level_results_v2.csv",
            {
                "parent_variable": marker,
                "variable": marker,
                "level": "yes",
                "row_chisq_p": 0.25,
                "comparison_status": "not_comparable",
            },
        )
        write_csv(directory, "pooled_descriptive_v2.csv", {"status": marker})
        write_csv(directory, "reported_test_records_v1.csv", {"reported_test_id": marker})
        write_csv(directory, "allocation_arithmetic_v1.csv", {"status": "not_assessed"})
        write_csv(
            directory, "randomization_run_receipt_v1.csv", {"simdistr_version": "not_requested"}
        )
        write_csv(directory, "simdistr_variable_pvalues_v1.csv", {"reason": "not_requested"})
        write_csv(directory, "simdistr_combined_descriptive_v1.csv", {"status": "not_requested"})

    result = subprocess.run(
        [quarto, "render", str(notebook), "--to", "html", "--output", "run-b.html"],
        cwd=current_reports,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "FORENSICS_STUDY_ID": "demo",
            "FORENSICS_REPORTS_ROOT": str(repo_root / "reports/runs/run-b"),
            "FORENSICS_PROCESSED_ROOT": str(processed),
        },
    )
    assert result.returncode == 0, result.stderr
    html = (current_reports / "run-b.html").read_text(encoding="utf-8")
    assert "RUN_B_CURRENT" in html
    assert "RUN_A_STALE" not in html
    pdf_result = subprocess.run(
        [quarto, "render", str(notebook), "--to", "pdf", "--output", "run-b.pdf"],
        cwd=current_reports,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "FORENSICS_STUDY_ID": "demo",
            "FORENSICS_REPORTS_ROOT": str(repo_root / "reports/runs/run-b"),
            "FORENSICS_PROCESSED_ROOT": str(processed),
        },
    )
    assert pdf_result.returncode == 0, pdf_result.stderr
    assert (current_reports / "run-b.pdf").is_file()
    pipeline = (project_root / "scripts/run_pipeline.sh").read_text(encoding="utf-8")
    private_review = (project_root / "scripts/run_manuscript_review.sh").read_text(encoding="utf-8")
    assert 'cd "$report_dir"' in pipeline
    assert 'cd "$REVIEW_REPORT_DIR"' in private_review


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
