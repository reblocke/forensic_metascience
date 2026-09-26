# INSPECT-SR local record model

## Authority and source snapshot

The local catalogue is pinned to INSPECT-SR guidance v1.1.2 at upstream commit
[`a349c4f1ddd9d232dfc2632938aad31382a9a770`](https://github.com/ianhussey/inspect-sr-guidance/tree/a349c4f1ddd9d232dfc2632938aad31382a9a770).
The official source files, retrieval receipt, attribution, license information,
and local checksums are under [`config/inspect_sr/v1.1.2/`](../config/inspect_sr/v1.1.2/).
The check wording in `catalogue.json` is copied from the official check headings;
domain focus labels and source hashes remain attached. The guidance states CC BY
4.0 for text and figures and MIT for code. This repository retains the upstream
files and their separate terms. Runtime code does not retrieve a newer revision.

The native method integration environment is pinned separately in
[`r_method_packages.lock.json`](../config/inspect_sr/r_method_packages.lock.json):
`scrutiny` 0.6.2 at commit `2a8eeac3ca9f893b946e45409317afaf42a805e3`,
`statcheck` 1.5.0, and `simdistr` 1.0.1. Each source archive is SHA-256 checked.
The setup script installs these only into the configured test library; the
production pipeline never installs packages. Runtime imports required by these
packages are prepared from CRAN at environment setup and captured in
`sessionInfo()`; they are not locked as a separate project dependency set.

Reproduce the local native lane after setting `R_LIBS_USER` to a disposable
library directory:

```bash
bash scripts/install_inspect_sr_r_methods.sh
FORENSICS_REQUIRE_R_INTEGRATION=1 PYTHONPATH=src uv run pytest -q tests/test_r_integration.py
```

The native lane checks exact package versions and fails if R or a pinned package
is missing. The Python-only lane may skip native integration; that skip does not
qualify the release gate.

Verify the snapshot and catalogue with:

```bash
PYTHONPATH=src uv run python -c 'from pathlib import Path; from research_project.inspect_sr import load_catalogue; load_catalogue(Path("config/inspect_sr/v1.1.2/catalogue.json"))'
```

The catalogue schema (`inspect_sr_catalogue_v1`), assessment record schema
(`inspect_sr_assessment_v1`), method revision (`inspect_sr_record_model_v1`),
and guidance version/hash are distinct fields. A source hash change invalidates
catalogue loading. A changed guidance version/hash requires a new assessment
revision with fresh pending responses; earlier assessments remain intact.

## Identity and source evidence

- Trial IDs are stable local IDs. A ClinicalTrials.gov ID is optional.
- Report IDs use a persistent identifier such as a DOI when known. If none is
  available, a stable local report key is required.
- Trial/report relationships are explicit. A report mapped to multiple trials
  requires a reviewed mapping before cross-report use.
- A source version is identified by source ID plus exact content SHA-256. A
  corrected source receives a new version; the old source version is retained.
- Evidence IDs use the source version, exact source locator, raw value/text,
  and extraction method/version. They do not use row numbers or extraction
  order as identity.
- Missing locators remain unresolved. Text extraction alone does not claim
  visual verification.

## Candidate evidence and method coverage

`src/research_project/inspect_sr/adapters.py` routes validated method outputs to
candidate evidence records. A candidate requires a completed or partial method
receipt with complete `method_receipt_v4` provenance, positive evaluated
coverage for the same run as the result, input evidence IDs drawn from that
receipt, and known source versions. Numeric extraction emits
`numeric_standardized_results_v2.csv`; run-scoped result IDs are separate from
source evidence IDs, which depend on source-version hashes, exact locators, raw
extracted values, and parser identity. Missing source hashes, locators, or
evidence IDs leave results unresolved. Older outputs remain readable as
historical records and are not promoted into current candidates. One
candidate can link to multiple checks while retaining one shared candidate ID;
this is not counted as independent evidence. Current machine routes are limited
to the numeric methods that actually emit those receipts: GRIM/GRIMMER/DEBIT,
statcheck, duplicates, and rounding-bias. The other checks are manual-only until
their producers have a validated receipt contract; similarly named Python
outputs or synthetic receipts do not activate a route.

The dossier reports method coverage as `available`, `missing`, `ineligible`,
`failed`, or `manual_only`. These are workflow/evidence states. Candidate records
use `candidate_only`; they have no INSPECT-SR response field. Check 3.2 is
manual-only at this revision: captions, figure numbering, and absence of image
inspection cannot produce a mapped result or a negative response. Actual image
or panel inspection must be recorded as human evidence.

Every check has an explicit manual evidence route in `CHECK_ROUTES`. Manual
observations require source identity/version, observation date, locator, text,
explanation, and reviewer identity. Search attempts and observations are
evidence records, not official Yes/No responses. Reassessment creates new dated
evidence with a new ID and may reference the earlier evidence using
`supersedes_evidence_id`.

Participant-flow arithmetic is accepted only when the source locator, population,
timepoint, mutually exclusive categories, and shared population/timepoint are
explicitly established. Clinical plausibility and arithmetic equality remain
separate tasks.

## Human review and storage boundary

An initial assessment contains all 21 official checks with
`workflow_status=pending` and `response=null`. The only response values are
`Yes`, `No`, `Unclear`, and `Not Applicable`; a pending or failed method never
becomes one of them. Method coverage, candidate evidence, human check responses,
domain judgments, overall judgments, and synthesis disposition are separate
records.

Generated candidate records belong in a fresh run-scoped directory beneath
`data/processed/`. Human-authored manual evidence and, in the later review
workflow, reviewer submissions and judgments belong under the ignored
`data/private/inspect_sr/` tree. `write_json_exclusive` refuses to replace an
existing record. Do not store source PDFs, private excerpts, correspondence, or
reviewer identity keys in public source control.

Independent submissions remain separate. The disagreement table is derived;
adjudication is a new human record referencing both submissions; finalization is
another record. Reviewer submissions, adjudications, resolved reviews, and
finalizations use version 3 contracts whose identities bind their complete
serialized content. Earlier versions remain historical and are not silently
upgraded. Finalization preserves the resolved review, both
reviewer-submission IDs, and the adjudication ID. A changed guidance or source
hash requires a fresh review revision. Early-stop reviews retain each unassessed check as
`not_assessed_early_stop`.

Use `scripts/inspect_sr.py` for the local offline workflow: prepare a pending
review, create source-versioned or manual evidence, then create a local
`inspect_sr_source_snapshot_v1` with `snapshot --assessment ...
--source-versions ... --evidence ...`. The snapshot stores the full versioned
records and checks current source bytes before each reviewed operation. Submit independent reviews,
compare, adjudicate, finalize, map native candidates, validate records, render
private HTML/PDF, and export synthesis. Human records are write-once under
`data/private/inspect_sr/`; public export is explicitly allowlisted, and its
approver identity is stored only in a separate private receipt. Start with
`uv run python scripts/inspect_sr.py --help`.

The report model in `src/research_project/inspect_sr/reporting.py` displays
human judgments only when the local snapshot, all referenced evidence, both
stored reviewer submissions, adjudication, and finalization validate together.
The `render` CLI command creates the private model and HTML/PDF under
`data/private/inspect_sr/reports/<assessment-id>/<revision>/`. The QMD reads
only that explicit model through `INSPECT_SR_REPORT_JSON`; a direct Quarto
render is suitable only for inspecting an already validated private model:

```bash
mkdir -p data/private/inspect_sr/reports
cp notebooks/inspect_sr_assessment.qmd data/private/inspect_sr/reports/
(cd data/private/inspect_sr/reports && \
  INSPECT_SR_REPORT_JSON="../review-model.json" quarto render \
  inspect_sr_assessment.qmd --to html --output review.html)
```

The rendered overview, full checks, evidence locators and alternatives, method
receipts, reviewer history, adjudication, and unresolved checks are all report
sections. Method packages are not required to render a review.

Synthesis exports require an approved `inspect_sr_synthesis_policy_v1` with an
explicit version, approver, approval date, rationale, and guidance hash. The
policy names both `primary` and `sensitivity` dispositions; the two may differ
only for `some concerns`. The caller explicitly chooses the policy variant,
unresolved-trial policy, and current source-snapshot hash for every trial.
Exports require finalized human adjudication. A changed source or guidance
revision is unresolved until reviewed again. One disposition is created per
trial, then added under `synthesis_*` fields on report and comparison rows with
cardinality checks; existing RoB, GRADE, effect, and other fields pass through
unchanged. Public export additionally requires
an explicit trial allowlist and reviewer identity and includes only trial,
report/comparison IDs, dispositions, reasons, and policy metadata. The
allowlisted public writer drops all arbitrary source text, notes, and reviewer
fields; approver identity remains in the private export receipt.

No domain or overall judgment is computed by this package. There is no universal
synthesis policy. FM-12 remains open until native R methods and current-run
HTML/PDF acceptance pass.
