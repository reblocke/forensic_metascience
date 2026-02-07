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
