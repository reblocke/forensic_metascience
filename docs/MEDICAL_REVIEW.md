# Optional medical manuscript reading layer

## Status and authority

FM-MED-01 is being delivered sequentially in this repository. The immutable
[implementation ticket](MEDICAL_REVIEW_TICKET.md) is the requirements source;
its proposed commands are not statements of current support. The accepted
implementation sequence is baseline → offline import → medical adaptation →
controlled execution → verification/reporting → evaluation readiness.

WP1–WP2 implement lossless offline upstream import, multi-document source
validation, structural extraction preflight, evidence-linked reconstruction,
comparison-specific medical routing and a deterministic private report model.
WP3 adds bounded local replay, source-specific authorization validation and
immutable recovery attempts. Every live backend is explicitly blocked because
filesystem/tool/egress restrictions are not yet qualified. WP4 now adds offline
counterevidence/arithmetic passes, private human dispositions, numeric source-review
attestations, read-only qualified R-reference handoffs and Markdown/Quarto reports.
WP4's requirement audit and required hosted Python/native/report gates passed at
`83e6252`. WP5 evaluation tooling is in progress: paired plan validation and
immutable freezing, operator-attested source-reference ledgers and offline
minimum-content source packets, offline candidate ingestion, metadata-blinded
human packets and operator-attested candidate assessment/adjudication are available.
Explicit synthesis accounting, threshold adoption, R analysis and final
qualification tooling remain unfinished.
Planning profiles encode review questions;
they do not establish live medical detection performance.
The feature is opt-in. No medical performance qualification is claimed.

The shared/module prompt catalogue also pins counterevidence and bounded-editor
templates. Hash changes or missing stage provenance refuse new planning/replay;
historical plans retain their recorded hashes. These templates authorize no model
execution or search. Counterevidence is supplied offline, and report assembly is
deterministic; the editor template has no enabled execution/adoption interface.

Existing `forensics_run_v3`, `method_receipt_v4`, numerical routes and INSPECT-SR
human contracts retain their semantics. Imported `assessment`, `numeric_check`,
confidence and suggested fixes remain model proposals. They never create a
qualified method result, an official response or a human judgment. Rounding-bias
and sequence diagnostics remain blocked; SPRITE remains unimplemented.

A `no_issue_identified` coverage declaration requires completed applicable work,
positive inspected units, cited evidence, and no missing materials or required
source gaps. Both planned `required_source_gaps` and legacy
`unresolved_required_sources` prevent reassurance. A process completing or an
empty findings list does not establish this coverage.

## Offline interface

Prepare the existing locked environment separately from production execution.
The importer and planner do not install anything, retrieve sources, transmit
content, execute supplied commands or call a model. JSON inputs have an explicit
20 MiB limit; oversized inputs fail instead of truncating evidence. This is an
input-size boundary, not a model token or spending limit.

```bash
uv run --offline --locked python scripts/medical_review.py --help
uv run --offline --locked python scripts/medical_review.py plan \
  --bundle data/private/medical_reviews/example/bundle.json \
  --profile clinical_trial --dry-run
uv run --offline --locked python scripts/medical_review.py import-reviewer \
  --bundle data/private/medical_reviews/example/bundle.json \
  --input data/private/medical_reviews/example/upstream.json --offline
```

Help and planning write no files, including Python bytecode. An absent bundle
produces `status=incomplete`, never an affirmative review-readiness result.
An existing bundle produces a deterministic context and check plan, plus
structural extraction diagnostics. It remains incomplete because checks have
not run. The four profiles are implemented planning scopes, not qualified
clinical review capability. Import is always offline, even without
the compatibility `--offline` flag. `run` executes only offline replay; live
requests produce a private blocked-attempt record and exit nonzero.

An import prints its run root. Repeating identical source bundle and exact input
bytes and unchanged adapter code reuses the same completed run only after checking its registered artifact
hashes. Adapter/reused-helper hashes are part of the import key. Inputs are parsed
from the same byte snapshot retained as the original output; a changed input or
bundle during import fails while preserving the attempted raw output. Changed findings under a previously imported finding identity conflict
before creating another run. Failed runs remain historical and require explicit
recovery; they are never overwritten or called successful replays.

## Source bundle boundary

`medical_review_bundle_v1` includes `study_id`, positive `revision`, `studies`,
`reports`, `documents`, `evidence`, `upstream_paper_id` and `planned_checks`.
Use stable local study identities for non-trial studies; `trial_id` is optional.
Reuse `stable_report_id`, `source_version_id` and `evidence_id` from the existing
record utilities where their semantics apply.

