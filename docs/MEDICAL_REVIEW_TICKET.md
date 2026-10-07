# FM-MED-01: Add an evidence-linked medical manuscript reviewer

**Status:** Proposed implementation ticket. No code changes or live model runs authorized by this document alone.
**Target repository:** `reblocke/forensic_metascience`.
**Inspected target revision:** `b629cab67ac8ee8c705a068ea81f5b849e095a26`.
**Reference implementation:** `Ingar30/reviewer`, inspected at `c591f4a498f6dc5083153811d6f678339cfb7c78`.
**Prepared:** October 4, 2026.
**Delivery form:** One repository-scoped feature, delivered through small, sequential pull requests.

## 1. Objective

Add an optional, study-design-aware medical manuscript reading layer inspired by Reviewer. Run it alongside the existing forensic methods, preserve its evidence-linked proposals, and make those proposals available for human verification and manuscript revision.

**Keep `forensic_metascience` as the system of record for source identity, executable checks, method coverage, and human adjudication. Do not turn an LLM criticism into a qualified method result or an INSPECT-SR judgment.**

The intended product is an inspectable medical manuscript audit, not autonomous peer review, a study-quality score, or a misconduct detector.

The medical layer must support two distinct products:

- **Manuscript appraisal:** scientific interpretation, methodological concerns, reporting gaps, numerical discrepancies, and proposed revisions.
- **Trustworthiness evidence assistance:** source comparisons and observations that a human may independently verify and explicitly adopt into the existing INSPECT-SR workflow when applicable.

These products may share evidence. They must not share an implicit scoring or judgment system.

### Scope of this ticket

Implement within the target repository. Do not create a second system of record, modify the upstream repository, fork or merge entire repositories, or require a separate maintained medical-review repository. Preserve the existing public pipeline and private `prediction_validation` route.

Build the offline importer and side-by-side pilot interface first. Then add the medical profiles, controlled execution, verification, and reporting. Keep the feature disabled by default after implementation; promotion requires a separately documented medical evaluation.

The interface names and new paths below are proposed. They do not currently exist unless explicitly identified as an existing integration point.

## 2. Verified starting points and boundaries

The following were inspected in the target repository. Recheck them against the implementation checkout before editing. Document meaningful drift rather than silently replacing newer behavior with the inspected version.

| Existing integration point | Verified responsibility | Required treatment |
|---|---|---|
| `AGENTS.md` | R-first forensic engines; Python helpers; Quarto reporting; explicit provenance and surgical changes | Preserve these conventions. Do not rewrite numerical engines in Python. [R1] |
| `scripts/run_manuscript_review.sh` | Private, offline `prediction_validation` route; fresh run roots; report rendering is opt-in | Leave existing arguments, defaults, and outputs compatible. [R2] |
| `scripts/forensics_run.py` and `research_project.run_manifest` | Run creation, output-root validation, stage updates, artifact registration | Reuse these interfaces instead of creating competing run identities. Inspect the helper implementation before reuse. [R3] |
| `docs/CREDIBILITY_CRITERIA.md` | `forensics_run_v3`; source/worktree fingerprints; method receipts; explicit network permissions; reporting contracts | Add medical-specific sidecars without weakening existing contracts. [R4] |
| `src/research_project/inspect_sr/adapters.py` | Qualified numerical candidates and explicit manual routes | Do not broaden `CHECK_ROUTES` or `METHOD_TO_CHECKS` for LLM findings. [R5] |
| `docs/INSPECT_SR.md` | Source/evidence identities; versioned, write-once human records; two-reviewer adjudication and finalization; restricted export | Reuse identities and preserve all authority boundaries. [R6] |
| Upstream `docs/extension_guide.md` | Prompt/config/schema extension points; conservative, evidence-preserving consolidation | Borrow narrow components with attribution rather than duplicating the whole stack. [R7] |

At the inspected revision, machine-routable INSPECT-SR candidates require qualified same-run numerical outputs and `method_receipt_v4`. Rounding-bias remains blocked; optional sequence diagnostics remain blocked; SPRITE remains unimplemented. **This ticket must not activate them, fabricate their receipts, or relabel their absence as a negative finding.** [R4–R6]

The current private prediction route uses specific transcribed tables and participant-flow inputs. Do not assume it is already a general medical parser or a universally applicable prediction-model audit. [R2, R8]

## 3. Architecture

```text
Authorized, versioned study sources
                  |
       Validated source bundle
                  |
       +----------+-----------+
       |                      |
Existing forensic       Optional medical
methods                 reading/review layer
       |                      |
Native outputs,         Raw reviewer outputs,
receipts, candidates    coverage, proposals
       |                      |
       +----------+-----------+
                  |
     Evidence-linked private audit dossier
                  |
      Counterevidence / verification pass
                  |
          Human verification
                  |
       +----------+-----------+
       |                      |
Manuscript appraisal    Explicit human adoption
and revision report     into INSPECT-SR, if relevant
                              |
                        Existing independent review,
                        adjudication and finalization
```

The branches are parallel. A reviewer may propose a numerical check; a numerical finding may prompt inspection of a footnote or supplement. Neither branch may silently overwrite the other's outputs.

### Minimal reuse strategy

