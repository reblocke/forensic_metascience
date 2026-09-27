# Handoff (for multi-session work)

## Active FM-12 continuation — 2026-09-26

The authorized repair is continuing on `codex/inspect-sr-resumption` from
`4b2d84bdf35f1b5e4893658026052902b242e524`. Existing uncommitted changes and
`run-b2.html` are preserved; its starting SHA-256 was
`2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.

- Fixed the mixed candidate/evidence table rows in
  `notebooks/inspect_sr_assessment.qmd` by normalizing displayed values to
  scalar text cells. The connected native-to-review CLI workflow now passes
  locally through current evidence, source snapshot, candidate mapping,
  independent submissions, adjudication, finalization, HTML/PDF rendering, and
  allowlisted export.
- Added `scripts/run_offline_test_lane.sh` and wired all three hosted lanes to
  create a network namespace, drop back to the runner account, carry explicit
  runtime variables, and invoke the prepared Python environment by absolute
  path. `scripts/check_pytest_junit.py` is required in each lane to reject an
  empty suite or any skip/failure/error. CI artifacts include JUnit, runtime
  inventories, source hashes, and allowlisted synthetic outputs; private stores
  are not uploaded.
- Added a failing adapter regression, confirmed it failed before the code fix,
  then blocked all rounding-bias candidate mapping. The native receipt remains
  `rounding_bias_blocked_v1` with unknown applicability, blocked execution,
  indeterminate result, zero evaluated units, preserved input count, null
  findings, and no anomaly output. Optional sequence checks remain blocked;
  SPRITE remains unimplemented.
- Replaced one-column private prediction-review fixtures with populated
  contract-shaped synthetic CSVs and added HTML/PDF artifact allowlisting. The
  mixed evidence/candidate report path checks rendered candidate evidence and
  its source locator. Added JUnit and required-artifact gate regressions.
- `docs/INSPECT_SR_ACCEPTANCE.md` maps R01–R32 and subsequent review findings
  to tests and lanes. README, credibility criteria, INSPECT-SR guide, and this
  decision/handoff now describe rounding-bias as blocked. R33–R34 remain
  deferred under FM-13.

### Ticket ledger at this checkpoint

| Ticket | Status against current local evidence |
|---|---|
| FM-01–FM-02 | Complete: eligibility, precision, denominators, source text, and P-value comparator cases pass mapped Python/R boundary tests. |
| FM-03 | Complete: malformed, partial, failed, zero-eligible, missing-dependency, and unknown outputs remain distinct in native receipt tests. |
| FM-04–FM-05 | Complete: no composite judgment; source-bound candidate mapping, current-run isolation, and immutable run-manifest behavior are covered. |
| FM-06 | Complete: design-gated seeded simdistr production path passes with independent numerical expectations. |
| FM-07 | Complete: negation-aware registration claims and malformed history handling pass. |
| FM-08 | Complete: pinned v1.1.2 source files, catalogue, licenses, and hashes are present and validated. |
| FM-09–FM-11 | Complete: source-linked candidates, independent review/adjudication, finalization, rendered reports, and allowlisted export pass connected synthetic CLI/report coverage. |
| FM-12 | Open: hosted Python, native R, and report/review lanes must pass on the same final PR head and merged `main`. |
| FM-13 | Deferred; R33–R34 remain outside this repair. |

“Complete” for FM-01–FM-11 means the implementation and mapped local
acceptance are complete. The all-lanes release/integration claim remains
withheld until FM-12 passes on hosted CI and merged `main`.

### Local acceptance receipts for the current uncommitted tree

- Python passed **133 tests, 17 deselected**; its JUnit gate reported zero
  skipped or failed tests:

  ```bash
  PYTHONPATH=src UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m 'not native_r and not report_integration' --junitxml=/tmp/fm-inspect-final-delivery-0926/python/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/python/junit.xml /tmp/fm-inspect-final-delivery-0926/python/python-version.txt
  ```

- Native R passed **13 tests, 136 deselected**; its JUnit gate reported zero
  skipped or failed tests:

  ```bash
  FM_TEST_ARTIFACT_DIR=/tmp/fm-inspect-final-delivery-0926/native PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m native_r --junitxml=/tmp/fm-inspect-final-delivery-0926/native/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/native/junit.xml /tmp/fm-inspect-final-delivery-0926/native/python-version.txt /tmp/fm-inspect-final-delivery-0926/native/r-packages.csv /tmp/fm-inspect-final-delivery-0926/native/r-session.txt /tmp/fm-inspect-final-delivery-0926/native/source-hashes.sha256 /tmp/fm-inspect-final-delivery-0926/native/native-method-receipts.csv /tmp/fm-inspect-final-delivery-0926/native/native-standardized-results.csv
  ```

- Report/review passed **4 tests, 7 deselected**; its JUnit gate reported zero
  skipped or failed tests. This selection rendered synthetic INSPECT-SR and
  private prediction-review reports in HTML/PDF and completed the CLI workflow,
  early-stop branch, symlink checks, and allowlisted export:

  ```bash
  FM_TEST_ARTIFACT_DIR=/tmp/fm-inspect-final-delivery-0926/report PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m report_integration tests/test_inspect_sr_reporting.py tests/test_inspect_sr_cli_workflow.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs --junitxml=/tmp/fm-inspect-final-delivery-0926/report/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/report/junit.xml /tmp/fm-inspect-final-delivery-0926/report/python-version.txt /tmp/fm-inspect-final-delivery-0926/report/r-packages.csv /tmp/fm-inspect-final-delivery-0926/report/r-session.txt /tmp/fm-inspect-final-delivery-0926/report/quarto-version.txt /tmp/fm-inspect-final-delivery-0926/report/quarto-environment.txt /tmp/fm-inspect-final-delivery-0926/report/source-hashes.sha256 /tmp/fm-inspect-final-delivery-0926/report/inspect-sr-review.html /tmp/fm-inspect-final-delivery-0926/report/inspect-sr-review.pdf /tmp/fm-inspect-final-delivery-0926/report/private-prediction-review.html /tmp/fm-inspect-final-delivery-0926/report/private-prediction-review.pdf
  ```
- Checks: `uv run ruff check .`, `uv run ruff format . --check`, `bash -n
  scripts/run_offline_test_lane.sh scripts/install_inspect_sr_r_methods.sh`,
  Ruby YAML parsing of `.github/workflows/ci.yml`, R parsing of
  `scripts/run_numeric_forensics.R` and `R/method_receipts.R`, and
  `git diff --check` passed.
- Local runtime: Python **3.13.0**, R **4.6.1**, Quarto **1.10.18**, TinyTeX
  **v2025.12** / LaTeX **2025**. R packages: scrutiny **0.6.2**, statcheck
  **1.5.0**, simdistr **1.0.1**, rmarkdown **2.32**, knitr **1.51**, cpp11
  **0.5.5**, progress **1.2.3**. Quarto PDF rendering passed. `pdflatex` is
  not separately available on the local shell PATH; Quarto resolves its bundled
  TinyTeX. Hosted CI records its own Quarto/TeX runtime inventory.
- Local JUnit SHA-256: Python
  `3163516bc48d38e116262fff2fe2dc7280581bfbe66fb32b7105c988a850b0fd`; native
  `72dd45b29fe51f8a32d2ca2383609acf6605a5d999a301b987a85cfe9b785fde`; report
  `1ceaf7d9f0c608292f7fb5fd02f451fef3dcf7748bc2e692e3957fecad5e4145`.
  Synthetic report hashes: INSPECT-SR HTML
  `afe55cfa54a149cf067f0f21479b87ed4bbd3ab736765d41c22572499a1c982d`, PDF
  `4fe7570198aaee722b67e27f9cbcb9bb70b9732cea6ff80640712d4a11b1a007`;
  private prediction HTML
  `45eadedb223aeabfb1a1244caf21229a1ea163dacf166ac6122ce868bcb46c0a`, PDF
  `5364e057575e8aa49c926450d7b195678a1ff460d7f19454d24f0852f3841b62`.
  Native method receipt SHA-256 is
  `757e42dcb558ecd1f5355987d2919d4df118a1bf3568a2f7def13b7b33e16566`; the
  standardized result SHA-256 is
  `73abf6ff558093218fa7e312bcce489045ea478b1bf80b36f9a863f41c0ec0e2`.
- The `run-b2.html` SHA-256 remains
  `2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.
  These are local receipts only. The macOS runs do not verify Linux network
  namespace setup; hosted CI must exercise that wrapper before FM-12 can close.

