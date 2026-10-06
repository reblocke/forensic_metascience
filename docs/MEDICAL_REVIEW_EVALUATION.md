# Medical reviewer evaluation status

Software acceptance, live operational acceptance and medical qualification are
independent gates. Current status: software in progress; live operational testing
not authorized or performed; medical qualification pending.

WP5 is in progress. Offline plan validation/freezing and source-reference ledger
validation/freezing, minimum-content source packets and offline candidate
ingestion, metadata-blinded candidate packets and operator-attested candidate
assessment/adjudication are implemented. Explicit synthesis membership and
loss/distortion accounting are implemented. Threshold adoption, R analysis
and final qualification tooling remain unfinished.
Actual source adjudication and live evaluation have not occurred. Before candidate
evaluation, approve the source corpus, providers/models, transmission/search
permissions, budgets, domain assessors and performance thresholds.

Compare the adaptation with a strong single-reviewer medical prompt and the
unmodified pinned Reviewer workflow. Preserve a computational forensic-only
reference branch. Common-input comparisons use equivalent evidence; full-bundle
comparisons require identical bundles or explicitly identify unmatched access.
Model/backend and effective permissions should be held constant where feasible;
otherwise label the comparison as workflow plus runtime.

Use authorized trials, RWD cohorts, diagnostic and prediction reports, including
clean sources, source-adjudicated concerns and paired defect/repair fixtures.
Previously analyzed sources are development data. Group dependence at the study
level. Keep the reference ledger hidden from reviewer workspaces. Preserve two
assessors' independent decisions and blinded adjudication where available.

Measure important reference issues detected, false/unresolved/optional concerns,
source attribution, synthesis losses, clean-control behavior, human verification
and revision time, failures, and total observed resource use including failed
attempts. Do not substitute finding count, agreement or verbosity for quality.
Separate extraction, reconstruction, reasoning, retrieval, numerical execution
and synthesis errors. Ledger recall does not measure every possible defect.

Approve thresholds before unblinding, then evaluate held-out studies over repeated
runs by design. Until sufficient evidence and an approved decision exist, the
feature remains opt-in and medically unqualified. Synthetic acceptance fixtures
provide engineering evidence only. No live evaluation is started by this file.

## Implemented plan boundary

`medical_evaluation_plan_input_v1` declares an `evaluation_id`, positive revision,
explicit nonnegative 31-bit seed, all three conditions, case records and null
`thresholds`. Each condition has a known condition ID and null or explicitly
declared provider/backend/model/tools/session-duration settings. Runtime equality
is planning metadata, not observed equivalence or source transmission permission.
Unequal declared runtimes are labeled `workflow_plus_runtime`.

Each case identifies its exact private bundle, development/held-out partition,
previous-analysis and synthetic flags, declared dependency group, applicable
initial profile IDs, one common-input manuscript version and the upstream
full-track source list. The initial unmodified upstream interface is main-only;
declaring supplement access without a verified adapter is refused. The two
adapted full-bundle conditions receive identical supplied source sets. Upstream
is explicitly unmatched when it lacks any of those sources. Source equivalence
does not establish extraction fidelity or executable backend compatibility.

Dependent reports are grouped using declared study families, canonical study and
report identities, and exact source content hashes. Development and held-out
partitions cannot split a connected dependency group. Renaming study/report/source
IDs does not make an exact source copy held-out. Previously analyzed or synthetic
cases cannot be labeled held-out evidence. These checks cannot establish unseen
corpus history or independence; human corpus approval remains necessary.

Validate a locally prepared plan without writes, calls, search or installation:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-plan \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/plan.json
```

Freeze only through the explicit operation:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-plan \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/plan.json --freeze
```

The input must be within its declared evaluation ID's private `evaluation/`
directory. Replace `EVALUATION_ID` and supply actual hash-validated bundles;
these examples do not create a corpus. Use
`config/medical_review/evaluation_plan.example.json` only as a synthetic template.
It deliberately has a placeholder source ID and cannot run unchanged.

Freezing creates a fresh `forensics_run_v3` under the existing ignored private run
root. It preserves exact raw plan bytes, comparator prompts/configuration,
upstream attribution and code, then registers `processed/medical_evaluation/plan.json`.
Repeated freezing creates a separate immutable attempt, retaining the same plan
identity for identical dependencies. Mid-freeze drift preserves a failed attempt
and raw input; it never publishes a completed plan. Dependent reuse checks source,
prompt/config and artifact hashes, plus the recorded archived-code binding.

