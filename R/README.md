# R package-wrapper layer

Use this folder for R code that interfaces with meta-science/credibility packages.

## Conventions
- Keep wrappers deterministic and side-effect-light.
- Keep package argument mappings explicit and documented in code comments or roxygen docs.
- Read normalized inputs from `data/processed/analysis_inputs/`.
- Write outputs to:
  - `data/processed/results/<analysis_id>/raw/`
  - `data/processed/results/<analysis_id>/standardized/`
  - `data/processed/metadata/` (versions, params, seed, timestamp)

## Suggested shape
- `R/io_*.R` for loaders/validators
- `R/run_<method>.R` for package execution wrappers
- `R/standardize_<method>.R` for harmonizing outputs across methods