1. Import upstream structured results through a thin, offline adapter. Retain exact original bytes and provenance.
2. Adapt selected upstream prompts and consolidation rules into a repository-owned medical profile. Record upstream paths, commit, hashes, license, and local modifications.
3. Keep the original upstream workflow available only as a separately authorized, pinned comparator in an isolated workspace. It is not a required runtime dependency for existing workflows.
4. Do not assume upstream has a stable multi-document API or accepts new medical schemas. Implement an explicit adapter boundary.
5. Do not import upstream's entire parser, orchestration framework, provider settings, or model defaults by default. Reuse existing extraction where adequate; assess specific parser gaps separately.

Preserve upstream attribution and applicable license notices for copied material. Do not publish source manuscripts, upstream runtime workspaces, provider transcripts, or licensed methods PDFs with the code.

## 4. Scope and delivery gates

### Initial supported profiles

Implement a shared clinical-methods core with four initial profiles:

- `clinical_trial`, including flags for randomized, quasi-randomized, cluster, noninferiority, and feasibility designs.
- `observational_rwd`, including descriptive, causal/comparative-effectiveness, EHR, claims, and target-trial-emulation questions.
- `diagnostic_accuracy`.
- `prediction_model`.

A paper can have multiple aims and profiles. Distinguish diagnostic prediction from prognosis and from treatment-benefit prediction. A trial report can also contain a prognostic model; do not force one exclusive label onto the entire document.

Recognize `systematic_review_meta_analysis`, `protocol`, `methods`, and `other` in routing. A protocol may use an applicable initial profile with stage-appropriate checks. Full systematic-review/meta-analysis and specialized methods modules are deferred. Mark unsupported checks as such; do not apply the closest profile and claim complete coverage.

### Non-goals

Do not build a new web application, autonomous submission system, investigator reputation score, automatic fraud allegation, or universal quality ranking. Do not automate official RoB, GRADE, QUADAS, PROBAST, or INSPECT-SR judgments. Do not execute arbitrary code supplied in a paper or generated by a reviewer. Do not add automatic OCR repair, graph digitization, or undisclosed retrieval of confidential source material.

Do not redesign unrelated R packages, private-record workflows, or existing reports. Model and backend comparison is an evaluation task, not a reason to implement a generic plugin framework.

## 5. Source bundle and study reconstruction

### 5.1 Source bundle

Add a versioned `medical_review_bundle_v1` manifest. Reuse existing source/evidence identity functions wherever their semantics fit. Add a wrapper or explicit mapping for non-trial studies; do not fabricate trial IDs merely to satisfy INSPECT-SR structures.

The bundle must identify:

| Element | Required information |
|---|---|
| Study/report mapping | Stable study and report IDs; optional trial IDs; explicit report-to-study relationships; reviewed mappings for multi-study reports |
| Documents | Manuscript, supplement, protocol, SAP, registry snapshot/history, correction, or supplied analysis output; source role and version |
| Provenance | Exact content hash, original local source reference, retrieval metadata where applicable, document date and date precision, and parser identity |
| Availability | Supplied, referenced-but-missing, inaccessible, excluded by permission, or not applicable; do not represent missing documents as empty files |
| Evidence | Page index and printed label when available; section; table/figure/cell or text offsets; exact text/raw value; source and parsed-artifact hashes |
| Permissions | Source classification and authorized processing/transmission scope, stored privately |

Preserve corrections and historical versions. A changed source creates a new version and bundle revision. Never overwrite a source or silently redirect old evidence to revised text.

Registry history is local-input-first, consistent with the existing repository. Adding an automatic history endpoint requires separate source and interface validation. Current registry content is not evidence of what was specified before enrollment or analysis. Record unknown dates as unknown; compare chronology only at the precision supported by the sources. [R4]

### 5.2 Parser preflight

Run local extraction and a deterministic structural preflight before substantive review. Assess page coverage, reading order, table structure, signs, units, formulas, and cross-references to the extent that the parser can actually check them. A parser check is not proof of source fidelity.

Retain both extracted text and access to original pages. Record visual inspection separately from text extraction. Unsupported image access, absent supplements, unusable tables, or uncertain signs must constrain downstream verification.

Do not invent missing cells, signs, denominators, equations, or figure values. Do not turn a parser failure into a manuscript defect. Document any optional model-assisted parser audit as a model assessment, not deterministic validation.

### 5.3 Structured study reconstruction

Before substantive reviewers run, create `medical_study_context_v1`. Each asserted field needs evidence or an explicit uncertainty state. Represent what the paper says separately from the system's interpretation and the target design a reviewer would prefer.

Capture, where applicable: scientific aim; target/source/analysis populations; eligibility; participant versus encounter unit; exposure/comparator; assignment; time zero; washout; follow-up; outcome definition and measurement; intercurrent events; censoring; estimand; analysis population; effect scale; missing-data approach; and prespecified/exploratory status.

For diagnosis/prediction, also capture the intended use, index time, reference standard or prediction horizon, threshold, predictor availability, and development/validation setting.

Do not let a mistaken shared reconstruction become an unquestioned premise for every agent. Each specialist must be able to inspect the cited sources, challenge the reconstruction, and preserve a competing interpretation.

## 6. Medical routing and reviewer responsibilities

### 6.1 Routing contract

Use an explicit, versioned check catalogue and a `medical_review_plan_v1` containing check IDs, applicable study/comparison IDs, assigned reviewer, required source roles, applicability rationale, and execution permissions.

Core responsibilities are source consistency, claim–evidence alignment, statistical interpretation, clinical meaning, and reporting completeness. These are responsibilities, not a requirement to spawn a separate model session for every heading.

