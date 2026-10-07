# Supervised development walkthrough

The offline foundation was merged through [PR #13](https://github.com/reblocke/forensic_metascience/pull/13).
Use one development study to check source preparation, evidence mapping and
operator effort before a larger medical pilot. A walkthrough is complete only
when genuine review output, verification, human dispositions and the standard
medical report have been inspected. Source intake and a successful plan are an
earlier checkpoint.

## Source intake

1. Choose an authorized development study and keep all related publications in
   the same study family. Once inspected, it cannot be untouched held-out data.
2. Retain immutable originals under `data/private/medical_reviews/<study-id>/`.
   Record retrieval URL/time, exact hashes, license, document role, publication
   identifier and local-processing permission. Preserve failed retrieval attempts.
3. Keep separate report identities for the manuscript, published protocol and
   analysis plan. An appendix belongs to its actual publication. A current
   protocol or registry record does not establish historical intent.
4. Declare unavailable documents explicitly. A text representation does not
   substitute for verified PDF layout. An older supplied protocol does not
   establish that later amendments are available or reviewed.
5. Retain parsed artifacts and their parser/version/hash. Inspect relevant PDF
   pages before relying on quotations, tables, signs, units or column order.
   Passing native-text routing does not establish semantic fidelity. A legitimate
   sparse continuation page is not automatically a manuscript defect.
6. Prepare `medical_review_bundle_v1` using the contract in
   [the medical review guide](MEDICAL_REVIEW.md). Keep reconstruction values
   evidence-linked, interpretations separate and unreconstructed fields unknown.

Source bytes, excerpts, private review logs and human records remain in ignored
stores. Do not put them into commits or CI artifacts.

## Planning checkpoint

Run the locked offline CLI, replacing the example study identity with the
explicit prepared bundle:

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py plan \
  --bundle data/private/medical_reviews/STUDY_ID/bundle.json \
  --profile clinical_trial --dry-run --offline
```

Inspect the actual study/comparison scope, representative specialist checks,
applicability, source-role gaps and parser limitations. Repeat planning and compare
the outputs. The planner writes no files; an operator can retain captured stdout
in an ignored diagnostic directory.

Expect `status=incomplete`, `model_calls=0`, `full_coverage=false` and unexecuted
checks. No missing role groups means only that the plan has a supplied member of
each required role group. It does not certify amendment completeness, source
fidelity, historical registry coverage or completion of medical checks.

An operator readiness report may summarize this checkpoint. Label it as intake
and planning only; it is not the standard medical-review report from an imported
or executed Reviewer run.

## Review and human verification

For the rest of the walkthrough, obtain a genuine compatible Reviewer JSON
payload and available provenance. Preserve its bytes and original identities.
Do not manufacture findings, an empty output placeholder or a completed
coverage record to get through the interface.

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py import-reviewer \
  --bundle data/private/medical_reviews/STUDY_ID/bundle.json \
  --input data/private/medical_reviews/STUDY_ID/upstream.json --offline
```

Use the printed private run root. Inspect source resolution and imported
coverage, then supply real counterevidence and supported numerical requests where
needed. Qualified numerical handoffs require the existing qualified method
receipts. Human dispositions and numeric input-review attestations must come
from the authorized human reviewer; an agent cannot stand in for that decision.
The guide documents `verify`, `verify-inputs` and `decide` input contracts.

Generate the standard report from the resulting explicit run:

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py render \
  --run data/processed/forensics_runs/private_reviews/STUDY_ID/RUN_ID --html --pdf
```

Inspect actual HTML/PDF output, evidence navigation, study/comparison labels,
unknown states, source gaps and caveats. Record preparation effort and any
workflow problems. No reassuring conclusion follows from an empty findings list.

## Next gate when review output is unavailable

Every live backend remains blocked. Prepare a focused backend implementation
plan after selecting the provider/backend/model and execution environment.
The next [backend implementation proposal](MEDICAL_REVIEW_LIVE_BACKEND_PLAN.md)
records the file map, sequential checks and outstanding selection/authorization
decisions; it does not itself qualify or enable a backend.
Before a live attempt, require:

- exact source-specific transmission authorization and purpose;
- separately approved search access, with search disabled by default;
- enforceable source/workspace, tool and egress restrictions;
- explicit session, duration, retry, resource and spending controls;
- auditable request/output/recovery records and operational isolation tests.

An API key or authorization flag does not qualify a backend. Approve the concrete
execution path and source record before sending study content. Medical pilot
definitions, qualified assessors, frozen criteria, blinded comparisons and
held-out qualification remain the subsequent scientific gate described in
[the evaluation guide](MEDICAL_REVIEW_EVALUATION.md).
