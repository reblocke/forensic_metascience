# Decisions (architecture + scientific choices)

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