Conditional specialists cover trial design/estimands, causal observational design, RWD measurement, diagnostic accuracy, prediction/AI, missingness/competing events, harms, and implementation/economic claims. Literature/reference lookup and copyediting are optional tracks, not mandatory prerequisites to clinical validity review.

Skip a check only with a recorded scope reason. Uncertain classification triggers the relevant union of profiles or an explicit unresolved route. A resource limit may defer checks, but cannot change their applicability to `not_applicable`.

Output-free planning must not secretly call a model. It may use operator-specified profiles and deterministic cues. Any model-assisted routing belongs to the explicitly authorized live stage and must retain its own execution receipt.

### 6.2 Medical checks to encode

These requirements implement the agreed review specification. They are not claims that upstream already provides the checks or that the adaptation has been validated.

| Module | Minimum review questions | False-positive safeguards |
|---|---|---|
| Trial design and estimands | Assignment mechanism/concealment; clustering; eligibility/assignment/follow-up alignment; ITT, per-protocol or as-treated contrast; intercurrent events; missing outcomes; prespecification; contamination and implementation | MRN parity is not concealed random allocation. A balance-table difference alone does not prove randomization failed. A legitimate pairwise comparison need not include every trial arm. |
| Observational causal design | Treatment strategies; time zero; prevalent users; immortal time; post-baseline conditioning; confounding by indication/severity/frailty/access/adherence/trajectory; positivity and remaining assumptions after matching/weighting | Do not demand causal identification for a descriptive aim. Identify the actual selection or confounding mechanism before asserting bias or its direction. Matching is not proof that all relevant confounding was removed. |
| RWD measurement | Code/phenotype logic and validation; repeated codes, labs, medication/procedure/encounter logic; temporal anchoring; capture outside network; utilization-driven selection; linkage; source coverage and denominators | Absence of a code is not automatically absence of disease. Requiring a test, lab, note, or follow-up encounter may alter the cohort; state the mechanism rather than issue a generic collider warning. |
| Diagnosis | Sampling scheme; reference-standard validity; incorporation and verification concerns; index/reference timing; thresholds; indeterminate results; reconstructable 2×2 counts; likelihood ratios and intended-use applicability | Case-control prevalence must not be substituted for clinical prevalence. Do not infer joint LRs from marginal LRs without a stated dependence assumption. Do not diagnose a specific bias direction without supporting design information. |
| Prediction/clinical AI | Prediction time/horizon; leakage; patient/site/time splitting; preprocessing within validation; calibration and uncertainty; discrimination versus utility; external validation scope; treatment-benefit versus risk prediction | Model development does not itself establish deployment benefit, but absence of an implementation trial is not automatically a defect in a development paper. Do not treat a high AUROC as sufficient evidence of clinical utility. |
| Inference and HTE | Effect sizes and intervals; clinical thresholds; subgroup interaction and scale; multiplicity; risk versus effect modeling; within-study versus between-study comparisons; noncollapsibility | One subgroup crossing the null and another not crossing does not establish a subgroup difference. Do not equate nonsignificance with equivalence or automatically call every nonsignificant result uninformative. Do not demand post-hoc power. |
| Noninferiority | Margin and its rationale; loss of efficacy versus burden/harms; estimand; adherence/crossover; uncertainty and assay sensitivity | Do not invent a universal margin or automatically interpret a declared noninferiority result as clinical equivalence. Distinguish reporting gaps from demonstrated design flaws. |
| Outcomes, missingness, competing events | What the measure estimates; death/discharge/disenrollment handling; risk versus hazard; days-alive/free definitions; recurrent versus first events; observation window and completeness | Do not automatically impute outcomes after death or censor competing events as ordinary loss to follow-up. Do not demand Fine–Gray for every competing-risk question; match the analysis to the estimand. |
| Harms and clinical interpretation | Ascertainment method, population, instrument, denominator and observation time; missing versus absent events; benefits/burdens; surrogate versus patient-important outcome; appropriate absolute effects | Similar counts do not establish safety when ascertainment or precision is limited. A recorded adverse event is not automatically an adverse treatment effect. Do not manufacture a clinical importance threshold. |
| Implementation and economic interpretation | Exposure to the implemented intervention; adaptations; fidelity; intended versus delivered strategy; payer/system perspective; spending horizon; death/disenrollment; implementation cost and net cost | Retain relevant economics capabilities for health-services papers. Do not confuse spending prediction, utilization reduction, savings, and cost effectiveness. |

For every material concern, require the implicated claim, source evidence, why it matters for this estimand, plausible alternative explanation, feasible correction, and suggested manuscript wording where useful. Separate confounding, selection/collider bias, measurement, missingness, model misspecification, and transportability.

Bias direction must be `unknown` unless a specific mechanism supports it. A repair may be rewording or clarification rather than a new analysis. No generic limitation inventories or demands for every possible sensitivity analysis.

### 6.3 Versioned methods guidance

Store concise, approved rule summaries with provenance, applicability, version, and license metadata. Separate reporting references from risk-of-bias/appraisal references and from interpretive methods papers.

Candidate reporting families are CONSORT/SPIRIT, STROBE/RECORD, STARD, TRIPOD+AI, and PRISMA. Verify and pin the actual sources before enabling guideline-specific claims. Do not assume the currently newest version should retrospectively determine whether an older paper complied with publication-time requirements.

