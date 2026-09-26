from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from research_project.inspect_sr.records import evidence_id

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inspect_sr.py"


def test_cli_exposes_local_review_lifecycle_without_network_options() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    for command in (
        "prepare",
        "prepare-evidence",
        "manual-evidence",
        "submit",
        "compare",
        "adjudicate",
        "finalize",
        "map-candidates",
        "validate",
        "render",
        "export",
    ):
        assert command in result.stdout
    assert "--allow-network" not in result.stdout


def test_private_record_store_rejects_paths_outside_repository(monkeypatch, tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("inspect_sr_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="data/private/inspect_sr"):
        module.private_root(tmp_path / "public")


def test_cli_maps_csv_native_records_to_private_candidate_dossier(
    monkeypatch, tmp_path: Path
) -> None:
    import argparse
    import importlib.util

    spec = importlib.util.spec_from_file_location("inspect_sr_cli_mapping", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    store = tmp_path / "data" / "private" / "inspect_sr"
    locator = "page=1;paragraph=2"
    raw_value = "synthetic p value"
    source_version = "sourcever-fixture"
    selected_evidence_id = evidence_id(source_version, locator, raw_value, "pdf_text", "fixture-v1")
    receipts = pd.DataFrame(
        [
            {
                "schema_version": "method_receipt_v3",
                "run_id": "run-fixture",
                "method_id": "statcheck",
                "method_version": "1",
                "package_name": "statcheck",
                "package_version": "1",
                "unit_of_evaluation": "report_text",
                "input_evidence_ids": selected_evidence_id,
                "parameters": "fixture",
                "applicability": "eligible",
                "execution": "completed",
                "result_status": "no_finding",
                "n_input": 1,
                "n_eligible": 1,
                "n_evaluated": 1,
                "n_failed": 0,
                "n_flagged": 0,
                "output_reference": "raw.csv",
                "diagnostic": "",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {
                "schema_version": "numeric_result_v2",
                "run_id": "run-fixture",
                "method_id": "statcheck",
                "result_id": "run-fixture_statcheck_1",
                "source_locator": locator,
                "input_evidence_ids": selected_evidence_id,
            }
        ]
    )
    evidence = [
        {
            "evidence_id": selected_evidence_id,
            "source_version_id": source_version,
            "locator": locator,
            "raw_value": raw_value,
            "extraction_method": "pdf_text",
            "extraction_version": "fixture-v1",
        }
    ]
    receipt_path, result_path = tmp_path / "receipts.csv", tmp_path / "results.csv"
    evidence_path = tmp_path / "evidence.json"
    output_path = store / "candidate-dossier.json"
    receipts.to_csv(receipt_path, index=False)
    results.to_csv(result_path, index=False)
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    module.command_candidate_map(
        argparse.Namespace(
            receipts=receipt_path,
            results=result_path,
            evidence=evidence_path,
            output=output_path,
        )
    )
    dossier = json.loads(output_path.read_text(encoding="utf-8"))
    assert dossier["schema_version"] == "inspect_sr_candidate_dossier_v2"
    assert dossier["candidate_evidence"][0]["candidate_status"] == "candidate_only"
