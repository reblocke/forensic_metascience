from __future__ import annotations

import hashlib
import json

import pytest
from support.medical_review_fixtures import write_json

from research_project.medical_review.context import build_study_context
from research_project.medical_review.routing import build_review_plan


@pytest.mark.parametrize("stage", ["counterevidence", "editor"])
def test_stage_prompt_is_hash_bound_in_output_free_plan(workspace, stage):
    repo, _, _, bundle, _ = workspace
    plan = build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)
    relative = f"prompts/medical_review/{stage}.txt"
    source = next((s for s in plan["prompt_sources"] if s["path"] == relative), None)
    assert source is not None
    assert source["sha256"] == hashlib.sha256((repo / relative).read_bytes()).hexdigest()
    assert plan["model_calls"] == 0 and plan["full_coverage"] is False
    (repo / relative).write_text("Synthetic changed stage prompt.")
    with pytest.raises(ValueError, match="prompt hash"):
        build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)


@pytest.mark.parametrize("stage", ["counterevidence", "editor"])
def test_stage_provenance_cannot_be_removed_silently(workspace, stage):
    repo, _, _, bundle, _ = workspace
    path = repo / "config/medical_review/check_catalogue.json"
    catalogue = json.loads(path.read_text())
    sources = catalogue["prompt_provenance"]["modules"]
    catalogue["prompt_provenance"]["modules"] = [
        s for s in sources if s["path"] != f"prompts/medical_review/{stage}.txt"
    ]
    write_json(path, catalogue)
    with pytest.raises(ValueError, match="prompt provenance"):
        build_review_plan(bundle, build_study_context(bundle), ["clinical_trial"], repo)
