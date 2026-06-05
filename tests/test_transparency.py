from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from research_project.transparency import (
    FIGURE_TABLE_COLUMNS,
    OPEN_PRACTICE_COLUMNS,
    PAGE_TEXT_COLUMNS,
    PREREGISTRATION_COLUMNS,
    REPOSITORY_COLUMNS,
    SOURCE_COLUMNS,
    URL_COLUMNS,
    build_page_text_table,
    build_research_object_lite,
    build_transparency_checks,
    detect_figure_table_mentions,
    detect_open_practices,
    detect_preregistration_links,
    detect_repository_links,
    extract_urls,
)


def test_research_object_lite_and_transparency_detection() -> None:
    page_texts = build_page_text_table(
        study_id="trial_x",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=[
            (
                "Data and analysis code are available at https://github.com/example/repo. "
                "Materials are available in the supplementary appendix. "
                "The trial was preregistered at https://aspredicted.org/abc and NCT12345678. "
                "Some deidentified data are available upon reasonable request. "
                "Figure 1 shows enrollment. Table 2 reports outcomes."
            )
        ],
    )
    sources = pd.DataFrame(
        [
            {
                "study_id": "trial_x",
                "source_type": "report",
                "source_pdf": "report.pdf",
                "source_path": "data/raw/report.pdf",
                "sha256": "a" * 64,
                "n_pages": 1,
            }
        ],
        columns=SOURCE_COLUMNS,
    )

    urls = extract_urls(page_texts)
    repository_links = detect_repository_links(urls)
    preregistration_links = detect_preregistration_links(page_texts, urls)
    open_practices = detect_open_practices(page_texts)
    mentions = detect_figure_table_mentions(page_texts)
    checks = build_transparency_checks(
        study_id="trial_x",
        sources=sources,
        urls=urls,
        repository_links=repository_links,
        preregistration_links=preregistration_links,
        open_practices=open_practices,
        figure_table_mentions=mentions,
    )
    research_object = build_research_object_lite(
        study_id="trial_x",
        study_title="Trial X",
        trial_id="trial_x_001",
        identifiers={"publication_doi": "10.1000/example"},
        sources=sources,
        urls=urls,
        repository_links=repository_links,
        preregistration_links=preregistration_links,
        open_practices=open_practices,
        figure_table_mentions=mentions,
    )

    assert set(urls["url_type"]) == {"repository", "preregistration_or_registry"}
    assert repository_links.iloc[0]["repository_type"] == "github"
    assert {"aspredicted", "clinicaltrials"}.issubset(set(preregistration_links["link_type"]))
    assert {"data", "code", "materials", "registration"}.issubset(set(open_practices["practice"]))
    assert bool(checks.iloc[0]["on_request_statement_detected"]) is True
    assert checks.iloc[0]["transparency_evidence_burden"] == 0.25
    assert {"figure", "table"} == set(mentions["mention_type"])
    assert research_object["schema_name"] == "forensic_metascience.research_object_lite"
    assert research_object["provenance"]["offline_default"] is True
    assert research_object["provenance"]["metacheck_dependency_used"] is False


def test_open_practice_detection_handles_hyphen_split_request_and_text_id() -> None:
    page_texts = build_page_text_table(
        study_id="trial_y",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=[
            "Data are available upon rea -\nsonable request from the study team.",
        ],
        starting_text_id=42,
    )
    sources = pd.DataFrame(
        [
            {
                "study_id": "trial_y",
                "source_type": "report",
                "source_pdf": "report.pdf",
                "source_path": "data/raw/report.pdf",
                "sha256": "b" * 64,
                "n_pages": 1,
            }
        ],
        columns=SOURCE_COLUMNS,
    )

    open_practices = detect_open_practices(page_texts)
    checks = build_transparency_checks(
        study_id="trial_y",
        sources=sources,
        urls=pd.DataFrame(),
        repository_links=pd.DataFrame(),
        preregistration_links=pd.DataFrame(),
        open_practices=open_practices,
        figure_table_mentions=pd.DataFrame(),
    )

    assert set(open_practices["text_id"]) == {42}
    assert bool(open_practices.iloc[0]["on_request"]) is True
    assert open_practices.iloc[0]["category"] == "upon request"
    assert bool(checks.iloc[0]["on_request_statement_detected"]) is True


def test_open_practice_detection_preserves_explicit_code_availability() -> None:
    page_texts = build_page_text_table(
        study_id="trial_code",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=["Analysis code and data are available at https://github.com/example/repo."],
    )

    open_practices = detect_open_practices(page_texts)

    assert {"code", "data"} == set(open_practices["practice"])
    assert set(open_practices["category"]) == {"repository"}
    assert set(open_practices["is_open"]) == {True}


def test_open_practice_detection_preserves_code_on_request() -> None:
    page_texts = build_page_text_table(
        study_id="trial_code_request",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=["Statistical code is available upon reasonable request from the study team."],
    )

    open_practices = detect_open_practices(page_texts)

    assert list(open_practices["practice"]) == ["code"]
    assert bool(open_practices.iloc[0]["on_request"]) is True
    assert bool(open_practices.iloc[0]["is_open"]) is False
    assert open_practices.iloc[0]["category"] == "upon request"


