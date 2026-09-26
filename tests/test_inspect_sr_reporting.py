from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from research_project.inspect_sr.records import EXPECTED_CHECK_IDS, create_assessment
from research_project.inspect_sr.reporting import build_report_model
from research_project.inspect_sr.synthesis_export import (
    build_synthesis_export,
    validate_synthesis_policy,
)


def _policy(some_primary: str = "include") -> dict:
    other = "exclude" if some_primary == "include" else "include"
    return {
        "schema_version": "inspect_sr_synthesis_policy_v1",
        "policy_id": "protocol-policy-1",
        "policy_version": "1.0.0",
        "approved_by": "review-chair",
        "approved_at": "2026-09-25",
        "rationale": "Prespecified review protocol decision.",
        "source_guidance_sha256": "a" * 64,
        "primary": {
            "no concerns": "include",
            "some concerns": some_primary,
            "serious concerns": "exclude",
        },
        "sensitivity": {
            "no concerns": "include",
            "some concerns": other,
            "serious concerns": "exclude",
        },
    }


def _finalization(trial_id: str, *, overall: str = "some concerns") -> dict:
    assessment = create_assessment(trial_id, "1.1.2", "a" * 64)
    judgment_set = {
        "domains": [
            {"domain_id": str(i), "judgment": overall, "rationale": "Human decision."}
            for i in range(1, 5)
        ],
        "overall": {"judgment": overall, "rationale": "Human synthesis decision."},
    }
    finalization = {
        "schema_version": "inspect_sr_finalization_v2",
        "record_type": "human_finalization",
        "assessment_id": assessment["assessment_id"],
        "reviewer_submission_ids": ["submission-a", "submission-b"],
        "adjudication_id": "adjudication-final",
        "trial_id": trial_id,
        "guidance_sha256": "a" * 64,
        "source_snapshot_sha256": "c" * 64,
        "workflow_status": "finalized",
        "review_record_id": "resolved-review",
        "early_stop_reason": None,
        "checks": [
            {
                "check_id": check_id,
                "workflow_status": "assessed",
                "response": "Unclear",
                "rationale": f"Reviewed {check_id}.",
                "evidence_ids": [],
            }
            for check_id in EXPECTED_CHECK_IDS
        ],
        "judgments": judgment_set,
    }
    identity = {
        "review_record_id": finalization["review_record_id"],
        "judgments": judgment_set,
        "early_stop_reason": "",
    }
    finalization["finalization_id"] = (
        "finalization_"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    )
    return finalization


def test_synthesis_policy_requires_explicit_versioned_primary_and_sensitivity() -> None:
    policy = _policy()
    validate_synthesis_policy(policy, guidance_sha256="a" * 64)
    policy["sensitivity"]["no concerns"] = "exclude"
    with pytest.raises(ValueError, match="only differ for some concerns"):
        validate_synthesis_policy(policy, guidance_sha256="a" * 64)
    with pytest.raises(ValueError, match="approval"):
        validate_synthesis_policy({**_policy(), "approved_by": ""}, guidance_sha256="a" * 64)


def test_export_requires_adjudicated_final_review_and_propagates_policy_by_trial() -> None:
    trial = "trial-local-1"
    review = _finalization(trial)
    reports = [
        {
            "report_id": "report-a",
            "trial_id": trial,
            "risk_of_bias": "unchanged",
            "disposition": "source-field",
        },
        {"report_id": "report-b", "trial_id": trial, "risk_of_bias": "unchanged"},
    ]
    comparisons = [
        {
            "comparison_id": "comparison-a",
            "trial_id": trial,
            "effect": 1.25,
            "include": "source-field",
        },
        {"comparison_id": "comparison-b", "trial_id": trial, "effect": 0.75},
    ]
    output = build_synthesis_export(
        [review],
        reports,
        comparisons,
        _policy("include"),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={trial: "c" * 64},
        unresolved_policy="block",
        policy_variant="primary",
    )
    assert len(output["trial_dispositions"]) == 1
    assert [row["disposition"] for row in output["trial_dispositions"]] == ["include"]
    assert [row["synthesis_disposition"] for row in output["report_dispositions"]] == [
        "include"
    ] * 2
    assert [row["synthesis_disposition"] for row in output["comparison_dispositions"]] == [
        "include"
    ] * 2
    assert [row["risk_of_bias"] for row in output["report_dispositions"]] == ["unchanged"] * 2
    assert output["report_dispositions"][0]["disposition"] == "source-field"
    assert output["report_dispositions"][0]["synthesis_disposition"] == "include"
    assert output["comparison_dispositions"][0]["include"] == "source-field"
    assert output["comparison_dispositions"][0]["synthesis_include"] is True
    assert [row["effect"] for row in output["comparison_dispositions"]] == [1.25, 0.75]
    sensitivity = build_synthesis_export(
        [review],
        reports,
        comparisons,
        _policy("include"),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={trial: "c" * 64},
        unresolved_policy="block",
        policy_variant="sensitivity",
    )
    assert sensitivity["trial_dispositions"][0]["disposition"] == "exclude"
    assert [row["synthesis_disposition"] for row in sensitivity["comparison_dispositions"]] == [
        "exclude",
        "exclude",
    ]
    assert [row["effect"] for row in sensitivity["comparison_dispositions"]] == [1.25, 0.75]
    without_adjudication = {**review, "adjudication_id": None}
    with pytest.raises(ValueError, match="finalized adjudicated review"):
        build_synthesis_export(
            [without_adjudication],
            [],
            [],
            _policy(),
            guidance_sha256="a" * 64,
            current_source_snapshot_sha256_by_trial={trial: "c" * 64},
            unresolved_policy="block",
            policy_variant="primary",
        )


