# Decisions (architecture + scientific choices)

## 2026-09-25: Repair INSPECT-SR review provenance and native result acceptance

- **Decision:** A private `inspect_sr_source_snapshot_v1` now binds one assessment to versioned source records and evidence records and rechecks the source bytes at review time. The local CLI creates and stores the manifest before reviewer submission. Finalized reports and actionable synthesis exports resolve the complete stored two-reviewer, adjudication, and finalization chain. A caller-supplied hash alone cannot establish currency. Human records remain append-only and private.
- **Identity and migration:** Reviewer submissions, adjudications, resolved reviews, and finalizations advance to v3 content identities. The assessment validator now checks its trial/guidance identity. Newly prepared local source versions use v2 with a private source path for byte rechecks. `method_receipt_v4` requires method-specific output fields and reconciliation of returned case/group identities before a completed no-finding state; `inspect_sr_synthesis_export_v3` requires a verified review chain. Older v1/v2/v3 records remain historical; no automatic upgrade or human-response conversion is performed.
- **Affected outputs:** New local private `snapshots/<sha256>.json`, `source-versions-v2/`, v3 human records, and `reports/<assessment-id>/<revision>/` models/HTML/PDF. New numeric runs write v4 `numeric_method_receipts.csv`; candidate mapping and run manifests require v4. New synthesis exports use v3. Historical run directories, source files, annotations, and `run-b2.html` are unchanged.
- **Report candidate acceptance:** Current report models advance to `inspect_sr_report_model_v2`. Candidate records must have a supported check route, exact source evidence and locator, and one same-run evaluated v4 receipt whose input IDs include that evidence; coverage is derived from validated receipts. Previously generated v1 report models remain historical artifacts and are not silently promoted to v2.
- **Execution boundaries:** CSV input retains printed text, leading-zero identifiers, and literal `NA`. Duplicate source filenames are unresolved unless a persistent source ID selects one. Optional scrutiny sequence diagnostics fail closed at the direct R entrypoint. Public payloads remain explicitly allowlisted, with approver identity only in a private approval record. No new dependency or scientific threshold was introduced.
- **Open scientific decision:** The current rounding-bias wrapper passes already printed values to `scrutiny::rounding_bias` using the same decimal precision. The package computes `reround(x, digits) - x`; synthetic printed values therefore yield zero by construction. Independent qualification of that default method remains open pending an approved input/method contract. Do not interpret its current no-finding result as evidence that original unrounded measurements were free of rounding bias.
- **Verification:** Regressions were written before the CSV/path/source and receipt fixes. Exact final test, render, and hosted CI receipts are recorded in `docs/HANDOFF.md`; FM-12 remains open until those lanes and the rounding-bias decision are resolved.

## 2026-09-25: Bind native numeric results to run and source evidence (FM-04/FM-05 repair)
- **Decision:** The numeric R runner accepts the active manifest `--run-id`, preserves its historical standardized CSV, and additionally writes `numeric_standardized_results_v2.csv` with a run-scoped result identity, exact source locator where available, and source evidence IDs. Numeric evidence identity is derived from a source-version SHA-256, exact locator, extracted raw value, and parser revision. If any source identity, raw value, or locator is missing, the record remains unresolved. Candidate mapping requires the v2 result contract and verifies evidence IDs against both the method receipt and source evidence content.
- **Context:** Earlier results exposed ordinal `case_id` values without a durable source identity, and the R runner generated a receipt run ID unrelated to the manifest. Candidate mapping checked that an evidence ID existed but not that the method had evaluated it.
- **Output impact and migration:** New runs add `metadata/source_versions.json`, `metadata/source_evidence.json`, and `numeric_standardized_results_v2.csv`; receipt schema is `method_receipt_v3`. The legacy standardized CSV remains unchanged for historical/compatibility consumers. No old ordinal case ID is promoted to evidence identity.
- **Verification:** Synthetic pinned-package integration passes a producer-to-candidate path and confirms run IDs, evidence membership, and exact locators. Missing-locator and missing-source cases remain unresolved. No source-paper analysis was run.

## 2026-09-25: Bind human review records to immutable identities (FM-10/FM-11 repair)
- **Decision:** Reviewer submissions, adjudications, resolved reviews, finalizations, and synthesis exports advance to v2 where identity or privacy validation changed. Submission/finalization content hashes are revalidated; resolved finalization preserves its resolved-review, both reviewer-submission, and adjudication IDs. Altered, incomplete, or stale finalizations cannot produce synthesis dispositions. Public export payloads omit reviewer/approver identity; the CLI stores its explicit approval identity in a separate private receipt.
- **Context:** Mutated review content could retain the old ID, finalization discarded adjudication provenance, and public exports serialized `public_reviewed_by`.
- **Workflow:** `scripts/inspect_sr.py` provides local-only preparation, evidence, independent review, adjudication, finalization, validation, candidate mapping, rendering, and explicitly allowlisted export. Human records are write-once under ignored `data/private/inspect_sr/`.
- **Verification:** Synthetic identity-tamper, adjudication-preservation, pending-check, privacy-canary, and CLI candidate-path tests pass. No public export or author contact was performed.