Every plan retains `execution=not_requested`, disabled LLM/search permissions,
pending qualification and disabled default enablement. Freezing completion refers
only to this planning stage. Threshold approval/adoption is intentionally refused
in this first increment; no automatic threshold or medical acceptance decision
is supplied. The full WP5 exit gate remains open until the remaining tooling and
its actual acceptance evidence are delivered.

## Implemented source-reference ledger boundary

Create the reference ledger from source review before candidate evaluation. The
new command consumes an explicit completed frozen plan and a local input; it does
not discover a latest run, retrieve sources, call models or authenticate assessors:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-reference \
  --plan-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/PLAN_RUN_ID \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/reference.json
```

Replace both IDs with actual recorded paths. `medical_evaluation_reference_input_v1`
has exactly `schema_version`, the frozen `plan_id`, and `case_reviews`. Every
planned case requires one record with `case_id`, `assessors`,
`assessor_shortfall_reason`, and `adjudication`.

Each assessor declares an `assessor_id`, private `human_identity`,
`domain_qualifications`, timezone-aware `date`, `blinded_to_condition=true`,
`source_bytes_reviewed=true`, all supplied `reviewed_source_version_ids`, and an
explicit `issues` array. Assessor identities must be distinct. Two assessors are
the normal reference design; one requires a nonblank shortfall reason, retained
as an evaluation limitation. Neither identity uniqueness nor a credentials
string proves independence or domain qualification. All such declarations are
operator attestations, including blinding and source-byte inspection.

Each observation contains `issue_id`, `study_id`, nullable `comparison_id`,
`issue_type`, boolean-or-null `important`, `description`, and nonempty canonical
`evidence_ids` in its reviewed study/comparison/report scope. The adjudicator
declares the same human/source attestations, a rationale and explicit issues.
Each adjudicated issue contains the observation's scope/content fields plus
`reference_id`, `disposition`, `rationale`, and `assessor_issue_refs`. Membership
records have `assessor_id` and `issue_id`. Every assessor observation must be
accounted for exactly once; distinct issues sharing a quote are not automatically
merged. Adjudicator-discovered issues may have empty observation membership and
still require source evidence. Dispositions are `reference_issue`,
`plausible_but_wrong`, or `unresolved`; disagreements and original descriptions
remain in the raw input and ledger. No official assessment fields are accepted.

The frozen ledger retains exact raw bytes, code snapshots, parent-plan manifest
binding, canonical evidence/locators, study analysis units, all observations and
adjudication rationales under a fresh private `forensics_run_v3`. Repeating the
operation creates a new attempt rather than replacing the old record or plan.
Input/parent/source/code drift during freezing preserves a failed attempt.
Dependent reuse validates registered artifact hashes and the raw/code/semantic
bindings; changed source or prompt dependencies require a new plan and ledger.

An empty, explicitly reviewed reference scope is labeled
`no_reference_issue_in_reviewed_sources`, retains required-source gaps, and has
`universal_clean_claim=false`. Unresolved observations retain an unresolved scope.
No ledger is sensitivity to all possible scientific defects. Every ledger keeps
`medical_performance_validated=false`, `official_assessment=null`, and records
whether synthetic cases are present. These files do not write INSPECT-SR records.
The packet stage described below withholds this ledger and private human metadata
from reviewer packet roots. Actual backend isolation and blinded evaluation are
not established by either local preparation command.

## Implemented offline source packets

Stage an explicit completed reference-ledger run. The operation copies local
sources and public instructions only; it has no live execution or search option:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-packets \
  --reference-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/REFERENCE_RUN_ID \
  --repetitions 2
```

Replace the IDs with actual frozen paths. Repetitions must be integers in 1..64
and default to one. Every case gets all three conditions and both tracks per
repetition. Common-input packets contain only the exact manuscript version.
Adapted full-bundle conditions contain the identical supplied source set. The
main-only original comparator remains unmatched when it lacks other supplied
documents; no undeclared upstream multi-document adapter is substituted.