A report declares its `report_id`, related `study_ids` and `mapping_reviewed`.
A document declares its source ID/version, role, availability, report relationships,
path/hash when supplied, parser, date/date precision and private permissions.
Supplied sources require explicit `permissions.local_processing=true`.
Unavailable sources have null paths and remain unavailable, never empty files.
Initial roles are manuscript, supplement, protocol, SAP, registry snapshot/history,
correction and supplied analysis output. Changes require new source versions and
bundle revisions; old runs retain their originals.

Inputs and their parsed artifacts currently belong beneath
`data/private/medical_reviews/<study-id>/`. Stage authorized local immutable
copies there; the importer does not traverse the operator's wider filesystem.
All source and parsed-artifact hashes are checked on each import/replay.

Evidence declares its canonical ID, source version, locator, exact `raw_value`,
parser ID/version, parsed path/hash, zero-based `page_index`, original
`upstream_page` convention, printed page label and section. No implicit page
number conversion occurs. Quote presence in a hash-checked parsed artifact is
not proof that parsing preserved a PDF table, sign or reading order.
`visual_inspected` remains separate; imported links retain
`input_verification=proposed_transcription`.

Map upstream source paths explicitly with a document's `upstream_paths` aliases.
Paths in upstream objects are reference data, not paths to open. Resolution
requires one supplied source, one exact quote/declared locator match and an
unambiguous reviewed study mapping. Wrong pages, fuzzy quotes and ambiguous
mappings remain unresolved. Path traversal is rejected. External references
remain unresolved; importing a URL does not fetch it.

The synthetic workspace fixture in `tests/support/medical_review_fixtures.py`
illustrates the contract. Corrections can share a source ID but require a new
canonical source-version ID, an optional `supersedes_source_version_id` and a
bundle revision. Supersession references must be declared and acyclic. Dates
use explicit year/month/day precision; overlapping date windows cannot establish
which event occurred first. Current registry text does not establish past intent.

### Reconstruction and comparison scopes

Optional `context_fields` maps study IDs to reported fields. Each field separates
`reported` (known/unknown/conflicting/not_applicable), `interpretations` and
`preferred_design`. Known/conflicting values require scoped evidence IDs; unknown
or inapplicable states require a reason. Interpretations require cited evidence
and rationale, and remain proposals. Source-semantic verification is false;
specialists may challenge every shared premise.

Declare `comparisons` with comparison/study IDs, optional report IDs and
`profile_ids`. `comparison_context_fields` supplies separate reconstruction
per comparison; it never silently inherits a study-level estimand. A report may
contain both a trial contrast and a prognostic model. Explicit report scope
prevents a comparison from borrowing another report's SAP/supplement.

The four initial scopes are clinical_trial, observational_rwd, diagnostic_accuracy
and prediction_model. Unknown design uses a conservative union; systematic-review
and specialized-methods modules remain unsupported. Protocol checks explicitly
review the planned approach rather than demand observed results. Every planned
check records applicability/rationale, reviewer responsibility, required source
roles/gaps and disabled model/search permissions. Bundle check overrides outside
the selected catalogue scope cause explicit refusal rather than disappearance.

### Extraction, prompts and guidance

Preflight uses existing pypdf for PDFs and UTF-8 for text. Retained page text and
original private source references remain separate from visual inspection. Empty
PDF pages produce extraction shortfalls, not manuscript defects. Text files have
null page counts. Reading order/table structure are unsupported; signs, units,
formulas and cross-references remain unverified. No OCR repair is performed.

The versioned check catalogue encodes the approved ticket's review questions and
false-positive safeguards. Shared evidence rules narrowly adapt two pinned
Reviewer prompts; exact originals, hashes, upstream commit and MIT notice are
retained. Every shared/module prompt hash is checked when planning; symlink,
traversal, missing or changed prompts fail. Context/plan/preflight hashes bind
import identities, and mid-import plan drift preserves a failed raw attempt.

External CONSORT/SPIRIT, STROBE/RECORD, STARD, TRIPOD+AI and PRISMA packs remain
unapproved and unavailable. No guideline-specific claims are enabled. Flipping
approval flags alone is refused; activating future guidance requires verified
source bytes, version/applicability/license review and a tested loading path.

## Upstream contract and attribution

