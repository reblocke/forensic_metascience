from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from research_project.inspect_sr.records import (
    create_assessment,
    evidence_id,
    link_report_to_trial,
    load_catalogue,
    new_assessment_for_guidance,
    source_version_id,
    stable_report_id,
    stable_trial_id,
    validate_assessment,
    verify_guidance_snapshot,
    write_json_exclusive,
)


def test_pinned_catalogue_contains_exact_official_check_ids_and_domains() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    catalogue = load_catalogue(repo_root / "config/inspect_sr/v1.1.2/catalogue.json")
    assert [check["check_id"] for check in catalogue["checks"]] == [
        *(f"1.{number}" for number in range(1, 4)),
        *(f"2.{number}" for number in range(1, 6)),
        *(f"3.{number}" for number in range(1, 3)),
        *(f"4.{number}" for number in range(1, 12)),
    ]
    assert catalogue["guidance_version"] == "1.1.2"
    assert catalogue["checks"][0]["official_wording"].startswith(
        "Does the study have an associated retraction?"
    )
    assert verify_guidance_snapshot(repo_root / "config/inspect_sr/v1.1.2") == []


def test_trial_report_and_evidence_ids_are_stable_under_row_reordering() -> None:
    trial = stable_trial_id("lungtime-publication-set")
    report_a = stable_report_id("doi:10.1000/a")
    report_b = stable_report_id("doi:10.1000/b")
    assert trial == stable_trial_id("lungtime-publication-set")
    assert not trial.startswith("NCT")
    assert report_a != report_b
    version = source_version_id(report_a, "a" * 64)
    evidence_a = evidence_id(version, "page=3;table=1;row=2;cell=arm_a", "33.3%", "parser", "v1")
    evidence_b = evidence_id(version, "page=3;table=1;row=2;cell=arm_a", "33.3%", "parser", "v1")
    assert evidence_a == evidence_b
    assert evidence_a != evidence_id(
        version, "page=3;table=1;row=3;cell=arm_a", "33.3%", "parser", "v1"
    )
    assert source_version_id(report_a, "b" * 64) != version
    link = link_report_to_trial(trial, report_a, reviewed=False, multi_trial_report=False)
    assert link["trial_id"] == trial and link["report_id"] == report_a
    with pytest.raises(ValueError, match="reviewed mapping"):
        link_report_to_trial(trial, report_a, reviewed=False, multi_trial_report=True)


def test_assessment_starts_with_21_pending_null_checks_and_guidance_migration_is_new() -> None:
    assessment = create_assessment("local-trial-id", "1.1.2", "guidance-hash")
    same_trial = create_assessment("local-trial-id", "1.1.2", "guidance-hash")
    assert len(assessment["checks"]) == 21
    assert assessment["assessment_id"] == same_trial["assessment_id"]
    assert all(
        item["workflow_status"] == "pending" and item["response"] is None
        for item in assessment["checks"]
    )
    validate_assessment(assessment)
    migrated = new_assessment_for_guidance(
        assessment, "1.2.0", "new-guidance-hash", explicit_review=True
    )
    assert migrated["assessment_id"] != assessment["assessment_id"]
    assert migrated["supersedes_assessment_id"] == assessment["assessment_id"]
    assert all(item["response"] is None for item in migrated["checks"])
    assert all(item["workflow_status"] == "pending" for item in migrated["checks"])
    assert assessment["guidance_sha256"] == "guidance-hash"
    with pytest.raises(ValueError, match="explicit review"):
        new_assessment_for_guidance(assessment, "1.2.0", "new-guidance-hash")


def test_record_writer_refuses_to_overwrite_human_authored_file(tmp_path: Path) -> None:
    target = tmp_path / "human-review.json"
    write_json_exclusive(target, {"response": "Yes"})
    original = target.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_json_exclusive(target, {"response": "No"})
    assert json.loads(original)["response"] == "Yes"
    assert target.read_text(encoding="utf-8") == original


def test_guidance_hash_tampering_is_detected(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "config/inspect_sr/v1.1.2"
    target = tmp_path / "v1.1.2"
    shutil.copytree(source, target)
    (target / "chapters/check_1_1.qmd").write_text("changed\n", encoding="utf-8")
    errors = verify_guidance_snapshot(target)
    assert any("check_1_1.qmd" in error for error in errors)
    with pytest.raises(ValueError, match="Invalid pinned guidance snapshot"):
        load_catalogue(target / "catalogue.json")
