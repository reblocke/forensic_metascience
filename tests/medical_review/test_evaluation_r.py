from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.native_r
@pytest.mark.parametrize("scenario", ["source", "unknown", "resources", "csv_boundary"])
def test_native_descriptive_evaluation_retains_scope_and_unknowns(tmp_path, scenario):
    rscript = shutil.which("Rscript")
    if not rscript:
        if os.environ.get("FORENSICS_REQUIRE_R_INTEGRATION") == "1":
            pytest.fail("Required native R evaluation runtime is missing.")
        pytest.skip("Rscript unavailable outside the required native lane.")
    root = Path(__file__).resolve().parents[2]
    program = tmp_path / "evaluation-check.R"
    program.write_text(
        """args <- commandArgs(trailingOnly=TRUE)
source(args[1])
views <- data.frame(view_id=c("v1","v2","v3"), packet_id=c("p1","p2","p3"),
  case_id=c("c1","c1","c2"), analysis_unit_id=c("study1","study1","study2"),
  partition="development", profile_ids="clinical_trial", track="common_input",
  condition_id=c("strong_single_reviewer","medical_adaptation","medical_adaptation"),
  repetition=1, source_set_id=c("main","other","main"), input_equivalence="equivalent",
  reviewer_supplied=c(TRUE,TRUE,TRUE), synthesis_supplied=c(FALSE,TRUE,FALSE))
findings <- data.frame(item_id=c("i1","i2"), view_id=c("v1","v1"), case_id="c1",
  stage="reviewer", disposition=c("confirmed_concern","unsupported_criticism"),
  serious_false_allegation=c(FALSE,NA), source_attribution=c("correct","incorrect"))
references <- data.frame(case_id=c("c1","c2"), reference_id="same-local-id",
  disposition="reference_issue", important=TRUE)
matches <- data.frame(item_id="i1", case_id="c1", reference_id="same-local-id")
synthesis <- data.frame(item_id="i1", view_id="v1", stage="reviewer",
  disposition="unavailable", distorted=NA, error_stage="unknown",
  caveats_lost=0, caveats_distorted=0, caveats_unresolved=0)
timings <- data.frame(view_id="v1", phase="candidate_assessment",
  verification_seconds=NA_real_, revision_seconds=0)
attempts <- data.frame(packet_id=c("p1","p1","p2"), attempt_id=c("a1","a2","a3"),
  status=c("failed","completed","completed"), elapsed_seconds=c(2,NA,1),
  input_tokens=c(10,NA,1), output_tokens=c(2,NA,1), total_tokens=c(12,NA,2),
  cost_amount=c(3,NA,5), cost_currency=c("USD","USD","EUR"))
result <- medical_evaluation_outcomes(views, findings, references, matches,
  synthesis, timings, attempts)
if (args[2] == "source") {
  rows <- result$findings_by_view_stage
  stopifnot(rows$important_reference_detected[rows$view_id=="v1" & rows$stage=="reviewer"]==1,
    rows$important_reference_detected[rows$view_id=="v3" & rows$stage=="reviewer"]==0)
  pair <- result$paired_case_comparisons
  stopifnot(all(pair$comparison_status == "unmatched_source_access"),
    all(is.na(pair$important_detection_difference)))
  wrong <- matches; wrong$case_id <- "c2"
  error <- try(medical_evaluation_outcomes(views, findings, references, wrong,
    synthesis, timings, attempts),silent=TRUE)
  stopifnot(inherits(error,"try-error"))
} else if (args[2] == "unknown") {
  rows <- result$findings_by_view_stage
  absent <- rows[rows$view_id=="v1" & rows$stage=="synthesis",]
  stopifnot(is.na(absent$important_reference_detected), is.na(absent$confirmed_records),
    all(!rows$review_coverage_available))
  burden <- result$effort_by_view_phase
  stopifnot(is.na(burden$verification_seconds[1]), burden$verification_known_sum[1]==0,
    burden$verification_unknown_count[1]==1, burden$revision_seconds[1]==0)
  stopifnot(rows$serious_false_unknown[rows$view_id=="v1" & rows$stage=="reviewer"]==1)
} else {
  resources <- result$resources_by_packet_currency
  usd <- resources[resources$packet_id=="p1",]
  stopifnot(usd$failed_attempts==1, usd$cost_known_sum==3, is.na(usd$cost_amount),
    usd$cost_unknown_count==1, usd$total_tokens_known_sum==12)
  stopifnot(nrow(resources)==3,
    is.na(resources$cost_amount[resources$packet_id=="p3"]),
    resources$reported_attempts[resources$packet_id=="p3"]==0)
}
if (args[2] == "csv_boundary") {
  views$case_id[views$case_id == "c2"] <- "NA"
  references$case_id[references$case_id == "c2"] <- "NA"
  tables <- list(views=views, findings=findings, references=references, matches=matches,
    synthesis=synthesis, timings=timings, attempts=attempts)
  dir.create(args[3])
  for (name in names(tables)) write.table(tables[[name]],
    file.path(args[3],paste0(name,".csv")),sep=",",row.names=FALSE,na="",quote=TRUE)
}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            rscript,
            str(program),
            str(root / "R/medical_evaluation.R"),
            scenario,
            str(tmp_path / "inputs"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    if scenario == "csv_boundary":
        output = tmp_path / "outputs"
        output.mkdir()
        command = [
            rscript,
            str(root / "scripts/analyze_medical_evaluation.R"),
            "--in",
            str(tmp_path / "inputs"),
            "--out",
            str(output),
        ]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        with (output / "findings_by_view_stage.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        assert all(row["case_id"] == "NA" for row in rows if row["view_id"] == "v3")
        with (output / "resources_by_packet_currency.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        assert next(row for row in rows if row["packet_id"] == "p1")["cost_amount"] == ""
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        repeated = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
        assert repeated.returncode != 0
        assert "choose a fresh run" in repeated.stderr
        assert {p.name: p.read_bytes() for p in output.iterdir()} == before
