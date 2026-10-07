from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import test_evaluation_tables as table_tests

from research_project.medical_review import evaluation_native_analysis as native
from research_project.medical_review.evaluation_analysis import prepare_analysis_tables
from research_project.medical_review.evaluation_native_analysis import (
    load_native_analysis,
    run_native_analysis,
)

source = table_tests.source


@pytest.fixture(scope="module")
def tables(source):
    repo, parent, _ = source
    return repo, prepare_analysis_tables(repo, parent)


def require_r():
    if not shutil.which("Rscript"):
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Required native R analysis runtime is missing.")
        pytest.skip("Rscript unavailable outside the required native lane.")


@pytest.mark.native_r
def test_native_analysis_executes_source_bound_r_and_keeps_qualification_pending(tables):
    require_r()
    repo, parent = tables
    run = run_native_analysis(repo, parent)
    loaded = load_native_analysis(repo, run)
    record = loaded["analysis"]
    assert record["medical_performance_validated"] is False
    assert record["official_assessment"] is None
    assert record["qualification"]["medical_performance"] == "pending"
    assert record["native_receipt"]["returncode"] == 0
    assert record["native_receipt"]["elapsed_seconds"] >= 0
    assert record["native_receipt"]["r_version"].startswith("R version")
    outputs = record["outputs"]
    assert len(outputs["findings_by_attempt_stage"]) == 12
    pairs = outputs["paired_case_comparisons"]
    assert all(p["left_attempt_id"] and p["right_attempt_id"] for p in pairs)
    unmatched = [p for p in pairs if p["comparison_status"] == "unmatched_source_access"]
    assert unmatched
    assert all(p["important_detection_difference"] is None for p in unmatched)
    assert all(r["cost_amount"] is None for r in outputs["resources_by_packet_currency"])
    assert loaded["tables"]["tables"]["record_id"] == record["tables_record_id"]


@pytest.mark.native_r
def test_native_code_drift_after_execution_preserves_failed_run_not_an_eligible_analysis(
    tables, monkeypatch
):
    require_r()
    repo, parent = tables
    original_execute = native._execute
    driver = repo / "scripts/analyze_medical_evaluation.R"
    raw = driver.read_bytes()
    before = set((repo / "data/processed").rglob("run_manifest.json"))

    def drift(*args, **kwargs):
        result = original_execute(*args, **kwargs)
        driver.write_bytes(raw + b"\n# Synthetic post-execution code drift.\n")
        return result

    try:
        with monkeypatch.context() as patch:
            patch.setattr(native, "_execute", drift)
            with pytest.raises(ValueError, match="changed"):
                run_native_analysis(repo, parent)
    finally:
        driver.write_bytes(raw)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    run = new.pop().parent
    assert (run / "processed/medical_evaluation/native/findings_by_attempt_stage.csv").exists()
    assert not (run / "processed/medical_evaluation/analysis.json").exists()
    with pytest.raises(ValueError, match="completed"):
        load_native_analysis(repo, run)


@pytest.mark.native_r
def test_actual_analysis_cli_executes_r_and_refuses_model_permission_flags(tables):
    require_r()
    repo, parent = tables
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    script = repo / "scripts/medical_review.py"
    shutil.copy(root / "scripts/medical_review.py", script)
    command = [sys.executable, str(script), "evaluation-analyze", "--tables-run", str(parent)]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr
    loaded = load_native_analysis(repo, Path(result.stdout.strip()))
    assert loaded["analysis"]["native_receipt"]["returncode"] == 0
    assert loaded["manifest"]["effective_settings"]["allow_llm"] is False
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    refused = subprocess.run(
        command + ["--allow-llm"], cwd=repo, capture_output=True, text=True, timeout=30
    )
    assert refused.returncode == 2
    assert set((repo / "data/processed").rglob("run_manifest.json")) == before