**Still open:** Push the reviewable commits, exercise the exact network-namespace
wrapper on hosted runners, pass all three hosted lanes on the same final PR SHA,
review and mark PR #5 ready, merge with a merge commit, then verify on merged
`main`. FM-12 remains open and no ticket is declared fully integrated yet. No
source-paper analysis, historical-results rewrite, deployment, or human
adjudication was performed.

## Hosted acceptance continuation — 2026-09-25

Draft PR #5 remains open and unmerged. On commit `a353f3d`, hosted Actions
runs `36212282299` and `36212284401` exposed two environment failures:
`python-fast` could not import the local `research_project` package in a
subprocess because the workflow lacked `PYTHONPATH=src`; `report-review`
reached Quarto but R could not load `rmarkdown`. The Python import failure was
reproduced locally without `PYTHONPATH` and corrected in the workflow. Adding
the missing R package to the hosted report environment awaits dependency
approval under `AGENTS.md`; the report lane and FM-12 remain blocked until it
is approved and passes. Both `native-r` jobs then failed during isolated R
setup: `fs` could not find libuv headers and transitive `cpp11`/`progress`
were unavailable, so scrutiny could not be installed. Repair of that hosted
test environment also awaits approval; neither native-R job reached its tests.

An additional failing regression showed that a report could accept candidate
evidence without a matching current method receipt or source evidence. The
report builder now checks candidate routes, evidence IDs and locators against
the receipt inputs, and derives supplied coverage from validated receipts.
New models use `inspect_sr_report_model_v2`; existing v1 models are retained as
historical outputs and must be rebuilt from current records for review.
After that change, `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o
addopts='' -m 'not native_r' -ra` passed **128 tests** with 13 native tests
deselected. The required local report command recorded below passed **11
tests**. The workflow fix and candidate guard require a new hosted run on the
committed head before acceptance.