The existing INSPECT-SR snapshot remains unchanged. Unavailable or unapproved guidance must appear as unavailable coverage, not be reconstructed from model memory. Do not copy the user's whole PDF collection into the repository or treat opinion/commentary as a universally binding rule.

## 7. New records and semantic invariants

Use small, versioned schemas and semantic validators. Prefer existing dependencies. Do not add an ORM, database, generic agent framework, or duplicate storage engine for this feature.

### 7.1 Reviewer proposals

Add `medical_reviewer_proposal_v1`, distinct from INSPECT-SR candidates and method receipts.

| Field group | Required content |
|---|---|
| Identity | Run, bundle/context/plan hashes, study/report/comparison scope, reviewer role, original upstream finding ID, stable namespaced proposal ID |
| Origin | Import or medical-native generation; upstream commit/schema if relevant; prompt/profile/model/backend/CLI identifiers where available; exact raw output reference/hash |
| Claim | Original finding text; normalized concern; implicated manuscript claim; check IDs; explicit proposal type |
| Classification | Reporting gap, methodological concern, numerical discrepancy, claim overreach, source discrepancy, parser artifact, unverifiable question, or optional improvement |
| Impact | Proposed severity and rationale; consequence for estimate/target/interpretation; bias direction with justification or `unknown` |
| Evidence | Supporting and contradicting source/evidence IDs; exact locators; resolution status; assumptions; missing materials |
| Repair | Specific clarification, analysis/design correction, or wording; distinguish necessary repair from optional extension |
| Links | Existing qualified result/receipt IDs and optional proposed numerical-check request; no invented method result |

Model confidence is a self-assessment, not a calibrated probability. Human verification status is stored in a separate record and defaults to pending. A model may not set itself to `human_verified`, author a human identity, or assign an official check response.

Import upstream fields losslessly. In particular, preserve `assessment`, `numeric_check`, `source_objects`, `claim_evidence_links`, and `cannot_verify_reason` as original data without translating their semantics into official responses or qualified numerical outputs. Unknown upstream versions fail closed; any migration must be explicit and tested.

Resolve references against the supplied bundle, not the operator's whole filesystem. Missing or ambiguous locations remain unresolved. Do not claim exact evidence identity from fuzzy matching alone. Duplicate import is idempotent; differing contents under the same upstream identifier create a conflict, not an overwrite.

### 7.2 Coverage is not a findings count

Add `medical_review_coverage_v1` with one record per planned check and study/comparison scope. Keep these axes separate:

- **Applicability:** `applicable`, `not_applicable`, `unknown`, with evidence/reason.
- **Execution:** `not_requested`, `not_started`, `completed`, `partial`, `failed`, `blocked`, or `unsupported`.
- **Assessment:** `potential_issue`, `no_issue_identified`, `not_reported_in_supplied_sources`, `cannot_verify`, or `not_assessed`.

Record planned/inspected source units, omitted units, evidence used, missing materials, and why the check stopped. Unavailable counts are null, not zero. These units describe declared coverage of a bounded task, not sensitivity to all possible paper defects.

A completed process may yield `cannot_verify`; a failed process cannot yield `no_issue_identified`. For a no-issue assessment, require a completed check, documented relevant evidence, and no unresolved required-source gap. An empty findings array alone never satisfies this rule.

Legacy/upstream imports lacking per-check coverage retain a completed *import* status but unavailable *review coverage*. Do not infer check completion from reviewer names, `run_status=ok`, or the existence of a report.

Keep the existing `method_receipt_v4` semantics and fields untouched. A model coverage record is not a numerical-method receipt.

### 7.3 Verification and human decisions

Add append-only `medical_verification_v1` records for the counterevidence pass. For each material proposal, inspect the original claim and the strongest accessible alternative explanation, including supplemental footnotes, corrected versions, estimand differences, and parser limitations.

Allowed model verification dispositions: `supported_candidate`, `contradicted`, `already_addressed`, `optional_extension`, and `unresolved`. None means independently human-confirmed. Record model/backend identity, evidence, and changes from the original proposal. Preserve rejected proposals and their reasons.

Store human dispositions separately as write-once `medical_human_disposition_v1`: pending, confirmed concern, dismissed, unresolved, or optional improvement. Require private human identity, date, rationale, reviewed evidence, and original proposal reference. Revisions supersede but never replace earlier records.

Do not auto-submit INSPECT-SR observations or reviews. Initially produce an evidence packet for manual adoption. A later explicit adoption command may create a separately attributed human observation only after the reviewer checks source bytes, locators, observation wording, and rationale. It must retain the agent-origin link and must not set a check response or judgment.

The existing two-reviewer, adjudication, finalization, and synthesis-policy requirements remain intact. A finalized manuscript critique is not a finalized INSPECT-SR assessment. Existing report schemas may not be widened merely to display agent proposals as adjudicated evidence.

## 8. Numerical verification boundary

A proposed `medical_numeric_check_request_v1` describes a requested calculation and its inputs. It is not evidence that execution occurred.

First route eligible checks to existing qualified engines using their current input contracts. For new arithmetic, implement a small deterministic calculator with explicit applicability and a separate typed result. Qualification for INSPECT-SR candidate mapping is outside this ticket.

Initial arithmetic targets: counts/percentages, participant accounting, unadjusted binary risk contrasts, and diagnostic sensitivity/specificity/LRs from verified counts. Preserve reported precision, denominator, orientation, time horizon, population, code/version, inputs, output and tolerances.

Require these protections:

- Only add participant-flow categories established as mutually exclusive and belonging to the same population/timepoint.
- Do not compare crude reconstructed effects with adjusted, weighted, imputed, clustered, or survival-model estimates as if they were the same estimand.
- Do not declare a confidence interval/P-value mismatch without the relevant inferential method, tail, adjustment, and rounding information.
- Do not calculate clinical PPV/NPV from an investigator-set case-control fraction without an appropriate target-prevalence assumption.
- Do not silently add continuity corrections or replace infinite/undefined ratios with finite values.
- Do not reduce a joint diagnostic finding to multiplied marginal LRs unless the required dependence assumption is explicit.
- Do not execute a model-generated snippet. Use reviewed calculator functions with typed inputs, or retain the proposal for manual verification.

LLM-extracted numerical inputs remain proposed transcriptions until source semantics are verified. Executing arithmetic correctly does not verify extraction correctness. Keep input-verification status visible next to the result.

## 9. Controlled execution, privacy, and reproducibility

### 9.1 Offline first

The importer, validators, replay tests, report builder, and human-disposition workflow must work without model credentials or network access. Existing commands remain offline by default.

The new live runner requires a provider-scoped authorization record and explicit `--allow-llm`. Search requires separate `--allow-web-search` and authorization for manuscript-derived queries. Existing registry `--allow-network` permission must not implicitly authorize model transmission or search.

Application-level `--offline` takes precedence over all allow flags. `uv --offline` controls dependency resolution only; it is not a network security boundary for a running model CLI.

Authorization must identify source bundle/hash, permitted documents, provider/backend, purposes, tools/search, validity period, and private approver identity. Do not infer permission from authentication, a local installation, public-repository status, or a generic publication license.

### 9.2 Enforce, do not merely prompt

Run the model against a minimum-access staging workspace. Sources are read-only. Human identities, assessments, unrelated project files, credentials, and benchmark reference ledgers are not mounted into the reviewer workspace.

Treat manuscripts, fetched pages, and imported reports as untrusted content. They cannot authorize commands, change the roster or schemas, enable network access, request secrets, or override the review instructions. Refuse path traversal, external/symlink escapes, arbitrary shell execution, and active content in imported material.

Use backend-supported restrictions and isolated process permissions. If a required restriction cannot be enforced for a backend/version, refuse that live mode and retain offline import/replay. Do not claim a no-search or no-egress mode based only on a prompt instruction. Do not bypass CLI approval/sandbox controls.

Preserve the original comparator's actual settings. An upstream comparator requiring transmissions not authorized for a source must remain unrun; silently changing its tool permissions produces a different comparison condition.

### 9.3 Run records and recovery

Reuse the run root and manifest helpers. Record source/context/plan/profile/prompt hashes, code revision and worktree fingerprint, backend and effective model identity, upstream revision if used, source access, search activity, raw outputs, validators, stage status, and verification/report lineage.

Require explicit concurrency, session/retry and duration limits. Record token usage and cost estimates when available; unknown remains unknown. A session count is not a guaranteed token or monetary cap. Do not promise a hard spend ceiling that the backend cannot enforce. No automatic provider/model fallback or paid quota escalation.

Successful stages are immutable. Resume creates a new attempt record and may reuse only validated outputs with matching dependencies. Changed sources, prompts, models, profiles, or permissions invalidate the affected reuse. Preserve failed attempts and partial coverage.

Do not retrofit broad resume behavior into the existing private runner. Keep the new feature's recovery in its own versioned sidecar while respecting the current run/artifact registration rules.

### 9.4 Storage

Proposed layout within existing boundaries:

```text
data/private/medical_reviews/<study-id>/
  sources/                           # authorized immutable local copies, when needed
  authorizations/                    # private permission and identity records
  human_dispositions/                # write-once records

data/processed/forensics_runs/private_reviews/<study-id>/<run-id>/
  run_manifest.json                  # existing run identity/contract
  processed/medical_review/
    bundle.json
    study_context.json
    review_plan.json
    evidence_map.json
    coverage.json
    proposals.json
    verification.json
    report_model.json
  generated/medical_review/
    raw/                             # exact imported/generated model outputs
    prompts/
    attempts/
    upstream_workspace/              # only if explicitly staged for comparator
  reports/medical_review/
    review.md
    review.html
    review.pdf                       # only when explicitly rendered
```

Private generated content stays inside ignored private run roots, including when `--output-root` is overridden. Verify ignore rules and fail unsafe output destinations. Do not place private model logs in a shared `data/generated/` directory simply because they are generated.

Existing `data/private/inspect_sr/` stays separate. Public export is not in the initial scope. No clinical source excerpts or private identities in CI artifacts, public handoffs, GitHub issues, or source commits.

## 10. Reports and synthesis

Build one deterministic `medical_review_report_model_v1` from validated records. Render Markdown plus opt-in Quarto HTML/PDF from that model. Quarto must read an explicit current-run JSON path, not scan for the newest report or execute upstream scripts.

The report should contain:

1. Scope, source availability, study reconstruction, and consequential unresolved gaps.
2. Material proposed concerns, each with evidence, alternatives, impact, requested correction, and human status.
3. Reporting omissions and optional improvements, separately labeled.
4. Numerical checks with input-verification status and native/result references.
5. Coverage and execution failures, including unsupported or deferred checks.
6. A full finding/provenance appendix and human-decision history.

