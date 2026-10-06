"""Deterministic, private reports from explicit evidence and immutable review lineage."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from research_project.medical_review.audit import (
    load_dossier,
    load_human_history,
    validate_human_record,
)
from research_project.medical_review.numeric_inputs import load_input_reviews, validate_input_review
from research_project.medical_review.records import (
    MAX_JSON_BYTES,
    PRIVATE_RUNS,
    REPORT_SCHEMA,
    content_hash,
    identity,
    private_path,
    write_json,
)
from research_project.run_manifest import create_run, update_run

TITLE = "AI-assisted manuscript audit: unverified proposals"


def _groups(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group exact observations conservatively; quotes alone never identify an issue."""
    groups: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        links = proposal["evidence_links"]
        key = {
            field: proposal[field]
            for field in (
                "study_id",
                "report_ids",
                "comparison_id",
                "normalized_concern",
                "claim",
                "classification",
                "repair",
            )
        }
        key["evidence_ids"] = sorted(
            {link.get("evidence_id") for link in links if link.get("evidence_id")}
        )
        # A missing anchor is not permission to collapse two potentially distinct observations.
        if not links or any(link.get("resolution") != "exact" for link in links):
            key["unresolved_proposal_id"] = proposal["proposal_id"]
        group_id = identity("medicalgroup", key)
        group = groups.setdefault(group_id, {"group_id": group_id, "proposal_ids": []})
        group["proposal_ids"].append(proposal["proposal_id"])
    return list(groups.values())


def _statuses(proposals, verification, history):
    superseded = {r["supersedes"] for r in history if r["supersedes"] is not None}
    result = []
    for proposal in proposals:
        digest = content_hash(proposal)
        passes = [
            r
            for r in verification
            if r["proposal_id"] == proposal["proposal_id"]
            and r["original_proposal_sha256"] == digest
        ]
        humans = [
            r
            for r in history
            if r["proposal_id"] == proposal["proposal_id"]
            and r["original_proposal_sha256"] == digest
            and r["disposition_id"] not in superseded
        ]
        dispositions = {r["disposition"] for r in humans}
        human_status = (
            next(iter(dispositions))
            if len(dispositions) == 1
            else "conflicting_human_decisions"
            if dispositions
            else "pending"
        )
        model_status = passes[-1]["disposition"] if passes else "unverified"
        presentation = "unverified_proposal"
        if model_status in {"contradicted", "already_addressed"}:
            presentation = "demoted_unverified_proposal"
        elif (
            proposal["classification"] == "optional_improvement"
            or model_status == "optional_extension"
        ):
            presentation = "optional_improvement"
        result.append(
            {
                "proposal_id": proposal["proposal_id"],
                "model_disposition": model_status,
                "presentation": presentation,
                "human_status": human_status,
                "active_human_disposition_ids": [r["disposition_id"] for r in humans],
            }
        )
    return result


def _escaped(value: Any) -> str:
    """Display data without allowing HTML, Markdown, R inline code or Quarto directives."""
    text = (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    )
    # Break unusually long identifiers for PDF wrapping; exact values remain in the model.
    text = re.sub(
        r"\S{65,}", lambda m: " ".join(m[0][i : i + 32] for i in range(0, len(m[0]), 32)), text
    )
    active = set("&<>`{}$\\[]*_!#|~")
    return "".join(f"&#{ord(c)};" if c in active else c for c in text)


def _record_lines(value: Any, prefix: str = "") -> list[str]:
    """Lossless display of all leaf values; original structures remain in the JSON model."""
    if isinstance(value, dict):
        return [
            line
            for key, child in sorted(value.items())
            for line in _record_lines(child, f"{prefix}.{key}" if prefix else key)
        ] or [f"**{_escaped(prefix)}:** empty object\n"]
    if isinstance(value, list):
        return [
            line
            for index, child in enumerate(value)
            for line in _record_lines(child, f"{prefix}[{index}]")
        ] or [f"**{_escaped(prefix)}:** empty list\n"]
    label = prefix.replace("_", " ").replace(".", " / ")
    return [f"**{_escaped(label)}:** {_escaped(value)}\n"]


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *[
            "| " + " | ".join(_escaped(cell).replace("\n", " ") for cell in row) + " |"
            for row in rows
        ],
        "",
    ]