## 2026-09-25: Require complete method receipt accounting (FM-03 repair)
- **Decision:** Current native outputs use `method_receipt_v3`. A completed receipt requires every eligible evaluation unit to be evaluated with no failures; a partial receipt requires evaluated and failed counts to account for every eligible unit. Invalid or unknown statcheck result schemas fail, while a valid empty logical result schema means the report text was evaluated without a finding. Missing dependencies remain `dependency_missing`.
- **Context:** Receipt validation previously treated short output tables as complete, accepted unknown statcheck results, and allowed zero-row valid output to be confused with a missing package.
- **Output impact and migration:** Newly generated `numeric_method_receipts.csv` records use v3. Python candidate mapping and run manifests require v3; existing v2 files remain untouched and readable as historical data but are not implicitly promoted to current candidate evidence. Rounding-bias eligibility counts distinct eligible `(trial_id, digits_x)` groups; `n_input` continues to count input rows.
- **Verification:** Added R regressions for partial outputs without a `consistency` column, malformed statcheck types, missing dependencies, and valid empty statcheck results. A producer-path duplicate-group fixture reproduced incorrect completed/partial accounting before the fix. Pinned-package native verification is recorded in the active handoff after execution.

## 2026-09-25: Version negation-aware registry claim matching (FM-07 repair)
- **Decision:** Registry claim matching treats `non-`, `non`, `un`, and explicit negation before a matched term as indeterminate agreement. The expanded registry-claim schema advances to `registration_claims_v4`.
- **Context:** Substring matching incorrectly treated “non-randomized” and “nonrandomized” as a match to a registry value of `RANDOMIZED`.
- **Rationale:** Presence of a shared substring does not establish agreement when the source claim is negated. Source statements remain available for human interpretation.
- **Output impact:** New outputs from `legacy_claims_to_expanded` carry schema v4. Historical v3 files are unchanged and remain readable as historical records.
- **Verification:** New synthetic regressions for hyphenated, closed-form, and explicit negation failed before the fix and pass after it. No network retrieval or trial-paper analysis was used.

## 2026-09-25: Replace corrected meta composite with explicit evidence coverage
- **Date:** 2026-09-25
- **Decision:** The default meta workflow emits category coverage and source-linked screening-signal records. It does not normalize category metrics, impute missing values, combine them into a study score, assign a risk tier, or generate a judgment. The retired formula is available only with `--legacy-reproduction` and writes beneath isolated `legacy/` directories with schema `legacy_composite_v1` and label `NOT_INSPECT`.
- **Context:** The previous Python and R paths mapped missing values to reassuring constants and combined heterogeneous measures into a weighted tier; the randomization contribution used `1 - Fisher P`. Production R duplicated the scorer, so replacing one helper alone was insufficient.
- **Options considered:** Preserve the aggregate as a triage aid; replace it with a different score; or remove corrected-path scoring and report coverage plus source-linked signals.
- **Why this choice:** No calibrated composite is specified. Missing, failed, or unsupported evidence cannot be represented as reassuring, and candidate signals must remain visible without collapsing across categories.
- **Consequences / follow-ups:** Category extraction records report availability and retains source paths. Nonmissing summary metrics indicate evidence is present; missing category reports or all-missing metrics are unavailable. Existing sources do not reliably distinguish failed from unsupported categories, so both remain unknown. Existing flagged row results are passed as `screening_signal` records with their source file and unit. These are not INSPECT check responses or human judgments.
- **Methods/packages affected:** `src/research_project/meta_forensics.py`, `scripts/extract_meta.py`, `scripts/build_meta_inputs.py`, `scripts/run_meta_forensics.R`, `notebooks/lungtime_meta_audit.qmd`. No dependency was added.
- **Assumptions locked in:** Category-level assessment here means nonmetadata summary metrics are present; this is coverage, not method validity. Only preexisting explicit row flags are surfaced; the meta layer introduces no concern threshold.
- **Output impact and migration:** Corrected outputs are `category_summaries_v2_raw.csv`, `category_coverage_v1_raw.csv`, `candidate_concerns_v1_raw.csv`, `meta_evidence_coverage_v1.csv`, `meta_candidate_concerns_v1.csv`, `meta_evidence_coverage_v1_out.csv`, `meta_candidate_concerns_v1_out.csv`, and `meta_coverage_summary_v1.csv`; the report is versioned as `<study>_meta_audit_v2.pdf`. Prior `category_summaries_raw.csv`, `meta_category_scores*`, `meta_overall*`, and the old report PDF are deprecated in corrected mode and remain untouched on disk. Explicit legacy outputs move under `inputs/legacy/` and `reports/legacy/`; legacy scores and tiers are not consumed by corrected outputs or the report. The pipeline passes only explicitly requested categories; requesting `meta` alone does not force a category calculation.
- **Verification evidence:** Missing-only coverage, source-linked concerns, direct R corrected-run behavior, and a frozen legacy fixture were tested. Full Python tests, Ruff checks, R syntax parsing, and Python compilation passed. No category source-paper analyses or report render were run.

## 2026-09-25: Isolate forensic runs and separate pipeline stages (FM-05)
- **Decision:** Forensics and private manuscript-review runs use unique run directories with a manifest that records selected inputs, configuration, stage states, and output hashes. Extraction is the default; report rendering is opt-in. Network fetches require `--allow-network`, and `--offline` overrides that flag. Help and dry-run paths do not create outputs. Legacy nested meta-report lookup requires the explicit `--legacy-layout` option and is unavailable with run-manifest mode.
- **Context:** The previous orchestrator mixed preprocessing, method execution, diagnostics, and rendering in shared directories. It also required unrelated PDFs up front and could aggregate summaries from earlier executions.
- **Why this choice:** Run-scoped paths, input hashes, output receipts, and stage checks prevent stale cross-run aggregation while keeping method calculation independent of rendering. The private manuscript-review path remains independent of RCT category selection.
- **Consequences / follow-ups:** Runs are written beneath `data/processed/forensics_runs/<study>/<run-id>/` or `data/processed/reviews/<study>/<run-id>/`. Shared human manifests are not updated by these runners. Corrected meta extraction rejects source changes or availability changes and accepts only its active run's report tree. Network and report rendering now require per-run opt-in.
- **Methods/packages affected:** `scripts/run_pipeline.sh`, `scripts/run_manuscript_review.sh`, `scripts/extract_meta.py`, `scripts/extract_randomization_table1.py`, `src/research_project/run_manifest.py`, and `src/research_project/forensics_manifest.py`. No dependency was added.
- **Migration:** Prior shared outputs remain in place and are not overwritten. Consumers should read a run's own `processed/`, `reports/`, and `run_manifest.json`. `--legacy-layout` is an explicit read path for existing `reports/<category>/<study>/` files.
- **Verification evidence:** The regression for an input appearing after run initialization failed before the guard and passed after it. Full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (59 tests); scoped Ruff checks/format, shell syntax checks, changed Python byte-compilation, and `git diff --check` passed. Help/dry-run were verified output-free; the network-disabled transport stub and private-review dry-run passed. No source-paper analysis or Quarto render was run; FM-12 remains open pending native method/report integration gates.