The adapter pins `Ingar30/reviewer` commit
`c591f4a498f6dc5083153811d6f678339cfb7c78` and schema SHA-256
`9399e39d1be1b6584bd452086bcb6f2f80a90b34826b8467658c3c88c8742641`.
The exact schema and MIT license are retained under
`config/medical_review/upstream/`; `provenance.json` records retrieval metadata,
checksums and reviewed extension references. Neither copied file was modified.

The upstream schema has no declared version field. Only its pinned shape is
accepted; unsupported fields/versions, duplicate JSON keys, nonfinite values,
conflicting source objects and duplicate finding IDs fail closed. Unknown
schema migrations require separate review and tests. The validator implements
only the vocabulary present in this pinned schema, using existing dependencies.

`adapter_upstream_revision` identifies the contract examined for compatibility.
`output_upstream_revision` is unknown unless the operator supplies a compatible
`--upstream-commit`; that declaration is provenance, not independently established
origin. Model/backend/prompt identities absent from the input remain unknown.
Exact raw input bytes, the original summary/notes and each complete original
finding are retained, including fields that have no qualified local counterpart.

## Coverage and artifacts

`medical_review_coverage_v1` keeps applicability, execution and assessment separate.
An upstream `run_status=ok` does not establish completion of any planned medical
check. Imported checks have unavailable coverage, `execution=not_requested`,
`assessment=not_assessed` and unknown (null) unit counts. The import itself may
complete. An empty finding list has precisely the same coverage limitation.

A no-issue assessment requires completed applicable execution, positive inspected
coverage, relevant evidence and no unresolved required-source gap. Failed,
blocked, unsupported and unrequested checks cannot provide reassurance.

The importer reuses the existing private forensic run root:

```text
data/private/medical_reviews/<study-id>/
  sources/                 # immutable authorized copies and parsed artifacts
  bundle.json
  upstream.json
  import_origins/           # immutable finding-conflict references

data/processed/forensics_runs/private_reviews/<study-id>/<run-id>/
  run_manifest.json
  generated/medical_review/raw/reviewer.json
  processed/medical_review/bundle.json
  processed/medical_review/study_context.json
  processed/medical_review/review_plan.json
  processed/medical_review/parser_preflight.json
  processed/medical_review/coverage.json
  processed/medical_review/proposals.json
  processed/medical_review/report_model.json
```

Each output is registered and hashed with existing run helpers. Override roots
must remain inside the same ignored private run boundary. Public destinations,
path traversal, symlinks, tracked private files and missing ignore protection
are rejected. Import-origin records carry their own content identity.
Medical records remain separate from `data/private/inspect_sr/`. Public export
is outside initial scope. No source excerpts or private logs belong in commits
or CI uploads.

## Acceptance, recovery and rollback

[MEDICAL_REVIEW_ACCEPTANCE.md](MEDICAL_REVIEW_ACCEPTANCE.md) tracks MED-01–27.
Run focused and baseline Python checks with the locked offline environment;
required native-R and synthetic Quarto lanes establish their own evidence.
Missing dependencies/skips do not pass a required lane. Mocked model responses
cannot establish clinical reasoning performance.

At WP1, failed runs are preserved and refused for replay; auditable attempt-level
recovery arrives in WP3. Do not delete a failed run to conceal its status. Preserve
raw outputs and use a new authorized import after resolving a real source/input
problem. Changed payload under an existing identity requires explicit conflict
resolution, not editing the historical record or bypassing the conflict index.

Rollback disables use of the new CLI and reverts its scoped code/config changes.
Existing workflows and historical numerical, medical and human records remain
readable. Preserve the ignored medical stores and import-origin references;
rollback must not erase an unsuccessful pilot.


## Controlled replay and the live gate

```bash
uv run --offline --locked python scripts/medical_review.py run \
  --bundle data/private/medical_reviews/example/bundle.json \
  --backend replay --input data/private/medical_reviews/example/upstream.json \
  --offline --max-duration-seconds 120 --max-source-bytes 67108864
# Explicit recovery creates a fresh attempt; all dependencies must still match.
uv run --offline --locked python scripts/medical_review.py run \
  --bundle data/private/medical_reviews/example/bundle.json \
  --backend replay --input data/private/medical_reviews/example/upstream.json \
  --offline --resume data/processed/forensics_runs/private_reviews/example/PRIOR_RUN
```

