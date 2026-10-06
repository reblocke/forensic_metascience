# Medical reviewer evaluation status

Software acceptance, live operational acceptance and medical qualification are
independent gates. Current status: software in progress; live operational testing
not authorized or performed; medical qualification pending.

WP5 is in progress. Offline plan validation/freezing and source-reference ledger
validation/freezing are implemented. Blinded packets, candidate adjudication,
threshold adoption, R analysis and final qualification tooling remain unfinished.
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
The forthcoming packet stage must withhold this ledger and private human metadata
from model workspaces; that stage and actual blinded evaluation are not implemented
by the reference-freezing command.