Opaque packet IDs and the predeclared seed determine a reproducible shuffled
administrative order. Each fresh canonical private run registers
`processed/medical_evaluation/source_packets.json`, the local request, code,
and every packet file. Repetition of preparation creates a new run, preserving
the same packet identities for unchanged dependencies/options. Each reviewer
root is `generated/medical_evaluation/reviewer_workspaces/PACKET_ID/`. Original
source bytes are copied to safe, bounded names; supported PDF/text/CSV/TSV/JSON
extensions are retained and other suffixes become `.bin` without changing bytes.
No extraction, OCR, code execution or source-fidelity assertion occurs.

`source_index.json` contains the opaque ID and staged source versions, hashes,
roles and local file names, with `source_fidelity_verified=false`. It has no
benchmark evidence annotations, private original paths, authorization records,
assessor identities, reference answers, or condition/partition/repetition map.
Preparation refuses sources in protected authorization/human/numeric-review or
evaluation stores. It also rejects recognized private review/evaluation/INSPECT-SR
record schemas in JSON, including nested records copied to `sources/` and
mislabelled as analysis output. Recognizable Reviewer output records are also
refused when they have no `schema_version`, as in the pinned upstream contract.
JSON privacy preflight is bounded and rejects
malformed or oversized JSON without treating that failure as a manuscript defect.
These controls do not establish confidentiality of arbitrary prose or unknown
record formats; operator corpus review and separate transmission approval remain
necessary, and live execution remains blocked.
The private administrative record retains those comparison identities, planned
runtime declarations, and exact original/upstream-path aliases. Staged aliases
are not inserted into old bundles and raw outputs are not rewritten. A later
candidate-ingestion adapter must bind citations to this recorded map explicitly.

The single-reviewer and medical-adaptation packets use the same public clinical
questions and safeguards. They do not copy document-derived context fields,
bundle check overrides/rationales, or source-reference evidence quotes. Reviewers
must reconstruct the study and applicability from the staged sources; the
declared routing-profile union is a hint, preserving mixed aims without copying
source reconstruction. The single-reviewer retains its strong prompt;
the adaptation retains its medical modules, counterevidence/editor instructions.
Public instructions and pinned output schema/license are byte-preserved.

Original-comparator packets retain only their source input/index and exact pinned
upstream schema, license and reference prompts. Those templates are not the full
executable Reviewer checkout, and their placeholders are not silently filled
with an adapted workflow. Its administrative status remains
`blocked_unmodified_workflow_not_staged_or_executed`. Actual unmodified workflow,
runtime settings, compatibility and permissions require a separately authorized
operational step; preparing a source packet does not reproduce that comparator.

File contents are read-only and non-executable (`0444`); packet directories are
read-only (`0555`). Reuse validates the exact file/directory inventory, modes,
registered hashes, parent manifest, source/prompt dependencies and archived-code
binding. Added inputs, symlinks, writable files or source changes refuse reuse.
Source/prompt/code drift during copying retains a failed attempt and completed
files rather than publishing `source_packets.json`. Metadata blinding does not
prove that assessors cannot infer a workflow from style. The candidate-output
packets below remove administrative metadata; actual independent source
adjudication and effective assessor blinding remain unverified.

Limits apply to copied workspace file contents: 64 MiB per packet and 512 MiB
total by default, explicitly adjustable with `--max-packet-bytes` and
`--max-total-bytes`. A preparation is also bounded to 1,024 packets, 16,384 files,
and 20 MiB per JSON artifact. Code/manifest bookkeeping is separate from workspace
byte limits. Exceeding a limit fails explicitly before staging where knowable;
changed source size is checked during streaming copy. No truncation, scope
reclassification, model fallback, token budget or spend guarantee is implied.
Split oversized corpora explicitly while preserving their declared study groups.

These are minimum-content artifacts, not a process sandbox. A future approved
backend must mount only its individual packet root and enforce filesystem/tool/
egress restrictions; the containing private run also has administrative material
and must not be given to a reviewer. All live backends remain blocked. Every
source-packet record keeps execution not requested, model/search permissions
disabled, backend isolation unqualified and medical performance unvalidated.

## Implemented offline candidate ingestion

Import explicitly supplied outputs against one completed source-packet run:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-candidates \
  --packets-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/PACKETS_RUN_ID \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/candidates.json