def test_open_practice_detection_ignores_software_use_urls() -> None:
    page_texts = build_page_text_table(
        study_id="trial_software",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=[
            (
                "Data processing, statistical analyses and figure generation were performed using "
                "SPSS (v27.0.1.0; https://www.ibm.com/spss), Graph Pad Prism "
                "(v9.5.1; https://www.graphpad.com/) and R (v4.0.3; https://www.r-project.org/). "
                "This analysis used the diffslope() function from the simba package "
                "(version 0.3-5, https://cran.r-project.org/web/packages/simba/)."
            )
        ],
    )

    open_practices = detect_open_practices(page_texts)

    assert "code" not in set(open_practices["practice"])
    assert "data" not in set(open_practices["practice"])


def test_open_practice_detection_ignores_doi_code_availability_boilerplate() -> None:
    page_texts = build_page_text_table(
        study_id="trial_doi",
        source_type="report",
        source_pdf="report.pdf",
        page_texts=[
            (
                "Online content Any methods, additional references, Nature Portfolio reporting "
                "summaries, source data, extended data, supplementary information, "
                "acknowledgements, peer review information and statements of data and code "
                "availability are available at https://doi.org/10.1038/example."
            )
        ],
    )

    open_practices = detect_open_practices(page_texts)

    assert "code" not in set(open_practices["practice"])


def test_build_transparency_inputs_writes_self_contained_out_dir(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    inputs_dir = in_dir / "inputs"
    inputs_dir.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "source_type": "report",
                "source_pdf": "report.pdf",
                "source_path": "data/raw/report.pdf",
                "sha256": "c" * 64,
                "n_pages": 1,
            }
        ],
        columns=SOURCE_COLUMNS,
    ).to_csv(inputs_dir / "research_object_sources.csv", index=False)
    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "source_type": "report",
                "source_pdf": "report.pdf",
                "page": 1,
                "text_id": 7,
                "text": "Data are available at https://osf.io/example.",
            }
        ],
        columns=PAGE_TEXT_COLUMNS,
    ).to_csv(inputs_dir / "transparency_page_texts.csv", index=False)
    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "source_pdf": "report.pdf",
                "page": 1,
                "text_id": 7,
                "url": "https://osf.io/example",
                "url_type": "repository",
                "context": "Data are available at https://osf.io/example.",
            }
        ],
        columns=URL_COLUMNS,
    ).to_csv(inputs_dir / "transparency_urls.csv", index=False)
    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "repository_type": "osf",
                "url": "https://osf.io/example",
                "source_pdf": "report.pdf",
                "page": 1,
                "text_id": 7,
                "context": "Data are available at https://osf.io/example.",
            }
        ],
        columns=REPOSITORY_COLUMNS,
    ).to_csv(inputs_dir / "transparency_repository_links.csv", index=False)
    pd.DataFrame(columns=PREREGISTRATION_COLUMNS).to_csv(
        inputs_dir / "transparency_preregistration_links.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "practice": "data",
                "is_open": True,
                "category": "repository",
                "location": "https://osf.io/example",
                "source_pdf": "report.pdf",
                "page": 1,
                "text_id": 7,
                "evidence_text": "Data are available at https://osf.io/example.",
                "on_request": False,
                "extract_confidence": "medium",
            }
        ],
        columns=OPEN_PRACTICE_COLUMNS,
    ).to_csv(inputs_dir / "transparency_open_practices.csv", index=False)
    pd.DataFrame(
        [
            {
                "study_id": "trial_z",
                "mention_type": "figure",
                "label": "Figure 1",
                "number": 1,
                "source_pdf": "report.pdf",
                "page": 1,
                "text_id": 7,
                "context": "Figure 1 shows enrollment.",
            }
        ],
        columns=FIGURE_TABLE_COLUMNS,
    ).to_csv(inputs_dir / "transparency_figure_table_mentions.csv", index=False)
    (inputs_dir / "research_object_lite.json").write_text(
        '{"schema_name":"forensic_metascience.research_object_lite"}',
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "build_transparency_inputs.py"),
            "--in",
            str(in_dir),
            "--out",
            str(out_dir),
        ],
        check=True,
        cwd=repo_root,
        env=env,
    )

    output_inputs = out_dir / "inputs"
    expected_files = [
        "research_object_sources.csv",
        "transparency_page_texts.csv",
        "transparency_urls.csv",
        "transparency_repository_links.csv",
        "transparency_preregistration_links.csv",
        "transparency_open_practices.csv",
        "transparency_figure_table_mentions.csv",
        "transparency_checks_input.csv",
        "research_object_lite.json",
    ]
    for file_name in expected_files:
        assert (output_inputs / file_name).exists()

    copied_open_practices = pd.read_csv(output_inputs / "transparency_open_practices.csv")
    checks = pd.read_csv(output_inputs / "transparency_checks_input.csv")
    assert copied_open_practices.iloc[0]["evidence_text"] == (
        "Data are available at https://osf.io/example."
    )
    assert checks.iloc[0]["n_availability_statements"] == 1
    assert checks.iloc[0]["n_repository_links"] == 1
