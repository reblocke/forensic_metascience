"""Extract protocol/registration congruence claims from trial PDFs."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from research_project.clinicaltrials_registry import (
    build_history_events,
    derive_clinicaltrials_claims,
    fetch_current_record,
    legacy_claims_to_expanded,
    normalize_current_record,
    resolve_registry_id,
)
from research_project.forensics_manifest import manifest_path, upsert_manifest_row
from research_project.registration_forensics import derive_registration_claims


def _import_pdf_reader() -> object:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Missing PDF dependency. Run `uv sync` from the repo root.") from exc
    return PdfReader


def _extract_page_texts(pdf_reader_cls: object, pdf_path: Path) -> list[str]:
    reader = pdf_reader_cls(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("Expected true or false")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--study-id", type=str, default="lungtime")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--registry-id", type=str, default="")
    parser.add_argument("--registry-url", type=str, default="")
    parser.add_argument("--registry-current-json", type=Path, default=None)
    parser.add_argument("--registry-history", type=Path, default=None)
    parser.add_argument("--publication-url", type=str, default="")
    parser.add_argument("--publication-doi", type=str, default="")
    parser.add_argument("--publication-pmid", type=str, default="")
    parser.add_argument("--allow-network", type=_parse_bool, default=True)
    parser.add_argument("--as-of-date", type=str, default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.report.exists():
        raise FileNotFoundError(f"Missing report PDF: {args.report}")
    if not args.protocol.exists():
        raise FileNotFoundError(f"Missing protocol PDF: {args.protocol}")

    pdf_reader_cls = _import_pdf_reader()
    report_texts = _extract_page_texts(pdf_reader_cls, args.report)
    protocol_texts = _extract_page_texts(pdf_reader_cls, args.protocol)
    report_text = "\n".join(report_texts)
    protocol_text = "\n".join(protocol_texts)

    claims = derive_registration_claims(
        trial_id=args.study_id,
        report_page_texts=report_texts,
        protocol_page_texts=protocol_texts,
    )

    registry_resolution = resolve_registry_id(
        explicit_registry_id=args.registry_id,
        registry_url=args.registry_url,
        report_text=report_text,
        protocol_text=protocol_text,
    )
    fetch_result = fetch_current_record(
        study_id=args.study_id,
        registry_id=registry_resolution["registry_id"],
        registry_id_source=registry_resolution["registry_id_source"],
        registry_url=args.registry_url,
        current_json_path=args.registry_current_json,
        allow_network=args.allow_network,
    )
    current_record = normalize_current_record(
        study_id=args.study_id,
        record=fetch_result.record,
        registry_source=fetch_result.metadata.iloc[0]["registry_current_source"]
        if not fetch_result.metadata.empty
        else "",
    )
    clinicaltrials_claims = derive_clinicaltrials_claims(
        trial_id=args.study_id,
        report_text=report_text,
        protocol_text=protocol_text,
        current_record=current_record,
        fetch_metadata=fetch_result.metadata,
        registry_resolution=registry_resolution,
        publication_doi=args.publication_doi,
        publication_pmid=args.publication_pmid,
        publication_url=args.publication_url,
        as_of_date=_parse_date(args.as_of_date),
    )
    expanded_claims = pd.concat(
        [legacy_claims_to_expanded(claims), clinicaltrials_claims],
        ignore_index=True,
    )
    history_events = build_history_events(
        study_id=args.study_id,
        registry_id=registry_resolution["registry_id"],
        history_path=args.registry_history,
    )

    inputs_dir = args.out / "inputs"
    metadata_dir = args.out / "metadata"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    claims_path = inputs_dir / "registration_claims.csv"
    expanded_claims_path = inputs_dir / "registration_claims_expanded.csv"
    current_csv_path = inputs_dir / "registration_registry_current.csv"
    current_json_path = inputs_dir / "registration_registry_current.json"
    history_events_path = inputs_dir / "registration_history_events.csv"
    metadata_path = metadata_dir / "registration_extract_metadata.csv"
    fetch_metadata_path = metadata_dir / "registration_registry_fetch_metadata.csv"

    claims.to_csv(claims_path, index=False)
    expanded_claims.to_csv(expanded_claims_path, index=False)
    current_record.to_csv(current_csv_path, index=False)
    if fetch_result.record is not None:
        with current_json_path.open("w", encoding="utf-8") as handle:
            json.dump(fetch_result.record, handle, indent=2, sort_keys=True)
    elif current_json_path.exists():
        current_json_path.unlink()
    history_events.to_csv(history_events_path, index=False)
    fetch_result.metadata.to_csv(fetch_metadata_path, index=False)
    pd.DataFrame(
        [
            {
                "study_id": args.study_id,
                "report_pdf": str(args.report),
                "protocol_pdf": str(args.protocol),
                "extract_confidence": "medium",
                "n_claims": len(claims),
                "n_expanded_claims": len(expanded_claims),
                "registry_id": registry_resolution["registry_id"],
                "registry_id_source": registry_resolution["registry_id_source"],
                "registry_resolution_status": registry_resolution["resolution_status"],
                "registry_resolution_message": registry_resolution["resolution_message"],
            }
        ]
    ).to_csv(metadata_path, index=False)

    repo_root = Path(__file__).resolve().parents[1]
    manifest = manifest_path(repo_root, args.study_id)
    upsert_manifest_row(
        manifest,
        study_id=args.study_id,
        source_pdf=f"{args.report.name}|{args.protocol.name}",
        category="registration",
        extract_confidence="medium",
        page_ref="claim_level",
        table_ref="report_vs_protocol_registry",
        analysis_ready=False,
    )

    print(f"Wrote {claims_path}")
    print(f"Wrote {expanded_claims_path}")
    print(f"Wrote {current_csv_path}")
    print(f"Wrote {history_events_path}")
    print(f"Wrote {metadata_path}")
    print(f"Wrote {fetch_metadata_path}")
    print(f"Updated {manifest}")


if __name__ == "__main__":
    main()
