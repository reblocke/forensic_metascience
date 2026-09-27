from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from support.inspect_sr_fixtures import write_numeric_method_fixture

from research_project.inspect_sr.records import EXPECTED_CHECK_IDS

pytestmark = pytest.mark.report_integration

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_sr.py"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_cli_complete_review_and_private_report(
    tmp_path: Path, preserve_synthetic_artifact
) -> None:
    if not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Quarto is required for the complete review workflow gate.")
        pytest.skip("Quarto unavailable; complete review report gate remains open.")
    synthetic_root = tmp_path / "repository"
    for relative in (
        Path("src/research_project"),
        Path("scripts/inspect_sr.py"),
        Path("notebooks/inspect_sr_assessment.qmd"),
        Path("config/inspect_sr"),
    ):
        source_path = ROOT / relative
        destination = synthetic_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, destination)
        else:
            shutil.copy2(source_path, destination)
    cli_script = synthetic_root / "scripts/inspect_sr.py"
    catalogue_path = synthetic_root / "config/inspect_sr/v1.1.2/catalogue.json"
    store = synthetic_root / "data" / "private" / "inspect_sr"

    def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        command_arguments = [*arguments]
        if command_arguments[0] != "map-candidates":
            command_arguments.extend(("--store", str(store)))
        result = subprocess.run(
            [sys.executable, str(cli_script), *command_arguments],
            cwd=synthetic_root,
            capture_output=True,
            text=True,
        )
        if check:
            assert result.returncode == 0, result.stderr
        return result

    def write(name: str, value: object) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    run("prepare", "--catalogue", str(catalogue_path), "--trial-key", "synthetic-review")
    assessment_path = next((store / "assessments").glob("*.json"))
    assessment = read_json(assessment_path)
    source = tmp_path / "synthetic.pdf"
    source.write_text(
        "Table 1 row 1 mean 0.25 SD 0.50; row 2 mean 0.26 SD 0.51.\nSynthetic source value 0.50",
        encoding="utf-8",
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
    native_rows = (("table1:row1", "0.25 (SD 0.50)"), ("table1:row2", "0.26 (SD 0.51)"))
    for locator, raw_value in native_rows:
        run(
            "prepare-evidence",
            "--source-file",
            str(source),
            "--source-id",
            "synthetic-report",
            "--check-id",
            "4.8",
            "--locator",
            locator,
            "--raw-value",
            raw_value,
            "--extraction-method",
            "numeric_pdf_table_extraction",
            "--extraction-version",
            "numeric_eligibility_precision_v3",
        )
    evidence_records = [read_json(path) for path in sorted((store / "evidence").glob("*.json"))]
    assert len(evidence_records) == 3
    manual_evidence = next(item for item in evidence_records if item["locator"] == "paragraph=1")
    version = read_json(next((store / "source-versions-v2").glob("*.json")))
    native_workspace = tmp_path / "native-workspace"
    native_input_dir = native_workspace / "inputs"
    native_output_dir = native_workspace / "outputs"
    write_numeric_method_fixture(
        native_input_dir,
        trial_id=assessment["trial_id"],
        source_version=version,
    )
    fixture_cases = pd.read_csv(native_input_dir / "scrutiny_cases.csv")
    source_evidence_by_id = {
        item["evidence_id"]: item
        for item in evidence_records
        if item["extraction_method"] == "numeric_pdf_table_extraction"
    }
    assert set(fixture_cases["evidence_id"]) == set(source_evidence_by_id)
    assert set(fixture_cases["trial_id"]) == {assessment["trial_id"]}
    for case in fixture_cases.to_dict(orient="records"):
        linked = source_evidence_by_id[case["evidence_id"]]
        assert case["source_version_id"] == version["source_version_id"]
        assert case["source_locator"] == linked["locator"]
        assert case["raw_value"] == linked["raw_value"]
    versions_path = write("versions.json", [version])
    evidence_path = write("evidence.json", evidence_records)
    snapshot_result = run(
        "snapshot",
        "--assessment",
        str(assessment_path),
        "--source-versions",
        str(versions_path),
        "--evidence",
        str(evidence_path),
    )
    digest = snapshot_result.stdout.strip()
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.fail("The connected CLI report workflow requires native R results.")
    native_run = subprocess.run(
        [
            rscript,
            str(ROOT / "scripts" / "run_numeric_forensics.R"),
            "--in",
            str(native_workspace),
            "--out",
            str(native_output_dir),
            "--run-id",
            "inspect-sr-connected-workflow",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert native_run.returncode == 0, native_run.stderr
    native_evidence_path = write(
        "native-evidence.json",
        [
            item
            for item in evidence_records
            if item["extraction_method"] == "numeric_pdf_table_extraction"
        ],
    )
    candidate_path = store / "candidate-dossiers" / "connected-native.json"
    run(
        "map-candidates",
        "--receipts",
        str(native_output_dir / "numeric_method_receipts.csv"),
        "--results",
        str(native_output_dir / "numeric_standardized_results_v2.csv"),
        "--evidence",
        str(native_evidence_path),
        "--output",
        str(candidate_path),
    )
    candidates = read_json(candidate_path)
    assert candidates["candidate_evidence"]
    assert candidates["schema_version"] == "inspect_sr_candidate_dossier_v3"
    assert candidates["unresolved_results"]
    assert all(
        row["schema_version"] == "inspect_sr_candidate_evidence_v2"
        and row["result_id"]
        and row["native_output_reference"]
        for row in candidates["candidate_evidence"]
    )
    assert any(
        row["check_id"] == "4.8" and row["candidate_status"] == "candidate_only"
        for row in candidates["candidate_evidence"]
    )
    assert candidates["coverage"]
    assert all(
        item["method_id"] != "scrutiny_rounding_bias" for item in candidates["candidate_evidence"]
    )
    assert set(candidates["coverage"][0]) == {
        "check_id",
        "status",
        "reason",
        "method_ids",
        "candidate_count",
        "manual_route",
        "limitations",
    }
    native_receipts = pd.read_csv(native_output_dir / "numeric_method_receipts.csv").to_dict(
        orient="records"
    )
    assert any(
        row["method_id"] == "scrutiny_rounding_bias" and row["execution"] == "blocked"
        for row in native_receipts
    )
    numeric_evidence = source_evidence_by_id[fixture_cases.iloc[0]["evidence_id"]]
    answers = [
        {
            "check_id": check_id,
            "response": "Unclear",
            "rationale": "Synthetic source reviewed.",
            "evidence_ids": (
                [manual_evidence["evidence_id"]]
                if check_id == "1.1"
                else [numeric_evidence["evidence_id"]]
                if check_id == "4.8"
                else []
            ),
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
    by_reviewer = {read_json(path)["reviewer_id"]: path for path in submission_paths}
    decisions = write(
        "decisions.json",
        [
            {
                "check_id": "1.1",
                "response": "Unclear",
                "rationale": "Disagreement adjudicated.",
                "evidence_ids": [manual_evidence["evidence_id"]],
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
        str(catalogue_path),
    )
    render_args = (
        "render",
        "--assessment",
        str(assessment_path),
        "--catalogue",
        str(catalogue_path),
        "--source-versions",
        str(versions_path),
        "--evidence",
        str(evidence_path),
        "--candidates",
        str(candidate_path),
        "--receipts",
        str(native_output_dir / "numeric_method_receipts.csv"),
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
        invalid_result = run(*invalid_args, check=False)
        assert invalid_result.returncode != 0
        assert "simple identifiers" in invalid_result.stderr
    assert not (tmp_path / "escaped-report").exists()
    report_dir = store / "reports" / assessment["assessment_id"] / "review-1"
    report_dir.mkdir(parents=True)
    outside = tmp_path / "outside-artifact.txt"
    outside.write_text("PRIVATE_PATH_CANARY", encoding="utf-8")
    for filename in (
        "report-model.json",
        "inspect_sr_assessment.qmd",
        "assessment.html",
        "assessment.pdf",
    ):
        redirected = report_dir / filename
        redirected.symlink_to(outside)
        blocked_result = run(*render_args, check=False)
        assert blocked_result.returncode != 0
        assert "report output" in blocked_result.stderr
        assert outside.read_text(encoding="utf-8") == "PRIVATE_PATH_CANARY"
        assert not (report_dir / "report-model.json").exists() or filename == "report-model.json"
        redirected.unlink()
    run(*render_args)
    assert (report_dir / "assessment.html").is_file()
    assert (report_dir / "assessment.pdf").is_file()
    assert not list(report_dir.glob(".render-*"))
    html = (report_dir / "assessment.html").read_text(encoding="utf-8")
    assert "FINALIZED" in html and "Disagreement adjudicated" in html
    assert all(
        label in html
        for label in (
            "result_id=",
            "run_id=",
            "method_version=",
            "value_numeric=",
            "p_value=null",
            "anomaly_flag=",
            "source_scope=",
            "native_output_reference=",
        )
    )
    assert "reviewer-a" in html and "reviewer-b" in html
    assert "method_result" in html
    assert numeric_evidence["evidence_id"] in html
    assert numeric_evidence["raw_value"] in html
    unresolved = candidates["unresolved_results"][0]
    assert unresolved["result_id"] in html
    assert unresolved["reason"] in html
    report_model = read_json(report_dir / "report-model.json")
    assert report_model["schema_version"] == "inspect_sr_report_model_v3"
    assert report_model["unresolved_results"] == candidates["unresolved_results"]
    assert "table1:row1" in html
    assert "scrutiny_rounding_bias" in html and "blocked" in html
    preserve_synthetic_artifact("inspect-sr-review.html", report_dir / "assessment.html")
    preserve_synthetic_artifact("inspect-sr-review.pdf", report_dir / "assessment.pdf")
    outside_report_dir = tmp_path / "outside-report-directory"
    outside_report_dir.mkdir()
    directory_canary = outside_report_dir / "canary.txt"
    directory_canary.write_text("PRIVATE_DIRECTORY_CANARY", encoding="utf-8")
    redirected_revision = report_dir.parent / "redirected-revision"
    redirected_revision.symlink_to(outside_report_dir, target_is_directory=True)
    redirected_args = list(render_args)
    redirected_args[revision_index] = "redirected-revision"
    blocked_directory = run(*redirected_args, check=False)
    assert blocked_directory.returncode != 0
    assert directory_canary.read_text(encoding="utf-8") == "PRIVATE_DIRECTORY_CANARY"
    assert not (outside_report_dir / "report-model.json").exists()
    redirected_revision.unlink()
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
        str(catalogue_path),
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
    assert len(read_json(public_path)["trial_dispositions"]) == 1
    source.write_text("Changed synthetic source value", encoding="utf-8")
    changed_source_result = run(
        "validate",
        "--kind",
        "finalization",
        "--record",
        str(finalization_path),
        "--catalogue",
        str(catalogue_path),
        check=False,
    )
    assert changed_source_result.returncode != 0
    assert "source bytes" in changed_source_result.stderr
    source.write_text(
        "Table 1 row 1 mean 0.25 SD 0.50; row 2 mean 0.26 SD 0.51.\nSynthetic source value 0.50",
        encoding="utf-8",
    )

    run("prepare", "--catalogue", str(catalogue_path), "--trial-key", "synthetic-early-stop")
    early_assessment_path = next(
        path
        for path in (store / "assessments").glob("*.json")
        if read_json(path)["trial_id"] != assessment["trial_id"]
    )
    early_assessment = read_json(early_assessment_path)
    early_snapshot_result = run(
        "snapshot",
        "--assessment",
        str(early_assessment_path),
        "--source-versions",
        str(versions_path),
        "--evidence",
        str(evidence_path),
    )
    early_digest = early_snapshot_result.stdout.strip()
    early_checks = [
        {
            "check_id": check_id,
            "response": "Yes" if check_id == "1.1" else None,
            "rationale": "Synthetic serious concern." if check_id == "1.1" else "",
            "evidence_ids": [manual_evidence["evidence_id"]] if check_id == "1.1" else [],
        }
        for check_id in EXPECTED_CHECK_IDS
    ]
    for reviewer_id in ("early-reviewer-a", "early-reviewer-b"):
        run(
            "submit",
            "--assessment",
            str(early_assessment_path),
            "--reviewer-id",
            reviewer_id,
            "--source-snapshot-sha256",
            early_digest,
            "--checks",
            str(write(f"{reviewer_id}.json", early_checks)),
        )
    early_submissions = {
        read_json(path)["reviewer_id"]: path
        for path in (store / "reviewer-submissions").glob("*.json")
        if read_json(path)["assessment_id"] == early_assessment["assessment_id"]
    }
    early_decisions = write("early-decisions.json", [])
    run(
        "adjudicate",
        "--first",
        str(early_submissions["early-reviewer-a"]),
        "--second",
        str(early_submissions["early-reviewer-b"]),
        "--adjudicator-id",
        "early-chair",
        "--decisions",
        str(early_decisions),
    )
    early_review = next(
        path
        for path in (store / "resolved-reviews").glob("*.json")
        if read_json(path)["assessment_id"] == early_assessment["assessment_id"]
    )
    early_judgments = write(
        "early-judgments.json",
        {
            "domains": [
                {
                    "domain_id": str(index),
                    "judgment": "serious concerns" if index == 1 else "no concerns",
                    "rationale": "Synthetic adjudicator decision.",
                }
                for index in range(1, 5)
            ],
            "overall": {
                "judgment": "serious concerns",
                "rationale": "Synthetic early-stop decision.",
            },
        },
    )
    pending = run(
        "finalize",
        "--review",
        str(early_review),
        "--judgments",
        str(early_judgments),
        check=False,
    )
    assert pending.returncode != 0 and "pending checks" in pending.stderr
    run(
        "finalize",
        "--review",
        str(early_review),
        "--judgments",
        str(early_judgments),
        "--early-stop",
        "--early-stop-reason",
        "Synthetic justified early stop.",
    )
    early_finalization = next(
        read_json(path)
        for path in (store / "finalizations").glob("*.json")
        if read_json(path)["assessment_id"] == early_assessment["assessment_id"]
    )
    assert early_finalization["workflow_status"] == "finalized_early_stop"
    assert (
        sum(
            check["workflow_status"] == "not_assessed_early_stop"
            for check in early_finalization["checks"]
        )
        == len(EXPECTED_CHECK_IDS) - 1
    )
