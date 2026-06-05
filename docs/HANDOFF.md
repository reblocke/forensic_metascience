# Handoff (for multi-session work)

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
