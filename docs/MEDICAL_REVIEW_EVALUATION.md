# Medical reviewer evaluation status

Software acceptance, live operational acceptance and medical qualification are
independent gates. Current status: software in progress; live operational testing
not authorized or performed; medical qualification pending.

WP5 is in progress. Its first increment implements offline plan validation and
immutable plan freezing; blinded packets, reference-ledger/adjudication workflows,
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
