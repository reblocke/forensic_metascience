"""Shared synthetic actual-R producer for medical handoff and Quarto integration."""

from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from research_project.inspect_sr.records import source_version_id
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.records import PRIVATE_RUNS
from research_project.run_manifest import create_run, update_run
from support.inspect_sr_fixtures import write_numeric_method_fixture
from support.medical_review_fixtures import write_json


def prepare_native_review(workspace, rscript):
    """Run the existing pinned engine on synthetic typed inputs; no receipt fabrication."""
    repo, bundle_path, incoming, bundle, upstream = workspace
    source = repo / "data/private/medical_reviews/synthetic/sources/numeric.txt"
    source.write_text(
        "Unweighted Bernoulli observations, n=4: 0.25 (SD 0.50)\n"
        "Unweighted Bernoulli observations, n=4: 0.26 (SD 0.51)\n"
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    version = {
        "source_id": "synthetic-report",
        "source_name": "synthetic.pdf",
        "source_version_id": source_version_id("synthetic-report", digest),
        "content_sha256": digest,
    }
    inputs = repo / "data/private/medical_reviews/synthetic/verification/native-inputs"
    evidence = write_numeric_method_fixture(inputs, source_version=version)
    doc = copy.deepcopy(bundle["documents"][0])
    doc.update(
        source_id=version["source_id"],
        source_version_id=version["source_version_id"],
        role="analysis_output",
        path=str(source.relative_to(repo)),
        sha256=digest,
        upstream_paths=["inputs/numeric.txt"],
    )
    bundle["documents"].append(doc)
    for row in evidence:
        bundle["evidence"].append(
            {
                "evidence_id": row["evidence_id"],
                "source_version_id": row["source_version_id"],
                "locator": row["locator"],
                "raw_value": row["raw_value"],
                "parser": {"id": row["extraction_method"], "version": row["extraction_version"]},
                "parsed_path": str(source.relative_to(repo)),
                "parsed_sha256": digest,
                "page_index": None,
                "upstream_page": None,
                "page_label": None,
                "section": "Synthetic table",
                "visual_inspected": False,
            }
        )
    write_json(bundle_path, bundle)
    finding = upstream["findings"][0]
    finding.update(
        finding_summary="Reported binary mean may be incompatible.",
        claim_text="Mean 0.26 for four unweighted Bernoulli observations.",
        suggested_fix="Check the original cell and declared scale/count.",
        evidence_summary="Unweighted Bernoulli observations, n=4: 0.26 (SD 0.51)",
        numeric_check=None,
    )
    finding["location"].update(
        page=None, page_label=None, section="Synthetic table", text_quote="0.26 (SD 0.51)"
    )
    finding["source_objects"][0].update(
        path="inputs/numeric.txt",
        page=None,
        page_label=None,
        section="Synthetic table",
        text_quote="0.26 (SD 0.51)",
    )
    finding["claim_evidence_links"][0]["claim_text"] = finding["claim_text"]
    finding["claim_evidence_links"][0]["note"] = "Synthetic numerical source; verify inputs."
    write_json(incoming, upstream)
    numeric, manifest = create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS.parent,
        study_id="synthetic",
        categories=["numeric"],
        config_path=bundle_path,
        input_paths=[source, *inputs.glob("*")],
    )
    shutil.copytree(inputs, numeric / "processed/numeric/inputs")
    output = numeric / "reports/numeric"
    output.mkdir()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            rscript,
            str(root / "scripts/run_numeric_forensics.R"),
            "--in",
            str(numeric / "processed/numeric"),
            "--out",
            str(output),
            "--run-id",
            numeric.name,
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    receipts = pd.read_csv(output / "numeric_method_receipts.csv")
    assert set(receipts.loc[receipts["package_name"] == "scrutiny", "package_version"]) == {"0.6.2"}
    for path in (
        output / "numeric_method_receipts.csv",
        output / "numeric_standardized_results_v2.csv",
    ):
        update_run(manifest, artifact=str(path))
    update_run(manifest, stage="numeric_methods", status="completed")
    update_run(manifest, status="completed")
    imported = import_reviewer(repo, bundle_path, incoming)
    return imported, numeric, output, root
