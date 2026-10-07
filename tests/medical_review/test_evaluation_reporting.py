from __future__ import annotations

import os
import shutil
import subprocess
import sys
from html import unescape
from pathlib import Path

import pytest
import test_evaluation_tables as table_tests

from research_project.medical_review import evaluation_reporting as reporting
from research_project.medical_review.evaluation_analysis import prepare_analysis_tables
from research_project.medical_review.evaluation_native_analysis import run_native_analysis
from research_project.medical_review.evaluation_reporting import (
    _source_links,
    load_evaluation_report,
    render_evaluation,
)
from research_project.medical_review.reporting import _escaped, _record_lines
from research_project.run_manifest import create_run

source = table_tests.source


def test_evaluation_display_wraps_long_id_values_and_labels_without_changing_data():
    value = "assessmentview_" + "a" * 64
    record = {"view_ids": {value: "V1"}}
    before = repr(record)
    lines = _record_lines(record, wrap_width=16)
    assert value not in unescape("".join(lines))
    assert "a" * 32 not in unescape("".join(lines))
    assert "a" * 16 in unescape("".join(lines))
    assert "V1" in "".join(lines)
    assert repr(record) == before
    assert _escaped(value) == _escaped(value, wrap_width=32)


def test_text_locators_remain_text_and_only_explicit_pdf_page_indices_add_fragments():
    model = {
        "source_navigation": [
            {
                "case_id": "case",
                "source_version_id": "pdf",
                "href": "../source.pdf",
                "source_reference": "sources/source.pdf",
            },
            {
                "case_id": "case",
                "source_version_id": "text",
                "href": "../source.txt",
                "source_reference": "sources/source.txt",
            },
        ]
    }
    evidence = {
        "source_version_id": "pdf",
        "locator": "Methods; printed page 7",
        "raw_value": "Exact quote.",
    }
    lines = _source_links(model, "case", [evidence])
    assert "[Original source evidence](../source.pdf)\n" in lines
    assert not any("#page=" in line for line in lines)
    page = _source_links(model, "case", [{**evidence, "page_index": 0}])
    assert "[Original source evidence](../source.pdf#page=1)\n" in page
    text = _source_links(
        model, "case", [{**evidence, "source_version_id": "text", "page_index": 0}]
    )
    assert "[Original source evidence](../source.txt)\n" in text
    with pytest.raises(ValueError, match="absent"):
        _source_links(model, "other-case", [evidence])


def test_render_timeout_retains_partial_log_and_output_without_success(workspace, monkeypatch):
    repo, bundle, *_ = workspace
    run, manifest = create_run(
        repo_root=repo,
        output_root=Path("data/processed/forensics_runs/private_reviews"),
        study_id="synthetic-report-timeout",
        categories=["medical_evaluation"],
        config_path=bundle,
        input_paths=[],
        settings={"offline": True},
    )
    directory = run / "reports/medical_evaluation"
    directory.mkdir(parents=True)
    partial = directory / "evaluation.html"
    partial.write_text("Synthetic partial output, never a completed report.")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], 180, output=b"Synthetic partial stdout", stderr=b"Synthetic timeout stderr"
        )

    monkeypatch.setattr(reporting.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="timed out"):
        reporting._render_format(run, manifest, {}, "html")
    log = directory / "quarto-html.log"
    assert b"Synthetic partial stdout" in log.read_bytes()
    assert b"Synthetic timeout stderr" in log.read_bytes()
    import json

    registered = json.loads(manifest.read_text())["artifacts"]
    assert any(r["path"].endswith("quarto-html.log") for r in registered)
    assert any(r["path"].endswith("evaluation.html") for r in registered)
    assert json.loads(manifest.read_text())["status"] != "completed"


@pytest.fixture(scope="module")
def analysis(source):
    repo, parent, _ = source
    if not shutil.which("Rscript"):
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Required R analysis runtime is missing.")
        pytest.skip("Rscript unavailable outside required integration lanes.")
    root = Path(__file__).resolve().parents[2]
    (repo / "notebooks").mkdir()
    shutil.copy(
        root / "notebooks/medical_review_evaluation.qmd",
        repo / "notebooks/medical_review_evaluation.qmd",
    )
    return repo, run_native_analysis(repo, prepare_analysis_tables(repo, parent))


