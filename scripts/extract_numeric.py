"""Extract numeric-integrity inputs from parsed baseline data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.inspect_sr.records import source_version_id, stable_report_id
from research_project.numeric_integrity import (
    build_numeric_table,
    build_scrutiny_input,
    build_statcheck_stub,
)
from research_project.source_tables import load_table_input, parse_mapped_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table1", type=Path, required=True)
    parser.add_argument("--report-pdf", type=Path, required=False)
    parser.add_argument("--source-pdf-path", type=Path)
    parser.add_argument("--table-input", type=Path)
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--source-pdf", type=str, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def extract_pdf_text(pdf_path: Path | None) -> str:
    """Extract concatenated text from a report PDF."""

    if pdf_path is None:
        return ""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing report PDF for statcheck input: {pdf_path}")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Missing PDF dependency for statcheck text extraction. "
            "Run `uv sync` from the repo root."
        ) from exc
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _source_version(path: Path, role: str, study_id: str) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {role} source PDF: {path}")
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    source_id = stable_report_id("", local_key=f"{study_id}:{role}:{path.name}")
    return {
        "source_id": source_id,
        "source_version_id": source_version_id(source_id, content_hash),
        "source_role": role,
        "source_name": path.name,
        "content_sha256": content_hash,
    }


def main() -> None:
    args = parse_args()
    table1_path = args.table1
    out_dir = args.out

    if not table1_path.exists():
        raise FileNotFoundError(f"Missing baseline table input: {table1_path}")

    spec = None
    if args.table_input:
        spec = load_table_input(args.table_input, Path(__file__).resolve().parents[1])
        table1_long = parse_mapped_table(spec, spec["baseline_table_id"])
    else:
        table1_long = pd.read_csv(
            table1_path,
            dtype={
                "raw_value": "string",
                "raw_statistic_value": "string",
                "reported_percent_raw": "string",
                "reported_p_raw": "string",
            },
        )
    numeric_table = build_numeric_table(table1_long)
    scrutiny_input = build_scrutiny_input(table1_long)
    statcheck_stub = build_statcheck_stub(table1_long)

    inputs_dir = out_dir / "inputs"
    metadata_dir = out_dir / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    numeric_path = inputs_dir / "numeric_table.csv"
    scrutiny_path = inputs_dir / "scrutiny_input.csv"
    statcheck_path = inputs_dir / "statcheck_input.csv"
    statcheck_text_path = inputs_dir / "statcheck_text.txt"
    metadata_path = metadata_dir / "numeric_extract_metadata.csv"
    source_versions_path = metadata_dir / "source_versions.json"

    numeric_table.to_csv(numeric_path, index=False)
    scrutiny_input.to_csv(scrutiny_path, index=False)
    statcheck_stub.to_csv(statcheck_path, index=False)
    statcheck_text_path.write_text(extract_pdf_text(args.report_pdf), encoding="utf-8")
    source_versions = []
    baseline_source_name = args.source_pdf
    if spec is not None:
        baseline = next(t for t in spec["tables"] if t["table_id"] == spec["baseline_table_id"])
        for source in spec["sources"]:
            name = Path(source["path"]).name
            source_versions.append(
                {
                    "source_id": source["source_id"],
                    "source_version_id": source["source_version_id"],
                    "source_name": name,
                    "content_sha256": source["sha256"],
                    "source_role": "source_table",
                    "extraction_method": "source_table_input_v1",
                    "extraction_version": "1",
                }
            )
            if source["source_id"] == baseline["source_id"]:
                baseline_source_name = name
    elif args.source_pdf_path:
        source_versions.append(
            _source_version(args.source_pdf_path, "baseline_table", args.study_id)
        )
    if args.report_pdf:
        report_version = _source_version(args.report_pdf, "study_report", args.study_id)
        if all(
            row["source_version_id"] != report_version["source_version_id"]
            for row in source_versions
        ):
            source_versions.append(report_version)
    source_versions_path.write_text(
        json.dumps(source_versions, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "source_pdf": baseline_source_name,
                "table1_source": str(table1_path),
                "report_pdf": str(args.report_pdf) if args.report_pdf else "",
                "extract_confidence": "high",
                "page_ref": "table1_source_page",
                "table_ref": "baseline_characteristics",
            }
        ]
    ).to_csv(metadata_path, index=False)

    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=args.source_pdf,
        category="numeric",
        extract_confidence="high",
        page_ref="table1_source_page",
        table_ref="baseline_characteristics",
        analysis_ready=False,
    )

    print(f"Wrote {numeric_path}")
    print(f"Wrote {scrutiny_path}")
    print(f"Wrote {statcheck_path}")
    print(f"Wrote {statcheck_text_path}")
    print(f"Wrote {metadata_path}")
    print(f"Wrote {source_versions_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
