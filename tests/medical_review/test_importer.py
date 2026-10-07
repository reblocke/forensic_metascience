from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.importer import import_reviewer, validate_upstream
from research_project.medical_review.records import validate_coverage

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_HASH = "9399e39d1be1b6584bd452086bcb6f2f80a90b34826b8467658c3c88c8742641"


def imported(workspace):
    repo, bundle_path, incoming, *_ = workspace
    return import_reviewer(repo, bundle_path, incoming)


def test_lossless_idempotent_import_and_canonical_evidence(workspace):
    repo, bundle_path, incoming, bundle, upstream = workspace
    original = incoming.read_bytes()
    run = imported(workspace)
    assert import_reviewer(repo, bundle_path, incoming) == run
    raw = run / "generated/medical_review/raw/reviewer.json"
    assert raw.read_bytes() == original
    proposals = json.loads((run / "processed/medical_review/proposals.json").read_text())
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["original"] == upstream["findings"][0]
    assert proposal["evidence_links"][0]["evidence_id"] == bundle["evidence"][0]["evidence_id"]
    assert proposal["evidence_links"][0]["resolution"] == "exact"
    assert proposal["qualified_result_ids"] == []
    assert "human_verified" not in proposal
    assert proposal["origin"]["output_upstream_revision"] is None
    manifest = json.loads((run / "run_manifest.json").read_text())
    assert manifest["schema_version"] == "forensics_run_v3"
    assert manifest["status"] == "completed"
    assert all(item["sha256"] for item in manifest["artifacts"])
    model = json.loads((run / "processed/medical_review/report_model.json").read_text())
    assert model["human_status"] == "pending"
    assert model["official_assessment"] is None