Title unadjudicated outputs **AI-assisted manuscript audit: unverified proposals**. Do not call them validated peer review. Distinguish model-supported candidates from human-confirmed concerns in every rendering.

If an editor model is used, it may summarize validated IDs, not invent findings, revise numerical results, suppress verification limits, or assign judgments. Every input proposal must be accounted for as displayed, grouped, dismissed with reason, optional, unresolved, or deferred. Preserve all source members of deduplicated groups and conflicting interpretations. Agent agreement is not independent evidence.

Validate report-model traceability and group membership deterministically. Test that major findings and their qualifications survive synthesis. Context limits must cause explicit bounded processing or failure, not silent evidence truncation.

## 11. Proposed implementation map

Keep responsibilities narrow. Combine modules where simpler; do not create empty abstractions for future backends.

| Location | Change |
|---|---|
| `src/research_project/medical_review/` **new** | Small modules for records/validation, bundle and routing, upstream import, runner, verification/human decisions, and reporting |
| `config/medical_review/` **new** | Versioned profile/check catalogue, guidance provenance, upstream provenance/attribution, synthetic examples, and backend permission configuration |
| `prompts/medical_review/` **new** | Shared evidence rules, initial medical modules, counterevidence prompt, bounded editor prompt |
| `scripts/medical_review.py` **new** | Thin CLI using existing run helpers; offline planning/import/replay first, live execution behind authorization |
| `notebooks/medical_manuscript_review.qmd` **new** | Private, current-run report model consumer |
| `tests/medical_review/` **new** | End-to-end acceptance scenarios, deterministic replay and negative fixtures |
| `docs/MEDICAL_REVIEW.md` and `docs/MEDICAL_REVIEW_EVALUATION.md` **new** | Contracts, commands, permissions, limitations, evaluation design and qualification status |
| `docs/DECISIONS.md`, `docs/HANDOFF.md`, `README.md` | Record design choices and scoped use without overstating validation |
| `.gitignore`, CI configuration | Minimal privacy protections and offline/native/render test selection, only where needed |

Inspect `research_project.run_manifest` and existing source/evidence record utilities before implementation. Reuse helpers instead of duplicating canonical identities. Avoid changes to `inspect_sr/adapters.py`, existing judgment contracts, R method qualification, and the old manuscript runner except narrowly necessary compatibility tests.

Any new dependency or interpreter requirement needs a documented approval and lockfile plan. Keep upstream comparator dependencies isolated rather than raising the target repository's minimum Python version just to run the comparator.

## 12. Sequential work packages

### WP1. Offline boundary and lossless importer

Inventory the checked-out interfaces and record drift. Implement source mapping, proposal import, raw-output retention, minimal coverage states, and deterministic report-model construction using synthetic upstream-shaped JSON. Add upstream attribution/provenance.

**Exit gate:** imports are lossless and idempotent; bad hashes/schemas/paths fail closed; missing coverage stays unknown; no source or human record is overwritten; old workflows remain unchanged.

### WP2. Study bundle, medical context, profiles, and guidance registry

Implement multi-document bundles and source chronology, study reconstruction, mixed-aim routing, and the four initial profiles. Encode the safeguards in Section 6 and bounded coverage requirements. Pin only guidance actually reviewed and approved.

**Exit gate:** clean/error/unsupported fixtures route correctly; missing supplements and conflicting context survive into the report; no guideline-specific assertion is emitted from an unapproved reference pack.

### WP3. Optional backend execution and isolation

Implement one explicitly approved backend first, plus offline replay. Bind execution to the bundle, permissions, effective settings, limits, and immutable attempts. Validate actual restrictions with synthetic sentinel documents.

**Exit gate:** unauthorized calls/search are blocked; logs demonstrate isolation; interruption preserves completed outputs and failed coverage. Unsupported backend restrictions cause refusal, not an insecure fallback.

### WP4. Numerical handoff, verification, human decisions, and reporting

Connect existing qualified result references; add bounded arithmetic only where required. Implement the counterevidence pass, write-once human dispositions, lossless consolidation, and Quarto reports. Provide an INSPECT-SR manual-adoption packet without automatic assessment writes.

**Exit gate:** an incorrect criticism resolved by a supplement is demoted; a valid numerical concern remains traceable; an LLM cannot fabricate a receipt/human status; all report formats preserve scope and qualifications.

### WP5. Medical pilot and qualification record

Prepare paired, blinded evaluation packets and a predeclared evaluation plan. Live evaluation requires separate permission and resources. Deliver scripts and an honest pending qualification record even when live evaluation is not yet authorized.

**Exit gate:** distinguish software acceptance, live backend operational acceptance, and medical performance validation. No default enablement until the performance criteria are approved and met on held-out sources.

## 13. End-to-end acceptance tests

Prioritize failures that invalidate the scientific workflow, not a large collection of tests that only check implementation details. Keep focused unit tests for pure identity, permission, and schema transforms where useful. Integration tests must exercise real import/CLI/storage/report boundaries; native tests must execute real qualified methods.