A replay creates a fresh canonical forensic run with immutable
`generated/medical_review/attempt_requested.json` and `attempt_result.json`.
The request binds bundle/context/plan/code, raw bytes, requested runtime/permissions,
authorization and limits. The result links a validated import run rather than
copying its proposals under a competing identity. Completed import stages can be
reused; incomplete imports require explicit resume and get a new suffixed import
attempt. Historical failed/interrupted output and manifests remain unchanged.
The attempt's own completed status never establishes substantive check coverage.

A trusted Python importer worker has a minimal environment, with no inherited
provider credentials. It accepts only fixed local importer operations, never
source-supplied commands. Immutable replay snapshots are hash-checked and local.
The source-byte cap is checked before worker execution. The replay worker gets
an enforced timeout using the remaining duration budget; local validation/setup
is measured but is not an OS-level hard deadline. One local session and zero
automatic retries are supported; other concurrency/retry settings are refused.
No provider fallback, quota escalation or claimed hard monetary cap exists.
Token/cost values absent from the input remain null. No model process runs.

The worker is **not a live model sandbox**. No staging directory or prompt is
claimed to enforce filesystem/tools/network isolation for a provider CLI. Every
live backend is currently blocked, even with otherwise valid source authorization.
This is the ticket's explicit blocked-live engineering path; operational smoke
testing and live sentinel isolation remain pending until a qualified backend
implementation exists. Offline replay remains usable without credentials.

### Source authorization contract

`medical_source_authorization_v1` contains exactly: schema_version,
bundle_sha256, sources, provider, backend, model, purposes, tools,
allow_web_search, valid_from, valid_until, approver and rationale. Each source
includes its canonical source_version_id, exact sha256 and classification.
The authorization must cover all supplied documents in the scoped bundle;
create a reduced explicit bundle if only some documents may be transmitted.
`purposes` must include medical_review. `tools` may name source_read/web_search;
search additionally requires allow_web_search=true and a separate CLI allow flag.
Provider/backend/model must match; dates require timezones and current validity.
The private approver and rationale are required. Authentication, registry-network
permission, publication licenses and authorization flags alone cannot enable a
live backend. No authorization is inferred from the implementation goal.

Application offline mode overrides every allow flag. `uv --offline` only controls
package resolution. A blocked or failed `run` returns exit code 3 with a private
run-root/status reference; validator/path errors return 2. Blocked/failed coverage
preserves applicability, null unknown unit counts and the stopping reason.
Public output roots, symlink references, corrupted receipts and changed resume
dependencies are refused. Successful/failed manifests are never reopened for edits.


## WP4 arithmetic and verification

`research_project.medical_review.numeric.calculate_request` implements the pure
`medical_numeric_check_request_v1` → `medical_arithmetic_result_v1` transform.
CLI/storage and separate human input-review attestations are implemented below;
read-only qualified-reference handoffs are described below. This core does not create a
numerical-method receipt or candidate.
Every result remains a proposed transcription until independently verified.

Requests declare run/proposal/study/comparison IDs, bundle hash, scoped evidence,
population, horizon, orientation, kind, typed inputs and optional reported comparison.
Supported kinds are percentage, participant_flow, binary_risk_contrast and
diagnostic_2x2. Unknown fields (including human/official/receipt fields) are refused.
Counts are nonnegative integers; reported values, tolerances and target prevalence
are bounded decimal strings. Results retain the exact request, calculator code
hash/version, explicit Decimal precision (34 digits), denominators and assumptions.
Participant accounting uses exact integer sums/differences even beyond the
decimal precision used for ratios. No source data is mutated and no supplied
code is executed.

Flow sums require explicitly mutually exclusive categories with the same population
and timepoint. Binary contrasts use unadjusted raw risks, exposed minus control;
adjusted/weighted/survival reconstructions are unsupported. Diagnostic sensitivity,
specificity and LRs use declared TP/FN/FP/TN counts. PPV/NPV from case-control or
unknown sampling requires a sourced target-prevalence assumption; cohort PPV/NPV
retains the declared representativeness assumption. Infinite/undefined ratios are
separate statuses with null values, never continuity-corrected or converted to
finite numbers. Joint marginal LR multiplication and inferential CI/P-value
reconstruction are unsupported here.

A reported comparison must match population, horizon, orientation, denominator
and unadjusted estimation. Incompatible estimates yield not_comparable, never a
false arithmetic contradiction. Finite comparisons use the supplied absolute
tolerance plus half a unit at the declared reported decimal precision (0–24).
Undefined/infinite values remain unassessed. Arithmetic agreement/disagreement
is not verification of extraction, estimand mapping or clinical interpretation.

