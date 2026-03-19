# Forensic Meta-Science Credibility Pipeline

This repository is a reproducible scaffold for **forensic meta-science investigations** focused on evaluating the credibility of published findings.

Conceptual reference (methods taxonomy + motivation):
- James Heathers' open book on forensic meta-science techniques: https://jamesheathers.curve.space/#an-introduction-to-techniques

Primary workflow:
- parse extracted study statistics into standardized analysis inputs
- run credibility analyses with established meta-science packages (primarily in R)
- compare results across methods
- render transparent Quarto reports for interpretation

## What This Repo Is (And Isn't)

- These methods are **screening tools**, not proof of misconduct or validity.
- Outputs depend on what can be extracted from manuscripts/protocols (often PDFs). Poor PDF text/table structure can reduce coverage and increase false negatives.
- Many methods assume conventional rounding and denominator choices; apparent "errors" can be benign (different denominators, weighting, imputation, rounding conventions, or reporting choices).
- Plot digitization is intentionally **human-in-the-loop** and should be treated as measurement data with operator uncertainty.

## Prerequisites

- Python `>= 3.11` and [`uv`](https://github.com/astral-sh/uv) (Python environment + tooling)
- R (tested with R `4.5.x`)
- Quarto CLI (for rendering `.qmd` reports)
- A LaTeX engine for PDF output (e.g., TinyTeX or TeX Live)
- `bash`

## Install

### 1) Clone and enter the repo

```bash
git clone <REPO_URL>
cd <REPO_DIR>
```

### 2) Sync Python tooling (used for utility scripts/tests)

```bash
uv sync
```

### 3) Install R packages

Required for this pipeline's R scripts:

```bash
Rscript -e "install.packages(c('readr','dplyr','tidyr','tibble'), repos='https://cloud.r-project.org')"
```

Packages that enable the implemented forensic methods (recommended):

```bash
Rscript -e "install.packages(c('simdistr','scrutiny','statcheck','metaDigitise'), repos='https://cloud.r-project.org')"
```

Notes:
- `simdistr` is required for the current `randomization` stage, and `numeric`/`meta` runs currently execute `randomization` first.
- `scrutiny`, `statcheck`, and `metaDigitise` are optional; when missing, the pipeline emits schema-valid empty outputs and records availability in category reports (for example `reports/numeric/<study>/numeric_package_status.csv`).

## Quickstart

### 1) Run repository checks
```bash
uv run pytest -q
uv run ruff check .
```

### 2) Run deterministic preprocessing entrypoint
```bash
bash scripts/run_pipeline.sh
```

### 2b) Run pipeline plus randomization forensics audit (LungTIME test case)
```bash
bash scripts/run_pipeline.sh --randomization-audit
```

### 2c) Run selected forensic categories (comma-separated)
```bash
bash scripts/run_pipeline.sh --forensics randomization,numeric,registration,visual,meta
```

### 2d) Run all categories (LungTIME test case)
```bash
bash scripts/run_pipeline.sh --forensics all
```

### 2e) Run visual category with interactive plot digitization (pilot)
```bash
bash scripts/run_pipeline.sh --forensics visual --digitize-plots true
```

### 3) Render Quarto reports (when `.qmd` notebooks are present)
```bash
quarto render notebooks
```

## Repository layout
- `R/` R wrappers for meta-science package calls and parameter mappings
- `src/` Python helper code for parsing, validation, and utility transformations
- `scripts/` reproducible entrypoints (pipeline, diagnostics, report orchestration)
- `notebooks/` Quarto notebooks/reports (`.qmd`) and exploratory artifacts
- `tests/` unit/integration tests for core transformation and interfaces
- `data/processed/manifests/<study_id>/forensics_manifest.csv` shared extraction/readiness manifest
- `data/raw/` immutable source inputs
- `data/processed/` deterministic intermediate/final analysis tables
- `data/generated/` synthetic or AI-generated data (explicitly labeled)
- `reports/` rendered credibility reports and diagnostic figures
- `docs/` decisions, workflow notes, handoffs

## Forensic category flow
- Shared pattern for each category: `extract -> build_inputs -> run_forensics -> render_report`.
- Category outputs:
  - `data/processed/<category>/<study>/inputs/*.csv`
  - `data/processed/<category>/<study>/metadata/*.csv`
  - `reports/<category>/<study>/*.csv` and rendered `*.pdf`
- Current implemented categories:
  - `randomization` (baseline balance and `simdistr`-oriented checks)
  - `numeric` (numeric/rounding consistency plus package-native `scrutiny` checks: GRIM, GRIMMER, DEBIT, duplicates, rounding-bias, and `statcheck`)
  - `registration` (report-versus-protocol congruence checks)
  - `visual` (caption/figure-sequence heuristics)
  - `meta` (cross-category anomaly aggregation)
  - `prediction_validation review` (manuscript-review path for nonrandomized prediction-model papers)

## Prediction-Validation Manuscript Review

For nonrandomized manuscripts, this repo now includes a dedicated review path:

```bash
bash scripts/run_manuscript_review.sh \
  --study-id local_prediction_review \
  --report "/absolute/path/to/local_manuscript.pdf" \
  --review-type prediction_validation
```

This path is designed for manuscripts where trial-randomization checks do not apply. It currently:

- extracts manuscript full text and page-level text
- scaffolds and validates manual transcription tables
- runs the shared `numeric` and `visual` screens where applicable
- adds manuscript-specific checks for:
  - Table 2 summary-statistic reproducibility
  - Table 3 confusion-matrix compatibility
  - Table E2 calibration-decile arithmetic / approximate Hosmer-Lemeshow consistency
  - Figure 1 cohort-flow arithmetic
- renders a single PDF report under `reports/reviews/<study>/`

Key limitation:
- This path assumes manual or semi-manual transcription of the high-yield tables (`Table 2`, `Table 3`, `Table E2`, and the flow diagram). It does not currently rely on fully automatic table extraction for proof PDFs.

## Numeric scrutiny contract
- Canonical cases: `data/processed/numeric/<study>/inputs/scrutiny_cases.csv`.
- Mean/SD extraction candidates: `data/processed/numeric/<study>/inputs/numeric_summary_long.csv`.
- Package-specific inputs: `scrutiny_grim_input.csv`, `scrutiny_grimmer_input.csv`, `scrutiny_debit_input.csv`, `scrutiny_duplicates_input.csv`, `scrutiny_rounding_bias_input.csv`.
- Report outputs: `reports/numeric/<study>/numeric_scrutiny_*`, `numeric_statcheck_raw.csv`, and `numeric_standardized_results.csv`.

## Plot digitization pilot contract
- Target manifest: `data/raw/figures/<study>/plot_digitization_targets.csv`.
- Generated `metaDigitise` project cache: `data/generated/plot_digitization/<study>/metaDigitise/`.
- Processed digitized points: `data/processed/visual/<study>/inputs/plot_digitized_values.csv`.
- Visual summary includes: `n_digitized_figures`, `n_digitized_series`, `n_digitized_points`, `digitization_ready`.
- Pipeline default remains non-interactive; opt in with `--digitize-plots true`.

## Tools And Packages (Why, Inputs, Limitations)

This repo is **R-first** for the inferential/forensic engines. Python is used for extraction, validation, and orchestration.

### Randomization / baseline balance (`randomization`)

- `simdistr` (CRAN): https://CRAN.R-project.org/package=simdistr
  - Objective: simulation-based joint screening of baseline balance signals using a standardized runtime table.
  - Inputs in this repo: `reports/randomization/<study>/simdistr_runtime_input.csv` (built from `data/processed/randomization/<study>/csf_input.csv`).
  - Limitations: baseline tables are not raw randomization logs; correlation among variables and differing test choices can affect combined signals; results are screening-level.

### Numeric integrity (`numeric`)

- `scrutiny` (CRAN): https://CRAN.R-project.org/package=scrutiny
  - Objective: apply numeric-consistency checks and descriptive diagnostics (GRIM/GRIMMER/DEBIT, duplication, rounding-bias).
  - Inputs in this repo:
    - canonical cases: `data/processed/numeric/<study>/inputs/scrutiny_cases.csv`
    - method-specific inputs: `scrutiny_grim_input.csv`, `scrutiny_grimmer_input.csv`, `scrutiny_debit_input.csv`, `scrutiny_duplicates_input.csv`, `scrutiny_rounding_bias_input.csv`
  - Limitations:
    - GRIM/GRIMMER depend on correctly interpreted rounding and denominator/sample size.
    - DEBIT applies only to binary/proportion-style summaries and has strict eligibility constraints.
    - Duplicate/rounding-bias signals can be benign (reporting conventions, rounding rules, reused constants).

- `statcheck` (CRAN): https://CRAN.R-project.org/package=statcheck
  - Objective: recompute p-values from extracted test statistics and compare to reported p-values.
  - Inputs in this repo: extracted PDF text (`data/processed/numeric/<study>/inputs/statcheck_text.txt`) plus `statcheck_input.csv`/stubs.
  - Limitations: coverage depends on how statistics are reported (often APA-like patterns); corrections, unusual formats, or narrative reporting can reduce accuracy; false positives/negatives are possible.

- Internal consistency checks (repo code)
  - Objective: recompute percent-from-counts and flag large discrepancies.
  - Inputs in this repo: `data/processed/numeric/<study>/inputs/numeric_table.csv`.
  - Limitations: manuscript percentages can use different denominators/weighting/rounding or filtered cohorts; flags require contextual review.

### Registration congruence (`registration`)

- Repo extraction + congruence checks
  - Objective: compare specific manuscript vs protocol claims (registration/methods congruence).
  - Inputs in this repo: extracted claim tables under `data/processed/registration/<study>/inputs/`.
  - Limitations: claims can be ambiguous; missing IDs/fields can silently reduce coverage; results should be reviewed with the source documents.

### Visual techniques (`visual`)

- Caption/sequence heuristics (repo code)
  - Objective: identify near-duplicate caption text and numbering gaps as light-weight screening signals.
  - Inputs in this repo: `data/processed/visual/<study>/inputs/figure_captions.csv` and `caption_duplicates.csv`.
  - Limitations: depends heavily on PDF text extraction; this is not pixel-level image manipulation detection.

- `metaDigitise` (CRAN): https://CRAN.R-project.org/package=metaDigitise
  - Objective: human-in-loop digitization of plotted values with calibration and exported point tables.
  - Inputs in this repo: `data/raw/figures/<study>/plot_digitization_targets.csv` plus local image files.
  - Limitations: operator calibration/click errors can distort all values; series/panel labeling mistakes can contaminate downstream analyses; treat outputs as measurements with uncertainty.

### Meta aggregation (`meta`)

- Repo aggregation logic (category-level scoring)
  - Objective: turn per-category summaries into an overall score and tier to prioritize review.
  - Inputs in this repo: `reports/<category>/<study>/*_summary.csv` and standardized tables.
  - Limitations: heuristic weighting and tiering (not a validated decision rule).

## Working principles
- No silent changes to assumptions or analysis defaults.
- Ask before adding dependencies or changing scientific assumptions.
- Keep package interfaces explicit and auditable.
- Preserve an end-to-end trail from raw extraction to final credibility summary.

See `AGENTS.md` for detailed operating conventions and `docs/DECISIONS.md` for scientific/architectural decision notes.