def test_synthesis_leaves_tampered_finalization_unresolved() -> None:
    review = _finalization("trial-tampered")
    review["checks"] = review["checks"][:-1]
    output = build_synthesis_export(
        [review],
        [],
        [],
        _policy(),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={"trial-tampered": "c" * 64},
        unresolved_policy="list",
        policy_variant="primary",
    )
    assert output["trial_dispositions"][0]["disposition"] == "unresolved"
    assert output["schema_version"] == "inspect_sr_synthesis_export_v2"


def test_unresolved_assessments_block_or_are_explicitly_listed() -> None:
    pending = _finalization("trial-local-pending")
    pending["workflow_status"] = "in_progress"
    with pytest.raises(ValueError, match="Unresolved assessments"):
        build_synthesis_export(
            [pending],
            [],
            [],
            _policy(),
            guidance_sha256="a" * 64,
            current_source_snapshot_sha256_by_trial={"trial-local-pending": "c" * 64},
            unresolved_policy="block",
            policy_variant="primary",
        )
    listed = build_synthesis_export(
        [pending],
        [],
        [],
        _policy(),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={"trial-local-pending": "c" * 64},
        unresolved_policy="list",
        policy_variant="primary",
    )
    assert listed["trial_dispositions"][0]["disposition"] == "unresolved"
    assert listed["trial_dispositions"][0]["include"] is None

    stale = _finalization("trial-local-stale")
    stale_export = build_synthesis_export(
        [stale],
        [],
        [],
        _policy(),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={"trial-local-stale": "b" * 64},
        unresolved_policy="list",
        policy_variant="primary",
    )
    assert stale_export["trial_dispositions"][0]["disposition"] == "unresolved"


def test_public_export_is_explicit_allowlisted_and_excludes_private_canaries() -> None:
    trial = "trial-local-public"
    review = _finalization(trial, overall="no concerns")
    output = build_synthesis_export(
        [review],
        [
            {
                "report_id": "report-public",
                "trial_id": trial,
                "private_excerpt": "PRIVATE_SOURCE_CANARY",
                "reviewer_email": "secret@example.test",
            }
        ],
        [
            {
                "comparison_id": "comparison-public",
                "trial_id": trial,
                "effect": 0.4,
                "private_notes": "PRIVATE_REVIEW_CANARY",
            }
        ],
        _policy(),
        guidance_sha256="a" * 64,
        current_source_snapshot_sha256_by_trial={trial: "c" * 64},
        unresolved_policy="block",
        policy_variant="primary",
        public=True,
        public_trial_ids=[trial],
        public_reviewed_by="release-reviewer",
    )
    serialized = json.dumps(output)
    assert "PRIVATE_SOURCE_CANARY" not in serialized
    assert "PRIVATE_REVIEW_CANARY" not in serialized
    assert "reviewer_email" not in serialized
    assert "release-reviewer" not in serialized
    assert output["report_dispositions"][0]["report_id"] == "report-public"


