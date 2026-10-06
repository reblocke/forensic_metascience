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
filesystem/tool/egress restrictions are not yet qualified. Numerical handoffs,
human dispositions, report rendering and medical evaluation remain pending. Planning profiles encode review questions;
they do not establish live medical detection performance.
The feature is opt-in. No medical performance qualification is claimed.

Existing `forensics_run_v3`, `method_receipt_v4`, numerical routes and INSPECT-SR
human contracts retain their semantics. Imported `assessment`, `numeric_check`,
confidence and suggested fixes remain model proposals. They never create a
qualified method result, an official response or a human judgment. Rounding-bias
and sequence diagnostics remain blocked; SPRITE remains unimplemented.

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
