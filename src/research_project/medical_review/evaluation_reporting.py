"""Private descriptive evaluation reports from an explicit validated R analysis."""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import recorded_artifact, validate_run_artifacts
from research_project.medical_review.evaluation_analysis import METADATA
from research_project.medical_review.evaluation_assessment import _write
from research_project.medical_review.evaluation_native_analysis import (
    _code_sources as native_code_sources,
)
from research_project.medical_review.evaluation_native_analysis import load_native_analysis
from research_project.medical_review.evaluation_packets import _json_bytes
from research_project.medical_review.records import (
    PRIVATE_RUNS,
    content_hash,
    identity,
    private_path,
    read_json,
)
from research_project.medical_review.reporting import (
    _escaped,
    _record_lines,
    _source_navigation,
    _table,
)
from research_project.run_manifest import create_run, sha256_file, update_run

MODEL_PATH = "processed/medical_evaluation/report_model.json"
QUALIFICATION_PATH = "processed/medical_evaluation/qualification.json"
REPORTS = "reports/medical_evaluation/"
TEMPLATE = "notebooks/medical_review_evaluation.qmd"


def _code_sources(repo: Path):
    return {
        **native_code_sources(repo),
        "evaluation_reporting.py": Path(__file__),
        "reporting.py": Path(__file__).with_name("reporting.py"),
        TEMPLATE: repo / TEMPLATE,
    }


