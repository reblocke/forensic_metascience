# Handoff (for multi-session work)

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

### Open gates and next work
- FM-01 through FM-04 are complete. FM-05 through FM-12 remain open; FM-13 remains deferred.
- R 4.6.0, Quarto 1.9.37, `readr`, and `dplyr` are installed. R package `scrutiny` is unavailable, so package-native method execution and the assembled release gate remain unverified.
- The audit commit `30b3fc2c9ba11b0a89e62f911043f2ca2ab5917a` is absent from the local object database. Work continues from clean current head `805cb282ed0f9f974f5d977592bbf95b419fd022`; no reset or fetch was performed.
- The disposable baseline worktree passed 39 pytest tests, Ruff check, and Ruff format check using the existing local Python environment. Offline `uv run --frozen pytest -q` could not provision uncached `ruff==0.15.0`; network access is prohibited by the packet.

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