### Offline verification and human boundaries

```bash
uv run --offline --locked python scripts/medical_review.py verify \
  --run data/processed/forensics_runs/private_reviews/example/IMPORT_RUN \
  --input data/private/medical_reviews/example/verification/pass.json
uv run --offline --locked python scripts/medical_review.py consolidate \
  --run data/processed/forensics_runs/private_reviews/example/METHODS_RUN \
  --run data/processed/forensics_runs/private_reviews/example/CLINICAL_RUN
uv run --offline --locked python scripts/medical_review.py decide \
  --run data/processed/forensics_runs/private_reviews/example/VERIFICATION_RUN \
  --input data/private/medical_reviews/example/verification/human.json
uv run --offline --locked python scripts/medical_review.py verify-inputs \
  --run data/processed/forensics_runs/private_reviews/example/VERIFICATION_RUN \
  --input data/private/medical_reviews/example/verification/numeric-review.json
uv run --offline --locked python scripts/medical_review.py render \
  --run data/processed/forensics_runs/private_reviews/example/VERIFICATION_RUN
# Add --html --pdf only after preparing the existing Quarto/R/TeX environment.
```

`medical_verification_input_v1` contains schema_version, counterevidence
and numeric_requests, with optional method_handoffs. Other fields are rejected;
older inputs without method_handoffs remain supported. Each counterevidence row declares proposal_id, disposition,
the unchanged reviewed_claim, strongest_alternative, rationale,
supporting_evidence_ids, contradicting_evidence_ids, missing_materials,
change_summary, model, backend and prompt_sha256. Unknown identities remain null.
Supported candidates require cited support; contradicted/already-addressed
dispositions require cited counterevidence. All five model dispositions remain
unverified by a human. Tests use supplied synthetic semantic responses; they do
not demonstrate clinical detection or counterevidence reasoning capability.

Each pass creates a fresh forensic run linked to its exact parent manifest and
original proposal snapshot. Raw input and calculator/audit code are archived and
registered. Parent inputs/manifests remain unchanged; mid-pass source/input/code
drift preserves a failed run. A historical arithmetic result whose code differs
is retained after archive/contract checks and explicitly labeled not reexecuted.
Archived arbitrary code is never executed to read historical results.

### Existing qualified method references

Each optional `method_handoffs` request contains exactly schema_version
(`medical_method_handoff_request_v1`), proposal_id, numeric_run_reference,
receipt_artifact, result_artifact, method_id, result_ids and rationale. Name an
existing terminal same-study numerical run beneath `data/processed/forensics_runs/`,
and its exact registered JSON/CSV receipt/result artifact paths relative to that
run. The numerical stage must be terminal; no newest-run search occurs. At most
64 requests per pass and 256 unique result IDs per request are supported. An
empty result-ID list can retain a method's unavailable/blocked coverage receipt.

This handoff reads the existing `method_receipt_v4` and `numeric_result_v2`
contracts and invokes the unchanged candidate qualifier against scoped canonical
bundle evidence. It creates a `medical_method_handoff_v1` reference, never a new
numerical result, method receipt or INSPECT-SR candidate. Missing source IDs or
locators remain unqualified; wrong identities, changed artifact hashes and unsafe
paths are refused. Partial failure and zero evaluated units remain visible, and
every reference has `review_reassurance=false`. Rounding-bias stays blocked.

References bind the original proposal, bundle, numerical manifest, full parsed
receipt/results and native-output bytes. A native output already registered in
the original numerical manifest has `binding=existing_run_receipt`; otherwise
its hash is explicitly `captured_at_handoff`, not claimed as an earlier receipt.
Later source/native-byte drift refuses reuse. The verification run archives the
existing qualifier/source-identity code as well as its medical adapter and raw
request. Production handoff does not invoke R; native integration tests execute
the existing pinned R engine to establish the real interoperability boundary.

New verification runs set `record_references_unique=true`: identical arithmetic
or method content identities appear once in the dossier while every attempt's
raw output, stage and lineage remain. Older runs without that setting retain
their historical representation; a new verification pass can normalize their
references without rewriting the old run or report.

### Consolidation and operator attestations