def _qualification(analysis: dict[str, Any]) -> dict[str, Any]:
    record = {
        "schema_version": "medical_evaluation_qualification_v1",
        "analysis_record_id": analysis["record_id"],
        "evaluation_id": analysis["evaluation_id"],
        "plan_id": analysis["plan_id"],
        "threshold_record_id": analysis["threshold_record_id"],
        **copy.deepcopy(analysis["qualification"]),
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["record_id"] = identity("medicalqualification", record)
    return record


def build_evaluation_report(repo: Path, loaded: dict[str, Any]) -> dict[str, Any]:
    """Format source-bound measurements; do not infer live success or human qualification."""
    tables = loaded["tables"]
    released = tables["unblinding"]
    synthesis = released["synthesis"]
    assessment = synthesis["packets"]["assessment"]
    candidates = assessment["packets"]["candidates"]
    source_packets = candidates["packets"]
    reference = source_packets["reference"]
    plan = reference["plan"]
    candidate_map = {r["candidate_id"]: r for r in candidates["candidates"]["candidates"]}
    judgments = {r["item_id"]: r for r in assessment["assessment"]["judgments"]}
    synth_judgments = {r["item_id"]: r for r in synthesis["synthesis"]["judgments"]}
    items = synthesis["packets"]["packets"]["items"]
    if set(judgments) != {r["item_id"] for r in items} or set(synth_judgments) != set(judgments):
        raise ValueError("Report must account for every assessed candidate and synthesis item.")
    navigation = []
    for case in plan["cases"]:
        for document in _source_navigation(repo, case["bundle"], PRIVATE_RUNS)["documents"]:
            navigation.append({"case_id": case["case_id"], **document})
    lineage = []
    for label, stage in (
        ("Native descriptive analysis", loaded),
        ("Frozen R tables", tables),
        ("Condition release", released),
        ("Threshold criteria", released["thresholds"]),
        ("Synthesis assessment", synthesis),
        ("Synthesis packets", synthesis["packets"]),
        ("Candidate assessment", assessment),
        ("Candidate packets", assessment["packets"]),
        ("Supplied candidates and attempts", candidates),
        ("Model source packets", source_packets),
        ("Source reference ledger", reference),
    ):
        lineage.append(
            {
                "label": label,
                "run_reference": str(stage["run_root"].relative_to(repo)),
                "manifest_sha256": sha256_file(stage["run_root"] / "run_manifest.json"),
            }
        )
    record = {
        "schema_version": "medical_evaluation_report_model_v1",
        "evaluation_id": plan["evaluation_id"],
        "analysis_record_id": loaded["analysis"]["record_id"],
        "qualification": _qualification(loaded["analysis"]),
        "analysis": copy.deepcopy(loaded["analysis"]),
        "source_tables": copy.deepcopy(tables["tables"]),
        "evaluation_plan": copy.deepcopy(plan),
        "thresholds": copy.deepcopy(released["thresholds"]["thresholds"]),
        "reference_ledger": copy.deepcopy(reference["ledger"]),
        "source_navigation": navigation,
        "lineage": lineage,
        "attempts": copy.deepcopy(candidates["candidates"]["attempts"]),
        "candidate_accounting": [
            {
                **copy.deepcopy(item),
                "candidate": copy.deepcopy(candidate_map[item["candidate_id"]]),
                "human_judgment": copy.deepcopy(judgments[item["item_id"]]),
                "synthesis_judgment": copy.deepcopy(synth_judgments[item["item_id"]]),
            }
            for item in items
        ],
        "synthesis_groups": copy.deepcopy(synthesis["synthesis"]["adjudication"]["groups"]),
        "review_coverage_available": False,
        "medical_performance_validated": False,
        "official_assessment": None,
    }
    record["rendered_markdown"] = _markdown(record)
    record["record_id"] = identity("medicalevaluationreport", record)
    _json_bytes(record)
    return record


def _source_links(model, case_id, evidence):
    lines = []
    documents = {
        r["source_version_id"]: r
        for r in model["source_navigation"]
        if r["case_id"] == case_id and r["href"] is not None
    }
    for ev in evidence:
        document = documents.get(ev["source_version_id"])
        if document is None:
            raise ValueError("Report evidence source is absent from its case navigation.")
        page = ev.get("page_index")
        fragment = (
            f"#page={page + 1}"
            if document["source_reference"].lower().endswith(".pdf")
            and type(page) is int
            and page >= 0
            else ""
        )
        lines.append(f"[Original source evidence]({document['href']}{fragment})\n")
        lines.extend(_record_lines(ev))
    return lines


def _markdown(model: dict[str, Any]) -> str:
    views = {
        r["view_id"]: f"V{i + 1}" for i, r in enumerate(model["source_tables"]["tables"]["views"])
    }
    attempts = {r["attempt_id"]: f"A{i + 1}" for i, r in enumerate(model["attempts"])}

    def compact(row):
        return (
            "; ".join(
                f"**{_escaped(k.replace('_', ' '))}:** "
                + _escaped(views.get(v, attempts.get(v, v)) if isinstance(v, str) else v)
                for k, v in row.items()
            )
            + "\n"
        )

    lines = [
        "# Medical review evaluation: qualification pending\n",
        "**Medical qualification: pending. Feature enabled by default: false.**\n",
        "These are descriptive measurements of supplied outputs and operator-attested human "
        "records. They establish neither live model execution nor validated medical review. "
        "Software acceptance needs separate exact-head test evidence. No official INSPECT-SR "
        "judgment is produced. Review coverage remains unavailable.\n",
        "## Scope and comparison rules\n",
        "Common-input and full-bundle tracks are separate. Model source access determines "
        "input matching; human assessment may use the full case bundle. Unmatched comparisons "
        "have no detection difference. Equal source bytes do not establish runtime equality. "
        "A supplied artifact union is not a single-run performance estimate. All declared "
        "attempt pairs remain dependent within study, case and planned repetition. No best "
        "retry, pooled inferential test, universal defect sensitivity or composite score "
        "is used.\n",
        "Complete original findings and exact identities remain in the "
        "[current report model](../../processed/medical_evaluation/report_model.json). "
        "V/A labels below are local display labels, not new source or run identities.\n",
    ]
    lines.extend(_record_lines(model["qualification"]))
    for case in model["evaluation_plan"]["cases"]:
        lines.append(f"### Case {_escaped(case['case_id'])}\n")
        lines.extend(
            _record_lines(
                {
                    k: case[k]
                    for k in (
                        "case_id",
                        "analysis_unit_id",
                        "partition",
                        "synthetic",
                        "previously_analyzed",
                        "profile_ids",
                    )
                }
            )
        )
    lines.append("### View and attempt labels\n")
    for view in model["source_tables"]["tables"]["views"]:
        lines.append(compact(view))
    lines.extend(_record_lines({"view_ids": views, "attempt_ids": attempts}))
    lines.append("### Attempt-level finding overview\n")
    lines.append(
        "Detected counts are important reference issue IDs in the bounded source ledger; "
        "they are not sensitivity to all defects. Complete denominators, unknown importance, "
        "source attribution and unavailable stages remain in the measurements below.\n"
    )
    fields = (
        ("important_reference_detected", "Detected"),
        ("confirmed_records", "Confirmed"),
        ("unsupported_records", "Unsupported"),
    )
    lines.extend(
        _table(
            ["View", "Attempt", "Stage", *[label for _, label in fields]],
            [
                [
                    views[row["view_id"]],
                    attempts.get(row["attempt_id"], "unreported"),
                    row["stage"],
                    *[row[key] if row[key] is not None else "unknown" for key, _ in fields],
                ]
                for row in model["analysis"]["outputs"]["findings_by_attempt_stage"]
            ],
        )
    )
    lines.append("## Source reference ledger\n")
    lines.append(
        "Reference issue detection is bounded by this ledger and its reviewed sources. "
        "A clean control means no reference issue in that scope, not a universally clean "
        "paper. Independent source assessors and their qualifications are operator attested; "
        "these records do not authenticate credentials or actual blinding.\n"
    )
    for scope in model["reference_ledger"]["case_reference_scope"]:
        lines.extend(_record_lines(scope))
    for issue in model["reference_ledger"]["reference_issues"]:
        lines.extend(_record_lines({k: v for k, v in issue.items() if k != "source_evidence"}))
        lines.extend(_source_links(model, issue["case_id"], issue["source_evidence"]))
    lines.append("## Original source navigation\n")
    for row in model["source_navigation"]:
        lines.extend(_record_lines({k: v for k, v in row.items() if k != "href"}))
        if row["href"] is not None:
            lines.append(f"[Original source version]({row['href']})\n")
    lines.append("## Descriptive measurements\n")
    lines.append(
        "Unknown values are null and remain unavailable; zero is observed zero. Counts "
        "describe source-adjudicated records. Human time is measured per view and phase; "
        "it is not allocated to individual attempts. Failure resources and separate "
        "currencies are retained. Error-stage labels are human annotations.\n"
    )
    for name, rows in model["analysis"]["outputs"].items():
        lines.append(f"### {_escaped(name)}\n")
        for index, row in enumerate(rows):
            label = views.get(row.get("view_id"), f"Record {index + 1}")
            lines.append(
                f"**{label}:** "
                + compact(
                    {k: v for k, v in row.items() if "view_id" not in row or k not in METADATA}
                )
            )
        if not rows:
            lines.append("No supplied records; no reassuring coverage inferred.\n")
    lines.append("## Human threshold definitions\n")
    lines.append(
        "Definitions are preserved as approved input data. This descriptive runner does "
        "not interpret free-text aggregation rules or decide whether medical thresholds "
        "were met. Held-out approval remains a separate human decision.\n"
    )
    lines.extend(_record_lines(model["thresholds"]))
    lines.append("## Full candidate and synthesis accounting\n")
    for index, row in enumerate(model["candidate_accounting"]):
        lines.append(
            f"### Finding {index + 1}: {views[row['view_id']]} / "
            f"{attempts[row['attempt_id']]} / {_escaped(row['stage'])}\n"
        )
        candidate = row["candidate"]
        lines.extend(
            _record_lines(
                {
                    "item_id": row["item_id"],
                    "candidate_id": candidate["candidate_id"],
                    "original_finding_id": candidate["original_finding_id"],
                    "raw_reference": candidate["raw_reference"],
                    "raw_sha256": candidate["raw_sha256"],
                }
            )
        )
        original = candidate["original"]
        lines.extend(
            _record_lines(
                {
                    k: original[k]
                    for k in (
                        "finding_summary",
                        "claim_text",
                        "issue_type",
                        "severity",
                        "evidence_summary",
                        "suggested_fix",
                        "cannot_verify_reason",
                    )
                }
            )
        )
        lines.append(
            "Original numeric claims remain unqualified model proposals in the complete model.\n"
        )
        for label in ("human_judgment", "synthesis_judgment"):
            judgment = row[label]
            lines.append(f"#### {_escaped(label)}\n")
            lines.extend(
                _record_lines(
                    {
                        k: v
                        for k, v in judgment.items()
                        if k
                        not in {
                            "evidence",
                            "candidate_id",
                            "case_id",
                            "item_id",
                            "packet_id",
                            "attempt_id",
                            "stage",
                        }
                    }
                )
            )
            lines.extend(_source_links(model, row["case_id"], judgment["evidence"]))
    lines.append("## Explicit synthesis groups\n")
    lines.extend(_record_lines(model["synthesis_groups"]))
    lines.append("## Attempts and lineage\n")
    for attempt in model["attempts"]:
        lines.append(f"### Attempt {attempts[attempt['attempt_id']]}\n")
        lines.append(compact({k: v for k, v in attempt.items() if k not in {"outputs", "usage"}}))
        lines.extend(_record_lines({"output_ids": [o["output_id"] for o in attempt["outputs"]]}))
    lines.extend(_record_lines(model["lineage"]))
    lines.append("## Independent source assessors\n")
    lines.extend(_record_lines(model["reference_ledger"]["case_reviews"]))
    return "\n".join(lines) + "\n"


def _render_format(run: Path, manifest: Path, env: dict[str, str], format_: str) -> None:
    """Preserve partial renderer evidence before propagating failure to the run handler."""
    output = run / (REPORTS + "evaluation." + format_)
    try:
        result = subprocess.run(
            ["quarto", "render", str(run / (REPORTS + "evaluation.qmd")), "--to", format_],
            cwd=run / REPORTS,
            env=env,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        _write(
            run,
            manifest,
            REPORTS + f"quarto-{format_}.log",
            (error.stdout or b"") + b"\n" + (error.stderr or b""),
        )
        if output.exists():
            update_run(manifest, artifact=str(output))
        raise ValueError(f"Quarto {format_} timed out; partial evidence is preserved.") from error
    _write(run, manifest, REPORTS + f"quarto-{format_}.log", result.stdout + b"\n" + result.stderr)
    if output.exists():
        update_run(manifest, artifact=str(output))
    if result.returncode or not output.is_file() or not output.stat().st_size:
        raise ValueError(f"Quarto {format_} evaluation render failed; see private logs.")


def render_evaluation(repo_root: Path, analysis_run: Path, *, html=False, pdf=False) -> Path:
    repo = repo_root.resolve()
    parent = private_path(repo, analysis_run, PRIVATE_RUNS)
    loaded = load_native_analysis(repo, parent)
    model = build_evaluation_report(repo, loaded)
    sources = _code_sources(repo)
    code = {k: p.read_bytes() for k, p in sources.items()}
    parent_hash = sha256_file(parent / "run_manifest.json")
    run, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS,
        study_id=model["evaluation_id"],
        categories=["medical_evaluation"],
        config_path=parent / "run_manifest.json",
        input_paths=[parent / "run_manifest.json"],
        settings={
            "medical_evaluation_report_stage": "report",
            "parent_run_reference": str(parent.relative_to(repo)),
            "parent_manifest_sha256": parent_hash,
            "code_sha256": content_hash(
                {k: hashlib.sha256(v).hexdigest() for k, v in code.items()}
            ),
            "report_model_sha256": content_hash(model),
            "html": html,
            "pdf": pdf,
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        for name, raw in code.items():
            _write(run, manifest, "generated/medical_evaluation/code/" + name, raw)
        _write(run, manifest, MODEL_PATH, _json_bytes(model))
        _write(run, manifest, QUALIFICATION_PATH, _json_bytes(model["qualification"]))
        _write(run, manifest, REPORTS + "evaluation.md", model["rendered_markdown"].encode())
        if html or pdf:
            _write(run, manifest, REPORTS + "evaluation.qmd", code[TEMPLATE])
            env = {**os.environ, "MEDICAL_EVALUATION_REPORT_JSON": str(run / MODEL_PATH)}
            runtime = {}
            for executable in ("quarto", "Rscript"):
                result = subprocess.run(
                    [executable, "--version"], capture_output=True, timeout=30, check=True
                )
                runtime[executable] = (
                    (result.stdout + result.stderr).decode(errors="replace").strip()
                )
            _write(run, manifest, REPORTS + "runtime.json", _json_bytes(runtime))
            for format_, requested in (("html", html), ("pdf", pdf)):
                if not requested:
                    continue
                _render_format(run, manifest, env, format_)
        if (
            sha256_file(parent / "run_manifest.json") != parent_hash
            or any(sources[k].read_bytes() != v for k, v in code.items())
            or build_evaluation_report(repo, load_native_analysis(repo, parent)) != model
        ):
            raise ValueError("Evaluation report source/code/parent changed during rendering.")
        update_run(manifest, stage="evaluation-report", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run


def load_evaluation_report(repo_root: Path, run_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve()
    run = private_path(repo, run_path, PRIVATE_RUNS)
    manifest = validate_run_artifacts(repo, run)
    settings = manifest["effective_settings"]
    if (
        manifest["status"] != "completed"
        or settings.get("medical_evaluation_report_stage") != "report"
    ):
        raise ValueError("Evaluation report is not successfully completed.")
    parent = private_path(repo, Path(settings["parent_run_reference"]), PRIVATE_RUNS)
    if sha256_file(parent / "run_manifest.json") != settings["parent_manifest_sha256"]:
        raise ValueError("Evaluation report parent manifest changed.")
    loaded = load_native_analysis(repo, parent)
    code = {
        k: sha256_file(
            recorded_artifact(repo, run, manifest, "generated/medical_evaluation/code/" + k)
        )
        for k in _code_sources(repo)
    }
    if content_hash(code) != settings["code_sha256"]:
        raise ValueError("Evaluation report code archive changed.")
    model = read_json(recorded_artifact(repo, run, manifest, MODEL_PATH))
    if (
        model != build_evaluation_report(repo, loaded)
        or content_hash(model) != settings["report_model_sha256"]
    ):
        raise ValueError("Evaluation report semantic/parent binding changed.")
    if (
        read_json(recorded_artifact(repo, run, manifest, QUALIFICATION_PATH))
        != model["qualification"]
    ):
        raise ValueError("Evaluation qualification record changed.")
    if (
        recorded_artifact(repo, run, manifest, REPORTS + "evaluation.md").read_text()
        != model["rendered_markdown"]
    ):
        raise ValueError("Evaluation Markdown/model binding changed.")
    for format_ in ("html", "pdf"):
        if settings[format_]:
            recorded_artifact(repo, run, manifest, REPORTS + "evaluation." + format_)
    return {"run_root": run, "manifest": manifest, "analysis": loaded, "report": model}
