"""Canonical, private table exports from an explicitly released evaluation chain."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import math
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation_assessment import _write
from research_project.medical_review.evaluation_governance import (
    _code_sources as governance_code_sources,
)
from research_project.medical_review.evaluation_governance import load_unblinding
from research_project.medical_review.evaluation_packets import _json_bytes
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    content_hash,
    identity,
    private_path,
    read_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

METADATA = (
    "view_id",
    "packet_id",
    "case_id",
    "analysis_unit_id",
    "partition",
    "profile_ids",
    "track",
    "condition_id",
    "repetition",
    "source_set_id",
    "input_equivalence",
)
TABLE_FIELDS = {
    "views": METADATA
    + (
        "reviewer_supplied",
        "synthesis_supplied",
        "case_reference_scope",
        "required_source_gap_scope_count",
        "synthetic",
        "previously_analyzed",
        "runtime_comparison",
    ),
    "findings": (
        "item_id",
        "candidate_id",
        "view_id",
        "packet_id",
        "case_id",
        "attempt_id",
        "stage",
        "disposition",
        "important",
        "serious_false_allegation",
        "source_attribution",
        "issue_type",
        "assessor_count",
        "assessor_shortfall_reason",
    ),
    "references": (
        "case_id",
        "reference_id",
        "analysis_unit_id",
        "study_id",
        "comparison_id",
        "disposition",
        "important",
        "issue_type",
    ),
    "matches": ("item_id", "case_id", "reference_id"),
    "synthesis": (
        "item_id",
        "candidate_id",
        "view_id",
        "packet_id",
        "case_id",
        "attempt_id",
        "stage",
        "disposition",
        "distorted",
        "error_stage",
        "group_id",
        "assessor_count",
        "assessor_shortfall_reason",
        "caveats_preserved",
        "caveats_lost",
        "caveats_distorted",
        "caveats_unresolved",
    ),
    "timings": (
        "view_id",
        "phase",
        "observer_role",
        "observer_id",
        "verification_seconds",
        "revision_seconds",
    ),
    "attempts": (
        "packet_id",
        "attempt_id",
        "status",
        "origin",
        "reviewer_supplied",
        "synthesis_supplied",
        "elapsed_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_amount",
        "cost_currency",
    ),
}


def csv_bytes(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    """Use empty fields only for unknown data; keep literal NA and false/zero distinct."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        if set(row) != set(fields):
            raise ValueError("Analysis CSV fields do not match their declared contract.")
        normalized = {}
        for key, value in row.items():
            if type(value) is float and not math.isfinite(value):
                raise ValueError("Analysis CSV numbers must be finite or unknown.")
            if value is not None and type(value) not in {str, bool, int, float}:
                raise ValueError("Analysis CSV values must be scalar data.")
            normalized[key] = (
                ""
                if value is None
                else ("TRUE" if value is True else "FALSE" if value is False else value)
            )
        writer.writerow(normalized)
    raw = stream.getvalue().encode("utf-8")
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Analysis table exceeds 20 MiB; split explicitly without truncation.")
    return raw


