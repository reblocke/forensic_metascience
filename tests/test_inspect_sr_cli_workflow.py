from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from research_project.inspect_sr.records import EXPECTED_CHECK_IDS

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_sr.py"
CATALOGUE = ROOT / "config" / "inspect_sr" / "v1.1.2" / "catalogue.json"


def test_cli_complete_review_and_private_report(monkeypatch, tmp_path: Path) -> None:
    if not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Quarto is required for the complete review workflow gate.")
        pytest.skip("Quarto unavailable; complete review report gate remains open.")
    spec = importlib.util.spec_from_file_location("inspect_sr_cli_complete", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    notebook_dir = tmp_path / "notebooks"
    notebook_dir.mkdir()
    shutil.copy2(ROOT / "notebooks" / "inspect_sr_assessment.qmd", notebook_dir)
    store = tmp_path / "data" / "private" / "inspect_sr"

    def run(*arguments: str) -> None:
        args = module.build_parser().parse_args([*arguments, "--store", str(store)])
        args.func(args)

    def write(name: str, value: object) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    run("prepare", "--catalogue", str(CATALOGUE), "--trial-key", "synthetic-review")
    assessment_path = next((store / "assessments").glob("*.json"))
    assessment = module.read_json(assessment_path)
    source = tmp_path / "synthetic-report.txt"
    source.write_text("Synthetic source value 0.50", encoding="utf-8")
    run(
        "prepare-evidence",
        "--source-file",
        str(source),
        "--source-id",
        "synthetic-report",
        "--check-id",
        "1.1",
        "--locator",
        "paragraph=1",
        "--raw-value",
        "0.50",
        "--extraction-method",
        "manual",
        "--extraction-version",
        "1",
    )
    run(
        "prepare-evidence",
        "--source-file",
        str(source),
        "--source-id",
        "synthetic-report",
        "--check-id",
        "1.1",
        "--locator",
        "paragraph=1",
        "--raw-value",
        "0.50",
        "--extraction-method",
        "manual",
        "--extraction-version",
        "1",
    )
    assert len(list((store / "evidence").glob("*.json"))) == 1
    version = module.read_json(next((store / "source-versions-v2").glob("*.json")))
    evidence = module.read_json(next((store / "evidence").glob("*.json")))
    versions_path = write("versions.json", [version])
    evidence_path = write("evidence.json", [evidence])
    run(
        "snapshot",
        "--assessment",
        str(assessment_path),
        "--source-versions",
        str(versions_path),
        "--evidence",
        str(evidence_path),
    )
    digest = module.read_json(next((store / "snapshots").glob("*.json")))["source_snapshot_sha256"]
    answers = [
        {
            "check_id": check_id,
            "response": "Unclear",
            "rationale": "Synthetic source reviewed.",
            "evidence_ids": [evidence["evidence_id"]],
        }
        for check_id in EXPECTED_CHECK_IDS
    ]
    for reviewer_id, first_response in (("reviewer-a", "No"), ("reviewer-b", "Yes")):
        own = [dict(row) for row in answers]
        own[0]["response"] = first_response
        run(
            "submit",
            "--assessment",
            str(assessment_path),
            "--reviewer-id",
            reviewer_id,
            "--source-snapshot-sha256",
            digest,
            "--checks",
            str(write(f"{reviewer_id}.json", own)),
        )
    submission_paths = (store / "reviewer-submissions").glob("*.json")
    by_reviewer = {module.read_json(path)["reviewer_id"]: path for path in submission_paths}
    decisions = write(
        "decisions.json",
        [
            {
                "check_id": "1.1",
                "response": "Unclear",
                "rationale": "Disagreement adjudicated.",
                "evidence_ids": [evidence["evidence_id"]],
            }
        ],
    )
    run(
        "adjudicate",
        "--first",
        str(by_reviewer["reviewer-a"]),
        "--second",
        str(by_reviewer["reviewer-b"]),
        "--adjudicator-id",
        "chair",
        "--decisions",
        str(decisions),
    )
    resolved_path = next((store / "resolved-reviews").glob("*.json"))
    judgments = write(
        "judgments.json",
        {
            "domains": [
                {"domain_id": str(i), "judgment": "some concerns", "rationale": "Reviewed."}
                for i in range(1, 5)
            ],
            "overall": {"judgment": "some concerns", "rationale": "Reviewed."},
        },
    )
    run("finalize", "--review", str(resolved_path), "--judgments", str(judgments))
    finalization_path = next((store / "finalizations").glob("*.json"))
    run(
        "validate",
        "--kind",
        "finalization",
        "--record",
        str(finalization_path),
        "--catalogue",
        str(CATALOGUE),
    )
    render_args = (
        "render",
        "--assessment",
        str(assessment_path),
        "--catalogue",
        str(CATALOGUE),
        "--source-versions",
        str(versions_path),
        "--evidence",
        str(evidence_path),
        "--candidates",
        str(write("candidates.json", {"coverage": [], "candidate_evidence": []})),
        "--receipts",
        str(write("receipts.json", [])),
        "--reviewer-submission",
        str(by_reviewer["reviewer-a"]),
        "--reviewer-submission",
        str(by_reviewer["reviewer-b"]),
        "--adjudication",
        str(next((store / "adjudications").glob("*.json"))),
        "--finalization",
        str(finalization_path),
        "--source-snapshot-sha256",
        digest,
        "--revision",
        "review-1",
        "--format",
        "both",
    )
    revision_index = render_args.index("--revision") + 1
    for invalid in (str(tmp_path / "escaped-report"), "../escaped-report"):
        invalid_args = list(render_args)
        invalid_args[revision_index] = invalid
        with pytest.raises(ValueError, match="simple identifiers"):
            run(*invalid_args)
    assert not (tmp_path / "escaped-report").exists()
    run(*render_args)
    report_dir = store / "reports" / assessment["assessment_id"] / "review-1"
    assert (report_dir / "assessment.html").is_file()
    assert (report_dir / "assessment.pdf").is_file()
    html = (report_dir / "assessment.html").read_text(encoding="utf-8")
    assert "FINALIZED" in html and "Disagreement adjudicated" in html
    assert "reviewer-a" in html and "reviewer-b" in html
    policy = write(
        "policy.json",
        {
            "schema_version": "inspect_sr_synthesis_policy_v1",
            "policy_id": "synthetic-policy",
            "policy_version": "1",
            "approved_by": "chair",
            "approved_at": "2026-09-25",
            "rationale": "Synthetic fixture only.",
            "source_guidance_sha256": assessment["guidance_sha256"],
            "primary": {
                "no concerns": "include",
                "some concerns": "include",
                "serious concerns": "exclude",
            },
            "sensitivity": {
                "no concerns": "include",
                "some concerns": "exclude",
                "serious concerns": "exclude",
            },
        },
    )
    reports = write(
        "reports.json",
        [
            {
                "report_id": "report-1",
                "trial_id": assessment["trial_id"],
                "private_canary": "PRIVATE_SOURCE_CANARY",
            }
        ],
    )
    comparisons = write(
        "comparisons.json",
        [
            {
                "comparison_id": "comparison-1",
                "trial_id": assessment["trial_id"],
            }
        ],
    )
    public_path = tmp_path / "public.json"
    run(
        "export",
        "--finalization",
        str(finalization_path),
        "--reports",
        str(reports),
        "--comparisons",
        str(comparisons),
        "--policy",
        str(policy),
        "--catalogue",
        str(CATALOGUE),
        "--guidance-sha256",
        assessment["guidance_sha256"],
        "--current-sources",
        str(write("current.json", {assessment["trial_id"]: digest})),
        "--unresolved",
        "block",
        "--policy-variant",
        "primary",
        "--public",
        "--trial-id",
        assessment["trial_id"],
        "--reviewed-by",
        "release-reviewer",
        "--output",
        str(public_path),
    )
    exported = public_path.read_text(encoding="utf-8")
    assert "PRIVATE_SOURCE_CANARY" not in exported
    assert "reviewer-a" not in exported and "release-reviewer" not in exported
    assert len(module.read_json(public_path)["trial_dispositions"]) == 1
    source.write_text("Changed synthetic source value", encoding="utf-8")
    with pytest.raises(ValueError, match="source bytes"):
        run(
            "validate",
            "--kind",
            "finalization",
            "--record",
            str(finalization_path),
            "--catalogue",
            str(CATALOGUE),
        )
    source.write_text("Synthetic source value 0.50", encoding="utf-8")