`consolidate` links 2–16 explicit compatible review branches. Bundle, context,
plan and parser-preflight snapshots must match exactly; differing snapshots and
duplicate/conflicting run/proposal identities are refused. Every original run
remains immutable. Repeated identical proposal/arithmetic identities do not
multiply evidence, and agent agreement remains non-independent. Human and
counterevidence records keep each proposal's original import reference, even when
reviewed from a consolidated dossier. Nested consolidation is unsupported; choose
explicit original review branches instead. No newest-run discovery is used.

`medical_human_disposition_input_v1` contains exactly schema_version, proposal_id,
disposition, human_identity, date, rationale, reviewed_evidence,
source_bytes_reviewed, locators_reviewed and supersedes. Each reviewed-evidence
row binds evidence_id, source_sha256, locator and raw_value. Require an explicit
timezone-qualified human date, identity, rationale and source/locator attestations.
Private write-once records live in the study's human_dispositions directory.
Revisions explicitly supersede the current same-reviewer/proposal record; old
bytes and original model provenance remain. Different reviewers' conflicting
decisions are shown as conflicts, never automatically adjudicated. A new context
does not inherit a decision bound to an older full proposal hash.

Software validates the declarations, identities and source hashes; it cannot
prove that the operator independently read or correctly interpreted the source.
Model verification cannot write these records or name a human reviewer. The
separate `decide` entrypoint is for an explicit human operator decision.

`medical_numeric_input_review_input_v1` separately binds an exact executed
result_id, human_identity, date, rationale, source_bytes_reviewed,
source_semantics_reviewed and field_bindings. Enumerate every non-null typed input
and population/horizon/orientation/kind/reported-comparison assumption. Each
binding supplies field, exact typed value, evidence_id, source_sha256, locator,
raw_value and interpretation. Every field must match the original request and
declared source. This creates a write-once `operator_attested_source_review`
sidecar; it never rewrites the original proposed-transcription result or creates
method/candidate eligibility. Corrected inputs require a new request. Confirming
a manuscript concern alone does not verify numerical extraction.

### Private reports and manual adoption

`render` creates a fresh report run with an explicit parent-manifest binding,
registered renderer code, deterministic report model, Markdown and manual
adoption packet. HTML/PDF are opt-in and record real Quarto/R versions and private
render logs; missing runtimes or failed renders preserve a failed run. Nothing is
installed during production execution. Quarto reads only its explicit current-run
JSON path and the trusted notebook template; it never discovers a newest report.

Every original proposal is displayed in exactly one conservative group. Exact
concern, claim, classification, scope, repair and resolved evidence identity must
match for grouping; a quote alone is insufficient. All member provenance,
conflicting severity/confidence and complete original finding fields remain in
the appendix/model. Summary notes and caveats cannot be dropped by validation.
Imported active Markdown, HTML, inline R and Quarto directives are escaped. Source
text cannot request commands, files or search. Large reports fail at the explicit
20 MiB JSON boundary instead of truncating evidence. Long display identifiers
wrap for PDF readability; machine-readable values remain exact.
Explicit upstream `category=reporting_gap` groups have a separate Reporting
omissions section. Optional improvements remain separate; mixed-category groups
stay among material proposals with their original categories displayed. This is
presentation of supplied labels, not automatic source-semantic classification.
Long display values include 64-character hashes; wrapping preserves every
character and never changes the JSON identity or original source bytes.
Long field labels or unbroken values use separate paragraphs so the label does
not consume the value's available PDF width.

New reports include protected original-source links and links beside exact cited
evidence. Targets are derived only from the rechecked bundle, retain the original
source version/hash, and use encoded paths relative to the private report layout.
Custom private output-root depth is recorded and validated; public destinations
remain refused. A declared zero-based PDF page index adds a one-based `#page=`
target; unknown page indices and non-PDF sources do not acquire invented pages.
Missing or permission-excluded sources stay explicitly unavailable without links.
Links neither fetch a source nor establish extraction fidelity or human review.
Historical renderer-bound reports may predate this additive navigation record;
they remain historical and are not rewritten on read.

All formats distinguish model dispositions from operator-attested human decisions,
retain unknown coverage and show numerical input-review status separately from
execution. They use the title **AI-assisted manuscript audit: unverified proposals**.
The manual packet retains proposals, evidence, human dispositions, arithmetic,
method-handoff and numeric-input-review IDs plus required
source/locator/wording/rationale checks. No INSPECT-SR store, official response,
finalized assessment, synthesis disposition or public export is written.
