# Forensic Meta-Science Credibility Pipeline

This repository is a reproducible scaffold for **forensic meta-science investigations** focused on evaluating the credibility of published findings.

Primary workflow:
- parse extracted study statistics into standardized analysis inputs
- run credibility analyses with established meta-science packages (primarily in R)
- compare results across methods
- render transparent Quarto reports for interpretation

## Quickstart

### 1) Sync Python tooling (used for utility scripts/tests)
```bash
uv sync
```

### 2) Run repository checks
```bash
uv run pytest -q
uv run ruff check .
```

### 3) Run deterministic pipeline entrypoint
```bash
bash scripts/run_pipeline.sh
```

### 3b) Run pipeline plus randomization forensics audit (LungTIME test case)
```bash
bash scripts/run_pipeline.sh --randomization-audit
```

### 3c) Run selected forensic categories (comma-separated)
```bash
bash scripts/run_pipeline.sh --forensics randomization,numeric,registration,visual,meta
```

### 3d) Run visual category with interactive plot digitization (pilot)
```bash
bash scripts/run_pipeline.sh --forensics visual --digitize-plots true
```

### 4) Render Quarto reports (when `.qmd` notebooks are present)
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
- `data/processed/metadata/` run provenance (package versions, params, seeds, hashes)
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

## Working principles
- No silent changes to assumptions or analysis defaults.
- Ask before adding dependencies or changing scientific assumptions.
- Keep package interfaces explicit and auditable.
- Preserve an end-to-end trail from raw extraction to final credibility summary.

See `/Users/blocke/Box Sync/Residency Personal Files/Scholarly Work/Locke Research Projects/forensic_metascience/AGENTS.md` for detailed operating conventions.
