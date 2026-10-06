from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from research_project.inspect_sr.records import evidence_id, source_version_id, stable_report_id


def write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def create_workspace(tmp_path: Path, repo_root: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    shutil.copy(repo_root / ".gitignore", repo / ".gitignore")
    shutil.copytree(repo_root / "config/medical_review", repo / "config/medical_review")
    shutil.copytree(repo_root / "prompts/medical_review", repo / "prompts/medical_review")
    private = repo / "data/private/medical_reviews/synthetic"
    private.mkdir(parents=True)
    source = private / "sources/main.txt"
    source.parent.mkdir()
    source.write_text("Random assignment used medical record number parity.\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    version = source_version_id("main", digest)
    report = stable_report_id("", local_key="synthetic-report")
    quote = "Random assignment used medical record number parity."
    parser = {"id": "synthetic_text", "version": "1"}
    ev = {
        "evidence_id": evidence_id(version, "page=1;paragraph=1", quote, parser["id"], "1"),
        "source_version_id": version,
        "locator": "page=1;paragraph=1",
        "raw_value": quote,
        "parser": parser,
        "parsed_path": str(source.relative_to(repo)),
        "parsed_sha256": digest,
        "page_index": 0,
        "upstream_page": 1,
        "page_label": "1",
        "section": "Methods",
        "visual_inspected": False,
    }
    bundle = {
        "schema_version": "medical_review_bundle_v1",
        "study_id": "synthetic",
        "revision": 1,
        "studies": [{"study_id": "synthetic", "trial_id": None}],
        "reports": [{"report_id": report, "study_ids": ["synthetic"], "mapping_reviewed": True}],
        "upstream_paper_id": "paper-1",
        "documents": [
            {
                "source_id": "main",
                "source_version_id": version,
                "role": "manuscript",
                "availability": "supplied",
                "path": str(source.relative_to(repo)),
                "sha256": digest,
                "report_ids": [report],
                "upstream_paths": ["inputs/main.txt"],
                "parser": parser,
                "date": None,
                "date_precision": "unknown",
                "permissions": {"classification": "private", "local_processing": True},
            }
        ],
        "evidence": [ev],
        "planned_checks": [
            {
                "check_id": "trial.assignment",
                "study_id": "synthetic",
                "comparison_id": None,
                "applicability": "applicable",
                "rationale": "Operator-selected trial assignment check.",
            }
        ],
    }
    bundle_path = write_json(private / "bundle.json", bundle)
    obj = {
        "id": "source-1",
        "type": "text",
        "label": "Methods",
        "path": "inputs/main.txt",
        "page": 1,
        "page_label": "1",
        "section": "Methods",
        "text_quote": quote,
        "url": None,
    }
    finding = {
        "id": "finding-1",
        "category": "methods",
        "finding_summary": "Assignment unclear.",
        "issue_type": "manuscript_issue",
        "severity": "high",
        "confidence": "medium",
        "location": {
            "page": 1,
            "page_label": "1",
            "section": "Methods",
            "text_quote": quote,
            "precision": "exact",
        },
        "claim_text": "Participants were randomized.",
        "assessment": "partially",
        "cannot_verify_reason": None,
        "evidence_summary": quote,
        "source_objects": [obj],
        "claim_evidence_links": [
            {
                "claim_text": "Participants were randomized.",
                "source_object_ids": ["source-1"],
                "relation": "contradicts",
                "note": "Check allocation mechanism.",
            }
        ],
        "numeric_check": {
            "reported_value": 10,
            "expected_value": None,
            "method": "proposal",
            "inputs": ["unverified count"],
            "recomputation_notes": "Not executed.",
        },
        "suggested_fix": "Clarify allocation mechanism.",
    }
    upstream = {
        "reviewer": "methods",
        "paper_id": "paper-1",
        "run_status": "ok",
        "summary": "Synthetic unverified review.",
        "findings": [finding],
        "notes": [],
    }
    incoming = write_json(private / "upstream.json", upstream)
    return repo, bundle_path, incoming, bundle, upstream
