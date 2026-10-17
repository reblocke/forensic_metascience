from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.native_r
def test_reconciliation_native_controls_and_fail_closed_methods(tmp_path):
    r = shutil.which("Rscript")
    if not r:
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Required Rscript unavailable")
        pytest.skip("Rscript unavailable")
    code = r"""
source("R/summary_reconciliation.R")
base <- list(assumption_status="conditional", adjustment="crude", weighting="unweighted",
 predictor_coding="binary", estimator="cross_product", se_method="wald_2x2",
 ci_method="wald", test_method="wald", N=112, D=46, m=109,
 reported=list(or="3.25"))
x <- reconcile_request(c(list(request_id="or", check="or_margins"), base))
stopifnot(x$status == "incompatible", x$n_evaluated == 1L,
 length(x$details$tables) == 4, !x$details$compatible)
base$reported$or <- "1.41"
stopifnot(reconcile_request(c(list(request_id="ok", check="or_margins"),
 base))$status == "compatible")
base$estimator <- "unknown"
stopifnot(reconcile_request(c(list(request_id="unknown", check="or_margins"),
 base))$n_evaluated == 0L)
base$estimator <- "firth"
stopifnot(reconcile_request(c(list(request_id="firth", check="or_margins"),
 base))$n_evaluated == 0L)
base$estimator <- "cross_product"
base$predictor_coding <- "unknown"
stopifnot(reconcile_request(c(list(request_id="coding", check="or_margins"),
 base))$n_evaluated == 0L)
base$predictor_coding <- "binary"
missing <- base; missing$D <- NULL
stopifnot(reconcile_request(c(list(request_id="margins", check="or_margins"),
 missing))$n_evaluated == 0L)
base$m <- 10
base$reported <- list(or="1.68", lower="1.12", upper="2.52")
b <- reconcile_request(c(list(request_id="bound", check="wald_bound"), base))
stopifnot(b$status == "incompatible", b$details$minimum_se >= sqrt(4/10+4/102))
base$adjustment <- "adjusted"; base$reported <- list(or="7.65",lower="2.04",upper="28.76",p="0.030")
w <- reconcile_request(c(list(request_id="wald", check="wald_consistency"), base))
stopifnot(w$status == "incompatible", abs(w$details$implied_p - .0026) < .0001)
base$test_method <- "likelihood_ratio"
stopifnot(reconcile_request(c(list(request_id="lr", check="wald_consistency"),
 base))$n_evaluated == 0L)
m <- reconcile_request(list(request_id="mortality",check="binary_contrast", events=c(24,22),
 denominators=c(55,57), assumption_status="conditional", weighting="unweighted"))
stopifnot(abs(m$details$rr - 1.1305785124) < 1e-8,
 abs(m$details$pearson_p - .587819) < 1e-5)
for (i in 1:2) {
 cells <- if (i==1) list(c(25,28,2),c(8,46,3)) else list(c(44,8,3),c(32,19,6))
 ex <- reconcile_request(list(request_id="exact",check="exact_contingency",cells=cells,
   denominators=c(55,57), assumption_status="declared", weighting="unweighted",
   categories=c("eradication","persistence","new_pathogen"),
   reported=list(p=if(i==1) "<0.001" else "0.023")))
 stopifnot(ex$status=="compatible", abs(ex$details$omnibus_p - c(.000612675,.02294047)[i]) < 1e-8,
           !isTRUE(all.equal(ex$details$omnibus_p, ex$details$collapsed_p)))
}
stopifnot(in_printed_interval(1.405, "1.41"), in_printed_interval(1.415,"1.41"),
 !in_printed_interval(1.42,"1.41"), in_printed_interval(.0001,"<0.001"),
 !in_printed_interval(.001,"<0.001"))
z <- enumerate_or(4,2,2)
stopifnot(z[[1]]$state=="zero", z[[3]]$state=="infinite")
u <- enumerate_or(4,0,0)
stopifnot(u[[1]]$state=="undefined")
bad <- tryCatch({enumerate_or(10,11,3); FALSE}, error=function(e) TRUE)
stopifnot(bad)
zero <- reconcile_request(list(request_id="zero", check="binary_contrast",
 events=c(0,0),denominators=c(10,10),assumption_status="conditional",
 weighting="unweighted"))
stopifnot(zero$details$rr_state == "undefined", is.nan(zero$details$rr))
cat("native reconciliation controls passed\n")
"""
    result = subprocess.run([r, "--vanilla", "-e", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_request_source_changes_and_invented_evidence_are_rejected(tmp_path):
    from research_project.summary_reconciliation import bind_evidence, validate_requests

    source = tmp_path / "source.txt"
    source.write_text("Group A 4/10; group B 6/10.\n")
    spec = {"schema_version": "summary_reconciliation_v1", "sources": [], "requests": []}
    import hashlib

    spec["sources"] = [
        {
            "source_id": "s",
            "path": "source.txt",
            "format": "text",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    ]
    evidence = bind_evidence(spec["sources"][0], "line=1", source.read_text().strip())
    scope = {
        key: "unknown"
        for key in [
            "population",
            "timepoint",
            "orientation",
            "predictor_coding",
            "adjustment",
            "weighting",
            "estimator",
            "se_method",
            "ci_method",
            "test_method",
        ]
    }
    spec["requests"] = [
        {
            "request_id": "sum",
            "check": "sum",
            "values": [4, 6],
            "reported": {"total": "10"},
            "assumption_status": "declared",
            "evidence": [evidence],
            **scope,
        }
    ]
    path = tmp_path / "requests.json"
    path.write_text(json.dumps(spec))
    validate_requests(path, tmp_path)
    source.write_text("Changed\n")
    with pytest.raises(ValueError, match="hash"):
        validate_requests(path, tmp_path)
    source.write_text("Group A 4/10; group B 6/10.\n")
    spec["requests"][0]["evidence"][0]["raw_value"] = "invented"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="evidence|source"):
        validate_requests(path, tmp_path)


@pytest.mark.native_r
def test_cli_preserves_native_tests_and_serializes_plain_json(tmp_path):
    r = shutil.which("Rscript")
    if not r:
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Required Rscript unavailable")
        pytest.skip("Rscript unavailable")
    request = {
        "request_id": "synthetic",
        "check": "binary_contrast",
        "assumption_status": "conditional",
        "weighting": "unweighted",
        "events": [3, 5],
        "denominators": [10, 10],
        "reported": {"rr": "0.60"},
    }
    path = tmp_path / "input.json"
    path.write_text(
        json.dumps({"schema_version": "summary_reconciliation_v1", "requests": [request]})
    )
    result = subprocess.run(
        [
            r,
            "--vanilla",
            "scripts/run_summary_reconciliation.R",
            "--input",
            str(path),
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads((tmp_path / "reconciliation_results.json").read_text())
    row = output["results"][0]
    assert row["status"] == "compatible"
    assert row["qualified_method_result"] is False
    assert row["details"]["native_pearson"]["method"]
    assert (tmp_path / "native_results.rds").is_file()
    assert not list(tmp_path.glob("*receipt*"))
    assert not list(tmp_path.glob("*assessment*"))


def test_execution_refuses_public_or_existing_output_before_reading_input(tmp_path):
    from research_project.summary_reconciliation import run_reconciliation

    absent = tmp_path / "missing-input.json"
    public = tmp_path / "reports" / "public"
    with pytest.raises(ValueError, match="data/processed"):
        run_reconciliation(absent, public, tmp_path)
    assert not public.exists()
    existing = tmp_path / "data" / "processed" / "existing"
    existing.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        run_reconciliation(absent, existing, tmp_path)
    assert not list(existing.iterdir())