## 2026-09-25: Gate baseline diagnostics by allocation design (FM-06)
- **Decision:** Separate reported variable-test records from recalculated level tests. Preserve one record per source P-value location, raw inequality, parent variable, and stable ID. Scope, method, tail, and analysis population remain `unknown` unless directly supplied; missing metadata prevents a computational comparison. One-versus-rest Pearson P values and `simdistr` require an explicit unstratified individual 1:1 design and expert opt-in. `simdistr` additionally requires a seed and source-reported percentage precision. Combined outputs are marked uncalibrated when variable dependence is unknown.
- **Allocation arithmetic:** The only supported allocation-count check is an unstratified single-list 1:1 fixed-block-of-four design. It requires explicit positive counts whose basis is randomized allocation, plus exactly one stratum and one list. Counts after post-randomization exclusions and multiple-stratum/list structures return unsupported status. This arithmetic record is separate from baseline hypothesis tests and does not produce a trustworthiness verdict.
- **Context:** The prior workflow repeated a variable-level P value across every categorical level, compared it with one-versus-rest Pearson tests, flagged absolute differences, pooled dependent P values, and ran `simdistr` with an invented three-decimal precision and no explicit seed/design.
- **Methods/packages affected:** `src/research_project/randomization.py`, `scripts/build_randomization_inputs.py`, `scripts/run_randomization_forensics.R`, `scripts/run_pipeline.sh`, and `notebooks/lungtime_randomization_audit.qmd`. No dependency was added.
- **Output impact and migration:** New inputs are `csf_input_v2.csv`, `reported_tests_v1.csv`, and `simdistr_input_v2.csv`. New run outputs are `row_level_results_v2.csv`, `reported_test_records_v1.csv`, `pooled_descriptive_v2.csv`, `allocation_arithmetic_v1.csv`, `randomization_run_receipt_v1.csv`, `simdistr_variable_pvalues_v1.csv`, and `simdistr_combined_descriptive_v1.csv`. The optional package input is `simdistr_runtime_input_v1.csv`. Earlier unversioned outputs and reports in old run directories are not rewritten.
- **Verification evidence:** Regression-first tests cover a multilevel factor, repeated and distinct source P-value rows, inequality preservation, canonical row-order stability, explicit design gating, fixed-block incomplete counts, post-exclusion/multiple-strata rejection, seed receipt, and no manufactured percentage precision. `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (64 tests); scoped Ruff check and format, R syntax parsing, `bash -n scripts/run_pipeline.sh`, and `git diff --check` passed. Synthetic Quarto HTML and PDF renders passed using temporary inputs. R package `simdistr` is unavailable; the runner records `dependency_missing`, and same-seed package-native numerical reproducibility remains unverified. No source-paper analysis or dependency installation was performed.

## 2026-09-25: Distinguish numeric-method execution receipts from findings
- **Date:** 2026-09-25
- **Decision:** Emit one `method_receipt_v1` row per numeric method and optional sequence check. A completed no-finding result requires positive evaluated coverage; missing dependencies, blocked inputs, failures, partial runs, unrequested methods, and unimplemented methods remain distinct. Package probability is descriptive metadata, not an inferential p-value. SPRITE candidate arm differences remain descriptive until a method is implemented.
- **Context:** The numeric runner previously conflated package availability with execution, marked caught errors as available, treated an empty output table ambiguously, mapped GRIM probability to `p_value`, and generated anomaly flags from a fixed SPRITE placeholder threshold. Trial identity was also taken from the first categorical count-percent row.
- **Options considered:** Keep package-status notes and infer execution from table emptiness; or add explicit method-level receipts and preserve non-executed evidence separately.
- **Why this choice:** Method eligibility, execution coverage, findings, and human judgments need independent records. A missing or failed method must not be interpreted as a negative result.
- **Consequences / follow-ups:** `numeric_method_receipts.csv` is the execution record; `numeric_package_status.csv` is compatibility metadata only. `numeric_descriptive_arm_differences.csv` contains SPRITE candidate inputs without anomaly/severity fields. The lungtime numeric report requires receipts; the prediction-validation report displays them when present and labels their absence as unverified. Existing human annotations and stored historical outputs were not regenerated.
- **Methods/packages affected:** Numeric `scrutiny` methods, optional scrutiny sequence methods, `statcheck`, and unimplemented `rsprite2`/SPRITE path. No dependency or scientific threshold was added.
- **Assumptions locked in:** Statcheck evaluates the report text as one unit; each package map evaluates summary cases; duplicate checks evaluate summary cases; rounding-bias checks evaluate trial-by-precision groups. `not_implemented` means applicability is unknown; it does not mean ineligible.
- **Output impact:** Adds `numeric_method_receipts.csv` and `numeric_descriptive_arm_differences.csv`; changes `numeric_standardized_results.csv` by adding case IDs and removing fabricated SPRITE findings, and leaves package probabilities out of `p_value`; unavailable GRIM-family counts in `numeric_summary.csv` remain missing rather than zero. These versioned runner outputs are newly generated; historical files remain immutable.
- **Verification evidence:** Regression-first tests in `tests/test_forensics_categories.py`; synthetic execution of `scripts/run_numeric_forensics.R` wrote outputs only under a temporary directory. Full pytest and Ruff checks passed; R syntax parsing passed. The `scrutiny` package is not installed, so package-native execution and report rendering against generated package outputs remain open integration gates.

## 2026-09-25: Gate GRIM, GRIMMER, and DEBIT by documented summary semantics
- **Date:** 2026-09-25
- **Decision:** Introduce numeric eligibility method revision `numeric_eligibility_v2`; retain baseline medians as median observations and exclude them from GRIM/GRIMMER/DEBIT. Eligibility requires explicit statistic kind, supported measurement scale, raw status, unweighted analysis, matching analysis n, documented non-imputation/transformation status, and evidence. DEBIT additionally requires an explicitly Bernoulli scale.
- **Context:** Existing code routed continuous median/range observations to GRIM and treated bounded values as binary based on their numeric range.
- **Options considered:** Continue inferring semantics from numeric ranges; or fail closed when extraction metadata does not establish method applicability.
- **Why this choice:** Numeric values alone do not establish the statistic or measurement scale required by these methods. Unknown legacy metadata therefore remains unevaluated.
- **Consequences / follow-ups:** Existing stored study outputs are immutable and are not rewritten. New generated scrutiny cases and method inputs carry method revision and eligibility metadata. Missing metadata maps to method-specific ineligibility reasons and null method findings; it does not create an INSPECT response or study judgment.
- **Methods/packages affected:** Python numeric input builders; R `scrutiny::grim_map`, `grimmer_map`, and `debit_map` entry points.
- **Assumptions locked in:** Arithmetic mean means an explicitly reported arithmetic mean; `integer_valued` and `bernoulli` require source evidence. A granularity adjustment is accepted only when explicitly documented. No new transformation formula is introduced.
- **Output impact:** Affected generated artifacts are `scrutiny_input.csv`, `scrutiny_cases.csv`, and method-specific `scrutiny_{grim,grimmer,debit}_input.csv`; each case now includes `numeric_eligibility_v2` and per-method eligibility reasons. Historical reports and raw extraction records are unchanged.
- **Verification evidence:** Failing regressions were recorded before the fix. `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (41 tests); `ruff check .` and `ruff format . --check` passed; R script syntax parsing passed. The direct R eligibility-boundary regression passed. R 4.6.0 and `readr`/`dplyr` were available; `scrutiny` was not installed, so package-native method execution was not tested.

