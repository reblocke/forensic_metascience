# Decisions (architecture + scientific choices)

## 2026-09-25: Replace corrected meta composite with explicit evidence coverage
- **Date:** 2026-09-25
- **Decision:** The default meta workflow emits category coverage and source-linked screening-signal records. It does not normalize category metrics, impute missing values, combine them into a study score, assign a risk tier, or generate a judgment. The retired formula is available only with `--legacy-reproduction` and writes beneath isolated `legacy/` directories with schema `legacy_composite_v1` and label `NOT_INSPECT`.
- **Context:** The previous Python and R paths mapped missing values to reassuring constants and combined heterogeneous measures into a weighted tier; the randomization contribution used `1 - Fisher P`. Production R duplicated the scorer, so replacing one helper alone was insufficient.
- **Options considered:** Preserve the aggregate as a triage aid; replace it with a different score; or remove corrected-path scoring and report coverage plus source-linked signals.
- **Why this choice:** No calibrated composite is specified. Missing, failed, or unsupported evidence cannot be represented as reassuring, and candidate signals must remain visible without collapsing across categories.
- **Consequences / follow-ups:** Category extraction records report availability and retains source paths. Nonmissing summary metrics indicate evidence is present; missing category reports or all-missing metrics are unavailable. Existing sources do not reliably distinguish failed from unsupported categories, so both remain unknown. Existing flagged row results are passed as `screening_signal` records with their source file and unit. These are not INSPECT check responses or human judgments.
- **Methods/packages affected:** `src/research_project/meta_forensics.py`, `scripts/extract_meta.py`, `scripts/build_meta_inputs.py`, `scripts/run_meta_forensics.R`, `notebooks/lungtime_meta_audit.qmd`. No dependency was added.
- **Assumptions locked in:** Category-level assessment here means nonmetadata summary metrics are present; this is coverage, not method validity. Only preexisting explicit row flags are surfaced; the meta layer introduces no concern threshold.
- **Output impact and migration:** Corrected outputs are `category_summaries_v2_raw.csv`, `category_coverage_v1_raw.csv`, `candidate_concerns_v1_raw.csv`, `meta_evidence_coverage_v1.csv`, `meta_candidate_concerns_v1.csv`, `meta_evidence_coverage_v1_out.csv`, `meta_candidate_concerns_v1_out.csv`, and `meta_coverage_summary_v1.csv`; the report is versioned as `<study>_meta_audit_v2.pdf`. Prior `category_summaries_raw.csv`, `meta_category_scores*`, `meta_overall*`, and the old report PDF are deprecated in corrected mode and remain untouched on disk. Explicit legacy outputs move under `inputs/legacy/` and `reports/legacy/`; legacy scores and tiers are not consumed by corrected outputs or the report. The pipeline passes only categories requested in the current run, with randomization included when meta is requested because the orchestrator runs it as a prerequisite.
- **Verification evidence:** Missing-only coverage, source-linked concerns, direct R corrected-run behavior, and a frozen legacy fixture were tested. Full Python tests, Ruff checks, R syntax parsing, and Python compilation passed. No category source-paper analyses or report render were run.

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