On commit `b0804de`, the hosted `python-fast` job in run
[`36212736603`](https://github.com/reblocke/forensic_metascience/actions/runs/36212736603)
passed install, Ruff lint, Ruff format, and tests. The same committed head
passed locally with **13 native R tests** (`FORENSICS_REQUIRE_R_INTEGRATION=1
R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run
--offline pytest -q -o addopts='' -m native_r -ra`; 128 deselected) and **11
report/review tests** (`FORENSICS_REQUIRE_REPORT_INTEGRATION=1
R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run
--offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py
tests/test_inspect_sr_cli_workflow.py
tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`).
These local passes do not clear the hosted R/report setup failures.

## Latest repair continuation — 2026-09-25

The prior "FM-01–FM-12 implemented and locally verified" sentence below was
premature. The review of `09a77dc` found invalid hosted CI expressions and
unbound review/source identities. Current branch work merges `main` with its
data-free onboarding and privacy guidance, retains the original untracked
`run-b2.html`, and repairs the reviewed defects. No source-paper analysis,
historical output rewrite, merge to `main`, or deployment has occurred.

FM-03, FM-05, and FM-08–FM-11 are reopened for v4 receipts, source mapping,
private snapshots, v3 human identities, and complete report/export validation.
FM-12 is open. FM-13 remains deferred. The rounding-bias method has a newly
identified input-contract problem requiring a scientific decision: printed
values rerounded at their printed precision produce zero bias by construction.
It is not independently qualified by an execution-only integration test.
### Local acceptance receipts on `a9d3ccb` (before the final handoff edit)

- `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m 'not native_r' -ra`: **127 passed, 13 deselected**. The deselected tests are the separately required native lane.
- `FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m native_r -ra`: **13 passed, 127 deselected**. This includes synthetic expected true/false results for GRIM, GRIMMER, DEBIT, duplicates, and statcheck, plus the exact binary extremes for simdistr. Rounding-bias execution ran, but its scientific input contract remains unqualified as described above.
- `FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py tests/test_inspect_sr_cli_workflow.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`: **10 passed**. This includes actual CLI finalization, HTML/PDF, allowlisted export, and private prediction-review HTML/PDF with current/stale sentinels.
- `UV_OFFLINE=1 uv run --offline ruff check .`: passed. `UV_OFFLINE=1 uv run --offline ruff format . --check`: passed, 59 files already formatted. `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh scripts/install_inspect_sr_r_methods.sh`, `ruby -e 'require "yaml"; YAML.parse_file(".github/workflows/ci.yml"); puts "workflow YAML parses"'`, and `git diff --check`: passed.
- Runtime: local R **4.6.1**, Quarto **1.10.18**, scrutiny **0.6.2**, statcheck **1.5.0**, simdistr **1.0.1**. Hosted pins remain R 4.6.0 and Quarto 1.9.37. The guidance `SHA256SUMS` hash is `76de5b5be8938b2329439f78c86ac4debe32f0fc7e42f843a8ead8ea9aae9c56`; catalogue hash is `313869d190ff35dfa0137559da440a5cc62cfce1d61d8aef23784ce79a2e1395`; R package-lock hash is `dea25709a20bbf923fd7b8e06b8a34a4f980de52ce95c15f72005db941a3af4d`.
- The connected synthetic source at snapshot creation had SHA-256 `1c86db65f48be61e87eeda4680a562a12b527cb2edff35a88f88bea584bd144a`; local snapshot identity was `687915e2475c3dd8e965722b6b798148d26cd35ca2ae637b06a1074c73ca92c8`. The test changed the source afterward and verified that validation failed until source bytes were restored.
- Five synthetic report/model files and `receipt.json` were copied without overwriting existing files to ignored `data/private/inspect_sr/verification/a9d3ccb/`. Their SHA-256 values are `638dc1402a75c244f98702bd95b9080716eefc6408dd2c0e3ee9a5388b9c4239` (INSPECT-SR HTML), `8a1be2a9e12b1a600f97a434c22a3fc22fbdca57f916c54b92081199f4a6ba7b` (PDF), `8844d1036a2ffc1f5db0d3ed7bbc7a88207d45799c7a1c8222b29a14c1037b24` (model JSON), `4f5a3408b202724879ecc7ef9485b4ed8e664a8bebbcbf3a096b4b6b9bcbb3e6` (private prediction HTML), and `4fdceb9b4e1845befe3e8ef9fa9e05ff4419558b12f7ec170ede055bd0111785` (PDF).

Hosted Actions and the scientific rounding-bias decision remain open. No source-paper analysis, production deployment, merge, automatic adjudication, or historical-results rewrite was run.


## Latest status — 2026-09-25

Implementation is on branch `codex/inspect-sr-resumption`, based on current
repository HEAD rather than resetting to the audit commit. The implementation
checkpoint commits are `d8b21a5` (source-linked native outputs), `e9a21ae`
(private review workflow), and `cb77b76` (required CI lanes). The original
untracked `run-b2.html` artifact is preserved and excluded from commits. No
source-paper analysis or historical output regeneration was run.

- **FM-01–FM-12 at this earlier checkpoint:** Claimed implemented and locally
  verified, pending hosted CI. Later review reopened the tickets noted above.
  FM-03–FM-07 corrections had regression-first coverage at that checkpoint.
  FM-08 uses the 26-file official v1.1.2 source snapshot at
  `a349c4f1ddd9d232dfc2632938aad31382a9a770`, with the complete 21-check
  catalogue and per-file hashes. FM-09–FM-11 keep candidate evidence, manual
  observations, reviewer submissions, adjudication, reports, and synthesis
  exports as distinct records.
- **FM-13:** Deferred.

Draft PR [#5](https://github.com/reblocke/forensic_metascience/pull/5) is open.
Hosted run `36205920711` was created for commit `5b3ca7537d483aa2a372e83642d8970eed86d854`
but concluded `failure` with zero jobs; `gh pr checks 5` reported no checks,
the jobs API returned `total_count: 0`, and GitHub provided no run log and refused
to retry it. Therefore hosted Python/native-R/report checks have not passed and
FM-12 remains open for hosted verification. The failure cause is not exposed by
the available run metadata.

### Verification receipts on the implementation code

- `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m 'not native_r' -ra`
  — passed, 115 passed and 11 deselected (Python lane).
- `FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m native_r -ra`
  — passed, 11 passed and 115 deselected. Native method package versions were
  scrutiny 0.6.2, statcheck 1.5.0, and simdistr 1.0.1; method receipts showed
  evaluated synthetic coverage for GRIM, GRIMMER, DEBIT, duplicate,
  rounding-bias, statcheck, and seeded simdistr.
- `FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`
  — passed, 8 tests, including current-run HTML/PDF report renders.
- `UV_OFFLINE=1 uv run --offline ruff check .` and
  `UV_OFFLINE=1 uv run --offline ruff format . --check` — passed; 56 files
  formatted. `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh scripts/install_inspect_sr_r_methods.sh`
  and `git diff --check` — passed.
- Local runtime: R 4.6.1, Quarto 1.10.18. CI is configured for R 4.6.0 and
  Quarto 1.9.37. The isolated local method library contains the three versions
  above. The source package archives are hash-recorded in
  `config/inspect_sr/r_method_packages.lock.json`.

Hosted Actions remain the release follow-up. The three jobs are separate Python,
required native-R, and report-review lanes; missing R/Quarto/method execution is
configured to fail or leave the integration gate incomplete. Transitive R
imports are installed from CRAN during test setup and are not independently
locked. Reviewer identities, ambiguous trial/report mappings, and each review's
synthesis policy remain explicit human inputs. No deployment, author contact,
automatic adjudication, or historical-results rewrite is authorized.

### FM-08–FM-12 artifact map

- **FM-08:** Added `config/inspect_sr/v1.1.2/` with 26 retrieved guidance/source files, `catalogue.json`, retrieval/license metadata, and `SHA256SUMS`. Added the persistent record model in `src/research_project/inspect_sr/records.py` and its tests. New record schemas include `inspect_sr_catalogue_v1`, `inspect_sr_assessment_v1`, and `inspect_sr_record_model_v1`. Initial checks are pending with null responses.
- **FM-09:** Added method candidate routes in `src/research_project/inspect_sr/adapters.py` and human observation records in `manual_evidence.py`; tests are in `tests/test_inspect_sr_evidence.py`. Candidate outputs use `inspect_sr_candidate_evidence_v1`; manual observations use `inspect_sr_manual_evidence_v1`. Existing v2 method receipts are required, with same-run and source-version checks. Unvalidated checks remain manual-only.
- **FM-10:** Added independent reviewer submission, disagreement, adjudication, resolution, finalization, and query draft records in `review.py`/`validation.py`; tests are in `tests/test_inspect_sr_review.py`. Schemas include `inspect_sr_reviewer_submission_v1`, `inspect_sr_adjudication_v1`, `inspect_sr_resolved_review_v1`, and `inspect_sr_finalization_v1`. Human records are written separately and are not regenerated from candidates.
- **FM-11:** Added the private review model/report in `reporting.py` and `notebooks/inspect_sr_assessment.qmd`, plus explicit policy validation and export in `synthesis_export.py`; tests are in `tests/test_inspect_sr_reporting.py`. Schemas include `inspect_sr_report_model_v1`, `inspect_sr_synthesis_policy_v1`, and `inspect_sr_synthesis_export_v1`. The QMD accepts only an explicit model path; public export is explicitly allowlisted.
- **FM-12:** Added `tests/test_r_integration.py`, the source/hash manifest `config/inspect_sr/r_method_packages.lock.json`, test-only installer `scripts/install_inspect_sr_r_methods.sh`, and separate CI jobs in `.github/workflows/ci.yml`. The pinned scrutiny adapter affects `numeric_scrutiny_{grim,grimmer,debit}_{raw,audit}.csv`, `numeric_standardized_results.csv`, and `numeric_method_receipts.csv` in new run directories; the statcheck receipt uses report text as its single input/evaluation unit. The seeded simdistr test reads/writes only temporary fixtures and verifies repeatability at a fixed seed.

The earlier notes below are chronological receipts from prior stages. Where they
say FM-08 is blocked by a missing source snapshot or native packages are absent,
those statements are superseded by the current pinned snapshot and the isolated
native test environment recorded in the latest decision entry.

## INSPECT-SR packet — 2026-09-25

### Completed
- **FM-01:** Added `numeric_eligibility_v2`. Baseline median observations remain in evidence and are ineligible for GRIM/GRIMMER/DEBIT. The Python input builders and R execution boundary require documented statistical semantics; absent metadata stays unknown and blocks execution. Method-specific reasons are retained in `scrutiny_cases.csv`.
- Regression coverage first reproduced the prior permissive behavior, then passed after implementation. Focused command: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_forensics_categories.py` (6 passed); full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (41 tests). `ruff check .`, `ruff format . --check`, and `Rscript -e 'invisible(parse(file="scripts/run_numeric_forensics.R"))'` passed.
- Affected generated outputs: `scrutiny_input.csv`, `scrutiny_cases.csv`, and `scrutiny_{grim,grimmer,debit}_input.csv`; stored historical outputs were not regenerated.
- **FM-02:** Advanced the numeric method revision to `numeric_eligibility_precision_v3`. Source cells, statistic text, precision, P-value comparator, and source locator are preserved across extraction/build and Python/R CSV reads. Noninteger/nonfinite denominators and counts are rejected; percentage compatibility is indeterminate without denominator role, unweighted status, and explicit supported rounding convention. The legacy percentage delta remains descriptive only.
- FM-02 verification: `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (46 tests collected); `ruff check .`, `ruff format . --check`, R syntax parse, and the Python→readr→Python string-precision roundtrip passed. Regression cases cover 1/3 as 33% and 33.3%, 34.0% incompatibility under nearest-half-up, unknown denominator status, weighted percentages, invalid counts, P<0.001, P=1.2, and an outcome-specific denominator with unknown role.
- FM-02 affected generated outputs: parsed Table 1 rows, `numeric_checks_input.csv`, `scrutiny_input.csv`, `scrutiny_cases.csv`, and package-specific numeric inputs. No stored historical artifacts were rewritten.
- **FM-03:** Added `method_receipt_v1` execution receipts for GRIM/GRIMMER/DEBIT, duplicate and rounding-bias checks, statcheck, optional sequence methods, and unimplemented SPRITE. Completed no-finding receipts require positive evaluated coverage; zero eligible inputs, missing dependencies, errors, partial evaluation, not-requested methods, and not-implemented methods remain explicit. Fixed trial-ID selection across means-only inputs, preserved case IDs in standardized method rows, stopped mapping package probability to inferential `p_value`, and moved SPRITE candidate differences to a descriptive output without anomaly fields. Summary finding counts remain null when a method is not fully evaluated.
- FM-03 affected generated outputs: adds `numeric_method_receipts.csv` and `numeric_descriptive_arm_differences.csv`; changes `numeric_standardized_results.csv`, `numeric_summary.csv`, and compatibility `numeric_package_status.csv`; updates `notebooks/lungtime_numeric_audit.qmd` and `notebooks/prediction_validation_review.qmd`. Existing outputs and annotations were not regenerated.
- FM-03 verification: regression-first receipt tests and the synthetic runner integration test passed (`PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_forensics_categories.py::test_r_method_receipt_contract_has_truthful_outcomes tests/test_forensics_categories.py::test_numeric_runner_receipts_keep_means_only_trial_and_exclude_sprite_stub`); full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (48 tests); `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parsing of runner and receipt helper, and `git diff --check` passed. The synthetic run used only a temporary directory. R `scrutiny` is absent, so native package execution and Quarto rendering against generated numeric outputs remain unverified; no source-paper analysis was run.
- **FM-04:** Replaced the corrected Python/R weighted meta score with explicit category coverage and source-linked candidate screening signals. Missing-only category metrics are unavailable; failure and unsupported states remain unknown because the current category reports do not distinguish them. Candidate rows come only from existing flagged outputs and preserve source file/unit. Legacy formula reproduction now requires `--legacy-reproduction`, uses `legacy_composite_v1`, is labeled `NOT_INSPECT`, and writes into isolated `inputs/legacy/` and `reports/legacy/` paths. The meta report no longer renders an aggregate score or score plot.
- FM-04 migration: corrected defaults no longer write/read `meta_category_scores.csv`, `meta_overall_seed.csv`, `meta_category_scores_out.csv`, or `meta_overall_summary.csv`; those existing files are preserved. New artifacts use explicit versions: `category_summaries_v2_raw.csv`, `category_coverage_v1_raw.csv`, `candidate_concerns_v1_raw.csv`, `meta_evidence_coverage_v1.csv`, `meta_candidate_concerns_v1.csv`, `meta_evidence_coverage_v1_out.csv`, `meta_candidate_concerns_v1_out.csv`, and `meta_coverage_summary_v1.csv`. The corrected report is `<study>_meta_audit_v2.pdf`; prior source summaries and PDF remain untouched. Legacy mode alone emits the deprecated composite artifacts under `legacy/`.
- FM-04 verification: regression-first coverage and missingness tests, candidate source-link extraction/build tests, direct corrected R runner test, and explicit Python→R legacy fixture reproduction passed. Full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (52 tests); `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parse, Python byte-compilation, and `git diff --check` passed. All execution used synthetic temporary fixtures; no real category reports were processed and no Quarto render was run.
- **FM-05:** Each forensics or private manuscript-review execution now gets a fresh `forensics_run_v1` directory, input/config fingerprints, stage statuses, and SHA-256 artifact receipts. The category runner fingerprints only selected-stage sources; missing optional inputs are recorded as unavailable. Extraction and report rendering are separate opt-ins, network access is off unless `--allow-network` is explicit, and `--offline` overrides it. Help/dry-run are output-free; numeric-only runs extract the baseline table without invoking simdistr or Quarto; category aggregation validates active-run inputs, stage receipts, artifact hashes, and report-root ownership. Shared human manifests are not updated by these runners. Historical meta report layout is available only with `extract_meta.py --legacy-layout`; it cannot be combined with a run manifest.
- FM-05 affected outputs: new run directories under `data/processed/forensics_runs/<study>/<run-id>/` (or the explicit repository-contained `--output-root`), including `run_manifest.json`, `processed/`, and `reports/`; private manuscript review outputs are similarly isolated under `data/processed/reviews/<study>/<run-id>/`. Existing shared outputs and human annotations were not regenerated.
- FM-05 verification: run/input-isolation and run-scoped digitizer path checks passed; `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (59 tests); scoped Ruff check and format check, `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh`, Python byte-compilation of changed entrypoints/modules, and `git diff --check` passed. The no-network transport stub, output-free help/dry-run, and private-review dry-run tests passed. No source-paper analysis or Quarto render was run. Native `scrutiny` package execution remains unavailable, so FM-12 is not qualified.
- **FM-06 implementation:** Reported variable tests now have separate `reported_test_v1` records with stable IDs, parent-variable links, raw P text/comparator, and unknown scope/method/tail/population left explicit. Recalculated one-versus-rest rows use stable IDs and canonical ordering, but no reported-versus-recalculated difference flag is emitted when test definitions are unknown. Inferential Pearson/simdistr outputs require explicit `unrestricted_individual_1to1` design plus expert opt-in; simdistr also requires a seed and source-reported percentage precision. Unknown dependence keeps pooled outputs descriptive and uncalibrated. A separate fixed-block-4 arithmetic result accepts only explicit randomized counts for one unstratified list; post-exclusion counts and multiple strata are unsupported.
- FM-06 affected-output map: input artifacts are versioned as `csf_input_v2.csv`, `reported_tests_v1.csv`, and `simdistr_input_v2.csv`; R outputs are `row_level_results_v2.csv`, `reported_test_records_v1.csv`, `pooled_descriptive_v2.csv`, `allocation_arithmetic_v1.csv`, `randomization_run_receipt_v1.csv`, `simdistr_variable_pvalues_v1.csv`, and `simdistr_combined_descriptive_v1.csv` (plus `simdistr_runtime_input_v1.csv` and raw stdout only when explicitly opted in with source precision). Older unversioned files and reports remain untouched in prior run directories.
- FM-06 verification: `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (64 tests), including the production R runner integration for three-level tests, MRN-parity gating, valid incomplete blocks, post-exclusion rejection, multiple-strata rejection, seed receipt, and precision preservation. `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parsing, `bash -n scripts/run_pipeline.sh`, and `git diff --check` passed. Synthetic Quarto HTML and PDF smoke renders passed using temporary inputs; no source-paper analysis ran. **The simdistr package is not installed**, so actual seeded simdistr numerical reproducibility remains open; no install or network request was made.

### Open gates and next work
- FM-01 through FM-05 are complete. FM-06 implementation is in place, with its simdistr reproducibility gate open; FM-07 through FM-12 remain open; FM-13 remains deferred.
- R 4.6.0, Quarto 1.9.37, `readr`, and `dplyr` are installed. R package `scrutiny` is unavailable, so package-native method execution and the assembled release gate remain unverified.
- The audit commit `30b3fc2c9ba11b0a89e62f911043f2ca2ab5917a` is absent from the local object database. Work continues from clean current head `805cb282ed0f9f974f5d977592bbf95b419fd022`; no reset or fetch was performed.
- The disposable baseline worktree passed 39 pytest tests, Ruff check, and Ruff format check using the existing local Python environment. Offline `uv run --frozen pytest -q` could not provision uncached `ruff==0.15.0`; network access is prohibited by the packet.

## 2026-09-24 README-13 documentation check

This check used default `main@805cb282ed0f9f974f5d977592bbf95b419fd022`
and existing README PR #4 at `298c80c82ffc02738799adeb9aa1129ba63da4f1`
in an isolated checkout. On 2026-09-24 MDT, `uv sync --locked` and
`uv run --frozen pytest -q tests/test_pipeline.py` completed with one passing
four-row fake-CSV test under CPython 3.14.4. The uv cache and Python installation
directory were redirected to isolated scratch; no study source PDF, registry,
private manuscript, R method, or Quarto report was opened or run. This checks
the Python fixture path only. The former README's R 4.5.x testing statement
has no retained runtime receipt here, and this documentation check did not
qualify an R, Quarto, PDF, or optional-package environment. Source findings
and status interpretation remain subject to the contracts below.

## Current state
- Multi-category forensic scaffold is implemented and runnable through a single pipeline entrypoint.
- A separate private manuscript-review path exists for nonrandomized prediction-validation reviews.
- Public trial runs can now be selected with `bash scripts/run_pipeline.sh --study-id <study_id> ...` using configs under `config/studies/`.

## What changed
- Added shared manifest helper and category modules:
  - `src/research_project/forensics_manifest.py`
  - `src/research_project/numeric_integrity.py`
  - `src/research_project/registration_forensics.py`
  - `src/research_project/visual_forensics.py`
  - `src/research_project/transparency.py`
  - `src/research_project/meta_forensics.py`
- Added category scripts (`extract -> build -> run`) and manifest updater:
  - `scripts/extract_numeric.py`, `scripts/build_numeric_inputs.py`, `scripts/run_numeric_forensics.R`
  - `scripts/extract_registration.py`, `scripts/build_registration_inputs.py`, `scripts/run_registration_forensics.R`
  - `scripts/extract_visual.py`, `scripts/build_visual_inputs.py`, `scripts/run_visual_forensics.R`
  - `scripts/extract_transparency.py`, `scripts/build_transparency_inputs.py`, `scripts/run_transparency_forensics.R`
  - `scripts/extract_meta.py`, `scripts/build_meta_inputs.py`, `scripts/run_meta_forensics.R`
  - `scripts/mark_forensics_ready.py`
- Added plot-digitization pilot workflow:
  - `scripts/init_plot_digitization_targets.py`
  - `scripts/run_plot_digitization.R`
  - target manifest contract under `data/raw/figures/<study>/plot_digitization_targets.csv`
  - standardized digitized-point input `data/processed/visual/<study>/inputs/plot_digitized_values.csv`
- Extended orchestration:
  - `scripts/run_pipeline.sh` now supports `--forensics randomization,numeric,registration,visual,transparency,meta`, `all`, and optional `--digitize-plots true|false`.
- Added PDF report notebooks:
  - `notebooks/lungtime_numeric_audit.qmd`
  - `notebooks/lungtime_registration_audit.qmd`
  - `notebooks/lungtime_visual_audit.qmd`
  - `notebooks/lungtime_transparency_audit.qmd`
  - `notebooks/lungtime_meta_audit.qmd`
- Added tests for new core logic:
  - `tests/test_forensics_categories.py`
- Deepened numeric forensics execution:
  - `scripts/extract_numeric.py` now emits `statcheck_text.txt` from report PDF text.
  - `scripts/run_numeric_forensics.R` now runs package-native `scrutiny` methods (`grim_map`, `grimmer_map`, `debit_map`, duplicate checks, rounding-bias checks) and `statcheck::statcheck` when installed.
  - Numeric outputs now include package raw tables, audits, and `numeric_standardized_results.csv`.
- Updated docs/contracts:
  - `README.md`, `docs/CREDIBILITY_CRITERIA.md`, `docs/DECISIONS.md`
- Added a ScienceVerse-informed transparency layer:
  - `research_object_lite.json` records source PDFs, file hashes, text refs, URLs, open-practice evidence, repository/preregistration links, and offline provenance.
  - v1 is offline by default with no LLM calls, no live repository/citation-risk API checks, and no direct `metacheck` dependency.
  - software-use and package/vendor documentation links are provenance context, not open-code evidence unless paired with explicit code/script availability language.
  - meta aggregation now exposes `evidence_burden_score` and `review_priority` while preserving `overall_score` and `risk_tier` for compatibility.
- Added study-config-driven public trial support:
  - `config/studies/lungtime.sh`
  - `config/studies/pronto.sh`
  - staged PRONTO source PDFs under `data/raw/studies/pronto/`
  - `scripts/run_pipeline.sh` now accepts `--study-id <study_id>`
  - public report renders now land in `reports/<category>/<study_id>/`
  - `src/research_project/randomization.py` now parses both original Table 1 layouts and supplement-style hierarchical baseline tables
  - `src/research_project/registration_forensics.py` now recognizes `ISRCTN` and UK trial phrasing (`randomisation`, `masked`, `open-label`)

## How to reproduce
```bash
# from repo root
uv sync
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh
bash scripts/run_pipeline.sh --study-id pronto --forensics all
bash scripts/run_pipeline.sh --forensics visual
bash scripts/run_pipeline.sh --forensics visual --digitize-plots false
quarto render notebooks/lungtime_visual_audit.qmd --to pdf
```

## What I verified
- `uv run ruff check .` passes.
- `uv run ruff format . --check` passes.
- `uv run pytest -q` passes.
- `uv run pytest -q tests/test_transparency.py tests/test_forensics_categories.py` passes.
- `bash scripts/run_pipeline.sh --forensics transparency` passes and renders transparency PDF.
- `bash scripts/run_pipeline.sh --forensics all` passes.
- `bash scripts/run_pipeline.sh` passes.
- `bash scripts/run_pipeline.sh --study-id pronto --forensics all` passes.
- `bash scripts/run_pipeline.sh --forensics visual` passes and renders visual PDF.
- `bash scripts/run_pipeline.sh --forensics visual --digitize-plots false` passes and remains non-interactive.
- `quarto render notebooks/lungtime_visual_audit.qmd --to pdf` passes.

## What remains / next steps
- Deepen package-native execution for `scrutiny`, `rsprite2`, `statcheck`, `metafor`, and `meta` once assumptions/parameter policies are locked.
- Implement package-native `rsprite2` execution (currently stub metric only) once method assumptions are fixed.
- Expand plot digitization beyond pilot one-figure target and add dual-rater concordance checks.
- Add fixture-based integration tests for each category CLI.

## Gotchas
- The public `scripts/run_pipeline.sh` entrypoint runs Python stages through `uv run python`; run `uv sync` first so declared PDF dependencies are available.
- Visual caption extraction can be sparse depending on PDF text quality; empty extraction is handled and still produces schema-valid outputs.
- Plot digitization is intentionally human-in-loop: it runs only when `--digitize-plots true` is set, and requires local figure image files matching the target manifest.

## 2026-03-19 manuscript-review addition

### What changed
- Added a nonrandomized manuscript-review path for prediction-model validation papers:
  - `src/research_project/prediction_review.py`
  - `scripts/extract_prediction_review.py`
  - `scripts/build_prediction_review_inputs.py`
  - `scripts/run_prediction_review_forensics.R`
  - `scripts/run_manuscript_review.sh`
  - `notebooks/prediction_validation_review.qmd`
- Review inputs and outputs are local-only artifacts under:
  - `data/processed/reviews/<study>/`
  - `reports/reviews/<study>/`
  - `reports/reviews/<study>/<study>_prediction_validation_review.pdf`
  - `notebooks/reports/<study>/` (local rerender byproduct only)
  - these paths are gitignored and should not be used for sharing source-manuscript contents
- Added focused unit coverage:
  - `tests/test_prediction_review.py`
- Updated docs:
  - `README.md`
  - `docs/DECISIONS.md`

### What was verified
- `uv run ruff check .`
- `uv run ruff format . --check`
- `uv run pytest -q`
- `PYTHONPATH="$PWD/src" python3 scripts/extract_prediction_review.py --report "<local_pdf>" --study-id <study_id> --review-type prediction_validation --out "$PWD/data/processed/reviews/<study_id>"`
- `PYTHONPATH="$PWD/src" python3 scripts/build_prediction_review_inputs.py --in "$PWD/data/processed/reviews/<study_id>" --out "$PWD/data/processed/reviews/<study_id>"`
- `bash scripts/run_manuscript_review.sh --study-id <study_id> --report "<local_pdf>" --review-type prediction_validation`
  - analytic stages completed
  - sandboxed Quarto render failed on `sysctl ... Operation not permitted`
- `quarto render notebooks/prediction_validation_review.qmd --to pdf --output-dir "$PWD/reports/reviews/<study_id>"`
- `PYTHONPATH="$PWD/src" python3 scripts/mark_forensics_ready.py --study-id <study_id> --category review_prediction_validation --source-pdf <local_pdf_name> --extract-confidence medium --page-ref "table2|table3|tablee2|figure1" --table-ref prediction_validation_review --ready`

### Privacy / sharing note
- Do not store manuscript-specific findings, source file names, or transcribed source statistics in tracked docs.
- Keep those outputs confined to the gitignored review artifact paths above.

### Gotchas
- The new manuscript-review scripts also use system `python3` so they can reuse the user-level PDF libraries already present on this machine.
- In sandboxed environments, `quarto render` may fail on an architecture probe; rerun the render outside the sandbox if the analysis files already exist and only PDF generation failed.

## 2026-04-21 ClinicalTrials.gov registration audit addition

### What changed
- Added ClinicalTrials.gov registry-aware registration screening:
  - `src/research_project/clinicaltrials_registry.py`
  - expanded `scripts/extract_registration.py` CLI inputs for NCT IDs, local current-record JSON, optional history files, publication identifiers, network control, and explicit as-of date
  - updated `scripts/build_registration_inputs.py` to prefer `registration_claims_expanded.csv` while preserving legacy claim compatibility
  - updated `scripts/run_registration_forensics.R` to summarize only assessed claims for mismatch rates and to copy registry-history events into report outputs
  - updated `scripts/run_pipeline.sh` to pass optional registry config fields and to run registration Python scripts through `uv run python`
- Added optional study-config fields in `config/studies/*.sh`:
  - `REGISTRY_ID`, `REGISTRY_URL`, `REGISTRY_CURRENT_REL_PATH`, `REGISTRY_HISTORY_REL_PATH`, `REGISTRY_ALLOW_NETWORK`, `REGISTRY_AS_OF_DATE`, `PUBLICATION_URL`, `PUBLICATION_DOI`, `PUBLICATION_PMID`
- Added registration report sections for registry source metadata, current-record claims, history events, and interpretation labels.
- Added `pypdf` to Python dependencies because registration extraction already required it but it was not declared in `pyproject.toml`.

### New outputs
- `data/processed/registration/<study>/inputs/registration_claims_expanded.csv`
- `data/processed/registration/<study>/inputs/registration_registry_current.csv`
- `data/processed/registration/<study>/inputs/registration_registry_current.json`
- `data/processed/registration/<study>/metadata/registration_registry_fetch_metadata.csv`
- `reports/registration/<study>/registration_history_events.csv`

### What I verified
```bash
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh --forensics registration
quarto render notebooks/lungtime_registration_audit.qmd --to pdf
```

### Notes
- Tests use local fixtures only and do not require live ClinicalTrials.gov network access.
- Normal pipeline runs may fetch ClinicalTrials.gov API v2 current records when a unique NCT ID is available and `REGISTRY_ALLOW_NETWORK="true"`.
- Registry history is local-input only for now; no stable live history endpoint is assumed.

### 2026-04-21 review-fix follow-up
- Fixed ClinicalTrials.gov helper missing-value handling so CSV blanks do not become literal `nan` strings in claims or history comparisons.
- Changed missing local registry-history files to informational sentinel rows and updated the R summary to count only substantive `value_changed` medium/high events as major history changes.
- Changed partial registry-date adjudication to interval-based logic for prospective-registration and results-overdue screens.
- Added unit tests covering missing values, missing history files, partial registration dates, and partial primary-completion dates.

## 2026-06-05 public pipeline Python environment stabilization

### What changed
- Added `pdfplumber` to declared Python dependencies because existing randomization and numeric-summary extraction already import it.
- Changed the public `scripts/run_pipeline.sh` Python stages to run through `uv run python` instead of system `python3`.
- Updated PDF dependency error messages to direct users to `uv sync`.
- Left `scripts/run_manuscript_review.sh` on system `python3` as a deliberately separate follow-up scope.

### What to verify
```bash
uv sync
uv run python -c "import pandas, pypdf, pdfplumber"
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh --forensics transparency
bash scripts/run_pipeline.sh --forensics all
```

## 2026-09-25 INSPECT-SR packet progress: FM-07

### Completed in this ticket
- Added v2 source claim records that carry the matched statement, page, explicit negation, population, and masking role through expanded claims. Allocation ratios now require nearby allocation/randomization context, so a time such as `12:30` is not extracted as an allocation ratio.
- Kept treatment, participant, care-provider, and outcome-assessor masking claims separate. Unmentioned or ambiguous evidence remains indeterminate.
- Added exact-byte SHA-256 and source-version status to current-registry fetch metadata; retain the exact bytes in `registration_registry_current_raw.json` alongside normalized JSON. Local JSON is explicitly labeled with unverified upstream version.
- Distinguished documented HTTP 404 from fetch failure and changed direct extraction to require explicit network opt-in.
- Normalized first-submitted, first-posted, registered-start/type, and actual recruitment-start dates separately. Prospective timing, the 365-day results-posting heuristic, and publication linkage are reported as metadata screens, never mismatch judgments.
- Separated history status from detected change events. Missing, malformed, undated, unchanged, and interval-overlapping sources do not generate synthetic changes. Receipts include source hash, date counts, chronology, detected events, and unknown completeness.
- Changed mismatch flags to three-state values; only `match`/`mismatch` contribute to the assessed denominator. Updated `notebooks/lungtime_registration_audit.qmd` to explain and display the v2 evidence and status fields.
- Updated tests in `tests/test_clinicaltrials_registry.py`, `tests/test_registration_forensics.py`, and `tests/test_forensics_categories.py`.

### Verification receipts
- `PYTHONPATH=src .venv/bin/python -m pytest -q` — passed (full suite).
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — passed (41 files already formatted at last check).
- `git diff --check` — passed.
- `Rscript -e 'invisible(parse(file="scripts/run_registration_forensics.R"))'` — passed.
- Synthetic R runner integration — passed: assessed denominator 2, mismatch count 1, unassessed mismatch flag remained NA; screen and history statuses survived into the summary.
- Synthetic Quarto report render — HTML and PDF both passed using temporary `fm07_fixture` data, removed after rendering. The initial HTML invocation used an unsupported `--output-file` option; retry with `--output` passed.
- `bash -n scripts/run_pipeline.sh` and Python `py_compile` for changed helpers — passed.
- No live registry request or source-paper analysis was run. HTTP 404 coverage uses a mocked transport. No dependencies were added.

### Open gates and next work
- FM-07 is complete and committed after final verification.
- FM-06 still has an open seeded `simdistr` numerical-reproducibility gate because `simdistr` is unavailable locally; no installation/network access was attempted. The API gate itself safely reports the dependency as missing.
- Continue with FM-08 next, following the packet dependency order. Do not call the packet integrated until FM-12 and native R/report verification are complete.

## Historical checkpoint (superseded): INSPECT-SR snapshot blocker

- **FM-08 open:** No implementation edits made. The ticket requires exact official v1.1.2 check wording, an immutable snapshot/hash, retrieval date, citation, and license/terms. The supplied ZIP has no guidance snapshot; its `SOURCES.md` only points to the live site and changelog. The local FM-08 target paths do not exist.
- **Network boundary:** User instruction requires explicit opt-in before network or interactive work. No retrieval was attempted and no check wording or hash was fabricated.
- **Action to unblock:** Provide the exact v1.1.2 snapshot and license/terms locally, or explicitly opt in to retrieving them. Resume FM-08 only after the exact content and hash can be verified.
- **FM-09, FM-10, FM-11 open:** Not implemented because their declared dependencies require FM-08, then FM-09, then FM-10. Building those records without a frozen catalogue would violate the packet contract.
- **Verification:** Read FM-08 and FM-09 through FM-11 tickets, FM-08 shared contract, source register, and the source files explicitly named by FM-08. No tests were run for these blocked tickets because no code changed.
- **Next after unblock:** FM-08 catalogue/records; FM-09 evidence mapping/manual routes; FM-10 independent review/adjudication; FM-11 report/synthesis export; then FM-12 integration/release gate. FM-13 remains optional/deferred.