## 2026-09-25: Preserve numeric source text and require denominator context
- **Date:** 2026-09-25
- **Decision:** Advance numeric methods to `numeric_eligibility_precision_v3`. Preserve source cells, raw statistic/count/percentage strings, printed decimals, P-value text/comparator, and source locators through Python and R CSV boundaries. Reject nonfinite or noninteger n/count inputs instead of rounding. Percentage compatibility requires an explicit denominator role, unweighted data, and one of the implemented rounding conventions (`nearest_half_up`, `nearest_half_even`, or `truncate`); otherwise report `indeterminate`.
- **Context:** Earlier numeric I/O stripped trailing zeros, rounded malformed n/count values, clipped P values, and used a fixed percentage-difference threshold as a finding.
- **Options considered:** Continue applying a tolerance to parsed floats; or retain the printed representation and compare only when data and reporting conventions are established.
- **Why this choice:** The source alone often does not say whether a table denominator is randomized, observed at a time point, or analyzed, and may omit its rounding convention. Those cases cannot support a compatibility verdict.
- **Consequences / follow-ups:** `abs_percent_delta` remains only as descriptive legacy metadata; the old `0.2` flag is retained under a legacy name and is not used as a finding. Existing raw inputs and stored reports remain unchanged. Current extraction defaults leave denominator role and rounding convention unknown, so the existing public trial outputs are indeterminate until source evidence explicitly resolves them.
- **Methods/packages affected:** `randomization.py` Table 1 parsing; Python numeric builders; R numeric CSV readers and method eligibility validation.
- **Assumptions locked in:** Only explicitly supported integer counts and positive integer denominators reach numeric method builders. `P<...` is stored as its displayed threshold plus the `<` comparator; no inequality is rewritten as equality in source records. Scientific notation in method-bound summary text is unsupported.
- **Output impact:** New generated extraction/summary records carry `raw_value`, `raw_count`, `raw_statistic_value`, `reported_decimals`, `reported_percent_raw`, `reported_p_raw`, `reported_p_comparator`, `source_locator`, `denominator_role`, `rounding_convention`, `compatibility_status`, and `input_status`. Method inputs carry the raw provenance fields and use `numeric_eligibility_precision_v3`. Historical CSVs and reports are not rewritten.
- **Verification evidence:** `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (46 collected); `ruff check .`, `ruff format . --check`, and R syntax parsing passed. Python→readr→Python round-trip retained `1.20` versus `1.2`, and R boundary tests rejected noninteger n and mismatched printed precision. R package `scrutiny` remains unavailable; package-native methods were not run.

Record decisions that affect reproducibility and interpretation.

## Template
- **Date:** YYYY-MM-DD
- **Decision:** (what was chosen)
- **Context:**
- **Options considered:**
- **Why this choice:**
- **Consequences / follow-ups:**
- **Methods/packages affected:** (R package names + versions)
- **Assumptions locked in:** (effect size model, priors, exclusion rules, etc.)
- **Output impact:** (which tables/figures/reports change)
- **Verification evidence:** (tests, diagnostics, or sensitivity checks run)

## 2026-02-06: Multi-category forensic scaffolding
- **Date:** 2026-02-06
- **Decision:** Add five forensic categories to a shared `extract -> build -> run -> report` pipeline pattern (`randomization`, `numeric`, `registration`, `visual`, `meta`) and add a shared manifest contract.
- **Context:** The repository started with randomization forensics only. The project roadmap requires broader Heathers-aligned forensic coverage and a single orchestration flag.
- **Options considered:**
  - Keep randomization-only and add categories ad hoc later.
  - Implement all category scaffolds now with package-optional hooks.
- **Why this choice:** It establishes deterministic interfaces and output locations now, while preserving flexibility for later method depth.
- **Consequences / follow-ups:** Category methods currently prioritize deterministic baseline checks and package-ready inputs. Future work should deepen package-native execution where scientific assumptions are pre-specified.
- **Methods/packages affected:** `simdistr` (existing), package-ready stubs for `scrutiny`, `rsprite2`, `statcheck`; meta aggregation consumes summary metrics.
- **Assumptions locked in:** All category reports render as PDF; anomaly scores are screen-level diagnostics, not definitive misconduct claims.
- **Output impact:** New outputs under `data/processed/<category>/<study>/`, `reports/<category>/<study>/`, and `data/processed/manifests/<study>/forensics_manifest.csv`.
- **Verification evidence:** `uv run ruff check .`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics randomization,numeric,registration,visual,meta`.

