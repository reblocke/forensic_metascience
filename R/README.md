# R package-wrapper layer

Use this folder for R code that interfaces with meta-science/credibility packages.

## Conventions
- Keep wrappers deterministic and side-effect-light.
- Keep package argument mappings explicit and documented in code comments or roxygen docs.
- Read normalized inputs from the active run's `processed/<category>/inputs/`.
- Write package-native and standardized outputs to that run's
  `reports/<category>/`, with method receipts alongside the outputs and output
  hashes in its `run_manifest.json`. Do not read shared historical category
  directories.

## Suggested shape
- `R/io_*.R` for loaders/validators
- `R/run_<method>.R` for package execution wrappers
- `R/standardize_<method>.R` for harmonizing outputs across methods