def _markdown(model: dict[str, Any]) -> str:
    lines = [
        f"# {TITLE}\n",
        "Model confidence is uncalibrated. Agent agreement is not independent evidence. "
        "Human records below are operator attestations; they do not finalize INSPECT-SR.\n",
        "Long identifiers are wrapped with spaces for display; "
        "exact values remain in the JSON model.\n",
        "## Scope and source availability\n",
        f"**Study:** {_escaped(model['bundle']['study_id'])}\n",
        *_table(
            ["Source", "Role", "Availability", "Date / precision"],
            [
                [
                    d["source_id"],
                    d["role"],
                    d["availability"],
                    f"{d.get('date')} / {d.get('date_precision', 'unknown')}",
                ]
                for d in model["bundle"]["documents"]
            ],
        ),
        "Exact source/evidence identities, mapping, permissions and parsed hashes are retained "
        "in the current-run report model. Unsupported extraction is not a manuscript defect.\n",
        "## Study reconstruction and unresolved gaps\n",
    ]
    for scope in [*model["study_context"]["studies"], *model["study_context"]["comparisons"]]:
        unknown = []
        for field, value in sorted(scope["fields"].items()):
            if (
                value["reported"]["status"] == "unknown"
                and value["reported"].get("reason") == "Not reconstructed."
                and not value["interpretations"]
                and value["preferred_design"] is None
            ):
                unknown.append(field)
            else:
                lines.extend(_record_lines(value, field))
        lines.append(
            f"**Unknown or not reconstructed:** {_escaped(', '.join(unknown) or 'none')}\n"
        )
    lines.extend(["## Upstream qualifications\n", *_record_lines(model["upstream_metadata"])])
    status_by_id = {r["proposal_id"]: r for r in model["proposal_statuses"]}
    for heading, optional in [
        ("Material proposed concerns", False),
        ("Optional improvements", True),
    ]:
        lines.append(f"## {heading}\n")
        for group in model["groups"]:
            members = [p for p in model["proposals"] if p["proposal_id"] in group["proposal_ids"]]
            statuses = [status_by_id[p["proposal_id"]] for p in members]
            if all(s["presentation"] == "optional_improvement" for s in statuses) != optional:
                continue
            lines.extend([f"### {_escaped(members[0]['normalized_concern'])}\n"])
            for proposal, status in zip(members, statuses, strict=True):
                lines.extend(
                    [
                        *_record_lines(status),
                        *_record_lines(
                            {
                                k: proposal[k]
                                for k in (
                                    "claim",
                                    "classification",
                                    "proposed_severity",
                                    "severity_rationale",
                                    "bias_direction",
                                    "repair",
                                    "evidence_links",
                                )
                            }
                        ),
                    ]
                )
                alternatives = [
                    r for r in model["verification"] if r["proposal_id"] == proposal["proposal_id"]
                ]
                lines.extend(_record_lines({"counterevidence_history": alternatives}))
    lines.extend(
        [
            "## Numerical checks\n",
            "Executed arithmetic retains proposed input transcriptions. A human concern decision "
            "does not verify numerical extraction or qualify a method receipt.\n",
            *_record_lines(model["arithmetic_results"], "Arithmetic"),
            *_record_lines(model["arithmetic_revalidation"], "Code revalidation"),
            *_record_lines(model["numeric_input_reviews"], "Numeric source review"),
            "## Coverage, unsupported checks and failures\n",
            "Review coverage remains unavailable. A completed import or render and an empty "
            "findings list cannot establish completed, reassuring review coverage.\n",
            *_table(
                ["Check / scope", "Applicable", "Execution / assessment", "Inspected", "Gaps"],
                [
                    [
                        f"{c['check_id']} / {c.get('comparison_id') or c['study_id']}",
                        c["applicability"],
                        f"{c['execution']} / {c['assessment']}",
                        c["inspected_units"],
                        c.get("missing_materials", []) + c.get("required_source_gaps", []),
                    ]
                    for c in model["coverage"]
                ],
            ),
            *_record_lines(
                {
                    key: model["review_plan"][key]
                    for key in (
                        "requested_profiles",
                        "selected_profiles",
                        "unsupported_profiles",
                        "routing_status",
                        "guidance_status",
                        "limitations",
                    )
                }
            ),
            *_record_lines(
                [
                    {
                        key: value
                        for key, value in source.items()
                        if key
                        not in (
                            "pages",
                            "parsed_sha256",
                            "source_version_id",
                        )
                    }
                    for source in (model["parser_preflight"] or {}).get("sources", [])
                ]
            ),
            *_record_lines(model["failures"]),
            "## Full finding and provenance appendix\n",
            *_record_lines(model["proposals"]),
            *_record_lines(model["groups"]),
            *_record_lines(model["source_run"]),
            *_record_lines(model["lineage"]),
            "## Human decision history\n",
            *_record_lines(model["human_history"]),
            "## Manual INSPECT-SR adoption packet\n",
            "No official assessment or synthesis disposition is created. Manual adoption requires "
            "independent review in the existing two-reviewer/adjudication workflow.\n",
            *_record_lines(model["manual_adoption_packet"]["required_manual_checks"]),
            "The write-once manual adoption packet is stored beside the report model. "
            "It retains every proposal, evidence and human-disposition reference.\n",
        ]
    )
    return "\n".join(lines) + "\n"


