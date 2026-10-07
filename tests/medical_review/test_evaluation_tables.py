from __future__ import annotations

import csv
import io
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import create_workspace
from test_evaluation_governance import inputs, ready_workspace

from research_project.medical_review import evaluation_analysis as analysis
from research_project.medical_review.evaluation_analysis import (
    export_tables,
    load_analysis_tables,
    prepare_analysis_tables,
)
from research_project.medical_review.evaluation_governance import load_unblinding, record_unblinding


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    root = Path(__file__).resolve().parents[2]
    workspace = create_workspace(tmp_path_factory.mktemp("analysis-tables"), root)
    ready = ready_workspace(workspace)
    repo, _, synthesis, thresholds, _ = ready
    (repo / "R").mkdir()
    (repo / "scripts").mkdir()
    shutil.copy(root / "R/medical_evaluation.R", repo / "R/medical_evaluation.R")
    shutil.copy(
        root / "scripts/analyze_medical_evaluation.R", repo / "scripts/analyze_medical_evaluation.R"
    )
    _, _, request = inputs(ready)
    run = record_unblinding(repo, thresholds, synthesis, request)
    return repo, run, load_unblinding(repo, run)


def test_tables_preserve_model_access_attempts_human_scope_and_unknowns(source):
    repo, parent, loaded = source
    record = export_tables(loaded)
    assert record["medical_performance_validated"] is False
    assert record["official_assessment"] is None
    tables = record["tables"]
    assert len(tables["views"]) == 6
    assert len(tables["findings"]) == len(tables["synthesis"]) == 16
    assert len(tables["attempts"]) == 6
    common = [v for v in tables["views"] if v["track"] == "common_input"]
    full = [v for v in tables["views"] if v["track"] == "full_bundle"]
    assert len({v["source_set_id"] for v in common}) == 1
    adapted = [v for v in full if v["condition_id"] != "original_reviewer"]
    original = next(v for v in full if v["condition_id"] == "original_reviewer")
    assert len({v["source_set_id"] for v in adapted}) == 1
    assert original["source_set_id"] != adapted[0]["source_set_id"]
    assert original["input_equivalence"] == "unmatched"
    assert all(a["cost_amount"] is None for a in tables["attempts"])
    assert all(f["attempt_id"] for f in tables["findings"])
    assert {t["phase"] for t in tables["timings"]} == {
        "candidate_assessment",
        "synthesis_assessment",
    }
    run = prepare_analysis_tables(repo, parent)
    assert load_analysis_tables(repo, run)["tables"] == record
    attempts_path = run / "processed/medical_evaluation/tables/attempts.csv"
    with attempts_path.open() as stream:
        assert all(a["cost_amount"] == "" for a in csv.DictReader(stream))
    before = (run / "processed/medical_evaluation/analysis_tables.json").read_bytes()
    assert load_analysis_tables(repo, run)["tables"] == record
    assert (run / "processed/medical_evaluation/analysis_tables.json").read_bytes() == before


def test_failed_table_freeze_retains_archives_without_publishing_eligible_record(
    source, monkeypatch
):
    repo, parent, _ = source
    original = analysis._write
    before = set((repo / "data/processed").rglob("run_manifest.json"))

    def fail(run, manifest, path, raw):
        original(run, manifest, path, raw)
        if path.endswith("tables/attempts.csv"):
            raise RuntimeError("Synthetic interrupted table export")

    with monkeypatch.context() as patch:
        patch.setattr(analysis, "_write", fail)
        with pytest.raises(RuntimeError, match="interrupted table export"):
            prepare_analysis_tables(repo, parent)
    new = set((repo / "data/processed").rglob("run_manifest.json")) - before
    assert len(new) == 1
    run = new.pop().parent
    assert not (run / "processed/medical_evaluation/analysis_tables.json").exists()
    with pytest.raises(ValueError, match="completed"):
        load_analysis_tables(repo, run)


def test_csv_serialization_preserves_literal_na_and_rejects_extra_fields():
    rows = [{"case_id": "NA", "value": None, "observed": False}]
    raw = analysis.csv_bytes(rows, ("case_id", "value", "observed"))
    assert list(csv.DictReader(io.StringIO(raw.decode()))) == [
        {"case_id": "NA", "value": "", "observed": "FALSE"}
    ]
    with pytest.raises(ValueError, match="fields"):
        analysis.csv_bytes(
            [{**rows[0], "official_assessment": "qualified"}], ("case_id", "value", "observed")
        )


def test_table_cli_binds_an_explicit_release_and_rejects_live_flags(source):
    repo, parent, _ = source
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    script = repo / "scripts/medical_review.py"
    shutil.copy(root / "scripts/medical_review.py", script)
    command = [sys.executable, str(script), "evaluation-tables", "--unblinding-run", str(parent)]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    loaded = load_analysis_tables(repo, Path(result.stdout.strip()))
    assert loaded["manifest"]["effective_settings"]["allow_llm"] is False
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    refused = subprocess.run(
        command + ["--allow-web-search"], cwd=repo, capture_output=True, text=True
    )
    assert refused.returncode == 2
    assert set((repo / "data/processed").rglob("run_manifest.json")) == before