## 2026-06-05: Add ScienceVerse-informed transparency layer
- **Date:** 2026-06-05
- **Decision:** Add a `transparency` category that creates a repo-owned `research_object_lite.json` and offline transparency evidence tables inspired by the ScienceVerse/MetaCheck research-object and module pattern.
- **Context:** ScienceVerse/MetaCheck provides a mature conceptual frame for machine-readable research descriptions and best-practice checks, but the public `metacheck` package is experimental, AGPL-licensed, broad in dependencies, and not needed for a deterministic v1 adapter.
- **Options considered:**
  - Add `metacheck` as a direct R dependency.
  - Borrow only the conceptual model in docs.
  - Add a narrow offline adapter category with explicit provenance.
- **Why this choice:** It improves conceptual clarity and review provenance without changing existing numeric, randomization, registration, or visual scientific results, and avoids introducing network/LLM behavior or licensing ambiguity into default runs.
- **Consequences / follow-ups:** Future citation-risk, repository-content, DOI, PubPeer, RetractionWatch, OSF/GitHub/Zenodo, or LLM-assisted checks must be opt-in and provenance-logged. Regex-based open-practice detection remains a screening aid with possible false positives.
- **Methods/packages affected:** No new transparency-specific R or Python dependencies; `metacheck` is not imported in v1.
- **Assumptions locked in:** Offline default; no LLM calls; no direct `metacheck` dependency; no automated quality, validity, misconduct, or ranking decision from transparency outputs. Software-use and package/vendor documentation links are provenance context, not open-code evidence unless paired with explicit code/script availability language.
- **Output impact:** Added `data/processed/transparency/<study>/inputs/research_object_lite.json`, transparency evidence CSVs, `reports/transparency/<study>/transparency_summary.csv`, a transparency PDF report, and a transparency row in the shared manifest.
- **Verification evidence:** `uv run ruff check .`, `uv run ruff format . --check`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics transparency`, `bash scripts/run_pipeline.sh --forensics all`.

## 2026-06-05: Declare PDF extraction dependency and uv-managed public pipeline runtime
- **Date:** 2026-06-05
- **Decision:** Add `pdfplumber` to the uv-managed Python environment and run all public `scripts/run_pipeline.sh` Python stages through `uv run python`.
- **Context:** The public all-category pipeline failed before analysis because system `python3` lacked `pandas`, while the uv environment lacked the already-used `pdfplumber` dependency required by randomization and numeric-summary extraction.
- **Options considered:**
  - Keep using system `python3` and rely on user-level packages.
  - Declare missing PDF dependencies and make the public pipeline use the project environment.
- **Why this choice:** The public pipeline should be reproducible from `pyproject.toml` and `uv.lock`, not dependent on machine-specific user Python state.
- **Consequences / follow-ups:** `scripts/run_manuscript_review.sh` still uses system `python3` and can be migrated separately. Public pipeline users should run `uv sync` before analysis.
- **Methods/packages affected:** Python extraction only; no R packages or scientific method assumptions changed.
- **Assumptions locked in:** `pdfplumber` is an extraction dependency already used by existing code, not a new forensic method.
- **Output impact:** No intended scientific output changes; regenerated public report artifacts may update due to rerunning the pipeline.
- **Verification evidence:** `uv sync`, `uv run python -c "import pandas, pypdf, pdfplumber"`, `uv run ruff check .`, `uv run ruff format . --check`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics transparency`, `bash scripts/run_pipeline.sh --forensics all`.

## 2026-02-06: Numeric package-native execution baseline
- **Date:** 2026-02-06
- **Decision:** Run `scrutiny::grim_map` and `statcheck::statcheck` directly in `scripts/run_numeric_forensics.R` when packages are available, and emit one standardized long-table output.
- **Context:** Numeric category previously produced only extraction/stub readiness artifacts.
- **Options considered:**
  - Keep package stubs only.
  - Add package-native execution with graceful fallback when packages are unavailable.