def build_report_model(repo_root: Path, dossier: dict[str, Any]) -> dict[str, Any]:
    """Consolidate validated records without changing their scientific or human authority."""
    repo = repo_root.resolve()
    history = load_human_history(repo, dossier)
    proposals = copy.deepcopy(dossier["proposals"])
    source = {
        "reference": str(dossier["run_root"].relative_to(repo)),
        "manifest_sha256": content_hash(dossier["manifest"]),
        "status": dossier["manifest"]["status"],
    }
    calculator_hash = hashlib.sha256(
        (Path(__file__).parent / "numeric.py").read_bytes()
    ).hexdigest()
    model = {
        "schema_version": REPORT_SCHEMA,
        "title": TITLE,
        "renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_run": source,
        **{
            key: copy.deepcopy(dossier[key])
            for key in (
                "bundle",
                "study_context",
                "review_plan",
                "coverage",
                "parser_preflight",
                "verification",
                "arithmetic_results",
                "lineage",
            )
        },
        "upstream_metadata": copy.deepcopy(dossier.get("upstream_metadata", {})),
        "failures": copy.deepcopy(dossier.get("failures", [])),
        "human_history": history,
        "numeric_input_reviews": load_input_reviews(repo, dossier),
        "proposals": proposals,
        "groups": _groups(proposals),
        "proposal_statuses": _statuses(proposals, dossier["verification"], history),
        "accounted_proposal_ids": [p["proposal_id"] for p in proposals],
        "agent_agreement_is_independent_evidence": False,
        "official_assessment": None,
        "synthesis_disposition": None,
        "review_complete": False,
        "review_coverage_available": False,
        "arithmetic_revalidation": [
            {
                "result_id": r["result_id"],
                "status": "recomputed_with_bound_code"
                if r["calculator"]["source_sha256"] == calculator_hash
                else "historical_code_archive_checked_not_reexecuted",
            }
            for r in dossier["arithmetic_results"]
        ],
        "manual_adoption_packet": {
            "schema_version": "medical_manual_adoption_packet_v1",
            "official_assessment": None,
            "automatic_adoption": False,
            "source_run": source,
            "bundle_sha256": content_hash(dossier["bundle"]),
            "proposal_ids": [p["proposal_id"] for p in proposals],
            "evidence": copy.deepcopy(dossier["bundle"]["evidence"]),
            "human_disposition_ids": [r["disposition_id"] for r in history],
            "required_manual_checks": [
                "Check original source bytes and version hashes.",
                "Check locators and the proposed observation wording.",
                "Write an independently attributed human rationale retaining agent-origin links.",
                "Use existing INSPECT-SR reviews, adjudication and finalization requirements.",
            ],
        },
    }
    model["rendered_markdown"] = _markdown(model)
    model["rendered_markdown_sha256"] = hashlib.sha256(
        model["rendered_markdown"].encode()
    ).hexdigest()
    validate_report_model(model, dossier)
    return model


