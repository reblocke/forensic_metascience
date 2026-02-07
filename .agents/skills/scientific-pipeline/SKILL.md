---
name: scientific-pipeline
description: Design or refactor a scientific data pipeline with clear folder structure, reproducible environments, orchestration (Snakemake/Make), and diagnostic plots.
---

## Objectives
- Separate data processing from visualization.
- Make the pipeline deterministic, re-runnable, and inspectable.
- Make it obvious where data came from and whether outputs are stale.

## Checklist
1. **Directory structure**
   - Ensure `data/raw`, `data/processed`, `data/generated`, `src`, `tests`, `scripts`, `reports` exist.
2. **Environment**
   - Ensure dependencies are pinned/recorded (uv/conda/docker).
3. **Orchestration**
   - Prefer Snakemake or Make (or, at minimum, one `scripts/run_pipeline.sh` entrypoint).
   - Define inputs/outputs per step.
4. **Validation**
   - Add fast sanity checks and cheap diagnostics (saved PNGs).
   - Promote critical checks to tests.
5. **Reproducibility**
   - No hard-coded paths.
   - Fixed random seeds where randomness is used.

## Deliverables
- A single documented entrypoint to run the pipeline.
- Tests for at least the core transformation.
- A short note in `docs/DECISIONS.md` for any scientific choice.
