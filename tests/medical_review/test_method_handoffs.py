from __future__ import annotations

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

from research_project.medical_review.audit import load_dossier, verify_review
from research_project.medical_review.importer import import_reviewer
from research_project.medical_review.method_handoffs import build_method_handoff
from research_project.medical_review.records import PRIVATE_RUNS
from research_project.medical_review.reporting import build_report_model
from research_project.run_manifest import create_run, update_run


def numerical_run(repo, bundle_path, input_paths=None):
    return create_run(
        repo_root=repo,
        output_root=PRIVATE_RUNS.parent,
        study_id="synthetic",
        categories=["numeric"],
        config_path=bundle_path,
        input_paths=input_paths or [],
    )


def request(dossier, numeric_run, method_id, result_ids):
    return {
        "schema_version": "medical_method_handoff_request_v1",
        "proposal_id": dossier["proposals"][0]["proposal_id"],
        "numeric_run_reference": str(numeric_run.relative_to(dossier["repo_root"])),
        "receipt_artifact": "reports/numeric/numeric_method_receipts.csv",
        "result_artifact": "reports/numeric/numeric_standardized_results_v2.csv",
        "method_id": method_id,
        "result_ids": result_ids,
        "rationale": "Synthetic explicit source-scoped numerical handoff.",
    }