```

The input has exact fields `schema_version=medical_evaluation_candidate_input_v1`,
`packets_record_id`, and `attempts`. Each attempt has `attempt_id`, `packet_id`,
`status`, `stop_reason`, `origin=offline_supplied`, `runtime`, `upstream_revision`,
`usage`, and `outputs`. Attempt IDs are unique within an input. Multiple explicit
attempts may reference the same packet; unreported packets remain separately
listed rather than being counted as successfully reviewed. Supported declared
statuses are completed, partial, failed, blocked and not_started. Incomplete
attempts require a reason; blocked/not-started attempts cannot contain outputs.

Each output has a bounded `output_id`, `stage=reviewer|synthesis`, and a
repo-relative `output_reference` inside this evaluation's private `evaluation/`
store. Outputs use the pinned Reviewer JSON contract, with their paper ID mapped
explicitly to the packet ID or the original bundle's declared upstream paper ID.
Original fields, summaries, notes, model assessments and raw bytes are retained.
Reviewer and synthesis findings remain separate; source memberships, deduplication,
losses and distortions are not inferred. Synthesis-only supplied output cannot
establish what the earlier reviewers found.

`runtime` is null or an operator-reported object with provider, backend, model and
an explicit tools list. It does not establish observed settings, source access,
authorization or a qualified live execution. `upstream_revision` is null or the
pinned commit for an original-comparator packet; even a declared pinned revision
does not prove the full unmodified workflow ran. No permission is granted and no
backend/search command is invoked. The original live comparator remains blocked.

`usage` has elapsed_seconds, input_tokens, output_tokens, total_tokens,
cost_amount and cost_currency. Unknown measurements are null, never filled with
zero. Reported values must be nonnegative, tokens integral, and a known cost must
include its currency. Costs/usage from failed attempts remain in the record. No
price lookup, currency conversion, spend guarantee or invented measurement occurs.

The new canonical private run retains exact input/output snapshots, code and
the source-packet manifest binding, then publishes
`processed/medical_evaluation/candidates.json` only after validation. Re-import
creates a separate run; unchanged inputs preserve candidate identities and do
not establish independent observations. An invalid model schema or forged human/
official field preserves a failed attempt and its raw outputs, without publishing
eligible candidates. Unsafe input identities/paths are rejected before staging.
Input, output, parent, source or code drift during freezing preserves failure;
reuse verifies registered artifacts and reconstructs the source-scoped record.

Citation resolution uses exact staged names and existing source/evidence identity
functions, restricted to the packet's supplied versions. No original path alias
is written into historical bundles and no original output is rewritten. An
unselected supplement, fuzzy quote, ambiguous anchor or wrong locator remains
unresolved even if the administrative bundle contains a corresponding annotation.
An exact anchor remains a proposed transcription, not proof of source fidelity
or human verification. Findings remain human-pending, with no qualified result
IDs or official judgment. Empty findings retain unavailable review coverage.

Preparation is bounded to 1,024 attempts, 4,096 outputs, 20 MiB per JSON and
128 MiB of retained raw outputs. The actual serialized combined record must fit
the JSON limit; explicit splitting preserves packet/study identities rather
than truncating evidence. These are storage/preparation bounds, not model costs.
The synthesis stage below supplies explicit accounting. Approved thresholds, R analysis,
qualification reporting and actual held-out performance remain required.

## Implemented candidate assessment boundary

Prepare human review packets from one explicit completed candidate run, then
record locally supplied human decisions against that exact packet run:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-blind \
  --candidates-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/CANDIDATES_RUN_ID
uv run --offline --locked python scripts/medical_review.py evaluation-assess \
  --packets-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/ASSESSMENT_PACKETS_RUN_ID \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/assessment.json
```

Replace every ID with a recorded path. Neither command executes models, searches,
authenticates humans, writes INSPECT-SR decisions or enables the feature. A
completed stage is an engineering record, not medical performance validation.

Each human workspace is
`generated/medical_evaluation/assessment_workspaces/VIEW_ID/` in a new private
canonical run. Give an assessor only the individual workspace roots intended
for their review. The containing run retains private administrative condition,
case, packet, attempt, stage and candidate mappings and must remain withheld.
Packets omit model/provider metadata, reviewer prompts, benchmark issue ledgers,
private human identities and document-derived bundle annotations. They remove
finding ID/category/severity/confidence fields while preserving the substantive
claim, proposed evidence, numerical check, caveats and suggested correction.
Original outputs remain unchanged in the parent candidate run. Source-object
IDs are pseudonymized consistently with their claim links; known staged paths
are normalized to local human source files. Unmapped citation paths are retained
as evidence limitations. Text, style, source access and unmapped paths may reveal
origin: metadata removal is not verified blinding. Review and actual blinding
are operator attestations, not authenticated observations.