def export_tables(loaded: dict[str, Any]) -> dict[str, Any]:
    """Map validated released records to R fields without selecting or pooling attempts."""
    synthesis = loaded["synthesis"]
    packets = synthesis["packets"]["packets"]
    assessment = synthesis["packets"]["assessment"]
    candidates = assessment["packets"]["candidates"]
    source_packets = candidates["packets"]
    reference = source_packets["reference"]
    plan = reference["plan"]
    cases = {c["case_id"]: c for c in plan["cases"]}
    sources = {p["packet_id"]: p for p in source_packets["packets"]["packets"]}
    items = {i["item_id"]: i for i in packets["items"]}
    scopes = {s["case_id"]: s for s in reference["ledger"]["case_reference_scope"]}
    attempts = candidates["candidates"]["attempts"]
    tables = {name: [] for name in TABLE_FIELDS}
    for view in packets["views"]:
        packet = sources[view["packet_id"]]
        case = cases[view["case_id"]]
        scoped = [a for a in attempts if a["packet_id"] == view["packet_id"]]
        tables["views"].append(
            {
                **{
                    k: view[k] for k in ("view_id", "packet_id", "case_id", "track", "condition_id")
                },
                "analysis_unit_id": packet["analysis_unit_id"],
                "partition": case["partition"],
                "profile_ids": "|".join(case["profile_ids"]),
                "repetition": packet["repetition"],
                # Human packets contain the full case. Compare the model's selected access.
                "source_set_id": content_hash(sorted(packet["source_version_ids"])),
                "input_equivalence": packet["input_equivalence"],
                **{
                    stage + "_supplied": any(
                        o["stage"] == stage for a in scoped for o in a["outputs"]
                    )
                    for stage in ("reviewer", "synthesis")
                },
                "case_reference_scope": scopes[case["case_id"]]["status"],
                "required_source_gap_scope_count": len(
                    scopes[case["case_id"]]["required_source_gaps"]
                ),
                "synthetic": case["synthetic"],
                "previously_analyzed": case["previously_analyzed"],
                "runtime_comparison": plan["runtime_comparison"],
            }
        )
    for row in assessment["assessment"]["judgments"]:
        item = items[row["item_id"]]
        tables["findings"].append(
            {
                **{
                    k: item[k]
                    for k in (
                        "item_id",
                        "candidate_id",
                        "view_id",
                        "packet_id",
                        "case_id",
                        "attempt_id",
                        "stage",
                    )
                },
                **{k: row[k] for k in TABLE_FIELDS["findings"] if k not in item},
            }
        )
        for reference_id in row["reference_ids"]:
            tables["matches"].append(
                {"item_id": row["item_id"], "case_id": row["case_id"], "reference_id": reference_id}
            )
    for row in reference["ledger"]["reference_issues"]:
        tables["references"].append({k: row[k] for k in TABLE_FIELDS["references"]})
    for row in synthesis["synthesis"]["judgments"]:
        item = items[row["item_id"]]
        tables["synthesis"].append(
            {
                **{
                    k: item[k]
                    for k in (
                        "item_id",
                        "candidate_id",
                        "view_id",
                        "packet_id",
                        "case_id",
                        "attempt_id",
                        "stage",
                    )
                },
                **{
                    k: row[k]
                    for k in (
                        "disposition",
                        "distorted",
                        "error_stage",
                        "group_id",
                        "assessor_count",
                        "assessor_shortfall_reason",
                    )
                },
                **{
                    "caveats_" + status: sum(c["status"] == status for c in row["critical_caveats"])
                    for status in ("preserved", "lost", "distorted", "unresolved")
                },
            }
        )
    for phase, record in (
        ("candidate_assessment", assessment["assessment"]),
        ("synthesis_assessment", synthesis["synthesis"]),
    ):
        people = [("assessor", p) for p in record["assessors"]] + [
            ("adjudicator", record["adjudication"])
        ]
        for role, person in people:
            observer = identity(
                "timingobserver",
                {
                    "record_id": record["record_id"],
                    "role": role,
                    "human_identity": person["human_identity"],
                },
            )
            for timing in person["view_timings"]:
                tables["timings"].append(
                    {**timing, "phase": phase, "observer_role": role, "observer_id": observer}
                )
    for attempt in attempts:
        tables["attempts"].append(
            {
                **{k: attempt[k] for k in ("packet_id", "attempt_id", "status", "origin")},
                **{
                    stage + "_supplied": any(o["stage"] == stage for o in attempt["outputs"])
                    for stage in ("reviewer", "synthesis")
                },
                **attempt["usage"],
            }
        )
    record = {
        "schema_version": "medical_evaluation_analysis_tables_v2",
        "evaluation_id": plan["evaluation_id"],
        "plan_id": plan["plan_id"],
        "reference_record_id": reference["ledger"]["ledger_id"],
        "unblinding_record_id": loaded["unblinding"]["record_id"],
        "threshold_record_id": loaded["thresholds"]["thresholds"]["record_id"],
        "candidate_record_id": candidates["candidates"]["record_id"],
        "assessment_record_id": assessment["assessment"]["record_id"],
        "synthesis_record_id": synthesis["synthesis"]["record_id"],
        "seed": plan["seed"],
        "tables": tables,
        "case_reference_scopes": copy.deepcopy(reference["ledger"]["case_reference_scope"]),
        "measurement_provenance": "operator_attested_not_authenticated",
        "runtime_comparison": plan["runtime_comparison"],
        "runtime_equivalence": "unverified_not_inferred_from_source_matching",
        "review_coverage_available": False,
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    for name, fields in TABLE_FIELDS.items():
        csv_bytes(tables[name], fields)
    record["record_id"] = identity("evaluationtables", record)
    _json_bytes(record)
    return record


def _code_sources(repo: Path) -> dict[str, Path]:
    return {
        **governance_code_sources(),
        "evaluation_analysis.py": Path(__file__),
        "R/medical_evaluation.R": repo / "R/medical_evaluation.R",
        "scripts/analyze_medical_evaluation.R": repo / "scripts/analyze_medical_evaluation.R",
    }


def prepare_analysis_tables(repo_root: Path, unblinding_run: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, unblinding_run, PRIVATE_RUNS)
    loaded = load_unblinding(repo, parent)
    record = export_tables(loaded)
    sources = _code_sources(repo)
    code = {k: p.read_bytes() for k, p in sources.items()}
    parent_hash = sha256_file(parent / "run_manifest.json")
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=record["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=parent / "run_manifest.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_analysis_stage": "tables",
            "parent_run_reference": str(parent.relative_to(repo)),
            "parent_manifest_sha256": parent_hash,
            "record_sha256": content_hash(record),
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        _write(run, manifest, "generated/medical_evaluation/tables_input.json", _json_bytes(record))
        for name, raw in code.items():
            _write(run, manifest, "generated/medical_evaluation/code/" + name, raw)
        for name, fields in TABLE_FIELDS.items():
            _write(
                run,
                manifest,
                "processed/medical_evaluation/tables/" + name + ".csv",
                csv_bytes(record["tables"][name], fields),
            )
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or any(sources[k].read_bytes() != v for k, v in code.items())
            or export_tables(load_unblinding(repo, parent)) != record
        ):
            raise ValueError("Analysis source/parent/code changed while freezing tables.")
        _write(
            run, manifest, "processed/medical_evaluation/analysis_tables.json", _json_bytes(record)
        )
        update_run(manifest, stage="analysis-tables", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_analysis_tables(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_analysis_stage") != "tables"
    ):
        raise ValueError("Analysis tables are not successfully completed.")
    parent = private_path(repo, Path(settings["parent_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["parent_manifest_sha256"]:
        raise ValueError("Analysis table parent manifest changed.")
    loaded = load_unblinding(repo, parent)
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/analysis_tables.json")
    )
    code = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources(repo)
    }
    if (
        content_hash(code) != settings["code_sha256"]
        or content_hash(record) != settings["record_sha256"]
        or export_tables(loaded) != record
    ):
        raise ValueError("Analysis table code/source/semantic binding changed.")
    if (
        read_json(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/tables_input.json")
        )
        != record
    ):
        raise ValueError("Analysis archived input changed.")
    for name, fields in TABLE_FIELDS.items():
        path = recorded_artifact(
            repo, run, manifest, "processed/medical_evaluation/tables/" + name + ".csv"
        )
        if path.read_bytes() != csv_bytes(record["tables"][name], fields):
            raise ValueError("Analysis CSV serialization changed.")
    return {"run_root": run, "manifest": manifest, "unblinding": loaded, "tables": record}
