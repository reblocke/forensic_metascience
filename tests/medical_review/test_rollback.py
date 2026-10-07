from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from support.medical_review_fixtures import write_json
from support.medical_review_native import prepare_native_review
from test_inspect_sr_reporting import _complete_review
from test_verification import decision

from research_project.medical_review.audit import load_dossier, record_human_disposition
from research_project.medical_review.importer import import_reviewer


def test_scoped_code_disable_preserves_history_and_existing_manifest_cli(workspace, tmp_path):
    repo, bundle, incoming, *_ = workspace
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "src", repo / "src")
    scripts = repo / "scripts"
    scripts.mkdir()
    for name in ("medical_review.py", "forensics_run.py", "run_manuscript_review.sh"):
        shutil.copy(root / "scripts" / name, scripts / name)
    official = repo / "data/private/inspect_sr/synthetic-historical"
    official.mkdir(parents=True)
    final, context = _complete_review(official, "synthetic-historical")
    write_json(official / "finalization.json", final)
    write_json(official / "context.json", context)
    original_official = {p: p.read_bytes() for p in official.rglob("*") if p.is_file()}
    run = import_reviewer(repo, bundle, incoming)
    dossier = load_dossier(repo, run)
    proposal = dossier["proposals"][0]
    first = record_human_disposition(repo, run, decision(dossier, proposal))
    first_record = json.loads(first.read_text())
    revision = record_human_disposition(
        repo, run, decision(dossier, proposal, "dismissed", first_record["disposition_id"])
    )
    retained = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (repo / "data").rglob("*")
        if p.is_file()
    }
    recovery = tmp_path / "disabled-feature-code"
    recovery.mkdir()
    for name, path in (
        ("package", repo / "src/research_project/medical_review"),
        ("cli.py", scripts / "medical_review.py"),
        ("config", repo / "config/medical_review"),
        ("prompts", repo / "prompts/medical_review"),
    ):
        shutil.move(path, recovery / name)
    env = {
        **os.environ,
        "PYTHONPATH": str(repo / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_OFFLINE": "1",
    }
    absent = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('research_project.medical_review') is None",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert absent.returncode == 0, absent.stderr
    historical = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from pathlib import Path; "
            "from research_project.inspect_sr.reporting import build_report_model; "
            "p=Path('data/private/inspect_sr/synthetic-historical'); "
            "context=json.loads((p/'context.json').read_text()); "
            "final=json.loads((p/'finalization.json').read_text()); "
            "model=build_report_model(**context, finalization=final, "
            "current_source_snapshot_sha256=context['source_snapshot']['source_snapshot_sha256']); "
            "assert model['judgments']['overall']['judgment']=='some concerns'",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert historical.returncode == 0, historical.stderr
    legacy = scripts / "forensics_run.py"
    for arguments in (
        ["--help"],
        [
            "validate-output",
            "--repo-root",
            str(repo),
            "--output-root",
            "data/processed/forensics_runs/private_reviews",
        ],
    ):
        result = subprocess.run(
            [sys.executable, str(legacy), *arguments],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    help_ = subprocess.run(
        ["bash", str(scripts / "run_manuscript_review.sh"), "--help"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert help_.returncode == 0 and "prediction_validation" in help_.stdout
    assert retained == {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (repo / "data").rglob("*")
        if p.is_file()
    }
    assert json.loads(revision.read_text())["supersedes"] == first_record["disposition_id"]
    assert (
        json.loads((run / "run_manifest.json").read_text())["schema_version"] == "forensics_run_v3"
    )
    assert original_official == {p: p.read_bytes() for p in official.rglob("*") if p.is_file()}


@pytest.mark.native_r
def test_actual_historical_numerical_candidates_still_qualify_after_code_disable(workspace):
    rscript = shutil.which("Rscript")
    if not rscript:
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Rollback qualification requires the actual R runtime.")
        pytest.skip("Rscript unavailable outside the required native lane.")
    imported, _, output, root = prepare_native_review(workspace, rscript)
    repo = workspace[0]
    dossier = load_dossier(repo, imported)
    evidence = [
        {
            **row,
            "extraction_method": row["parser"]["id"],
            "extraction_version": row["parser"]["version"],
        }
        for row in dossier["bundle"]["evidence"]
    ]
    write_json(output / "rollback-evidence.json", evidence)
    retained = {p: p.read_bytes() for p in (repo / "data").rglob("*") if p.is_file()}
    shutil.copytree(root / "src", repo / "src")
    recovery = repo.parent / "disabled-native-feature-code"
    recovery.mkdir()
    shutil.move(repo / "src/research_project/medical_review", recovery / "package")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util,json,sys; from pathlib import Path; import pandas as pd; "
            "from research_project.inspect_sr.adapters import map_candidate_result; "
            "assert importlib.util.find_spec('research_project.medical_review') is None; "
            "p=Path(sys.argv[1]); "
            "receipts=pd.read_csv(p/'numeric_method_receipts.csv')"
            ".where(lambda f:f.notna(),None).to_dict('records'); "
            "rows=pd.read_csv(p/'numeric_standardized_results_v2.csv')"
            ".where(lambda f:f.notna(),None).to_dict('records'); "
            "evidence=json.loads((p/'rollback-evidence.json').read_text()); "
            "candidates=[c for r in rows if r['method_id']=='scrutiny_grim_map' "
            "for c in map_candidate_result(r,receipts,evidence)]; "
            "assert candidates and "
            "all(c['candidate_status']=='candidate_only' for c in candidates); "
            "assert any(r['method_id']=='scrutiny_rounding_bias' "
            "and r['execution']=='blocked' for r in receipts)",
            str(output),
        ],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": str(repo / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert retained == {p: p.read_bytes() for p in (repo / "data").rglob("*") if p.is_file()}
    assert not pd.read_csv(output / "numeric_method_receipts.csv").empty
