# Forensic Meta-Science Credibility Criteria

This document defines minimum standards for analyses that evaluate research-claim credibility in this repository.

## 1) Input data contract
- Raw extraction sources stay immutable in `data/raw/`.
- Current pipeline inputs are written to `data/processed/forensics_runs/<study>/<run-id>/processed/<category>/`.
- Run-specific extraction metadata and the `run_manifest.json` remain inside the same run directory.
- Run manifests use `forensics_run_v3` and record selected source hashes, effective settings, code revision, a source/documentation worktree fingerprint, stages, and output hashes.
- Shared study readiness manifests are maintained only by their explicit updater; the run orchestrator does not update human readiness annotations.
- Each normalized table should include:
  - stable study/result identifiers
  - the inferential statistic(s) needed by downstream packages
  - explicit directionality/tail conventions when relevant
  - enough metadata to trace back to source records

## 2) Package interface contract (R-first)
- Place R package wrappers in `R/`.
- Keep one function/module per package family when practical.
- For each package run, save:
  - package-native output under the run's `reports/<category>/` or `processed/<category>/inputs/`
  - standardized output for cross-method comparison under the run's category report folder
  - package, parameter, seed, source, and output provenance in the run manifest or method receipt
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
- Native integration checks pin `scrutiny` 0.6.2, `statcheck` 1.5.0, and `simdistr` 1.0.1 with SHA-256 verified source archives; `scripts/install_inspect_sr_r_methods.sh` is test setup only. The production workflow does not install packages.
- CI keeps a locked Python fast lane separate from mandatory native R and Quarto HTML/PDF report-review lanes. The native lane fails if all method checks would be skipped; report tests render only synthetic current-run inputs into temporary/private test directories.
- A Git commit alone does not identify uncommitted implementation files; the run manifest records a separate worktree source/documentation fingerprint.
- Keep deterministic transformations; no ad-hoc manual edits of processed outputs.
- Document scientific assumptions in `docs/DECISIONS.md`.

## 5) Transparency / research-object checks
- Current-run transparency inputs are written under `data/processed/forensics_runs/<study>/<run-id>/processed/transparency/`.
- The repo-owned `research_object_lite.json` contract records source PDFs, file hashes, page-level text refs, detected URLs, repository links, preregistration/registry links, open-practice evidence, figure/table mentions, and offline provenance.
- The v1 transparency category is offline by default:
  - no LLM calls
  - no live DOI, PubPeer, RetractionWatch, OSF, GitHub, Zenodo, or other repository API calls
  - no direct `metacheck` package dependency
- Automated transparency checks are evidence maps for human review, not automated quality, validity, misconduct, or ranking decisions.
- Software-use and package/vendor documentation links are recorded as provenance context only; they do not satisfy open-code evidence unless the text also states code or scripts are available.
- Network or LLM-assisted checks require explicit opt-in flags plus provenance outputs documenting what external services were used.

## 6) Quarto reporting contract
- Author reports/notebooks as `.qmd` in `notebooks/`.
- Reports must read from explicit current-run roots and write rendered artifacts to that run's `reports/<category>/` directory.
- Final report tables/figures should reference method names, assumptions, and sensitivity checks.
- Forensics category reports render to PDF only when `--render-reports` is selected. The report stage fails if the expected run-scoped output is absent.
- `notebooks/inspect_sr_assessment.qmd` requires explicit current report-model JSON through `INSPECT_SR_REPORT_JSON`. Reviewer material and rendered review reports stay under gitignored `data/private/inspect_sr/`; the QMD does not read shared category outputs or emit inferred legacy judgments.
- Quarto report fixtures should render both HTML and PDF into a temporary current-run directory. Missing R, Quarto, or PDF runtimes are blocked/skipped coverage, never a pass.

## 7) INSPECT-SR human review and synthesis
- Use only the locally pinned v1.1.2 catalogue and its verified source hashes.
- Catalogue checks, source versions, evidence, candidate method results, human responses, domain judgments, overall judgments, adjudication, and synthesis policy are separate records.
- Candidate results require a complete `method_receipt_v2` for the same run and exact source evidence. A check without a validated receipt remains manual-only; a missing image is not a negative response.
- Final synthesis requires an approved, versioned policy, current guidance and source snapshot hashes, and finalized human adjudication. Primary versus sensitivity policy must be selected explicitly.
- Trial dispositions are one row per stable trial ID; report and comparison joins preserve row counts and existing RoB/effect fields. Unresolved trials block export unless the caller explicitly selects unresolved-list mode.
- Public export requires explicit trial selection and review and contains only allowlisted identifiers/dispositions. It must not carry source excerpts, private notes, or reviewer identity fields.

## 8) Verification minimums
- Add/maintain unit tests for parsing and standardization logic.
- Add at least one integration-style test for end-to-end package interface behavior on a small fixture.
- Run standard checks before closing work:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run ruff format . --check`
  - output-free help/dry-run checks for orchestration changes
  - synthetic run-scoped execution for pipeline changes; do not run source-paper analyses as a substitute for scientific validation
  - Quarto HTML/PDF smoke checks with temporary run-scoped inputs when `.qmd` files or render paths change
  - missing R/Quarto/package runtimes are blocked or skipped coverage, never a pass
