from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json
from test_evaluation_plan import plan_input

from research_project.medical_review.evaluation import freeze_evaluation_plan, load_evaluation_plan
from research_project.medical_review.evaluation_reference import (
    freeze_reference_ledger,
    load_reference_ledger,
    validate_reference_input,
)


def reference_input(plan):
    case = plan["cases"][0]
    evidence = case["bundle"]["evidence"][0]
    versions = sorted(
        d["source_version_id"]
        for d in case["bundle"]["documents"]
        if d["availability"] == "supplied"
    )
    issue = {
        "issue_id": "assignment-observation",
        "study_id": case["bundle"]["study_id"],
        "comparison_id": None,
        "issue_type": "assignment",
        "important": True,
        "description": "Synthetic source states MRN-parity assignment.",
        "evidence_ids": [evidence["evidence_id"]],
    }
    assessors = [
        {
            "assessor_id": f"assessor-{i}",
            "human_identity": f"private-synthetic-human-{i}",
            "domain_qualifications": (
                "Synthetic clinical-methods assessor fixture, not a real credential."
            ),
            "date": "2026-10-06T12:00:00-06:00",
            "blinded_to_condition": True,
            "source_bytes_reviewed": True,
            "reviewed_source_version_ids": versions,
            "issues": [copy.deepcopy(issue)] if i == 1 else [],
        }
        for i in (1, 2)
    ]
    return {
        "schema_version": "medical_evaluation_reference_input_v1",
        "plan_id": plan["plan_id"],
        "case_reviews": [
            {
                "case_id": case["case_id"],
                "assessors": assessors,
                "assessor_shortfall_reason": None,
                "adjudication": {
                    "human_identity": "private-synthetic-adjudicator",
                    "domain_qualifications": "Synthetic fixture only.",
                    "date": "2026-10-06T12:05:00-06:00",
                    "blinded_to_condition": True,
                    "source_bytes_reviewed": True,
                    "reviewed_source_version_ids": versions,
                    "rationale": "Preserve the synthetic assessor disagreement and cited scope.",
                    "issues": [
                        {
                            "reference_id": "reference-assignment",
                            "disposition": "reference_issue",
                            "study_id": issue["study_id"],
                            "comparison_id": None,
                            "issue_type": "assignment",
                            "important": True,
                            "description": issue["description"],
                            "evidence_ids": issue["evidence_ids"],
                            "assessor_issue_refs": [
                                {"assessor_id": "assessor-1", "issue_id": issue["issue_id"]}
                            ],
                            "rationale": (
                                "Synthetic source supports the reference concern, "
                                "no misconduct conclusion."
                            ),
                        }
                    ],
                },
            }
        ],
    }


def frozen(workspace):
    repo, *_ = workspace
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/plan.json",
        plan_input(workspace),
    )
    run = freeze_evaluation_plan(repo, path)
    return run, load_evaluation_plan(repo, run)


def test_reference_preserves_independent_observations_disagreement_and_source_scope(workspace):
    repo, *_ = workspace
    _, plan = frozen(workspace)
    data = reference_input(plan)
    ledger = validate_reference_input(plan, data)
    assert ledger["original"] == data
    assert ledger["case_reviews"][0]["assessors"][1]["issues"] == []
    issue = ledger["reference_issues"][0]
    assert issue["case_id"] == plan["cases"][0]["case_id"]
    assert issue["analysis_unit_id"] == plan["cases"][0]["analysis_unit_id"]
    assert (
        issue["source_evidence"][0]["locator"]
        == plan["cases"][0]["bundle"]["evidence"][0]["locator"]
    )
    assert ledger["record_type"] == "operator_attested_source_reference"
    assert ledger["contains_synthetic_cases"] is True
    assert ledger["medical_performance_validated"] is False
    assert ledger["official_assessment"] is None