@pytest.mark.native_r
def test_private_evaluation_report_preserves_attempts_evidence_and_pending_gates(analysis):
    repo, parent = analysis
    run = render_evaluation(repo, parent)
    loaded = load_evaluation_report(repo, run)
    model = loaded["report"]
    assert model["qualification"]["medical_performance"] == "pending"
    assert model["medical_performance_validated"] is False
    assert model["official_assessment"] is None
    assert len(model["candidate_accounting"]) == 16
    assert len(model["source_navigation"]) == 2
    markdown = (run / "reports/medical_evaluation/evaluation.md").read_text()
    decoded = unescape(markdown)
    assert "unmatched_source_access" in decoded
    assert "not a single-run" in markdown
    assert "Source reference ledger" in markdown
    assert "candidate_assessment" in decoded and "synthesis_assessment" in decoded
    assert "Independent source assessors" in markdown
    assert model["source_navigation"][0]["href"] in markdown
    for item in model["candidate_accounting"]:
        assert item["candidate"]["original"]["finding_summary"] in decoded
        for caveat in item["synthesis_judgment"]["critical_caveats"]:
            assert caveat["input_quote"] in decoded
    assert not (run / "reports/medical_evaluation/evaluation.html").exists()
    assert not (repo / "data/private/inspect_sr").exists()


@pytest.mark.report_integration
def test_real_quarto_evaluation_html_pdf_keep_source_links_and_qualification(
    analysis, preserve_synthetic_artifact
):
    if not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Required Quarto runtime is missing.")
        pytest.skip("Quarto unavailable outside required report lanes.")
    from pypdf import PdfReader

    repo, parent = analysis
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    script = repo / "scripts/medical_review.py"
    shutil.copy(root / "scripts/medical_review.py", script)
    command = [sys.executable, str(script), "evaluation-render", "--analysis-run", str(parent)]
    result = subprocess.run(
        command + ["--html", "--pdf"], cwd=repo, capture_output=True, text=True, timeout=420
    )
    assert result.returncode == 0, result.stderr
    run = Path(result.stdout.strip())
    model = load_evaluation_report(repo, run)["report"]
    html = (run / "reports/medical_evaluation/evaluation.html").read_text()
    pdf = PdfReader(run / "reports/medical_evaluation/evaluation.pdf")
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    import pdfplumber

    with pdfplumber.open(run / "reports/medical_evaluation/evaluation.pdf") as layout:
        for index, page in enumerate(layout.pages, 1):
            for word in page.extract_words():
                assert word["x0"] >= 70 and word["x1"] <= page.width - 70, (
                    index,
                    word,
                )
    for label in ("Medical qualification: pending", "Source reference ledger"):
        assert label in html and label in text
    assert all(row["href"] in html for row in model["source_navigation"])
    links = [
        annotation.get_object().get("/A", {}).get("/URI")
        for page in pdf.pages
        for annotation in page.get("/Annots", [])
    ]
    assert any(row["href"] in str(link) for row in model["source_navigation"] for link in links)
    assert model["qualification"]["feature_enabled_by_default"] is False
    before = set((repo / "data/processed").rglob("run_manifest.json"))
    refused = subprocess.run(
        command + ["--allow-web-search"], cwd=repo, capture_output=True, text=True, timeout=30
    )
    assert refused.returncode == 2
    assert set((repo / "data/processed").rglob("run_manifest.json")) == before
    for format_ in ("md", "html", "pdf"):
        preserve_synthetic_artifact(
            f"medical-evaluation.{format_}",
            run / f"reports/medical_evaluation/evaluation.{format_}",
        )
    preserve_synthetic_artifact(
        "medical-evaluation-report-model.json",
        run / "processed/medical_evaluation/report_model.json",
    )
    preserve_synthetic_artifact(
        "medical-evaluation-qualification.json",
        run / "processed/medical_evaluation/qualification.json",
    )
