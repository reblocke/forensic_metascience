# Forensic Meta-Science Credibility Criteria

This document defines minimum standards for analyses that evaluate research-claim credibility in this repository.

## 1) Input data contract
- Raw extraction sources stay immutable in `data/raw/`.
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
  - package-native output under `reports/<category>/<study>/` or `data/processed/<category>/<study>/inputs/`
  - standardized output for cross-method comparison under the category report folder
  - run metadata under `data/processed/<category>/<study>/metadata/`
- Preserve backward-compatible outputs when expanding a category contract.

## 3) Registration / registry checks
- Report-versus-protocol congruence claims are written to `registration_claims.csv`.
- Expanded registry-aware claims are written to `registration_claims_expanded.csv`.
- ClinicalTrials.gov current-record outputs, when applicable, are written to:
  - `registration_registry_current.csv`
  - `registration_registry_current.json`
  - `registration_registry_fetch_metadata.csv`
- Registry history checks are local-input only unless a stable public history endpoint is explicitly adopted and documented.
- Missing, ambiguous, or non-NCT registry cases should be represented as `not_assessed` or `indeterminate`, not as failures.
- Mismatch rates should use assessed rows only.

## 4) Reproducibility and provenance
- Capture package versions and session info for each run.
- Record package parameters/options and seed values.
- Keep deterministic transformations; no ad-hoc manual edits of processed outputs.
- Document scientific assumptions in `docs/DECISIONS.md`.

## 5) Quarto reporting contract
- Author reports/notebooks as `.qmd` in `notebooks/`.
- Reports should read from `data/processed/` and write rendered artifacts to `reports/`.
- Final report tables/figures should reference method names, assumptions, and sensitivity checks.
- Forensics category reports should render to PDF at `reports/<category>/<study>/`.

## 6) Verification minimums
- Add/maintain unit tests for parsing and standardization logic.
- Add at least one integration-style test for end-to-end package interface behavior on a small fixture.
- Run standard checks before closing work:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run ruff format . --check`
  - `bash scripts/run_pipeline.sh`
  - `quarto render notebooks` (when `.qmd` files are changed)
