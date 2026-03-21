# Forensic Meta-Science Credibility Criteria

This document defines minimum standards for analyses that evaluate research-claim credibility in this repository.

## 1) Input data contract
- Raw extraction sources stay immutable in `data/raw/`.
- Normalized analysis inputs are written to `data/processed/analysis_inputs/`.
- Category-specific inputs are written to `data/processed/<category>/<study>/inputs/`.
- Category-specific extraction metadata are written to `data/processed/<category>/<study>/metadata/`.
- Shared study manifest is written to `data/processed/manifests/<study>/forensics_manifest.csv`.
- Each normalized table should include:
  - stable study/result identifiers
  - the inferential statistic(s) needed by downstream packages
  - explicit directionality/tail conventions when relevant
  - enough metadata to trace back to source records

## 2) Package interface contract (R-first)
- Place R package wrappers in `R/`.
- Keep one function/module per package family when practical.
- For each package run, save:
  - package-native output (`data/processed/results/<analysis_id>/raw/`)
  - standardized output for cross-method comparison (`data/processed/results/<analysis_id>/standardized/`)
  - run metadata (`data/processed/metadata/`)

## 3) Reproducibility and provenance
- Capture package versions and session info for each run.
- Record package parameters/options and seed values.
- Keep deterministic transformations; no ad-hoc manual edits of processed outputs.
- Document scientific assumptions in `docs/DECISIONS.md`.

## 4) Quarto reporting contract
- Author reports/notebooks as `.qmd` in `notebooks/`.
- Reports should read from `data/processed/` and write rendered artifacts to `reports/`.
- Final report tables/figures should reference method names, assumptions, and sensitivity checks.
- Forensics category reports should render to PDF at `reports/<category>/<study>/`.

## 5) Verification minimums
- Add/maintain unit tests for parsing and standardization logic.
- Add at least one integration-style test for end-to-end package interface behavior on a small fixture.
- Run standard checks before closing work:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run ruff format . --check`
  - `bash scripts/run_pipeline.sh`
  - `quarto render notebooks` (when `.qmd` files are changed)