Human packets include **all supplied case sources** so assessors can verify a
claim against source truth and counterevidence. `reviewer_source_version_ids`
separately identifies the sources available to the model in that comparison.
This does not retroactively give a common-input reviewer supplement access.
Source bytes remain exact; source fidelity is not established by copying them.
All planned packets have views, including unreported packets or empty findings;
those views retain unavailable coverage and never imply a clean paper.

Source files and JSON packets are read-only (`0444`), directories `0555`. Reuse
checks exact inventory, modes, registered hashes, candidate/source dependencies,
parent manifest, and archived code. Preparation allows at most 64 MiB per view,
512 MiB total, 1,024 views, 16,384 files and 20 MiB per JSON record. Streaming
source drift/overflow fails without truncation and preserves a failed run.
These are local artifact bounds, not assessor isolation or model resource limits.

`medical_evaluation_assessment_input_v1` has exactly `schema_version`,
`assessment_packets_id`, nullable `supersedes_run_reference`, `assessors`, and
`adjudication`. Every person declares private `human_identity`,
`domain_qualifications`, timezone-aware `date`, `blinded_to_condition=true`,
`source_bytes_reviewed=true`, the full supplied `reviewed_source_version_ids`
for their `reviewed_view_ids`, `view_timings`, and explicit `judgments`. Primary
assessors also declare unique `assessor_id`; duplicate assessor human identities
are refused. Qualifications and independence cannot be established by these
strings. Every reviewed view has exactly one timing row containing `view_id`,
`verification_seconds`, and `revision_seconds`. Times are nonnegative finite
numbers or null; zero means reported zero, null means unavailable. No timing is
inferred from finding counts or file timestamps.

Every primary judgment has `item_id`, `disposition`, `issue_type`, boolean-or-null
`important` and `serious_false_allegation`, `source_attribution`, `evidence`, and
`rationale`. Dispositions are `confirmed_concern`, `unsupported_criticism`,
`unresolved`, or `optional_improvement`; a serious false allegation can only be
an unsupported criticism. Source attribution is correct, incorrect, unresolved,
or not_provided. A resolved judgment requires explicit source evidence; unresolved
judgments may lack it. Evidence rows have `source_version_id`, `locator`, and
`raw_value` within that candidate's case sources. Existing evidence identity
logic assigns a separate `human_source_review` sidecar identity. The operator
attests the quote/locator; the tool does not prove physical source verification
or mutate the bundle's annotations.

Each assessor must account for every item in their reviewed views. Adjudication
must cover every view/item, preserve the exact membership of all independent
observations through `assessor_ids`, and provide `reference_ids` and nullable
`assessor_shortfall_reason` for each judgment. Reference IDs are scoped within
their predeclared case, allowing equal local labels across different cases.
Fewer than two primary observations require an explicit shortfall reason rather
than a claim of independent two-assessor confirmation. Disagreements, original
input and separate primary judgments are retained. Empty views remain explicit;
no judgment or coverage is manufactured for them. This records candidate-level
judgments only: semantic deduplication and synthesis loss/distortion memberships
use the separate synthesis stage below and are never inferred from shared
wording or citations.

Each successful operation creates a new private `forensics_run_v3`, retaining
raw input/code, parent binding and `processed/medical_evaluation/assessment.json`.
Supersession requires an explicit private repo-relative prior assessment run,
the same packet scope/adjudicator, and a later adjudication date. Old records
remain byte-for-byte unchanged. Loaders validate every referenced predecessor,
raw/source/code/semantic bindings and refuse cycles or chains of 100 ancestors.
Input or dependency drift during recording retains failure without publishing
a decision. All records keep `medical_performance_validated=false`,
`official_assessment=null` and unavailable completed review coverage. Numerical
proposal qualification and existing human-adjudication contracts remain intact.

## Implemented explicit synthesis accounting boundary

Prepare stage-paired packets from one completed candidate assessment, then record
explicit local human memberships and judgments:

```bash
uv run --offline --locked python scripts/medical_review.py evaluation-synthesis-packets \
  --assessment-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/ASSESSMENT_RUN_ID
uv run --offline --locked python scripts/medical_review.py evaluation-synthesis \
  --packets-run data/processed/forensics_runs/private_reviews/EVALUATION_ID/SYNTHESIS_PACKETS_RUN_ID \
  --input data/private/medical_reviews/EVALUATION_ID/evaluation/synthesis.json
```

Each new private run retains its parent binding and code. Human roots remain
`generated/medical_evaluation/assessment_workspaces/VIEW_ID/`, within the **new**
run, with `synthesis_packet.json` and exact copied full-case sources. They label
`reviewer_input` and `synthesis_output` roles using opaque attempt/output scopes.
Original summary, notes, finding caveats and proposed numerical checks remain
visible; provider/model, original output names, conditions, benchmark ledger and
private human records remain outside the roots. Prior candidate-assessment
packets/decisions are unchanged. Stage structure, source access and textual style
can reveal origin; metadata removal does not authenticate blinding.

`declared_pair_complete` requires supplied outputs in both stages, a reported
completed attempt, and all reported output statuses `ok`. It is **operator
reported**, not verified execution, exhaustive reviewer coverage or a qualified
method receipt. A supplied empty synthesis output differs from an absent output.
No stage, zero loss, source agreement or clean review is inferred from empty
finding arrays. Partial/failed attempts and unreported packets remain traceable.

Input schema `medical_evaluation_synthesis_input_v1` has exactly
`schema_version`, `synthesis_packets_id`, nullable `supersedes_run_reference`,
`assessors`, and `adjudication`. Human/source/date/blinding/view/timing fields
match candidate assessment. Every person adds `groups` and explicit per-item
`judgments`; primary assessors have unique `assessor_id` and human identity.
Every reviewed view/item is accounted for. Independent grouping decisions,
disagreements, source evidence and operator attestations remain separate.

Groups have `group_id`, nonempty `reviewer_item_ids` and `synthesis_item_ids`,
`conflicting_interpretations`, and `rationale`. IDs are unique within a person's
input. Members must belong to the same packet and attempt, have the declared
roles and occur in at most one group. Item judgments must agree exactly with
these memberships. The program does not discover semantic duplicates or equate
agent agreement with independent evidence.

Item judgments have `item_id`, nullable `group_id`, `disposition`, boolean-or-null
`distorted`, `error_stage`, `evidence`, `critical_caveats`, and `rationale`.
Reviewer dispositions are displayed, grouped, dismissed, optional, unresolved,
deferred, lost or unavailable. Synthesis dispositions are mapped, new_in_synthesis,
unresolved or unavailable. Displayed/grouped/mapped items require explicit groups;
displayed versus grouped distinguishes one versus multiple original members.
Lost/new claims require a declared complete stage pair. Missing stages remain
unavailable; they cannot become observed losses, including caveat loss inside
an otherwise unresolved item. Unknown distortion remains
null, and an unavailable item cannot claim assessed distortion/caveats.

Each critical caveat has `input_quote`, nullable `output_quote`, status
preserved/lost/distorted/unresolved, and `rationale`. Input quotes must occur
literally in the associated finding or its supplied summary/notes; retained or
distorted output quotes must occur in an explicitly linked synthesis artifact.
Literal occurrence checks establish traceability, not semantic preservation.
Humans attest the interpretation. Lost caveats have no retained output quote;
distorted caveats require an explicit distortion flag. Resolved accounting also
requires case-scoped source evidence using the existing evidence-ID function;
physical source verification is not authenticated.

`error_stage` is source_extraction, study_reconstruction, reasoning, retrieval,
numerical_execution, report_synthesis, unknown or not_applicable. No error cause
is inferred from a model's confidence or a missing output. Adjudicated item rows
add exact `assessor_ids` and an explicit shortfall reason below two observations.
Every primary observation is retained even if final grouping changes.

Immutable same-scope/same-adjudicator supersession and bounded ancestry preserve
old bytes. Registered raw/code/parent/source/semantic bindings govern reuse;
source/input/code drift retains a failed attempt without publishing a decision.
Workspace and JSON limits match candidate assessment, with streaming copy checks
and exact read-only inventory validation. All records keep unavailable completed
review coverage, `medical_performance_validated=false` and
`official_assessment=null`. Existing INSPECT-SR and numerical contracts remain
unchanged. Qualification thresholds and R outcome analysis are separate work.
