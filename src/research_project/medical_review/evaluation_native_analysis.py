"""Actual base-R descriptive execution with immutable private inputs and receipts."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation_analysis import (
    TABLE_FIELDS,
    csv_bytes,
    load_analysis_tables,
)
from research_project.medical_review.evaluation_analysis import (
    _code_sources as tables_code_sources,
)
from research_project.medical_review.evaluation_assessment import _write
from research_project.medical_review.evaluation_candidates import _snapshot
from research_project.medical_review.evaluation_packets import _json_bytes
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    content_hash,
    identity,
    private_path,
    read_json,
)
from research_project.run_manifest import create_run, sha256_file, update_run

OUTPUTS = (
    "findings_by_view_stage",
    "findings_by_attempt_stage",
    "synthesis_by_view",
    "effort_by_view_phase",
    "resources_by_packet_currency",
    "error_stage_by_view",
    "paired_case_comparisons",
    "runtime",
)
FLAGS = {"output_supplied", "review_coverage_available", "independent_experimental_units"}
NUMBERS = {
    "repetition",
    "important_reference_detected",
    "important_reference_unknown",
    "serious_false_unknown",
    "distortion_unknown",
    "caveats_preserved",
    "caveats_lost",
    "caveats_distorted",
    "caveats_unresolved",
    "verification_seconds",
    "revision_seconds",
    "elapsed_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_amount",
    "important_detection_difference",
    "reported_attempts",
    "completed_attempts",
    "partial_attempts",
    "failed_attempts",
    "blocked_attempts",
    "not_started_attempts",
}
TIMEOUT_SECONDS = 120


def _code_sources(repo: Path):
    return {**tables_code_sources(repo), "evaluation_native_analysis.py": Path(__file__)}


def _execute(rscript: str, driver: Path, inputs: Path, outputs: Path, stdout: Path, stderr: Path):
    with stdout.open("xb") as out, stderr.open("xb") as err:
        return subprocess.run(
            [rscript, str(driver), "--in", str(inputs), "--out", str(outputs)],
            cwd=inputs.parent,
            stdout=out,
            stderr=err,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )


def _read_csv(raw: bytes) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    fields = reader.fieldnames
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("Native analysis CSV has missing/duplicate fields.")
    result = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Native analysis CSV row shape mismatch.")
        parsed = {}
        for field, text in row.items():
            if text == "":
                value = None
            elif field in FLAGS:
                if text not in {"TRUE", "FALSE"}:
                    raise ValueError("Native analysis boolean contract mismatch.")
                value = text == "TRUE"
            elif field in NUMBERS or field.endswith(("_count", "_records", "_known_sum")):
                value = float(text)
                if not math.isfinite(value):
                    raise ValueError("Native analysis numeric data must be finite or unknown.")
            else:
                value = text
            parsed[field] = value
        result.append(parsed)
    return result


def _record(loaded: dict[str, Any], outputs: dict[str, Any], receipt: dict[str, Any]):
    runtime = {r["name"]: r["value"] for r in outputs["runtime"]}
    if (
        len(runtime) != len(outputs["runtime"])
        or runtime.get("schema_version") != "medical_evaluation_descriptive_tables_v2"
        or runtime.get("medical_performance_validated") != "false"
        or runtime.get("inferential_analysis") != "not_performed"
        or runtime.get("r_version") != receipt["r_version"]
        or not str(runtime.get("r_version", "")).startswith("R version")
        or receipt["returncode"] != 0
    ):
        raise ValueError("Native analysis runtime/qualification receipt mismatch.")
    tables = loaded["tables"]
    record = {
        "schema_version": "medical_evaluation_native_analysis_v2",
        "evaluation_id": tables["evaluation_id"],
        "tables_record_id": tables["record_id"],
        "plan_id": tables["plan_id"],
        "unblinding_record_id": tables["unblinding_record_id"],
        "threshold_record_id": tables["threshold_record_id"],
        "reference_record_id": tables["reference_record_id"],
        "outputs": outputs,
        "native_receipt": receipt,
        "measurement_provenance": tables["measurement_provenance"],
        "runtime_comparison": tables["runtime_comparison"],
        "runtime_equivalence": tables["runtime_equivalence"],
        "qualification": {
            "software_acceptance": "requires_separate_exact_head_evidence",
            "live_operational_acceptance": "not_established_by_offline_supplied_outputs",
            "medical_performance": "pending",
            "threshold_evaluation": "human_defined_rules_not_automatically_interpreted",
            "held_out_performance": "not_established_by_descriptive_execution",
            "feature_enabled_by_default": False,
        },
        "review_coverage_available": False,
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("nativedescriptiveanalysis", record)
    _json_bytes(record)
    return record


def run_native_analysis(repo_root: Path, tables_run: Path) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, tables_run, PRIVATE_RUNS)
    loaded = load_analysis_tables(repo, parent)
    sources = _code_sources(repo)
    code = {k: p.read_bytes() for k, p in sources.items()}
    for name in ("R/medical_evaluation.R", "scripts/analyze_medical_evaluation.R"):
        archived = recorded_artifact(
            repo, parent, loaded["manifest"], "generated/medical_evaluation/code/" + name
        )
        if archived.read_bytes() != code[name]:
            raise ValueError("R code changed since table preparation; freeze new tables.")
    parent_hash = sha256_file(parent / "run_manifest.json")
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=loaded["tables"]["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=parent / "run_manifest.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_native_stage": "analysis",
            "parent_run_reference": str(parent.relative_to(repo)),
            "parent_manifest_sha256": parent_hash,
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "timeout_seconds": TIMEOUT_SECONDS,
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    inputs = run / "generated/medical_evaluation/native_inputs"
    outputs = run / "processed/medical_evaluation/native"
    stdout = run / "logs/medical_evaluation/native.stdout"
    stderr = run / "logs/medical_evaluation/native.stderr"
    input_bytes = {
        name: csv_bytes(loaded["tables"]["tables"][name], fields)
        for name, fields in TABLE_FIELDS.items()
    }
    try:
        for name, raw in code.items():
            _write(run, manifest, "generated/medical_evaluation/code/" + name, raw)
        for name, raw in input_bytes.items():
            _write(
                run, manifest, "generated/medical_evaluation/native_inputs/" + name + ".csv", raw
            )
        outputs.mkdir(parents=True)
        stdout.parent.mkdir(parents=True)
        rscript = shutil.which("Rscript")
        if rscript is None:
            raise ValueError(
                "Rscript unavailable; native analysis is blocked without a substitute."
            )
        binary = Path(rscript).resolve()
        executable_hash = sha256_file(binary)
        started = time.monotonic()
        try:
            completed = _execute(
                rscript,
                run / "generated/medical_evaluation/code/scripts/analyze_medical_evaluation.R",
                inputs,
                outputs,
                stdout,
                stderr,
            )
        finally:
            for log in (stdout, stderr):
                if log.exists():
                    update_run(manifest, artifact=str(log))
            for name in OUTPUTS:
                path = outputs / (name + ".csv")
                if path.exists():
                    update_run(manifest, artifact=str(path))
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            raise ValueError("Native R analysis failed; consult the preserved private stderr.")
        parsed = {name: _read_csv(_snapshot(outputs / (name + ".csv"))) for name in OUTPUTS}
        runtime = {r["name"]: r["value"] for r in parsed["runtime"]}
        receipt = {
            "schema_version": "medical_evaluation_native_receipt_v1",
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "timeout_seconds": TIMEOUT_SECONDS,
            "r_version": runtime.get("r_version"),
            "base_version": runtime.get("base_version"),
            "platform": runtime.get("platform"),
            "executable_sha256": executable_hash,
            "input_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in input_bytes.items()},
            "output_sha256": {k: sha256_file(outputs / (k + ".csv")) for k in OUTPUTS},
            "seed_used": None,
            "randomness": "not_used_descriptive_transforms",
            "source_table_seed": loaded["tables"]["seed"],
            "execution_scope": "native_descriptive_execution_not_model_or_medical_validation",
        }
        _write(
            run, manifest, "processed/medical_evaluation/native_receipt.json", _json_bytes(receipt)
        )
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or any(sources[k].read_bytes() != v for k, v in code.items())
            or sha256_file(binary) != executable_hash
            or any(
                (inputs / (name + ".csv")).read_bytes() != raw for name, raw in input_bytes.items()
            )
            or load_analysis_tables(repo, parent)["tables"] != loaded["tables"]
        ):
            raise ValueError(
                "Native analysis source/input/parent/code/runtime changed during execution."
            )
        record = _record(loaded, parsed, receipt)
        _write(run, manifest, "processed/medical_evaluation/analysis.json", _json_bytes(record))
        update_run(manifest, stage="native-analysis", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_native_analysis(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_native_stage") != "analysis"
    ):
        raise ValueError("Native analysis is not successfully completed.")
    parent = private_path(repo, Path(settings["parent_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["parent_manifest_sha256"]:
        raise ValueError("Native analysis parent manifest changed.")
    loaded = load_analysis_tables(repo, parent)
    code = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources(repo)
    }
    if content_hash(code) != settings["code_sha256"]:
        raise ValueError("Native analysis code archive changed.")
    receipt = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/native_receipt.json")
    )
    for name, fields in TABLE_FIELDS.items():
        raw = _snapshot(
            recorded_artifact(
                repo, run, manifest, "generated/medical_evaluation/native_inputs/" + name + ".csv"
            )
        )
        if (
            raw != csv_bytes(loaded["tables"]["tables"][name], fields)
            or hashlib.sha256(raw).hexdigest() != receipt["input_sha256"][name]
        ):
            raise ValueError("Native analysis input binding changed.")
    parsed = {}
    for name in OUTPUTS:
        path = recorded_artifact(
            repo, run, manifest, "processed/medical_evaluation/native/" + name + ".csv"
        )
        if sha256_file(path) != receipt["output_sha256"][name]:
            raise ValueError("Native analysis output binding changed.")
        parsed[name] = _read_csv(_snapshot(path))
    record = read_json(
        recorded_artifact(repo, run, manifest, "processed/medical_evaluation/analysis.json")
    )
    if _record(loaded, parsed, receipt) != record:
        raise ValueError("Native analysis semantic/output/receipt binding changed.")
    return {"run_root": run, "manifest": manifest, "tables": loaded, "analysis": record}