def validate_report_model(model: dict[str, Any], dossier: dict[str, Any]) -> None:
    """Check complete group traceability and unchanged parent evidence/authority."""
    if (
        model.get("schema_version") != REPORT_SCHEMA
        or model.get("title") != TITLE
        or any(model.get(k) is not None for k in ("official_assessment", "synthesis_disposition"))
        or any(
            model.get(k) is not False
            for k in (
                "review_complete",
                "review_coverage_available",
                "agent_agreement_is_independent_evidence",
            )
        )
    ):
        raise ValueError("Medical report schema/authority mismatch.")
    for key in (
        "bundle",
        "proposals",
        "study_context",
        "review_plan",
        "coverage",
        "verification",
        "arithmetic_results",
        "parser_preflight",
        "lineage",
    ):
        if model[key] != dossier[key]:
            raise ValueError("Report source traceability changed.")
    if model["upstream_metadata"] != dossier.get("upstream_metadata", {}) or (
        model["failures"] != dossier.get("failures", [])
        or model["source_run"]
        != {
            "reference": str(dossier["run_root"].relative_to(dossier["repo_root"])),
            "manifest_sha256": content_hash(dossier["manifest"]),
            "status": dossier["manifest"]["status"],
        }
    ):
        raise ValueError("Report qualifications/source traceability changed.")
    ids = [p["proposal_id"] for p in dossier["proposals"]]
    grouped = [p for g in model["groups"] for p in g["proposal_ids"]]
    if len(ids) != len(set(ids)) or sorted(grouped) != sorted(ids):
        raise ValueError("Every input proposal must appear in exactly one report group.")
    if model["groups"] != _groups(dossier["proposals"]) or model["accounted_proposal_ids"] != ids:
        raise ValueError("Report grouping does not preserve exact source membership.")
    for human in model["human_history"]:
        validate_human_record(dossier["repo_root"], human)
    for review in model["numeric_input_reviews"]:
        validate_input_review(dossier["repo_root"], review)
        matching = [
            r for r in dossier["arithmetic_results"] if r["result_id"] == review["result_id"]
        ]
        if len(matching) != 1 or content_hash(matching[0]) != review["result_sha256"]:
            raise ValueError("Report numeric input review lacks its exact current result.")
    packet = model["manual_adoption_packet"]
    if (
        packet.get("schema_version") != "medical_manual_adoption_packet_v1"
        or packet.get("automatic_adoption") is not False
        or packet.get("official_assessment") is not None
        or packet.get("source_run") != model["source_run"]
        or packet.get("bundle_sha256") != content_hash(dossier["bundle"])
        or packet.get("proposal_ids") != ids
        or packet.get("evidence") != dossier["bundle"]["evidence"]
        or packet.get("human_disposition_ids")
        != [r["disposition_id"] for r in model["human_history"]]
        or not packet.get("required_manual_checks")
    ):
        raise ValueError("Manual adoption packet authority/traceability changed.")
    if (
        model["proposal_statuses"]
        != _statuses(dossier["proposals"], dossier["verification"], model["human_history"])
        or model["rendered_markdown_sha256"]
        != hashlib.sha256(model["rendered_markdown"].encode()).hexdigest()
    ):
        raise ValueError("Report presentation differs from its validated records.")
    if model["renderer_source_sha256"] == hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest() and (model["rendered_markdown"] != _markdown(model)):
        raise ValueError("Report presentation differs from its bound renderer.")


