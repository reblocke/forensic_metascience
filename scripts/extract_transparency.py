"""Extract machine-readable transparency evidence from study source PDFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.transparency import (
    build_page_text_table,
    build_research_object_lite,
    build_source_record,
    detect_figure_table_mentions,
    detect_open_practices,
    detect_preregistration_links,
    detect_repository_links,
    extract_urls,
)


def _import_pdf_reader() -> object:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Missing PDF dependency. Run `uv sync` from the repo root.") from exc
    return PdfReader


def _extract_page_texts(pdf_reader_cls: object, pdf_path: Path) -> list[str]:
    reader = pdf_reader_cls(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=None)
    parser.add_argument("--supplement", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--study-title", type=str, default="")
    parser.add_argument("--trial-id", type=str, default="")
    parser.add_argument("--registry-id", type=str, default="")
    parser.add_argument("--registry-url", type=str, default="")
    parser.add_argument("--publication-url", type=str, default="")
    parser.add_argument("--publication-doi", type=str, default="")
    parser.add_argument("--publication-pmid", type=str, default="")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def _source_paths(args: argparse.Namespace) -> list[tuple[str, Path]]:
    candidates = [
        ("report", args.report),
        ("protocol", args.protocol),
        ("supplement", args.supplement),
        ("baseline", args.baseline),
    ]
    paths = []
    for source_type, path in candidates:
        if path is None:
            continue
        if not path.exists():
            raise FileNotFoundError(f"Missing {source_type} PDF: {path}")
        paths.append((source_type, path))
    return paths


def _deduplicate_sources(source_paths: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    by_path: dict[Path, list[str]] = {}
    for source_type, path in source_paths:
        resolved = path.resolve()
        by_path.setdefault(resolved, []).append(source_type)
    return [("|".join(roles), path) for path, roles in by_path.items()]


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    pdf_reader_cls = _import_pdf_reader()

    source_rows: list[dict[str, object]] = []
    page_tables: list[pd.DataFrame] = []
    next_text_id = 1
    for source_type, source_path in _deduplicate_sources(_source_paths(args)):
        page_texts = _extract_page_texts(pdf_reader_cls, source_path)
        source_rows.append(
            build_source_record(
                study_id=args.study_id,
                source_type=source_type,
                source_path=source_path,
                repo_root=repo_root,
                n_pages=len(page_texts),
            )
        )
        page_table = build_page_text_table(
            study_id=args.study_id,
            source_type=source_type,
            source_pdf=source_path.name,
            page_texts=page_texts,
            starting_text_id=next_text_id,
        )
        next_text_id += len(page_table)
        page_tables.append(page_table)

    sources = pd.DataFrame(source_rows)
    page_texts = pd.concat(page_tables, ignore_index=True) if page_tables else pd.DataFrame()
    urls = extract_urls(page_texts)
    repository_links = detect_repository_links(urls)
    preregistration_links = detect_preregistration_links(page_texts, urls)
    open_practices = detect_open_practices(page_texts)
    figure_table_mentions = detect_figure_table_mentions(page_texts)
    research_object = build_research_object_lite(
        study_id=args.study_id,
        study_title=args.study_title,
        trial_id=args.trial_id,
        identifiers={
            "registry_id": args.registry_id,
            "registry_url": args.registry_url,
            "publication_url": args.publication_url,
            "publication_doi": args.publication_doi,
            "publication_pmid": args.publication_pmid,
        },
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

    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    sources_path = inputs_dir / "research_object_sources.csv"
    page_texts_path = inputs_dir / "transparency_page_texts.csv"
    urls_path = inputs_dir / "transparency_urls.csv"
    repository_path = inputs_dir / "transparency_repository_links.csv"
    preregistration_path = inputs_dir / "transparency_preregistration_links.csv"
    open_practices_path = inputs_dir / "transparency_open_practices.csv"
    mentions_path = inputs_dir / "transparency_figure_table_mentions.csv"
    object_path = inputs_dir / "research_object_lite.json"
    metadata_path = metadata_dir / "transparency_extract_metadata.csv"

    sources.to_csv(sources_path, index=False)
    page_texts.to_csv(page_texts_path, index=False)
    urls.to_csv(urls_path, index=False)
    repository_links.to_csv(repository_path, index=False)
    preregistration_links.to_csv(preregistration_path, index=False)
    open_practices.to_csv(open_practices_path, index=False)
    figure_table_mentions.to_csv(mentions_path, index=False)
    object_path.write_text(json.dumps(research_object, indent=2, sort_keys=True), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "n_source_files": len(sources),
                "n_pages": int(sources["n_pages"].sum()) if not sources.empty else 0,
                "n_urls": len(urls),
                "n_repository_links": len(repository_links),
                "n_preregistration_links": len(preregistration_links),
                "n_availability_statements": len(open_practices),
                "external_network_used": False,
                "llm_used": False,
                "metacheck_dependency_used": False,
                "extract_confidence": "medium",
            }
        ]
    ).to_csv(metadata_path, index=False)

    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf="|".join(sources["source_pdf"].astype(str).tolist()),
        category="transparency",
        extract_confidence="medium",
        page_ref="page_level_text",
        table_ref="research_object_lite",
        analysis_ready=False,
    )

    print(f"Wrote {sources_path}")
    print(f"Wrote {page_texts_path}")
    print(f"Wrote {urls_path}")
    print(f"Wrote {repository_path}")
    print(f"Wrote {preregistration_path}")
    print(f"Wrote {open_practices_path}")
    print(f"Wrote {mentions_path}")
    print(f"Wrote {object_path}")
    print(f"Wrote {metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
