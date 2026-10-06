# Medical review acceptance map

This matrix preserves all 27 FM-MED-01 scenarios. Implementation/testing notes
are partial evidence, not a blanket acceptance result. Software acceptance is
in progress. Live operational acceptance and medical qualification are pending.

Tests with mocked semantic responses check orchestration and safeguards only.
Clinical detection performance requires the separately authorized pilot. Every
required lane must retain its actual command, runtime and pass/fail/blocked result
in the handoff. A skipped or absent required runtime is not a passing gate.

| ID | Scenario | Required result | Work package / lane | Current evidence |
|---|---|---|---|---|
| MED-01 | Existing private/public commands with the feature unused | Same offline defaults, current output contracts, and no backend requirement | baseline | WP1 hosted Python/native/report passed at 632ebe0; WP2 final-head gates tracked separately |
| MED-02 | Help and dry-run/plan-only | No model calls, searches, output files, or installs; planning with absent sources is explicitly incomplete | WP1/WP2 | Real CLI help, absent/present-source planning and no-write boundary tested |
| MED-03 | Valid upstream result imported twice | Exact raw bytes retained; stable identity; no duplicate proposal or false evidence multiplication | WP1 | Lossless byte retention and identical real CLI replay tested |
| MED-04 | Unknown upstream schema or duplicate ID with changed payload | Explicit rejection/conflict; no silent field loss or overwrite | WP1 | Pinned schema and changed duplicate payload rejection tested |
| MED-05 | Wrong source hash, fuzzy-only quote, wrong page, ambiguous study map | Evidence unresolved or rejected; no exact-source claim | WP1/WP2 | Wrong quote/page/path, hashes and unreviewed mapping tested; full extraction pending |
| MED-06 | Source/SAP/registry corrected after review | New version and invalidated dependent reuse; old review remains historical | WP2/WP3 | Date precision/history and source/bundle revision invalidation tested; live dependency reuse remains blocked |
| MED-07 | Supplement missing or table unreadable | Relevant check is unverifiable; report states the missing evidence | WP2/WP4 | Missing SAP constrains verification; blank-PDF extraction remains partial; report model retains gaps and preflight limitations |
| MED-08 | Upstream `ok` with empty findings and no coverage records | Import succeeds; substantive coverage remains unavailable | WP1 | Empty ok import and Markdown report retain unavailable/null coverage; no complete/reassuring review claim |
| MED-09 | Mixed trial and prediction aims; unsupported meta-analysis component | Relevant union selected; unsupported scope explicit; no full-coverage claim | WP2 | Mixed and comparison-specific profiles, unknown union and unsupported scope tested |
| MED-10 | MRN-parity assignment described as randomization | Design discrepancy proposed with evidence; no assertion of concealed random allocation | WP2/pilot | Evidence-linked MRN reconstruction preserves reported claim versus interpretation; live detection requires pilot |
| MED-11 | Post-baseline exposure creates guaranteed survival time | Specific time-zero concern; properly aligned repaired control does not trigger it | WP2/WP4/pilot | Paired supplied-response replays preserve scoped time-zero concern versus aligned control, cited reconstruction and unknown coverage; live detection capability still requires the pilot |
| MED-12 | Apparent endpoint switch explained by a dated amendment | Both versions and chronology retained; no unsupported allegation of selective reporting | WP2/WP4/pilot | Dated original/amended SAP and pre-enrollment chronology retained; supplied amendment/footnote counterevidence demotes the criticism without erasure, missing-amendment control stays unresolved; no automated human adjudication |
| MED-13 | Crude/adjusted effects, differing denominators, or different time horizons | No false arithmetic contradiction across incompatible estimands | WP4 | Bounded arithmetic negative controls and immutable verification storage pass; read-only native R handoffs preserve existing source qualification |
| MED-14 | Verified 2×2 discrepancy versus case-control PPV and zero-cell controls | Correct bounded calculation; invalid prevalence use and undefined quantities not silently repaired | WP4 | Bounded diagnostic arithmetic controls pass; typed operator input attestations and storage implemented; clinical source-semantic correctness remains human responsibility |
| MED-15 | Partial method failure, zero evaluated units, blocked rounding-bias | Never a no-finding result; no new INSPECT-SR candidate route | WP4/native R | Actual pinned R results flow through the medical CLI into read-only references; source-unbound statcheck stays unqualified and rounding-bias blocked. Synthetic partial/zero-evaluated contract controls retain unavailable coverage; no candidate writes |
| MED-16 | Subgroup CIs differ in null crossing, without interaction evidence | No unsupported subgroup-effect conclusion | WP2/WP4/pilot | Paired subgroup supplied-response replay retains the unsupported null-crossing claim versus qualified control and the interaction safeguard; engineering orchestration evidence only |
| MED-17 | Precise nonsignificant result, exploratory development model, known missing harms ascertainment | No boilerplate underpowered claim, no compulsory deployment-trial criticism, and no unsupported safety reassurance | WP2/WP4/pilot | Three paired supplied-response cases retain interpretation/development/harms scope and qualified controls; safeguards are explicit, but live medical reasoning remains unvalidated |
| MED-18 | LLM supplies `human_verified`, fake receipt, or official assessment fields | Rejected or quarantined; existing human and method records unchanged | WP1/WP4 | Importer/verification official-field rejection, separate operator human/input review and no INSPECT writes tested; handoff requests refuse embedded receipts/results and preserve actual numerical output bytes |
| MED-19 | Two agents make the same observation; two distinct issues share a quote | True duplicate grouped with all provenance; distinct issues retained; no independence claim | WP4 | Conservative grouping and actual two-import consolidation preserve all originals; changed source-object labels do not multiply identical observations; distinct issues retained |
| MED-20 | Major concern with a critical caveat enters editor synthesis | Finding and caveat remain accounted for in Markdown/HTML/PDF | WP4/report integration | Major concern/caveat and proposed-transcription/unqualified-arithmetic status survive actual private Markdown/Quarto HTML/PDF; actual R qualified/unqualified/blocked handoffs survive HTML/PDF. Protected original-source/evidence links are validated in real HTML/PDF annotations; all 13 generic and 23 native-reference PDF pages inspected after the final navigation change. Final delivered-head audit/hosted gates remain required |
| MED-21 | Malicious document/import requests secrets, extra files, commands, or search | Instructions treated as data; no unauthorized read, execution, or transmission | WP3 | Malicious replay retained as data, no secret/command/search action; all live execution refused; live sentinel sandbox pending |
| MED-22 | Allow flags conflict with application offline mode; model CLI cannot enforce restrictions | Offline wins; unsupported live mode fails closed | WP3/operational | Application offline wins; every unqualified live backend refuses execution, including valid authorization; live sandbox sentinel gate pending |
| MED-23 | Timeout, quota failure, resume after changed prompt/model/source | Partial status retained; no paid fallback; mismatched reuse refused | WP3 | Real worker timeout, explicit new-attempt recovery and changed dependency/receipt refusal tested; no provider fallbacks; live quota testing pending |
| MED-24 | Unsafe output override, symlink escape, public export attempt | Rejected; private logs, excerpts and identities remain inside protected roots | WP1/WP3 | Import/replay private-path controls and public report destination refusal tested; inert imported Markdown/HTML/Quarto content verified |
| MED-25 | Human confirms/dismisses then revises a proposal | Write-once history, supersession link, evidence and original model provenance retained | WP4 | Write-once operator-attested revisions, original provenance, same-reviewer supersession and changed-context binding tested; no automatic consensus |
| MED-26 | New medical report exists without finalized INSPECT-SR review | No official judgment or synthesis disposition appears or becomes exportable | WP4/report integration | Private reports/manual adoption packet keep official assessment and synthesis disposition null; actual CLI/HTML/PDF create no INSPECT store |
| MED-27 | Real R/Quarto dependencies absent in required acceptance lane | Blocked/failed acceptance, never a passing mock substitute | baseline/native/report | WP3 hosted 220/13/5 passed without skips; WP4 navigation checkpoint local Python315/native14/report7 passed with no failures/errors/skips; final delivered-head gates remain required |