def test_report_draft_has_no_computed_judgment_or_legacy_category() -> None:
    assessment = create_assessment("trial-local-1", "1.1.2", "a" * 64)
    model = build_report_model(
        assessment=assessment,
        catalogue={
            "checks": [
                {"check_id": check_id, "official_wording": f"Question {check_id}"}
                for check_id in EXPECTED_CHECK_IDS
            ]
        },
        source_versions=[],
        evidence_records=[],
        candidate_dossier={"coverage": [], "candidate_evidence": []},
        reviewer_submissions=[],
        adjudication=None,
        finalization=None,
    )
    assert model["report_status"] == "DRAFT — PENDING"
    assert model["judgments"] is None
    assert all(check["workflow_status"] == "pending" for check in model["checks"])
    assert "trustworthiness_category" not in model
    finalized = _finalization("trial-local-1")
    final_model = build_report_model(
        assessment=assessment,
        catalogue={
            "checks": [
                {"check_id": check_id, "official_wording": f"Question {check_id}"}
                for check_id in EXPECTED_CHECK_IDS
            ]
        },
        source_versions=[],
        evidence_records=[],
        candidate_dossier={"coverage": [], "candidate_evidence": []},
        reviewer_submissions=[],
        adjudication={"adjudication_id": "adjudication-final"},
        finalization=finalized,
        current_source_snapshot_sha256="c" * 64,
    )
    assert final_model["judgments"]["overall"]["judgment"] == "some concerns"


def test_inspect_sr_report_qmd_renders_html_and_pdf_in_requested_directory(tmp_path: Path) -> None:
    if not shutil.which("quarto"):
        if os.environ.get("FORENSICS_REQUIRE_REPORT_INTEGRATION") == "1":
            pytest.fail("Quarto is required by FORENSICS_REQUIRE_REPORT_INTEGRATION=1")
        pytest.skip("Quarto is unavailable; native report integration remains open.")
    model = {
        "schema_version": "inspect_sr_report_model_v1",
        "report_status": "DRAFT — PENDING",
        "trial_id": "trial-fixture",
        "guidance_version": "1.1.2",
        "guidance_sha256": "a" * 64,
        "assessment_id": "assessment-fixture",
        "judgments": None,
        "checks": [
            {
                "check_id": check_id,
                "official_wording": f"Fixture wording for {check_id}",
                "workflow_status": "pending",
                "response": None,
                "rationale": None,
                "evidence_ids": [],
                "evidence_records": [],
                "manual_evidence": [],
                "candidate_evidence": [],
            }
            for check_id in EXPECTED_CHECK_IDS
        ],
        "source_versions": [
            {
                "source_id": "source-fixture",
                "source_version_id": "sourcever-fixture",
                "content_sha256": "b" * 64,
            }
        ],
        "method_receipts": [
            {
                "method_id": "scrutiny_grim_map",
                "execution": "completed",
                "n_eligible": 1,
                "n_evaluated": 1,
                "n_failed": 0,
            }
        ],
        "reviewer_submissions": [
            {
                "reviewer_id": "private-reviewer-canary",
                "submission_id": "submission-fixture",
                "source_snapshot_sha256": "c" * 64,
                "workflow_status": "in_progress",
            }
        ],
        "adjudication": {"adjudication_id": "adjudication-fixture"},
        "unresolved_items": [
            {"check_id": check_id, "workflow_status": "pending", "response": None}
            for check_id in EXPECTED_CHECK_IDS
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(model), encoding="utf-8")
    report_dir = tmp_path / "reports" / "inspect_sr"
    report_dir.mkdir(parents=True)
    qmd = Path(__file__).parents[1] / "notebooks" / "inspect_sr_assessment.qmd"
    render_template = report_dir / qmd.name
    shutil.copy2(qmd, render_template)
    for output in ("html", "pdf"):
        env = {**os.environ, "INSPECT_SR_REPORT_JSON": str(review_path)}
        subprocess.run(
            [
                "quarto",
                "render",
                str(render_template),
                "--to",
                output,
                "--output",
                f"assessment.{output}",
            ],
            cwd=report_dir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        rendered = report_dir / f"assessment.{output}"
        assert rendered.is_file()
        if output == "html":
            contents = rendered.read_text(encoding="utf-8")
            assert "DRAFT — PENDING" in contents
            assert "overall_score" not in contents
            assert "legacy_composite" not in contents
            assert "No human overall judgment is finalized" in contents
            assert "4.11" in contents
            assert "private-reviewer-canary" in contents
            assert "adjudication-fixture" in contents
