---
name: refactor-and-clean
description: Safely refactor code: identify dead code, improve naming, reduce duplication, run format/lint, and protect behavior with tests.
---

## Procedure
1. Identify the refactoring goal (clarity, modularity, performance, API stability).
2. Ensure tests exist for current behavior (add if missing).
3. Refactor in small steps; run tests after each step.
4. Remove dead code (trust git history).
5. Run `ruff` and ensure the pipeline still runs.
6. Update docs if interfaces change.

## Guardrails
- Do not change scientific behavior unless requested.
- If behavior must change, document the change and update tests.