@pytest.mark.parametrize(
    "change",
    [
        "authority",
        "identity",
        "domain",
        "blind",
        "source",
        "evidence",
        "scope",
        "accounting",
        "coverage",
    ],
)
def test_reference_rejects_missing_authority_boundaries_or_incomplete_accounting(workspace, change):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    review = data["case_reviews"][0]
    if change == "authority":
        review["adjudication"]["official_assessment"] = "Yes"
    elif change == "identity":
        review["assessors"][1]["human_identity"] = review["assessors"][0]["human_identity"]
    elif change == "domain":
        review["assessors"][0]["domain_qualifications"] = ""
    elif change == "blind":
        review["adjudication"]["blinded_to_condition"] = False
    elif change == "source":
        review["assessors"][0]["source_bytes_reviewed"] = False
    elif change == "evidence":
        review["adjudication"]["issues"][0]["evidence_ids"] = ["invented"]
    elif change == "scope":
        review["adjudication"]["issues"][0]["study_id"] = "another-study"
    elif change == "accounting":
        review["adjudication"]["issues"] = []
    else:
        review["assessors"][0]["reviewed_source_version_ids"] = []
    with pytest.raises(ValueError):
        validate_reference_input(plan, data)


def test_clean_reference_scope_is_explicit_and_never_universal_reassurance(workspace):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    data["case_reviews"][0]["assessors"][0]["issues"] = []
    data["case_reviews"][0]["adjudication"]["issues"] = []
    ledger = validate_reference_input(plan, data)
    assert ledger["reference_issues"] == []
    assert ledger["case_reference_scope"][0]["status"] == "no_reference_issue_in_reviewed_sources"
    assert ledger["case_reference_scope"][0]["required_source_gaps"]
    assert ledger["case_reference_scope"][0]["universal_clean_claim"] is False


def test_single_assessor_needs_explicit_shortfall_and_preserves_that_limit(workspace):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    data["case_reviews"][0]["assessors"].pop()
    with pytest.raises(ValueError, match="shortfall"):
        validate_reference_input(plan, data)
    data["case_reviews"][0]["assessor_shortfall_reason"] = (
        "Synthetic second-assessor-unavailable control."
    )
    ledger = validate_reference_input(plan, data)
    assert ledger["case_reference_scope"][0]["independent_assessor_count"] == 1
    assert ledger["case_reference_scope"][0]["assessor_shortfall_reason"]


def test_freezing_reference_is_append_only_bound_to_plan_and_retains_original(workspace):
    repo, *_ = workspace
    parent, plan = frozen(workspace)
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/reference.json",
        reference_input(plan),
    )
    raw = path.read_bytes()
    run = freeze_reference_ledger(repo, parent, path)
    loaded = load_reference_ledger(repo, run)
    assert loaded["plan"] == plan
    assert (run / "generated/medical_evaluation/raw/reference_input.json").read_bytes() == raw
    assert json.loads((run / "run_manifest.json").read_text())["status"] == "completed"
    assert run != parent
    assert not (repo / "data/private/inspect_sr").exists()
    artifact = run / "processed/medical_evaluation/reference_ledger.json"
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash|artifact"):
        load_reference_ledger(repo, run)


@pytest.mark.parametrize("disposition", ["plausible_but_wrong", "unresolved"])
def test_wrong_and_unresolved_references_remain_visible(workspace, disposition):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    data["case_reviews"][0]["adjudication"]["issues"][0]["disposition"] = disposition
    ledger = validate_reference_input(plan, data)
    assert ledger["reference_issues"][0]["disposition"] == disposition
    assert ledger["original"]["case_reviews"][0]["assessors"][0]["issues"]
    expected = (
        "unresolved_source_reference"
        if disposition == "unresolved"
        else "no_reference_issue_in_reviewed_sources"
    )
    assert ledger["case_reference_scope"][0]["status"] == expected


def test_distinct_issues_sharing_a_quote_are_not_automatically_deduplicated(workspace):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    review = data["case_reviews"][0]
    observation = copy.deepcopy(review["assessors"][0]["issues"][0])
    observation.update(
        issue_id="second-issue",
        issue_type="interpretation",
        description="Distinct synthetic concern, same quote.",
    )
    review["assessors"][0]["issues"].append(observation)
    adjudicated = copy.deepcopy(review["adjudication"]["issues"][0])
    adjudicated.update(
        reference_id="second-reference",
        issue_type="interpretation",
        description=observation["description"],
        assessor_issue_refs=[{"assessor_id": "assessor-1", "issue_id": "second-issue"}],
    )
    review["adjudication"]["issues"].append(adjudicated)
    ledger = validate_reference_input(plan, data)
    assert len(ledger["reference_issues"]) == 2
    assert (
        ledger["reference_issues"][0]["evidence_ids"]
        == ledger["reference_issues"][1]["evidence_ids"]
    )


