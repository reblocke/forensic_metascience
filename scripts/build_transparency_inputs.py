"""Build report-ready transparency inputs from extracted evidence tables."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError

from research_project.transparency import (
    FIGURE_TABLE_COLUMNS,
    OPEN_PRACTICE_COLUMNS,
    PAGE_TEXT_COLUMNS,
    PREREGISTRATION_COLUMNS,
    REPOSITORY_COLUMNS,
    SOURCE_COLUMNS,
    URL_COLUMNS,
    build_transparency_checks,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_dir", type=Path, required=True)
    return parser.parse_args()


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _copy_if_present(source_path: Path, destination_path: Path) -> None:
    if not source_path.exists():
        return
    if source_path.resolve() == destination_path.resolve():
        return
    shutil.copyfile(source_path, destination_path)


def main() -> None:
    args = parse_args()
    inputs = args.in_dir / "inputs"
    sources = _read_csv(inputs / "research_object_sources.csv", SOURCE_COLUMNS)
    page_texts = _read_csv(inputs / "transparency_page_texts.csv", PAGE_TEXT_COLUMNS)
    urls = _read_csv(inputs / "transparency_urls.csv", URL_COLUMNS)
    repository_links = _read_csv(inputs / "transparency_repository_links.csv", REPOSITORY_COLUMNS)
    preregistration_links = _read_csv(
        inputs / "transparency_preregistration_links.csv", PREREGISTRATION_COLUMNS
    )
    open_practices = _read_csv(inputs / "transparency_open_practices.csv", OPEN_PRACTICE_COLUMNS)
    figure_table_mentions = _read_csv(
        inputs / "transparency_figure_table_mentions.csv", FIGURE_TABLE_COLUMNS
    )
    study_id = str(sources["study_id"].iloc[0]) if not sources.empty else str(args.in_dir.name)

    checks = build_transparency_checks(
        study_id=study_id,
        sources=sources,
        urls=urls,
        repository_links=repository_links,
        preregistration_links=preregistration_links,
        open_practices=open_practices,
        figure_table_mentions=figure_table_mentions,
        external_network_used=False,
        llm_used=False,
        metacheck_dependency_used=False,
    )

    output_inputs = args.out_dir / "inputs"
    output_inputs.mkdir(parents=True, exist_ok=True)
    sources_path = output_inputs / "research_object_sources.csv"
    page_texts_path = output_inputs / "transparency_page_texts.csv"
    urls_path = output_inputs / "transparency_urls.csv"
    repository_path = output_inputs / "transparency_repository_links.csv"
    preregistration_path = output_inputs / "transparency_preregistration_links.csv"
    open_practices_path = output_inputs / "transparency_open_practices.csv"
    mentions_path = output_inputs / "transparency_figure_table_mentions.csv"
    checks_path = output_inputs / "transparency_checks_input.csv"
    sources.to_csv(sources_path, index=False)
    if (inputs / "transparency_page_texts.csv").exists():
        page_texts.to_csv(page_texts_path, index=False)
    urls.to_csv(urls_path, index=False)
    repository_links.to_csv(repository_path, index=False)
    preregistration_links.to_csv(preregistration_path, index=False)
    open_practices.to_csv(open_practices_path, index=False)
    figure_table_mentions.to_csv(mentions_path, index=False)
    checks.to_csv(checks_path, index=False)
    _copy_if_present(
        inputs / "research_object_lite.json", output_inputs / "research_object_lite.json"
    )
    print(f"Wrote {sources_path}")
    if page_texts_path.exists():
        print(f"Wrote {page_texts_path}")
    print(f"Wrote {urls_path}")
    print(f"Wrote {repository_path}")
    print(f"Wrote {preregistration_path}")
    print(f"Wrote {open_practices_path}")
    print(f"Wrote {mentions_path}")
    print(f"Wrote {checks_path}")


if __name__ == "__main__":
    main()