Offline reproductions:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration'
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
```

`test_importer.py` exercises real storage and the thin CLI using only synthetic
local sources. Registered artifacts bind exact original bytes. Baseline native
and Quarto lanes use the existing required integration markers and pinned R
methods; medical HTML/PDF and actual-R handoff report tests exercise WP4.
`test_semantic_replay.py` contains ten paired problem/control supplied-response
replays and two amendment/missing-amendment counterevidence cases. These execute
real replay/import/storage/report interfaces without testing live detection.
`test_prompt_scope.py` binds counterevidence/editor templates and rejects changed
hashes or missing stage provenance; neither template enables a backend.
`test_source_navigation.py` exercises exact protected targets, encoded filenames,
default/custom private report roots, unavailable sources, PDF page/unknown-page
targets, changed-source/symlink refusal, public-root refusal and historical-field
compatibility. Real report integration checks HTML/PDF hyperlinks as well as text.
Hosted receipts for
the delivered revision remain a separate check from local passes.

## WP4 requirement audit

This audit checks the verification/reporting requirements beyond the scenario
matrix. It does not close WP4 until the delivered-head native/report/Python
receipts are available. All cited fixtures are synthetic; actual R and Quarto
execution establishes those interfaces, not clinical detection performance.

| Ticket requirement | Implementation and direct evidence | Remaining boundary |
|---|---|---|
| 7.2: No reassurance with unexecuted work or required-source gaps | `records.validate_coverage`; importer tests for empty `ok`, failed/zero coverage, and a real imported plan's `required_source_gaps`. The completed declaration is rejected until the gap is removed; legacy unresolved-source gaps are also rejected. | No imported findings count establishes substantive coverage. |
| 7.3: Original claim, strongest alternative, scoped counterevidence and five model dispositions | `audit._verification` / `verify_review`; verification tests require original claim and real scoped evidence, reject authority fields and preserve immutable parents. Dated-amendment/footnote and missing-amendment paired replays retain both chronology and original criticism. | Counterevidence is supplied offline; model-supported never means human-confirmed. No live verification model is enabled. |
| 7.3: Separate write-once human decisions and manual INSPECT-SR adoption | `audit.record_human_disposition` / `load_human_history`; real CLI tests and supersession, identity/source attestation, cross-reviewer refusal and changed-context controls. `reporting` emits a traceable manual-adoption packet. | Operator attestations are validated, not independently authenticated. No automatic adoption, response, adjudication, finalization or export is performed. |
| 8: Existing qualified numerical references, without new candidate routes | `method_handoffs` validates registered terminal same-study numerical runs through the existing qualifier. Actual pinned R production feeds the native handoff and HTML/PDF tests; qualified, source-unbound unqualified and blocked statuses survive. Fabricated/changed receipts and medical-import-as-numerical-run controls refuse. | Existing qualification/routes are unchanged. Partial/zero-evaluated negative cases are controlled contract fixtures, not positive native receipts. |
| 8: Bounded arithmetic and explicit source semantics | `numeric.calculate_request` and `numeric_inputs`; counts/percentages, participant accounting, binary contrasts and diagnostic 2×2 tests cover orientation, horizons/denominators, mutually exclusive categories, case-control prevalence and zero cells. Attestation tests bind every executed input and assumption to source evidence. | Arithmetic is explicitly unqualified. Inferential CI/P-value methods, generated snippets, automatic continuity correction and marginal-LR multiplication are unsupported. |
| 9/10: Immutable lineage, private destinations and inert source content | `audit.load_dossier`, verification/report runs, exclusive-write human records and private-path guards. Tests retain failed mid-pass attempts; reject drift, unsafe destinations and active imported content; preserve historical representations. | Clinical sources, transcripts and identities are not public artifacts. Existing INSPECT-SR and old private runner contracts remain separate. |
| 10: Deterministic model, conservative grouping and complete finding accounting | `reporting.build_report_model` / `validate_report_model`; same-observation/distinct-issue tests, real two-import consolidation, group-member/caveat tampering refusal, separate omission/optional sections and current-run CLI reporting. | Editor/counterevidence prompt hashes are pinned but authorize no model execution. Agreement is not independent evidence and review completion remains false. |
| 10: Source-linked Markdown/Quarto HTML/PDF retain scope, caveats, qualifications and human history | Original-source navigation tests check exact versions, encoded paths, missing/unknown-page controls and changed-source/symlink refusal. Actual HTML/PDF tests inspect link destinations and native qualification labels. The navigation checkpoint visually inspected every generic/native PDF page after layout fixes. | No parser or link is proof of medical source fidelity. Delivered-head render receipts remain required; clinical performance and independent human adjudication remain pending. |
| 16: Reproduction, rollback and separate gates | Usage/decision/handoff documents retain exact commands, qualified-method limits, opt-in status, immutable recovery and scoped rollback. The actual required CI lanes reject missing/skipped receipts. | WP4 hosted attempts 1/2 failed package retrieval before native/report tests. The same-byte canonical CRAN fallback needs new-head hosted evidence; WP5 readiness and live/medical qualification remain outstanding. |