def test_missing_case_and_repeated_observation_membership_are_rejected(workspace):
    _, plan = frozen(workspace)
    data = reference_input(plan)
    missing = copy.deepcopy(data)
    missing["case_reviews"] = []
    with pytest.raises(ValueError, match="every planned case"):
        validate_reference_input(plan, missing)
    issue = data["case_reviews"][0]["adjudication"]["issues"][0]
    issue["assessor_issue_refs"].append(copy.deepcopy(issue["assessor_issue_refs"][0]))
    with pytest.raises(ValueError, match="multiply accounted"):
        validate_reference_input(plan, data)


def test_repeated_freeze_preserves_both_attempts_and_parent_manifest(workspace):
    repo, *_ = workspace
    parent, plan = frozen(workspace)
    original_manifest = (parent / "run_manifest.json").read_bytes()
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/reference.json",
        reference_input(plan),
    )
    first = freeze_reference_ledger(repo, parent, path)
    second = freeze_reference_ledger(repo, parent, path)
    assert first != second
    assert (
        load_reference_ledger(repo, first)["ledger"]
        == load_reference_ledger(repo, second)["ledger"]
    )
    assert (parent / "run_manifest.json").read_bytes() == original_manifest
    (parent / "run_manifest.json").write_bytes(original_manifest + b" ")
    with pytest.raises(ValueError, match="parent plan manifest changed"):
        load_reference_ledger(repo, first)


def test_input_drift_preserves_failed_reference_attempt_and_raw_input(workspace, monkeypatch):
    from research_project.medical_review import evaluation_reference as module

    repo, *_ = workspace
    parent, plan = frozen(workspace)
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/reference.json",
        reference_input(plan),
    )
    raw = path.read_bytes()
    real_update = module.update_run

    def change_input(manifest, **kwargs):
        result = real_update(manifest, **kwargs)
        if kwargs.get("artifact", "").endswith("raw/reference_input.json"):
            path.write_bytes(raw + b" ")
        return result

    monkeypatch.setattr(module, "update_run", change_input)
    with pytest.raises(ValueError, match="changed while freezing"):
        freeze_reference_ledger(repo, parent, path)
    attempts = list(
        (repo / "data/processed/forensics_runs/private_reviews/evaluation-synthetic").glob(
            "*/run_manifest.json"
        )
    )
    failed = [p for p in attempts if json.loads(p.read_text())["status"] == "failed"]
    assert len(failed) == 1
    assert (
        failed[0].parent / "generated/medical_evaluation/raw/reference_input.json"
    ).read_bytes() == raw
    assert not (failed[0].parent / "processed/medical_evaluation/reference_ledger.json").exists()


def test_reference_cli_freezes_without_live_calls_or_inspect_writes(workspace):
    repo, *_ = workspace
    parent, plan = frozen(workspace)
    path = write_json(
        repo / "data/private/medical_reviews/evaluation-synthetic/evaluation/reference.json",
        reference_input(plan),
    )
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/medical_review.py"),
            "evaluation-reference",
            "--plan-run",
            str(parent),
            "--input",
            str(path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    loaded = load_reference_ledger(repo, Path(result.stdout.strip()))
    assert loaded["ledger"]["medical_performance_validated"] is False
    assert loaded["manifest"]["effective_settings"]["allow_llm"] is False
    assert loaded["manifest"]["effective_settings"]["allow_web_search"] is False
    assert not (repo / "data/private/inspect_sr").exists()


def test_reference_limit_covers_actual_indented_artifact_and_record_identity(
    workspace, monkeypatch
):
    from research_project.medical_review import evaluation_reference as module

    _, plan = frozen(workspace)
    data = reference_input(plan)
    ledger = validate_reference_input(plan, data)
    compact_size = len(json.dumps(ledger, ensure_ascii=False).encode())
    pretty_size = len(json.dumps(ledger, sort_keys=True, ensure_ascii=False, indent=2).encode()) + 1
    assert pretty_size > compact_size
    monkeypatch.setattr(module, "MAX_JSON_BYTES", compact_size + 1)
    with pytest.raises(ValueError, match="exceeds"):
        validate_reference_input(plan, data)