def render_review(
    repo_root: Path,
    source_run: Path,
    *,
    output_root: Path | None = None,
    html: bool = False,
    pdf: bool = False,
) -> Path:
    """Create a fresh private report run; optional R/Quarto rendering fails explicitly."""
    repo = repo_root.resolve()
    root = private_path(repo, output_root or PRIVATE_RUNS, PRIVATE_RUNS)
    dossier = load_dossier(repo, source_run)
    model = build_report_model(repo, dossier)
    if (
        len((json.dumps(model, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
        > MAX_JSON_BYTES
    ):
        raise ValueError("Report exceeds 20 MiB; explicit bounded splitting is required.")
    template = repo / "notebooks/medical_manuscript_review.qmd"
    template_bytes = template.read_bytes() if html or pdf else None
    binding = {
        "source_run_reference": str(dossier["run_root"].relative_to(repo)),
        "source_manifest_sha256": content_hash(dossier["manifest"]),
        "report_model_sha256": content_hash(model),
        "report_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "template_sha256": hashlib.sha256(template_bytes).hexdigest() if template_bytes else None,
        "html": html,
        "pdf": pdf,
    }
    run, manifest = create_run(
        repo_root=repo,
        output_root=root,
        study_id=dossier["bundle"]["study_id"],
        categories=["medical_review"],
        config_path=dossier["run_root"] / "processed/medical_review/bundle.json",
        input_paths=[],
        settings={
            **binding,
            "medical_report_key": content_hash(binding),
            "offline": True,
            "allow_llm": False,
            "allow_web_search": False,
        },
    )
    try:
        renderer = run / "generated/medical_review/code/reporting.py"
        renderer.parent.mkdir(parents=True)
        renderer.write_bytes(Path(__file__).read_bytes())
        if hashlib.sha256(renderer.read_bytes()).hexdigest() != binding["report_code_sha256"]:
            raise ValueError("Report renderer changed during execution.")
        update_run(manifest, artifact=str(renderer))
        for name, value in (
            ("bundle", dossier["bundle"]),
            ("report_model", model),
            ("manual_adoption_packet", model["manual_adoption_packet"]),
        ):
            path = run / f"processed/medical_review/{name}.json"
            write_json(path, value)
            update_run(manifest, artifact=str(path))
        reports = run / "reports/medical_review"
        reports.mkdir(parents=True)
        markdown = reports / "review.md"
        markdown.write_text(model["rendered_markdown"], encoding="utf-8")
        update_run(manifest, artifact=str(markdown))
        if html or pdf:
            qmd = reports / "review.qmd"
            qmd.write_bytes(template_bytes)
            update_run(manifest, artifact=str(qmd))
            env = {
                **os.environ,
                "MEDICAL_REVIEW_REPORT_JSON": str(
                    run / "processed/medical_review/report_model.json"
                ),
            }
            runtime = {}
            for executable, arguments in (
                ("quarto", ["--version"]),
                ("Rscript", ["--version"]),
            ):
                version = subprocess.run(
                    [executable, *arguments], capture_output=True, timeout=30, check=True
                )
                runtime[executable] = (
                    (version.stdout + version.stderr).decode("utf-8", errors="replace").strip()
                )
            runtime_path = reports / "runtime.json"
            write_json(runtime_path, runtime)
            update_run(manifest, artifact=str(runtime_path))
            for format_, requested in (("html", html), ("pdf", pdf)):
                if not requested:
                    continue
                result = subprocess.run(
                    ["quarto", "render", str(qmd), "--to", format_],
                    cwd=reports,
                    env=env,
                    capture_output=True,
                    timeout=180,
                    check=False,
                )
                log = reports / f"quarto-{format_}.log"
                log.write_bytes(result.stdout + b"\n" + result.stderr)
                update_run(manifest, artifact=str(log))
                if result.returncode:
                    raise ValueError(f"Quarto {format_} render failed; see the private run log.")
                update_run(manifest, artifact=str(reports / f"review.{format_}"))
        if (
            content_hash(load_dossier(repo, source_run)["manifest"])
            != binding["source_manifest_sha256"]
        ):
            raise ValueError("Report source changed during rendering.")
        update_run(manifest, stage="medical-report", status="completed")
        update_run(manifest, status="completed")
    except Exception as error:
        update_run(manifest, status="failed", error=str(error))
        raise
    return run
