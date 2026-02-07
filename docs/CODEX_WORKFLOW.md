# Codex workflow (practical)

This is an end-to-end workflow for using Codex (CLI/app/IDE) to build **forensic meta-science code that you can trust**.

## 0) One-time setup

### 0.1 Global `~/.codex/AGENTS.md` (recommended)
Codex can load a global instructions file and then layer in repository instructions. Keep your global file short and behavior-focused.

Create:
```bash
mkdir -p ~/.codex
$EDITOR ~/.codex/AGENTS.md
```

Suggested contents:
```md
# ~/.codex/AGENTS.md

## Working agreements
- Always write a brief plan before editing code.
- Prefer small diffs and checkpoint commits.
- Default to writing/expanding tests for core logic.
- Run the repo's standard checks before you claim a task is done.
- Ask before adding new dependencies or changing scientific assumptions/public interfaces.

## Output format
When I give you a task, respond with:
1) Clarifying questions (only if needed)
2) Plan (steps, files, commands)
3) Risks (silent failure modes)
4) Then implement + summarize verification.
```

### 0.2 Install optional skills (recommended)
This repo includes skills under `.agents/skills/`. You can also keep personal skills in `$HOME/.agents/skills/`.

## 1) Start a task

### 1.1 Make the task concrete
Before invoking Codex, write down:
- **Goal** (what you want)
- **Constraints** (performance, dependencies, backwards compatibility)
- **Definition of done** (tests, outputs, docs)
- **Reproduction** (commands + minimal data slice)
- **Credibility method scope** (which package(s)/method families must be used)

Use `docs/TASK_TEMPLATE.md`.

### 1.2 Create a safe workspace
For non-trivial work:
```bash
git checkout -b feat/my-task
# optional: checkpoint commit before letting the agent make large edits
```

If you're using the Codex app, prefer isolated worktrees for parallel exploration.

## 2) Plan (Codex produces a plan you approve)

### Prompt template
```text
You are working in this repository.

Goal:
- ...

Context:
- ...

Constraints:
- ...

Definition of done:
- Tests: ...
- Commands passing: ...
- Outputs: ...
- Docs: ...

Please:
1) Read @AGENTS.md and any relevant files.
2) Propose a plan: steps + files to touch + commands to run.
3) Do not edit any files until I approve the plan.
```

## 3) Execute (small increments)

### 3.1 Prefer test-first
For new functionality:
1) Add a failing unit test (or golden-file style integration test).
2) Implement the smallest change to make it pass.
3) Run tests and lint.

### 3.2 Keep diffs reviewable
Ask Codex to:
- limit each change set to one cohesive idea
- avoid drive-by refactors unless explicitly requested

### 3.3 Log what happened
If the work is longer than one session, update `docs/HANDOFF.md`.

## 4) Evaluate (avoid being fooled)
Research code fails *silently* more often than it crashes.

Add cheap checks early:
- shape checks, monotonicity checks, sanity ranges
- diagnostic plots saved under `reports/diagnostics/`

Then promote the best checks to automated tests.

For meta-science analyses, include at least one check that compares standardized outputs across methods or package versions.

## 5) Stabilize (development mode)
Once the result looks correct:
- refactor for clarity (names, small functions)
- remove dead code
- make configuration explicit (YAML/TOML/CLI args)
- add docs (README + docstrings + `docs/DECISIONS.md`)

## 6) Ship
Before merging:
```bash
uv run ruff check .
uv run ruff format .
uv run pytest -q
bash scripts/run_pipeline.sh
quarto render notebooks  # if .qmd files changed
```

Then open a PR with:
- what changed
- what you verified
- how to reproduce