def test_empty_ok_import_has_unavailable_review_coverage(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    upstream["findings"] = []
    write_json(incoming, upstream)
    run = import_reviewer(repo, bundle_path, incoming)
    coverage = json.loads((run / "processed/medical_review/coverage.json").read_text())
    assert coverage[0]["execution"] == "not_requested"
    assert coverage[0]["assessment"] == "not_assessed"
    assert coverage[0]["inspected_units"] is None
    assert coverage[0]["coverage_available"] is False


def test_changed_payload_under_same_id_conflicts_without_overwriting(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    first = imported(workspace)
    original = (first / "generated/medical_review/raw/reviewer.json").read_bytes()
    upstream["findings"][0]["suggested_fix"] = "Different payload."
    write_json(incoming, upstream)
    with pytest.raises(ValueError, match="conflict"):
        import_reviewer(repo, bundle_path, incoming)
    assert (first / "generated/medical_review/raw/reviewer.json").read_bytes() == original
    assert (
        len(list((repo / "data/processed/forensics_runs/private_reviews/synthetic").iterdir())) == 1
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("human_verified", True),
        ("method_receipt", {}),
        ("response", "Yes"),
        ("schema_version", "future"),
    ],
)
def test_unknown_or_official_upstream_fields_fail_closed(workspace, field, value):
    _, _, _, _, upstream = workspace
    upstream["findings"][0][field] = value
    with pytest.raises(ValueError, match="Unsupported|Unexpected"):
        validate_upstream(upstream, ROOT, SCHEMA_HASH)


def test_unknown_schema_hash_is_rejected(workspace):
    repo, bundle_path, incoming, *_ = workspace
    with pytest.raises(ValueError, match="schema"):
        import_reviewer(repo, bundle_path, incoming, schema_sha256="0" * 64)


@pytest.mark.parametrize("change", ["quote", "page", "path", "study_map"])
def test_inexact_reference_never_gets_exact_evidence(workspace, change):
    repo, bundle_path, incoming, bundle, upstream = workspace
    obj = upstream["findings"][0]["source_objects"][0]
    if change == "quote":
        obj["text_quote"] = "Random assignment used medical-record number parity."
    elif change == "page":
        obj["page"] = 2
    elif change == "path":
        obj["path"] = "inputs/other.txt"
    else:
        bundle["reports"][0]["study_ids"].append("second")
        bundle["studies"].append({"study_id": "second", "trial_id": None})
        bundle["reports"][0]["mapping_reviewed"] = False
        write_json(bundle_path, bundle)
    write_json(incoming, upstream)
    run = import_reviewer(repo, bundle_path, incoming)
    proposals = json.loads((run / "processed/medical_review/proposals.json").read_text())
    assert proposals[0]["evidence_links"][0]["resolution"] == "unresolved"
    assert proposals[0]["evidence_links"][0]["evidence_id"] is None


def test_bad_source_or_parsed_hash_is_rejected_before_output(workspace):
    repo, bundle_path, incoming, bundle, _ = workspace
    source = repo / bundle["documents"][0]["path"]
    source.write_text("changed source", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        import_reviewer(repo, bundle_path, incoming)
    assert not (repo / "data/processed").exists()


def test_duplicate_json_keys_and_duplicate_finding_ids_are_rejected(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    incoming.write_text('{"reviewer":"one","reviewer":"two"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate JSON"):
        import_reviewer(repo, bundle_path, incoming)
    upstream["findings"].append(copy.deepcopy(upstream["findings"][0]))
    write_json(incoming, upstream)
    with pytest.raises(ValueError, match="Duplicate finding"):
        import_reviewer(repo, bundle_path, incoming)


def test_unsafe_outputs_and_symlinks_are_rejected(workspace, tmp_path):
    repo, bundle_path, incoming, *_ = workspace
    for output in (repo / "reports", tmp_path / "public"):
        with pytest.raises(ValueError, match="private"):
            import_reviewer(repo, bundle_path, incoming, output_root=output)
    destination = repo / "data/processed/forensics_runs/private_reviews"
    destination.parent.mkdir(parents=True)
    destination.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink|private"):
        import_reviewer(repo, bundle_path, incoming)


def test_changed_completed_artifact_refuses_reuse(workspace):
    run = imported(workspace)
    (run / "generated/medical_review/raw/reviewer.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact"):
        imported(workspace)


def test_traversal_reference_and_unlinked_claim_are_rejected(workspace):
    repo, bundle_path, incoming, _, upstream = workspace
    upstream["findings"][0]["source_objects"][0]["path"] = "../../secret"
    write_json(incoming, upstream)
    with pytest.raises(ValueError, match="traversal"):
        import_reviewer(repo, bundle_path, incoming)
    upstream["findings"][0]["source_objects"][0]["path"] = "inputs/main.txt"
    upstream["findings"][0]["claim_evidence_links"][0]["source_object_ids"] = ["missing"]
    write_json(incoming, upstream)
    with pytest.raises(ValueError, match="source object"):
        import_reviewer(repo, bundle_path, incoming)


def test_no_issue_requires_positive_documented_coverage():
    coverage = {
        "schema_version": "medical_review_coverage_v1",
        "check_id": "x",
        "study_id": "synthetic",
        "comparison_id": None,
        "applicability": "applicable",
        "rationale": "fixture",
        "execution": "failed",
        "assessment": "no_issue_identified",
        "inspected_units": 0,
        "evidence_ids": [],
        "missing_materials": [],
    }
    with pytest.raises(ValueError, match="no.issue|No.issue"):
        validate_coverage(coverage)


def test_no_issue_rejects_required_source_gaps_from_imported_plan(workspace):
    run = imported(workspace)
    path = run / "processed/medical_review/coverage.json"
    original = path.read_bytes()
    rows = json.loads(original)
    coverage = copy.deepcopy(next(row for row in rows if row["required_source_gaps"]))
    coverage.update(
        applicability="applicable",
        execution="completed",
        assessment="no_issue_identified",
        inspected_units=1,
        evidence_ids=[workspace[3]["evidence"][0]["evidence_id"]],
        missing_materials=[],
    )
    # Simulate a completed declaration; the actual imported source gap must still
    # prevent reassurance even when the other positive-coverage fields are set.
    with pytest.raises(ValueError, match="No-issue"):
        validate_coverage(coverage)
    coverage["required_source_gaps"] = []
    validate_coverage(coverage)
    coverage["unresolved_required_sources"] = ["legacy-required-source"]
    with pytest.raises(ValueError, match="No-issue"):
        validate_coverage(coverage)
    assert path.read_bytes() == original


def test_cli_plan_help_and_import_replay_are_real_boundaries(workspace):
    repo, bundle_path, incoming, *_ = workspace
    shutil.copytree(ROOT / "src/research_project", repo / "src/research_project")
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    script = repo / "scripts/medical_review.py"
    before = sorted(str(p.relative_to(repo)) for p in repo.rglob("*") if p.is_file())
    commands = [
        ("--help",),
        ("plan", "--bundle", "missing.json", "--profile", "clinical_trial", "--dry-run"),
        ("plan", "--bundle", str(bundle_path), "--profile", "clinical_trial", "--dry-run"),
    ]
    for arguments in commands:
        result = subprocess.run(
            [sys.executable, str(script), *arguments], cwd=repo, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        if arguments[0] == "plan" and arguments[2] == str(bundle_path):
            planned = json.loads(result.stdout)
            assert planned["status"] == "incomplete"
            assert planned["review_plan"]["checks"]
            assert planned["model_calls"] == planned["files_written"] == 0
    after = sorted(str(p.relative_to(repo)) for p in repo.rglob("*") if p.is_file())
    # Python bytecode creation is disabled by the thin CLI before importing its modules.
    assert before == after
    arguments = [
        sys.executable,
        str(script),
        "import-reviewer",
        "--bundle",
        str(bundle_path),
        "--input",
        str(incoming),
        "--offline",
    ]
    result = subprocess.run(arguments, cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    again = subprocess.run(arguments, cwd=repo, capture_output=True, text=True)
    assert again.returncode == 0 and result.stdout == again.stdout


def test_changed_input_during_import_preserves_failed_attempt(workspace, monkeypatch):
    from research_project.medical_review import importer

    repo, bundle_path, incoming, _, upstream = workspace
    original_bytes = incoming.read_bytes()
    original_create = importer.create_run

    def changed_input(**kwargs):
        upstream["notes"].append("Changed while importing.")
        write_json(incoming, upstream)
        return original_create(**kwargs)

    monkeypatch.setattr(importer, "create_run", changed_input)
    with pytest.raises(ValueError, match="changed during import"):
        importer.import_reviewer(repo, bundle_path, incoming)
    run = next((repo / "data/processed/forensics_runs/private_reviews/synthetic").iterdir())
    assert json.loads((run / "run_manifest.json").read_text())["status"] == "failed"
    assert (run / "generated/medical_review/raw/reviewer.json").read_bytes() == original_bytes


def test_adapter_change_creates_new_attempt_instead_of_reusing(workspace, monkeypatch):
    from research_project.medical_review import importer

    original = imported(workspace)
    monkeypatch.setattr(importer, "_adapter_hash", lambda: "f" * 64)
    new_run = imported(workspace)
    assert new_run != original
    old_proposal = json.loads((original / "processed/medical_review/proposals.json").read_text())[0]
    new_proposal = json.loads((new_run / "processed/medical_review/proposals.json").read_text())[0]
    assert old_proposal["proposal_id"] == new_proposal["proposal_id"]


def test_changed_catalogue_during_import_preserves_failed_attempt(workspace, monkeypatch):
    from research_project.medical_review import importer

    repo, bundle_path, incoming, *_ = workspace
    original_create = importer.create_run

    def changed_catalogue(**kwargs):
        result = original_create(**kwargs)
        path = repo / "config/medical_review/check_catalogue.json"
        catalogue = json.loads(path.read_text())
        catalogue["checks"][0]["question"] = "Changed during import."
        write_json(path, catalogue)
        return result

    monkeypatch.setattr(importer, "create_run", changed_catalogue)
    with pytest.raises(ValueError, match="plan.*changed|changed.*plan"):
        importer.import_reviewer(repo, bundle_path, incoming)
    run = next((repo / "data/processed/forensics_runs/private_reviews/synthetic").iterdir())
    assert json.loads((run / "run_manifest.json").read_text())["status"] == "failed"
    assert (
        run / "generated/medical_review/raw/reviewer.json"
    ).read_bytes() == incoming.read_bytes()


def test_replay_refuses_symlinked_manifest(workspace, tmp_path):
    run = imported(workspace)
    manifest = run / "run_manifest.json"
    outside = tmp_path / "outside-manifest.json"
    outside.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink|manifest"):
        imported(workspace)


def test_internal_private_directory_symlink_is_rejected(workspace):
    repo, bundle_path, incoming, bundle, _ = workspace
    original = repo / bundle["documents"][0]["path"]
    alias = original.parent.parent / "alias"
    alias.symlink_to(original.parent, target_is_directory=True)
    bundle["documents"][0]["path"] = str((alias / original.name).relative_to(repo))
    write_json(bundle_path, bundle)
    with pytest.raises(ValueError, match="symlink"):
        import_reviewer(repo, bundle_path, incoming)


def test_force_tracked_private_input_is_not_accepted(workspace):
    repo, bundle_path, incoming, *_ = workspace
    subprocess.run(
        ["git", "add", "--force", str(bundle_path.relative_to(repo))], cwd=repo, check=True
    )
    with pytest.raises(ValueError, match="tracked"):
        import_reviewer(repo, bundle_path, incoming)


def test_tampered_import_origin_is_rejected(workspace):
    repo, *_ = workspace
    imported(workspace)
    origin = next((repo / "data/private/medical_reviews/synthetic/import_origins").glob("*.json"))
    record = json.loads(origin.read_text())
    record["first_run_id"] = "fabricated"
    write_json(origin, record)
    with pytest.raises(ValueError, match="origin"):
        imported(workspace)