@pytest.mark.native_r
def test_actual_r_results_bind_medical_handoff_without_rewriting_proposal_or_human_store(
    workspace, preserve_synthetic_artifact
):
    rscript = shutil.which("Rscript")
    if not rscript:
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Rscript is required for medical numerical handoff acceptance.")
        pytest.skip("Rscript unavailable; native medical handoff remains unverified.")
    repo, *_ = workspace
    imported, numeric, output, root = prepare_native_review(workspace, rscript)
    dossier = load_dossier(repo, imported)
    frozen = (imported / "processed/medical_review/proposals.json").read_bytes()
    original_receipt = (output / "numeric_method_receipts.csv").read_bytes()
    rows = pd.read_csv(output / "numeric_standardized_results_v2.csv")
    grim = rows.loc[rows["method_id"] == "scrutiny_grim_map", "result_id"].tolist()
    handoffs = [
        request(dossier, numeric, "scrutiny_grim_map", grim),
        request(dossier, numeric, "scrutiny_rounding_bias", []),
    ]
    for method in (
        "scrutiny_grimmer_map",
        "scrutiny_debit_map",
        "scrutiny_duplicates",
        "statcheck",
    ):
        handoffs.append(
            request(
                dossier,
                numeric,
                method,
                rows.loc[rows["method_id"] == method, "result_id"].tolist(),
            )
        )
    input_path = write_json(
        repo / "data/private/medical_reviews/synthetic/verification/methods.json",
        {
            "schema_version": "medical_verification_input_v1",
            "counterevidence": [],
            "numeric_requests": [],
            "method_handoffs": handoffs,
        },
    )
    shutil.copytree(root / "src/research_project", repo / "src/research_project")
    (repo / "scripts").mkdir()
    shutil.copy(root / "scripts/medical_review.py", repo / "scripts/medical_review.py")
    cli = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts/medical_review.py"),
            "verify",
            "--run",
            str(imported),
            "--input",
            str(input_path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 0, cli.stderr
    derived = Path(cli.stdout.strip())
    dossier = load_dossier(repo, derived)
    for name, original in (
        ("inspect_sr_adapters.py", root / "src/research_project/inspect_sr/adapters.py"),
        ("inspect_sr_records.py", root / "src/research_project/inspect_sr/records.py"),
    ):
        assert (
            derived / "generated/medical_review/code" / name
        ).read_bytes() == original.read_bytes()
    linked = dossier["method_handoffs"]
    assert linked[0]["receipt"]["n_evaluated"] == 2
    assert linked[0]["native_output"]["binding"] == "captured_at_handoff"
    assert all(
        r["qualification"] == "qualified_existing_result_reference" for r in linked[0]["results"]
    )
    assert [r["result"]["anomaly_flag"] for r in linked[0]["results"]] == [False, True]
    assert linked[1]["receipt"]["execution"] == "blocked" and linked[1]["results"] == []
    assert linked[1]["review_reassurance"] is False
    assert all(
        r["qualification"] == "qualified_existing_result_reference"
        for h in linked[2:5]
        for r in h["results"]
    )
    assert linked[-1]["receipt"]["package_version"] == "1.5.0"
    assert all(
        r["qualification"] == "unqualified_existing_result_reference" for r in linked[-1]["results"]
    )
    assert (output / "numeric_method_receipts.csv").read_bytes() == original_receipt
    assert (imported / "processed/medical_review/proposals.json").read_bytes() == frozen
    model = build_report_model(repo, dossier)
    assert model["method_handoffs"] == linked
    assert "Existing method references" in model["rendered_markdown"]
    assert model["official_assessment"] is None
    assert model["manual_adoption_packet"]["method_handoff_ids"] == [
        r["handoff_id"] for r in linked
    ]
    assert not (repo / "data/private/inspect_sr").exists()
    preserve_synthetic_artifact(
        "medical-native-handoffs.json", derived / "processed/medical_review/method_handoffs.json"
    )
    native_file = numeric / linked[0]["native_output"]["reference"]
    original_native = native_file.read_bytes()
    native_file.write_bytes(original_native + b"\nsynthetic corruption\n")
    with pytest.raises(ValueError, match="binding changed"):
        load_dossier(repo, derived)
    native_file.write_bytes(original_native)
    repeated = verify_review(repo, derived, input_path)
    assert load_dossier(repo, repeated)["method_handoffs"] == linked


def test_handoff_cannot_supply_fake_receipt_or_qualified_result_content(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    imported = import_reviewer(repo, bundle_path, incoming)
    dossier = load_dossier(repo, imported)
    numeric, _ = numerical_run(repo, bundle_path)
    data = request(dossier, numeric, "scrutiny_grim_map", ["invented"])
    data["receipt"] = {"schema_version": "method_receipt_v4", "execution": "completed"}
    with pytest.raises(ValueError, match="contract"):
        build_method_handoff(repo, dossier, data)


def test_handoff_refuses_medical_import_as_numerical_execution(workspace):
    repo, bundle_path, incoming, _, _ = workspace
    imported = import_reviewer(repo, bundle_path, incoming)
    dossier = load_dossier(repo, imported)
    data = request(dossier, imported, "scrutiny_grim_map", ["invented"])
    with pytest.raises(ValueError, match="numeric.*stage|numerical.*run"):
        build_method_handoff(repo, dossier, data)


def contract_fixture(workspace, execution, receipt_changes=None):
    """Synthetic receipt-state negative controls; actual R qualification is tested separately."""
    repo, bundle_path, incoming, bundle, _ = workspace
    imported = import_reviewer(repo, bundle_path, incoming)
    dossier = load_dossier(repo, imported)
    numeric, manifest = numerical_run(repo, bundle_path)
    e = bundle["evidence"][0]
    receipt = dict(
        schema_version="method_receipt_v4",
        run_id=numeric.name,
        method_id="scrutiny_grim_map",
        method_version="synthetic-contract",
        package_name="scrutiny",
        package_version="0.6.2",
        unit_of_evaluation="summary_case",
        input_evidence_ids=e["evidence_id"],
        parameters="synthetic negative control",
        applicability="eligible",
        execution=execution,
        result_status="indeterminate",
        n_input=2,
        n_eligible=2,
        n_evaluated=1 if execution == "partial" else 0,
        n_failed=1 if execution == "partial" else 2,
        n_flagged=0 if execution == "partial" else None,
        output_reference="native.csv",
        diagnostic="Synthetic partial/failure control.",
    )
    receipt.update(receipt_changes or {})
    result = dict(
        schema_version="numeric_result_v2",
        run_id=numeric.name,
        result_id="synthetic-result",
        method_id="scrutiny_grim_map",
        source_locator=e["locator"],
        input_evidence_ids=e["evidence_id"],
        candidate_kind="method_result",
        details="Synthetic negative control.",
        metric="consistency",
        value_numeric=1,
        p_value=None,
        anomaly_flag=False,
        source_unit="synthetic-row",
    )
    receipts = write_json(numeric / "reports/numeric/receipts.json", [receipt])
    results = write_json(numeric / "reports/numeric/results.json", [result])
    native = numeric / "reports/numeric/native.csv"
    native.write_text("synthetic negative control\n")
    for path in (receipts, results, native):
        update_run(manifest, artifact=str(path))
    update_run(manifest, stage="numeric_methods", status="completed")
    update_run(manifest, status="completed")
    data = request(dossier, numeric, "scrutiny_grim_map", ["synthetic-result"])
    data.update(
        receipt_artifact="reports/numeric/receipts.json",
        result_artifact="reports/numeric/results.json",
    )
    return repo, dossier, numeric, data


@pytest.mark.parametrize("execution", ["partial", "failed"])
def test_partial_or_zero_evaluated_method_never_becomes_reassuring_coverage(workspace, execution):
    repo, dossier, _, data = contract_fixture(workspace, execution)
    linked = build_method_handoff(repo, dossier, data)
    assert linked["receipt"]["result_status"] == "indeterminate"
    assert linked["receipt"]["n_failed"] > 0
    assert linked["review_reassurance"] is False
    assert linked["results"][0]["new_candidate_written"] is False
    if execution == "failed":
        assert linked["receipt"]["n_evaluated"] == 0
        assert linked["results"][0]["qualification"] == "unqualified_existing_result_reference"


@pytest.mark.parametrize(
    "change", ["same_run", "different_study", "unscoped_source", "symlink", "fractional_count"]
)
def test_handoff_fails_closed_on_receipt_identity_source_and_storage_drift(workspace, change):
    repo, dossier, numeric, data = contract_fixture(workspace, "partial")
    path = numeric / data["receipt_artifact"]
    row = json.loads(path.read_text())[0]
    if change == "same_run":
        row["run_id"] = "some-other-run"
    if change == "fractional_count":
        row["n_evaluated"] = 0.5
    if change in {"same_run", "fractional_count"}:
        write_json(path, [row])
    if change == "different_study":
        manifest = numeric / "run_manifest.json"
        value = json.loads(manifest.read_text())
        value["study_id"] = "another-study"
        write_json(manifest, value)
    if change == "unscoped_source":
        # An exact existing record cannot become same-study evidence by relabeling the request.
        dossier["bundle"]["evidence"] = []
    if change == "symlink":
        raw = path.read_bytes()
        target = numeric / "reports/numeric/other.json"
        target.write_bytes(raw)
        path.unlink()
        path.symlink_to(target)
    with pytest.raises(ValueError, match="hash|symlink|evidence|same-study|integer"):
        build_method_handoff(repo, dossier, data)


def test_registered_fractional_receipt_count_is_rejected_by_qualification_contract(workspace):
    repo, dossier, _, data = contract_fixture(workspace, "partial", {"n_evaluated": 0.5})
    with pytest.raises(ValueError, match="integer"):
        build_method_handoff(repo, dossier, data)
