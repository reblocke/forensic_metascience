# Task template (paste into Codex)

## Goal
-

## Context
- What dataset / experiment / model is this about?
- Links to relevant issues/papers/notes:
- Which credibility method(s) are in scope (e.g., p-curve, p-uniform, robust Bayesian model)?
- Which existing package(s) should be used?

## Constraints
- Performance:
- Dependencies allowed / disallowed:
- Backwards compatibility / API stability:
- Data privacy constraints:
- Scientific assumptions that must remain unchanged:

## Definition of done
- Tests added/updated:
- Commands passing:
  - `UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -m 'not native_r and not report_integration'`
  - `UV_OFFLINE=1 uv run --offline --locked ruff check .`
  - `UV_OFFLINE=1 uv run --offline --locked ruff format . --check`
  - `bash scripts/run_pipeline.sh --forensics all --dry-run --offline`
  - Native R and synthetic Quarto HTML/PDF lanes when their interfaces change (see `docs/INSPECT_SR_ACCEPTANCE.md`)
- Outputs generated (where):
- Package provenance captured (where):
- Quarto/report artifacts generated (where):
- Docs updated (where):

## Known risks / edge cases
-
- Potential silent failure mode in inference:
- Plan to detect it (test/check/diagnostic):

## Files to read first
- @AGENTS.md
- @...