| ID | Scenario | Required result |
|---|---|---|
| MED-01 | Existing private/public commands with the feature unused | Same offline defaults, current output contracts, and no backend requirement |
| MED-02 | Help and dry-run/plan-only | No model calls, searches, output files, or installs; planning with absent sources is explicitly incomplete |
| MED-03 | Valid upstream result imported twice | Exact raw bytes retained; stable identity; no duplicate proposal or false evidence multiplication |
| MED-04 | Unknown upstream schema or duplicate ID with changed payload | Explicit rejection/conflict; no silent field loss or overwrite |
| MED-05 | Wrong source hash, fuzzy-only quote, wrong page, ambiguous study map | Evidence unresolved or rejected; no exact-source claim |
| MED-06 | Source/SAP/registry corrected after review | New version and invalidated dependent reuse; old review remains historical |
| MED-07 | Supplement missing or table unreadable | Relevant check is unverifiable; report states the missing evidence |
| MED-08 | Upstream `ok` with empty findings and no coverage records | Import succeeds; substantive coverage remains unavailable |
| MED-09 | Mixed trial and prediction aims; unsupported meta-analysis component | Relevant union selected; unsupported scope explicit; no full-coverage claim |
| MED-10 | MRN-parity assignment described as randomization | Design discrepancy proposed with evidence; no assertion of concealed random allocation |
| MED-11 | Post-baseline exposure creates guaranteed survival time | Specific time-zero concern; properly aligned repaired control does not trigger it |
| MED-12 | Apparent endpoint switch explained by a dated amendment | Both versions and chronology retained; no unsupported allegation of selective reporting |
| MED-13 | Crude/adjusted effects, differing denominators, or different time horizons | No false arithmetic contradiction across incompatible estimands |
| MED-14 | Verified 2×2 discrepancy versus case-control PPV and zero-cell controls | Correct bounded calculation; invalid prevalence use and undefined quantities not silently repaired |
| MED-15 | Partial method failure, zero evaluated units, blocked rounding-bias | Never a no-finding result; no new INSPECT-SR candidate route |
| MED-16 | Subgroup CIs differ in null crossing, without interaction evidence | No unsupported subgroup-effect conclusion |
| MED-17 | Precise nonsignificant result, exploratory development model, known missing harms ascertainment | No boilerplate underpowered claim, no compulsory deployment-trial criticism, and no unsupported safety reassurance |
| MED-18 | LLM supplies `human_verified`, fake receipt, or official assessment fields | Rejected or quarantined; existing human and method records unchanged |
| MED-19 | Two agents make the same observation; two distinct issues share a quote | True duplicate grouped with all provenance; distinct issues retained; no independence claim |
| MED-20 | Major concern with a critical caveat enters editor synthesis | Finding and caveat remain accounted for in Markdown/HTML/PDF |
| MED-21 | Malicious document/import requests secrets, extra files, commands, or search | Instructions treated as data; no unauthorized read, execution, or transmission |
| MED-22 | Allow flags conflict with application offline mode; model CLI cannot enforce restrictions | Offline wins; unsupported live mode fails closed |
| MED-23 | Timeout, quota failure, resume after changed prompt/model/source | Partial status retained; no paid fallback; mismatched reuse refused |
| MED-24 | Unsafe output override, symlink escape, public export attempt | Rejected; private logs, excerpts and identities remain inside protected roots |
| MED-25 | Human confirms/dismisses then revises a proposal | Write-once history, supersession link, evidence and original model provenance retained |
| MED-26 | New medical report exists without finalized INSPECT-SR review | No official judgment or synthesis disposition appears or becomes exportable |
| MED-27 | Real R/Quarto dependencies absent in required acceptance lane | Blocked/failed acceptance, never a passing mock substitute |

Mocked semantic outputs test orchestration and guardrails only. They do not establish that a live model will identify immortal time, subgroup errors, or any other clinical issue. Those capabilities belong in the medical pilot.

## 14. Medical validation design

### Comparison conditions

Evaluate a strong single-reviewer medical prompt, unmodified pinned Reviewer where compatible, and the medical adaptation. Retain existing forensic-only outputs as the computational reference branch; do not treat them as a complete gold standard for methodological critique.

Use two clearly distinguished tracks:

- **Common-input track:** all three receive the same supported evidence, initially the main PDF, to estimate differences not explained by supplement access.
- **Full-bundle track:** the single-reviewer and medical adaptation receive identical complete bundles. Include upstream only if it can access the same material through a documented adapter; otherwise report it as an unmatched comparator, not an equivalent-input comparison.

Hold model/backend and effective permissions constant where feasible. If they differ, describe the comparison as workflow-plus-runtime, not an isolated test of multi-agent architecture.

### Corpus and adjudication

Start with authorized clinical trials, RWD cohorts, diagnostic-accuracy studies, and prediction-model reports. Include clean papers, source-adjudicated issues, and synthetic paired cases in which a defect is deliberately introduced or repaired. Use realistic PDFs to test extraction separately from text-only semantic fixtures.

Create a reference issue ledger before evaluating candidates, with source locations, type, importance, and plausible-but-wrong criticisms. Do not show it to the reviewers. Use two domain-qualified assessors where possible; preserve disagreements and adjudicate blinded to condition. Group dependence at the study level, including multiple reports of the same study.

Do not call recall against this ledger sensitivity to every possible scientific defect. Previously analyzed papers are development data, not a held-out test set.

### Outcomes

Report separately: important reference issues detected; confirmed versus false-positive criticisms; unresolved and optional suggestions; correct source attribution; findings lost or distorted during synthesis; clean-control behavior; human verification/revision time; completion/failure rate; and total observed resource use, including failed attempts.

Do not reward verbosity, finding count, model agreement, or a post-hoc composite score. Distinguish error in source extraction, study reconstruction, reasoning, retrieval, numerical execution, and report synthesis. Report results by study design and over repeated runs; do not treat every finding as an independent experimental unit.