- **Why this choice:** It adds real package-level evidence without making the pipeline brittle on machines lacking those packages.
- **Consequences / follow-ups:** `rsprite2` remains stub-only pending explicit methodological assumptions for execution; add full execution in a later step.
- **Methods/packages affected:** `scrutiny`, `statcheck`, `rsprite2` (stub metric only).
- **Assumptions locked in:** GRIM output is treated as a screening signal and combined with rounding/statcheck outputs in standardized form.
- **Output impact:** New numeric report artifacts: `numeric_scrutiny_raw.csv`, `numeric_scrutiny_audit.csv`, `numeric_statcheck_raw.csv`, `numeric_standardized_results.csv`.
- **Verification evidence:** `uv run ruff check .`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics numeric`.

## 2026-02-07: Extend numeric scrutiny coverage with DEBIT/GRIMMER/duplicates
- **Date:** 2026-02-07
- **Decision:** Extend numeric forensics to run package-native `scrutiny` methods beyond GRIM, including `grimmer_map`, `debit_map`, duplicate checks, and rounding-bias checks, with deterministic empty-output behavior for ineligible datasets.
- **Context:** The numeric pipeline needed broader Heathers-aligned data-technique coverage and explicit eligibility handling for method-specific inputs.
- **Options considered:**
  - Keep GRIM-only scrutiny execution and postpone DEBIT/GRIMMER integration.
  - Integrate additional scrutiny methods now with a canonical case contract and package-ready input splits.
- **Why this choice:** It improves method coverage without changing scientific claims, and keeps the pipeline robust when methods have zero eligible rows.
- **Consequences / follow-ups:** Sequence-space checks (`*_map_seq`) remain optional behind `--scrutiny-seq`; interpretation stays screening-oriented and must be triangulated with context.
- **Methods/packages affected:** `scrutiny` (`grim_map`, `grimmer_map`, `debit_map`, `duplicate_detect`, `duplicate_tally`, `rounding_bias`, optional seq variants), `statcheck`.
- **Assumptions locked in:** DEBIT eligibility requires directly extracted binary-style `x` and `sd` (no SD derivation from counts/proportions); header-only outputs are valid when no rows are eligible.
- **Output impact:** Added `scrutiny_cases.csv`, `numeric_summary_long.csv`, method-specific scrutiny inputs, and report artifacts `numeric_scrutiny_grimmer_*`, `numeric_scrutiny_debit_*`, `numeric_scrutiny_duplicates.csv`, `numeric_scrutiny_rounding_bias.csv`.
- **Verification evidence:** `uv run ruff check .`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics numeric`.

## 2026-02-07: Add human-in-loop plot digitization pilot
- **Date:** 2026-02-07
- **Decision:** Add optional plot digitization using `metaDigitise` with a pilot target manifest, generated cache, and standardized digitized-point output consumed by visual forensics.
- **Context:** Visual forensics previously used caption/numbering heuristics only and did not capture numeric data from plots.
- **Options considered:**
  - Keep visual checks text-only.
  - Add interactive digitization as an opt-in workflow while preserving non-interactive default pipeline behavior.
