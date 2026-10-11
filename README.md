# Forensic Meta-Science

A research toolkit for checking published findings and reviewing medical studies
with a traceable path back to the source documents. R runs the forensic methods;
Python prepares evidence and coordinates workflows; Quarto produces reports.
Researchers and reviewers choose the checks, verify source evidence and make the
final judgments.

## Choose a workflow

| Your goal | What the code provides | Start here |
|---|---|---|
| Screen a published study | Extract evidence, run selected forensic checks and retain method outputs, coverage and optional PDF reports. | `scripts/run_pipeline.sh`; [forensic contracts](docs/CREDIBILITY_CRITERIA.md) |
| Prepare private prediction checks | Extract text and scaffold transcription for summary-statistic, classification, calibration and cohort-flow checks. Calculations need populated tables. | `scripts/run_manuscript_review.sh`; [example below](#private-prediction-manuscripts) |
| Conduct an INSPECT-SR review | The pinned 21-check catalogue, source-linked evidence, independent reviewer submissions, adjudication, finalization and controlled synthesis export. | `scripts/inspect_sr.py`; [review guide](docs/INSPECT_SR.md) |
| Review a medical study bundle | Reconstruct study/comparison scope, plan review questions, import findings or use an authorized Codex reading pass, then verify, record human decisions and report. | `scripts/medical_review.py`; [medical guide](docs/MEDICAL_REVIEW.md), [Codex guide](docs/MEDICAL_REVIEW_CODEX_BACKEND.md) |
| Evaluate reading workflows | Paired comparison plans, blinded assessment packets, human reference judgments, frozen criteria, held-out study groups and descriptive R analysis. | `medical_review.py evaluation-*`; [evaluation guide](docs/MEDICAL_REVIEW_EVALUATION.md) |

Forensic screens cover baseline balance (`randomization`), numerical consistency
(`numeric`: GRIM, GRIMMER, DEBIT, duplicates and statcheck), report/protocol/registry
congruence (`registration`), caption and figure-sequence checks (`visual`),
source and open-practice evidence (`transparency`), and cross-category coverage
and concerns (`meta`). Plot digitization is an optional human-operated step.
Image manipulation assessment requires human inspection.

The workflows can be used separately. Medical reading adds proposals alongside
forensic evidence; it cannot create a qualified numerical result or an INSPECT-SR
judgment. Evaluation tooling does not establish medical performance by itself.

## Set up and try it without study data

Use Python 3.11 or later, Git, Bash and [uv](https://docs.astral.sh/uv/).
From a terminal:

```bash
git clone https://github.com/reblocke/forensic_metascience.git
cd forensic_metascience
uv sync --locked

# A small synthetic Python check; no paper, model call or R analysis.
uv run --offline --locked pytest -q \
  tests/test_pipeline.py::test_pipeline_writes_output_and_creates_zscore

# Preview stages and required source paths without creating a run.
bash scripts/run_pipeline.sh --study-id lungtime --forensics all --offline --dry-run
```

Add R and the required packages for forensic calculations. The
[pinned R setup](docs/INSPECT_SR.md#authority-and-source-snapshot) uses an isolated
library; production runs do not install packages. Quarto is needed for HTML/PDF
reports, with a LaTeX engine for PDF. Python-only planning, imports and Markdown
reports do not require those report runtimes. Codex reading has additional
runtime and authorization requirements described below.

### Configured published studies

Configurations for `lungtime` and `pronto` are in [config/studies/](config/studies/).
Stage authorized source PDFs at the paths declared in your chosen configuration.
For another study, add a configuration and check that its extraction rules fit
the documents; the example configurations are not universal PDF parsers.

```bash
bash scripts/run_pipeline.sh --study-id lungtime --forensics numeric --offline
```

Select a comma-separated category list or `all`. Numeric screening also extracts
baseline tables; randomization inference runs only when selected. Add
`--render-reports` for category PDFs. Registry retrieval requires
`--allow-network`; application `--offline` overrides it. Local registry snapshots
can be used instead. Current registry records cannot establish historical intent.

### Private prediction manuscripts

Preview the requirements for your authorized local manuscript:

```bash
bash scripts/run_manuscript_review.sh \
  --study-id my_prediction_review --report /path/to/manuscript.pdf \
  --review-type prediction_validation --offline --dry-run
```

This specialized route uses manually transcribed tables, currently organized
around Table 2, Table 3, Table E2 and Figure 1. Removing `--dry-run` starts
extraction, but the shell's initial blank templates cannot complete calculation.
Prepared, source-verified tables are needed by the [input builder](scripts/build_prediction_review_inputs.py)
and [R checks](scripts/run_prediction_review_forensics.R). PDF rendering is opt-in
with `--render-report`. For broader prediction-model reading, use the medical
bundle workflow below.

### Medical study bundles

Keep authorized originals and a `bundle.json` under
`data/private/medical_reviews/<study-id>/`. A bundle declares manuscripts,
supplements, protocols, analysis plans, registry records and corrections,
including missing sources, versions, permissions and study/comparison scope.
See the [bundle contract](docs/MEDICAL_REVIEW.md#source-bundle-boundary).

```bash
uv run --offline --locked python scripts/medical_review.py plan \
  --bundle data/private/medical_reviews/my_study/bundle.json \
  --profile clinical_trial --offline --dry-run

# Import genuine compatible Reviewer JSON already held locally.
uv run --offline --locked python scripts/medical_review.py import-reviewer \
  --bundle data/private/medical_reviews/my_study/bundle.json \
  --input data/private/medical_reviews/my_study/upstream.json --offline
```

Planning writes no files or model requests. Initial profiles are `clinical_trial`,
`observational_rwd`, `diagnostic_accuracy` and `prediction_model`; unresolved
designs retain unknown applicability and broad review questions.

After import or generation, inspect source links and missing coverage, use
`verify` for supplied counterevidence and arithmetic checks, and link existing
qualified numerical receipts where appropriate. Human source verification and
`decide` dispositions remain separate records. Use the printed run root with
`render --run PATH` for Markdown, adding `--html --pdf` for Quarto output.
Local replay and explicit recovery preserve failed attempts and original outputs.
The [medical guide](docs/MEDICAL_REVIEW.md) documents these stages and inputs.

**Optional Codex reading.** The `codex_cli` backend is implemented, but current
operational qualification is blocked: the locally patched macOS ARM64 runtime
`codex-cli-0.161.0-medical-no-tools-v1` repeats requests after an authentication
failure. Historical passing receipts cannot authorize the revised adapter.
A standard installed Codex CLI is also insufficient. After qualification passes,
the workflow is: qualify that runtime offline → prepare an indexed
source packet → obtain separate human authorization for those exact sources and
transmission purpose → run one reading pass → import, verify, decide and report.
It uses ChatGPT authentication with `gpt-6-astra` / `max`, one session, a
10-minute deadline, no automatic retries or fallback, and disabled tools/search.
Each environment needs a valid matching qualification receipt. See the
[operator guide](docs/MEDICAL_REVIEW_CODEX_BACKEND.md) for limits and commands and
[PR #15](https://github.com/reblocke/forensic_metascience/pull/15) for delivery status.
Synthetic isolation checks establish neither source permission nor medical
performance; real-study transmission and medical qualification are separate gates.

### Human appraisal and workflow evaluation

For INSPECT-SR, prepare the assessment and source snapshot, collect two independent
human submissions, resolve disagreements through adjudication, then finalize and
apply an explicitly approved synthesis policy. Public exports require an
allowlist. Start with `uv run --offline --locked python scripts/inspect_sr.py --help`
and the [INSPECT-SR guide](docs/INSPECT_SR.md).

For medical evaluation, use the [evaluation guide](docs/MEDICAL_REVIEW_EVALUATION.md)
to compare the adaptation, a strong single-reviewer prompt and the pinned original
Reviewer workflow. Separate comparisons using common inputs from those using
full document bundles. The tooling prepares packets and imports supplied outputs;
it does not run the original Reviewer comparator. Qualified assessors, source
approval, criteria frozen before unblinding and sufficient held-out evidence
are required for a medical qualification decision.

## Read the results and keep evidence private

Each forensic run has its own `run_manifest.json`, inputs, method outputs and
reports under `data/processed/forensics_runs/<study>/<run-id>/`. Private manuscript
and medical runs use the ignored `private_reviews/` subtree. Human records and
medical sources live under ignored `data/private/` stores. Keep private PDFs,
excerpts, identities, logs and dispositions out of commits and public artifacts.

Check coverage and method receipts before interpreting a finding. Missing inputs,
failed or blocked checks, and an empty findings list cannot provide reassurance.
PDF text matching does not verify tables, figures, signs or reading order.
Flags are leads for human review, not proof of misconduct or validity.
Rounding-bias and sequence diagnostics remain blocked; SPRITE is unimplemented.

## Code and further documentation

- [scripts/](scripts/): command-line entrypoints; use `--help` for options.
- [R/](R/) and [src/](src/): methods, parsing, validation and orchestration to reuse
  in your own workflow under the [evidence contracts](docs/CREDIBILITY_CRITERIA.md).
- [notebooks/](notebooks/): Quarto report templates.
- [docs/DECISIONS.md](docs/DECISIONS.md), [docs/HANDOFF.md](docs/HANDOFF.md) and
  [docs/TODO.md](docs/TODO.md): rationale, dated verification and deferred work.

For Python development checks without native R or report execution:

```bash
uv run --offline --locked pytest -q -m 'not native_r and not report_integration'
uv run --offline --locked ruff check .
uv run --offline --locked ruff format . --check
```

CI separately checks Python, native R and actual Quarto HTML/PDF reports.
Software checks are distinct from human source appraisal and medical validation.

Dependabot monitors Python and GitHub Actions dependencies and proposes security
fixes for review; merges remain manual. Routine version-update PRs are disabled.
The pinned R method archives and separately built Codex runtime require their own
dependency review and qualification. See [the monitoring decision](docs/DECISIONS.md#2026-10-11-restore-dependency-monitoring-and-consolidate-main).

Repository code is [MIT licensed](LICENSE); publisher documents and retained
third-party materials keep their own terms. Cite the repository and the commit
or release used. Maintainer: Brian W. Locke ([@reblocke](https://github.com/reblocke)).
