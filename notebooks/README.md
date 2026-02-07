# Notebooks

Use Quarto notebooks (`.qmd`) for reproducible reporting and exploratory analysis.

Recommendations:
- Prefer Quarto as the default authoring format so diffs are readable and renders are deterministic.
- Read analysis inputs from `data/processed/` and write rendered artifacts to `reports/`.
- Keep computation-heavy transforms in pipeline code (`R/`, `src/`, or `scripts/`) and keep notebooks focused on interpretation.
- Capture session/package provenance for final reports when inference may depend on package version details.
- If you do use Jupyter, periodically restart the kernel and run all cells from the top.