Before unblinding, approve thresholds for acceptable important-issue coverage, serious false allegations, traceability, and human verification burden. Leave qualification pending if thresholds or sufficient held-out evidence are absent. Synthetic acceptance tests alone cannot qualify the system for routine medical review.

## 15. CLI and verification expectations

Proposed new entrypoint: `scripts/medical_review.py` with bounded `plan`, `import-reviewer`, `run`, `verify`, `decide`, and `render` operations. Implement offline/replay paths before live `run`. Avoid flags that imply current support for future backends or unsupported profiles.

Examples below are intended acceptance interfaces, **not commands available at the inspected revision**:

```bash
# Show requirements only. No files written and no remote calls.
uv run --offline --locked python scripts/medical_review.py plan \
  --bundle data/private/medical_reviews/example/bundle.json \
  --profile clinical_trial --dry-run

# Validate and import an already-authorized upstream output locally.
uv run --offline --locked python scripts/medical_review.py import-reviewer \
  --bundle data/private/medical_reviews/example/bundle.json \
  --input data/private/medical_reviews/example/upstream-result.json \
  --offline

# Live transmission is a separate, explicitly authorized action.
# MODEL_ID and the authorization file must be real, approved configuration.
uv run --offline --locked python scripts/medical_review.py run \
  --bundle data/private/medical_reviews/example/bundle.json \
  --profile clinical_trial --backend APPROVED_BACKEND --model MODEL_ID \
  --allow-llm \
  --authorization data/private/medical_reviews/example/authorizations/approval.json
```

Document exact implemented commands, error behavior, expected artifacts, and effective model/permissions in the handoff. No credentials in command examples or logs.

Existing baseline verification commands to preserve and extend:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q \
  -m 'not native_r and not report_integration'
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
```

Run existing mandatory native-R and Quarto report lanes plus the new end-to-end cases in a prepared environment. Do not install dependencies as part of production execution. No live provider call in routine CI. Separate synthetic backend-isolation tests from an explicitly approved live operational smoke test.

## 16. Definition of done and rollback

### Engineering acceptance

- [ ] Current interfaces rechecked; drift and design decisions recorded.
- [ ] Offline importer, bundle, profiles, coverage, proposals, verification, and private human dispositions implemented.
- [ ] Original outputs retained; hashes, source mappings and relationships validated.
- [ ] At least one approved live backend supported, or live execution explicitly documented as blocked while offline functionality remains usable.
- [ ] Existing qualified-method and INSPECT-SR authority boundaries unchanged.
- [ ] MED-01 through MED-27 exercised in their appropriate lanes; failures/skips identified honestly.
- [ ] Markdown and Quarto renderings checked for source links, status labels, major concerns and qualifications.
- [ ] Documentation, upstream attribution, privacy checks, rollback procedure and exact reproduction commands delivered.

### Operational and scientific qualification, tracked separately

- [ ] Authorized live backend smoke test completed with actual permissions and effective model recorded.
- [ ] Medical evaluation plan and reference ledger frozen before candidate evaluation.
- [ ] Held-out evaluation completed and approved decision recorded, or qualification explicitly remains pending.
- [ ] Feature remains opt-in; no statement of validated medical peer-review performance without supporting evaluation.

Rollback consists of disabling the new feature and reverting its scoped code/config changes. Existing public/private workflows, historical numerical outputs, and INSPECT-SR records must remain readable and unchanged. Do not delete historical medical runs or rewrite human records to conceal a failed pilot.

The final implementation handoff must state what was implemented, what was actually run, what failed or remains blocked, which sources/models were used, where private artifacts live, and what still requires approval. A green mocked pipeline is not a medical validation result.

## Source ledger

This ticket's requirements are proposed design decisions. The ledger below supports the descriptions of existing repository behavior and the upstream reuse points. Paths are pinned to the inspected revisions; no new live run or test suite was executed while preparing this ticket.

**Target revision:** `b629cab67ac8ee8c705a068ea81f5b849e095a26`.

- **R1:** `AGENTS.md`. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/AGENTS.md`
- **R2:** `scripts/run_manuscript_review.sh`. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/scripts/run_manuscript_review.sh`
- **R3:** `scripts/forensics_run.py`, including its imports from `research_project.run_manifest`. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/scripts/forensics_run.py`
- **R4:** `docs/CREDIBILITY_CRITERIA.md`. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/docs/CREDIBILITY_CRITERIA.md`
- **R5:** `src/research_project/inspect_sr/adapters.py`, inspected lines 1–200. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/src/research_project/inspect_sr/adapters.py`
- **R6:** `docs/INSPECT_SR.md`. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/docs/INSPECT_SR.md`
- **R8:** `README.md`, particularly current execution, coverage, and prediction-validation sections. `https://github.com/reblocke/forensic_metascience/blob/b629cab67ac8ee8c705a068ea81f5b849e095a26/README.md`

**Upstream revision:** `c591f4a498f6dc5083153811d6f678339cfb7c78`.

- **R7:** `docs/extension_guide.md`. `https://github.com/Ingar30/reviewer/blob/c591f4a498f6dc5083153811d6f678339cfb7c78/docs/extension_guide.md`
- Upstream source/output-contract context also comes from the README, configuration, prompts and `schemas/reviewer_output.schema.json` inspected during the preceding design discussion. Recheck the exact interface before implementing the importer; do not infer undocumented APIs from this ticket.