- **Why this choice:** It adds reproducible data extraction from plots without breaking unattended runs.
- **Consequences / follow-ups:** Digitized outputs reflect operator calibration/click decisions and should be treated as measurement data with uncertainty; dual-rater workflows can be added later.
- **Methods/packages affected:** `metaDigitise` (interactive extraction), existing visual caption heuristics.
- **Assumptions locked in:** Pilot scope is one figure target; `--digitize-plots` defaults to `false`; empty digitization output is valid and represented explicitly.
- **Output impact:** Added `data/raw/figures/<study>/plot_digitization_targets.csv`, `data/generated/plot_digitization/<study>/metaDigitise/`, `data/processed/visual/<study>/inputs/plot_digitized_values.csv`, and new visual summary metrics (`n_digitized_figures`, `n_digitized_series`, `n_digitized_points`, `digitization_ready`).
- **Verification evidence:** `uv run ruff check .`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics visual`, `bash scripts/run_pipeline.sh --forensics visual --digitize-plots false`.

## 2026-03-19: Add nonrandomized prediction-validation manuscript review path
- **Date:** 2026-03-19
- **Decision:** Add a dedicated `prediction_validation` manuscript-review workflow for nonrandomized prediction-model papers, separate from the trial-oriented `randomization` and `registration` categories.
- **Context:** Some manuscripts need internal statistical screening even when there is no randomization process to audit. Prediction-model validation papers concentrate their high-yield checks in reported tables, confusion-matrix summaries, calibration summaries, and flow diagrams rather than trial allocation.
- **Options considered:**
  - Force the manuscript into the existing category pipeline only.
  - Add a dedicated review entrypoint that reuses shared numeric/visual screens and layers manuscript-specific checks on top.
- **Why this choice:** Prediction-model validation papers need different arithmetic and plausibility checks than randomized trials. A separate path avoids overloading the trial workflow while preserving shared package execution where it still applies.
- **Consequences / follow-ups:** High-yield tables are transcribed manually or semi-manually rather than auto-parsed from proof PDFs; future work can add more structured support for calibration plots, confusion-matrix interval reconstruction, or ROC digitization.
- **Methods/packages affected:** Shared `scrutiny`, `statcheck`, and visual-caption heuristics; new manuscript-specific checks for summary-statistic reproducibility, confusion-matrix compatibility, calibration-decile sums, and flow reconciliation.
- **Assumptions locked in:** This workflow is manuscript-only and screening-oriented; it does not claim full model reproduction without individual-level predictions or raw data. Manual transcription is the default for the key tables.
- **Output impact:** Added `scripts/run_manuscript_review.sh`, `scripts/extract_prediction_review.py`, `scripts/build_prediction_review_inputs.py`, `scripts/run_prediction_review_forensics.R`, `src/research_project/prediction_review.py`, `notebooks/prediction_validation_review.qmd`, and outputs under `data/processed/reviews/<study>/` and `reports/reviews/<study>/`.
- **Verification evidence:** `uv run ruff check .`, `uv run pytest -q`, `bash scripts/run_manuscript_review.sh --study-id <study_id> --report <local_pdf> --review-type prediction_validation`.

## 2026-03-25: Add config-driven public study selection and supplement baseline parsing
- **Date:** 2026-03-25
- **Decision:** Add `--study-id` support to `scripts/run_pipeline.sh`, move new public study sources under `data/raw/studies/<study>/`, and extend baseline-table parsing to support supplement-style hierarchical tables with dynamic arm labels.
- **Context:** A second public trial case (`pronto`) needed to run through the same category pipeline without duplicating the LungTIME-specific orchestration and without forcing all baselines to look like the original Table 1 layout.
- **Options considered:**
  - Add a one-off PRONTO script and study-specific report copies.
  - Parameterize the existing public pipeline with study configs and make the baseline parser accept both original and supplement table layouts.
- **Why this choice:** It keeps one public pipeline entrypoint, makes report rendering/output paths study-scoped, and reduces the amount of duplicated notebook/orchestration code.
- **Consequences / follow-ups:** Public study configs now live under `config/studies/`; notebooks are rendered with study ID environment variables; Quarto output filenames are moved into per-study report folders after render. Registration congruence checks now recognize `ISRCTN` and UK spelling/phrasing patterns.
- **Methods/packages affected:** `simdistr`, `scrutiny`, `statcheck`, Quarto report rendering, report/protocol congruence helpers.
- **Assumptions locked in:** When a richer baseline table is available in a supplement, that supplement can be the preferred source for baseline randomization forensics; missing manuscript-reported baseline p-values are valid and should not block report rendering.
- **Output impact:** Added `config/studies/lungtime.sh`, `config/studies/pronto.sh`, staged raw inputs under `data/raw/studies/pronto/`, and study-scoped outputs under `data/processed/<category>/pronto/` and `reports/<category>/pronto/`.
- **Verification evidence:** `uv run pytest -q tests/test_forensics_categories.py tests/test_randomization.py`, `uv run ruff check ...`, `bash scripts/run_pipeline.sh --study-id pronto --forensics all`.

## 2026-04-21: Add ClinicalTrials.gov current-record registration screening
- **Date:** 2026-04-21
- **Decision:** Expand the `registration` category to resolve NCT identifiers, optionally fetch ClinicalTrials.gov API v2 current records, normalize registry fields, and emit expanded claim-level registry screening rows alongside the existing report-versus-protocol congruence outputs.
- **Context:** Registration checks previously compared only manuscript/protocol text. Trial reviews also need screening for prospective registration, registry-publication congruence, results posting, and registry-field alignment when a ClinicalTrials.gov record is available.
- **Options considered:**
  - Keep registration checks source-text only.
  - Add registry-aware current-record checks with optional local history input and conservative indeterminate labeling.
- **Why this choice:** It adds high-yield registry screening without making tests depend on live network access or overstating automated text-matching confidence.
- **Consequences / follow-ups:** Registry history is supported through local staged CSV/JSON snapshots only unless a stable public history endpoint is later verified. Non-NCT registries remain source-text congruence checks only.
- **Methods/packages affected:** ClinicalTrials.gov API v2 current-record JSON; no new R or Python package dependencies.
- **Assumptions locked in:** Only NCT IDs trigger ClinicalTrials.gov-specific checks. Missing, ambiguous, or unsupported registry data are labeled `not_assessed` or `indeterminate`. Partial ClinicalTrials.gov dates are compared as possible intervals, not coerced to the first day of the period. Results-overdue screening uses a 365-day threshold after primary completion when registry results are absent.
- **Output impact:** Added `registration_claims_expanded.csv`, `registration_registry_current.csv`, `registration_registry_current.json`, `registration_registry_fetch_metadata.csv`, and `registration_history_events.csv`; existing `registration_claims.csv`, `registration_checks_input.csv`, `registration_row_results.csv`, and `registration_summary.csv` are preserved.
- **Verification evidence:** `uv run ruff check .`, `uv run ruff format . --check`, `uv run pytest -q`, `bash scripts/run_pipeline.sh --forensics registration`, `quarto render notebooks/lungtime_registration_audit.qmd --to pdf`.

## 2026-09-25: Version registry evidence and separate history from detected changes (FM-07)
- **Decision:** Emit source-linked registration claims under `registration_source_claims_v2` and `registration_claims_v2`. Preserve snippets, page references, negation, population, and role-specific masking claims. Allocation ratios require nearby allocation/randomization language; missing or ambiguous source evidence stays indeterminate.
- **Context:** Prior extraction could read a time such as `12:30` as a ratio, treat absent evidence as a mismatch, and collapse distinct masking roles. Registry screening also conflated first-posted with first-submitted dates, represented history absence as an event, and promoted metadata screens to mismatches.
- **Registry provenance:** Hash exact bytes read for a local JSON record or API v2 response. Label local JSON version as unverified. Distinguish a documented API 404 (`record_not_found`) from transport/parse failures. Keep first submission, first posting, registered start and its ACTUAL/ESTIMATED type, and actual recruitment start as separate fields. Direct extraction defaults to network disabled; fetching requires an explicit opt-in.
- **History:** Emit events only from dated snapshots with unambiguous order. Write a separate history status receipt with exact source hash, supplied/dated/undated counts, chronology status, detected-event count, and completeness marked unknown. Missing, malformed, undated, unchanged, or overlapping history does not create a change event or establish that no registration existed.
- **Interpretation:** Registration timing, 365-day results-posting, and publication-linkage checks are `screen_status` metadata. They do not become mismatch flags. `mismatch_flag` is missing unless the row is explicitly assessed as match/mismatch; only those two statuses enter the mismatch denominator.
- **Output impact:** Versioned claims carry evidence and screening fields into the registration runner and report. `registration_registry_current_raw.json` stores the exact fetched/local bytes covered by the source hash; the normalized JSON remains a separate convenience artifact. Updated `notebooks/lungtime_registration_audit.qmd` documents the separation and displays source evidence, date provenance, and history availability.
- **Verification evidence:** `PYTHONPATH=src .venv/bin/python -m pytest -q`; `.venv/bin/ruff check .`; `.venv/bin/ruff format --check .`; `git diff --check`; R script parse; synthetic native-R runner integration (assessed denominator 2, mismatch 1, unassessed flag NA); synthetic Quarto HTML and PDF renders. No live registry fetch or source-paper analysis was run.
- **Remaining limits:** History completeness remains unknown for local snapshots unless the source provides an independently verified completeness guarantee. Local JSON has no asserted upstream version. This ticket does not establish a trial judgment or a registry absence.

## Historical 2026-09-25 checkpoint: FM-08 source unavailable (superseded below)
- **Decision:** Do not create a frozen INSPECT-SR catalogue from the audit summary or memory. FM-08 requires exact official wording, immutable version/hash, retrieval date, citation, and separate license/terms; none is bundled in the supplied ZIP.
- **Evidence checked:** The packet's `SOURCES.md` points to the live INSPECT-SR site and changelog and reports v1.1.2 as latest on the audit date. The ZIP contains the ticket, contracts, crosswalk, acceptance material, and source register, but no official guidance snapshot or license text. The FM-08 target paths are absent locally.
- **Boundary:** The request prohibits network work without explicit opt-in. No network retrieval, catalogue fabrication, or code/schema edit for FM-08 was performed.
- **Smallest actionable blocker:** Supply a locally staged, exact v1.1.2 source snapshot with citation and license/terms, or explicitly opt in to retrieving those materials. Then verify the snapshot/hash and resume FM-08.
- **Downstream effect:** FM-09 depends on FM-08; FM-10 depends on FM-08 and FM-09; FM-11 depends on FM-08, FM-09, and FM-10. These tickets remain open and were not implemented against an unverified checklist.

## 2026-09-25: Resume INSPECT-SR against pinned sources and close local integration gate

- **Decision:** Pin the official INSPECT-SR v1.1.2 source snapshot at commit `a349c4f1ddd9d232dfc2632938aad31382a9a770`, retaining its source files, attribution, license terms, retrieval metadata, catalogue, and per-file SHA-256 receipt. This supersedes the earlier hold because the user authorized source retrieval and the exact source was verified.
- **R method pins:** Record the user-selected `scrutiny` 0.6.2 commit `2a8eeac3ca9f893b946e45409317afaf42a805e3`, `statcheck` 1.5.0, and `simdistr` 1.0.1 source archives and hashes in `config/inspect_sr/r_method_packages.lock.json`. Install them only into an isolated test library through `scripts/install_inspect_sr_r_methods.sh`; no Python project dependency or `uv.lock` change was made. Transitive imports are prepared from CRAN for testing and their session versions are printed, not separately frozen.
- **Corrections:** Repaired run-scoped pipeline artifact receipts and report destinations; updated meta consumers for current randomization contracts; made method receipts reject incomplete/unknown results; retained proportion precision for simdistr; fixed negation-aware registration matching; made manifests immutable with settings/code/worktree provenance; and fixed malformed history-date handling. The native method test found that scrutiny 0.6.2 requires numeric inputs, explicit printed-decimal arguments, and precision-grouped map calls; adapters now meet that API. The same production-path test found that statcheck's evaluation unit is report text, so its input count now matches its evaluated unit.
- **Records and outputs:** FM-08 through FM-11 now preserve the independent catalogue, persistent trial/report/source/evidence identities, candidate evidence, manual observations, reviewer submissions, adjudication, report model/history, and explicit synthesis policy/export. Human submissions are exclusive-write records. Historical files, old tiers, and annotations were not regenerated or converted. Changed runner contracts and report paths are versioned and documented with their affected outputs in this implementation's handoff.
- **Integration configuration:** CI now has a locked Python fast job, a required native-R job that asserts exact package versions and positive method coverage, and a Quarto job that renders synthetic current-run HTML/PDF reports. Tests remain offline after package/runtime preparation. A required native job fails if R or a pinned method is missing; Python-lane skips are not treated as gate passes.
- **Verification:** On the final code head, `PYTHONPATH=src uv run pytest -q -o addopts='' -ra` passed (114 passed, 2 expected native-package skips, 67.28s). With isolated pinned packages, `FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library PYTHONPATH=src uv run pytest -q -o addopts='' -ra tests/test_r_integration.py` passed (3, 5.58s). Synthetic report tests passed (7, 43.72s, including HTML and PDF). `uv run ruff check .`, `uv run ruff format . --check`, shell syntax, R script parsing, guidance checksums, package-lock JSON, workflow YAML parsing, `uv sync --locked --dev`, and `git diff --check` passed. No source-paper analysis was run.
- **Open status:** FM-01–FM-12 implementation and local verification are complete; FM-13 remains deferred. The configured GitHub Actions jobs still need to run on the eventual committed head. Transitive R dependencies are not pinned independently, and human reviewer identities, ambiguous trial/report mappings, and review-specific synthesis policy remain explicit human inputs. No deployment or historical-results rewrite is authorized.
