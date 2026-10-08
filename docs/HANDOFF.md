# Handoff (for multi-session work)

## 2026-10-08 Native-tool candidate checkpoint; actual qualification pending

The user approved version-only lockfile normalization and clarified that the
external build cache is pre-authorized. The normalized 0.161.0 baseline built;
its separately preserved executable has SHA-256
`ec7ea1cd3076f5b37e77c6f01c2689951430fb3239b1bcdd5f7ac6e727ad4d55`.
An actual synthetic request reproduced native tool exposure before production
source edits. Original source remains clean and the installed 0.157.0 CLI hash
remains unchanged.

- Added assessment-only source-build manifest validation, v3 raw response/dispatch
  evidence and candidate reauditing. Preparation/run reject candidate receipts.
- Retained `tools/codex-no-tools/native-tools.patch`, version-only normalization,
  build recipe/recorder and local upstream reproducer materials. No upstream post,
  installation, candidate adoption or real study transmission occurred.
- Test-first configuration regression failed against the baseline (false discarded,
  serialized null), then passed with the patch. Core tests passed for omitted/true/
  false configuration, empty-registry/worker behavior and fatal pre-handler calls;
  the existing allowed-tool filtering test passed. Regenerated the actual schema.
- Initial core compilation failed on five old fixture literals; their new field is
  `None` and the failure is retained separately. Modified Rust files pass formatting
  and source whitespace checks. Unified-diff artifacts preserve hashed context
  spaces using a scoped attribute; source checks remain active.
- Focused Python validation passed 126 tests with zero failures/errors/skips.
  A later post-final phase correction and its regression passed focused qualification
  tests. The candidate release build is still running; actual qualification, final
  focused verification and fresh three-lane CI/artifact validation remain.

Private state, command receipts and original logs:
`data/private/medical_reviews/runtime_candidates/source-0.161.0/`.
Use `assessment-state.json` to locate the current build attempt and external cache.
Keep PR #15 draft. Actual runtime success may establish a passing assessment only;
operational adoption and separate source-specific authorization remain later gates.

## 2026-10-08 Isolated CLI source-build preflight; original lockfile blocks build

Started the approved assessment-only CLI patch milestone from `e2fef42` on
`codex/medical-review-codex-backend`. Cloned official 0.161.0 source at
`979011409de0a60b52f179721948e65531d26144` and installed its prescribed Rust 1.95.0
toolchain inside the ignored private candidate directory, with no PATH or user
configuration changes. The upstream source checkout remains clean.

The first required baseline command, `cargo fetch --locked --target
aarch64-apple-darwin`, exited 101: Cargo requires a lockfile update. Read-only
metadata inspection confirms every local workspace package has manifest version
0.161.0 but original lockfile version 0.0.0. The original lockfile hash is
`3206e2fdb53a3498758ce2f2972f19fae26beb261befd65cc0eb9e02efe23d52` and its bytes
match the pinned Git source. No compilation, native-tool patch or candidate
qualification ran. The installed CLI remains unchanged.

Preserved logs, source/toolchain state, metadata, a structured build-blocker report
and an unapplied normalization proposal beneath
`data/private/medical_reviews/runtime_candidates/source-0.161.0/`. The proposal
changes only local package versions, preserves all third-party lock entries and
has SHA-256 `9b2995d1b406de9526a4db5b1360c872eaa459bbb5dea1bd2412f560befd36bc`.
The user subsequently approved that scope extension. Applied the normalization
in a separate build checkout, preserving the original checkout and lockfile.
The normalized locked fetch passed without further lockfile changes. Baseline
compilation was interrupted for internal-disk headroom, then resumed with its
generated cache in a dedicated external directory. The user subsequently required
all work to remain in pre-approved folders to prevent repeated access prompts.
Stopped that build with SIGINT (exit 130); its process group is gone. The external
cache was preserved in place. The user clarified that the external drive is
pre-authorized and explicitly approved resuming there; the access-prompt cause
remains unidentified. The build resumed with the same cache. Source, toolchain,
drafts and logs remain inside the repository. The local disk had only 4.9 GiB
available, so the dedicated external cache remains necessary. Both interruptions are operational
pauses, not successful build or qualification evidence. Preserve all attempt logs
and the private workspace-access-pause record. Stop again if the normalized
lockfile requires any other change.

Reproduction after locating the isolated toolchain and source:

```bash
RUSTUP_HOME="$MEDICAL_CODEX_BUILD_ROOT/rustup" CARGO_HOME="$MEDICAL_CODEX_BUILD_ROOT/cargo" "$MEDICAL_CODEX_BUILD_ROOT/cargo/bin/cargo" fetch --locked --target aarch64-apple-darwin --manifest-path "$MEDICAL_CODEX_BUILD_ROOT/source/codex-rs/Cargo.toml"
```

Expected exit is 101 against the original source/lockfile; use `build-source`
instead of `source` for the approved normalized control. This is build evidence,
not a runtime-qualification receipt. PR #15 remains draft; live execution,
candidate adoption, real-source approval, merging and medical qualification remain
separate gates. Earlier runtime and CI evidence remains preserved.

## 2026-10-07 Codex isolation corrections; no supported runtime qualifies

Updated PR #15 on `codex/medical-review-codex-backend`; preserved its earlier
commits, receipts, branches and PR history. No merge or real source run occurred.

- Added explicit supported skill/agent/instruction controls and strict all-request
  tool/context auditing. Qualification receipts are v2; validation reconstructs
  configuration, checks raw artifacts and recomputes sandbox/wire acceptance.
- Added assessment-only executable probes, raw request/header/stream retention,
  output-cap and unknown-configuration probes, candidate misuse/tamper/context
  regressions, complete-prompt JSON escaping/reserve checks and a conservative
  macOS zombie-group cleanup correction.
- Actual pinned 0.157.0 and sequential isolated official 0.161.0/0.160.0 probes
  pass 18/19 checks. The remaining failure is native `functions` exposure. Supported
  code-mode namespace exclusion still leaves the wrapper visible. Catalogue bytes
  are identical; original distributions/digests and negative receipts are retained
  under ignored private boundaries. Installed CLI, PATH, user config and app remain
  unchanged. No passing candidate is recommended for adoption.
- Final software validation and artifact hashes are recorded on the final commit in
  PR #15, independently of operational failure. Keep the PR draft. Earlier receipts
  do not clear this revised implementation. The feature remains opt-in; numerical
  proposals, human-pending status and incomplete coverage are unchanged.

Reproduce (catalogue and candidate paths are supplied locally):

```bash
PYTHONPATH=src uv run --offline --locked pytest -q tests/medical_review/test_codex_backend.py tests/medical_review/test_codex_qualification.py tests/medical_review/test_codex_packet.py tests/medical_review/test_codex_execution.py tests/medical_review/test_execution.py tests/medical_review/test_reporting.py -m 'not native_r and not report_integration'
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE"
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE" --probe-executable "$MEDICAL_CODEX_CANDIDATE"
uv run --offline --locked ruff check .
uv run --offline --locked ruff format . --check
git diff --check
```

Expected qualification exit is 3 for each tested executable. Private diagnostics:
`reports/diagnostics/medical_review_codex_isolation/`; immutable qualification and
candidate-intake artifacts: `data/private/medical_reviews/runtime_qualifications/`
and `runtime_candidates/`. See [the operator workflow](MEDICAL_REVIEW_CODEX_BACKEND.md)
for assessment eligibility, evidence rules, resource limits and recovery. Resume
only with an exact supported configuration/runtime that removes native tool
exposure and passes actual qualification. Any candidate adoption requires a
separate explicit decision. After qualification succeeds, prepare a new packet
and obtain separate source-specific authorization. Medical evaluation remains later.


## 2026-10-07 Codex backend implementation; live qualification blocked

Implemented the approved Codex CLI path on `codex/medical-review-codex-backend`,
starting from preserved planning commit `86411d1`. The branch retains PR #14's
walkthrough and all previous branch/PR history; no merge was performed.

- Added deterministic private packet/index preparation, source authorization v2,
  strict Astra/max invocation, actual offline CLI qualification, bounded streams,
  kernel concurrency locking and orphan/deadline guardians.
- Retained original generation envelopes and derived imports with transformation
  hashes. A registered scoped layer preserves Codex provenance without rewriting
  historical proposals. Dossiers, verification, human decisions and Markdown/Quarto
  reports preserve that layer and incomplete coverage.
- Added test coverage for blocked provider starts, malformed authority, unknown
  citations, scope, empty findings, timeouts/child termination, controller-crash
  recovery, success-only reuse and human-decision provenance. Report CI requires
  four new synthetic generation/import artifacts and their companion hashes.
- Focused tests passed 94 selections before the final printed-page-label safeguard;
  fresh hosted CI on the committed head is the delivery acceptance gate. Printed
  PDF page labels are left unknown; physical indices/pages retain their conventions.
- Actual synthetic CLI qualification reached its loopback provider using synthetic
  ChatGPT credentials. Allowed reads, denied outside/symlink reads/writes/network,
  Astra/max, context byte reserve, zero retry on server/context errors, successful
  response and cancellation passed. Tool definitions and injected skill/agent
  instructions remained visible: **qualification failed** and live use is blocked.
  Failed configuration attempts and all later negative receipts are retained privately.
- Actual synthetic Quarto HTML/PDF render passed after selecting the existing
  isolated R library and Quarto's bundled Pandoc. Default R lacked report packages;
  default Pandoc was an incompatible Intel executable. No dependencies were added.
  Visually inspected the new provenance/runtime/source-link PDF pages (3 and 4 of
  13); no clipping or overlap was observed. New CI verifies the final model again.
- Ruff check, Ruff format check and `git diff --check` passed. No real provider/model
  execution, study transmission, medical adjudication or medical qualification ran.
- Initial PR CI run 37657166909 passed 477 Python, 24 native-R and 9 report tests,
  with zero failures/skips and 25 verified companion hashes. The parallel push
  exposed a crash-recovery test race: credential removal happens just before
  guardian exit releases its lock. The test now waits for actual lock release
  within its original deadline; controller behavior and qualification policy are
  unchanged. Fresh receipts on the corrected final commit remain required.

Reproduction (operator supplies the local model catalogue):

```bash
PYTHONPATH=src uv run --offline --locked pytest -q tests/medical_review/test_codex_backend.py tests/medical_review/test_codex_packet.py tests/medical_review/test_codex_execution.py tests/medical_review/test_execution.py tests/medical_review/test_planning.py tests/medical_review/test_reporting.py -m 'not native_r and not report_integration'
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE"
R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools FORENSICS_REQUIRE_REPORT_INTEGRATION=1 PYTHONPATH=src uv run --offline --locked pytest -q tests/medical_review/test_reporting.py::test_codex_generation_import_lineage_renders_html_pdf
uv run --offline --locked ruff check .
uv run --offline --locked ruff format . --check
git diff --check
```

Private local diagnostics are under
`reports/diagnostics/medical_review_codex_qualification/`; runtime qualification
receipts are in the fixed ignored private runtime boundary. The qualification
command's expected current exit is 3. See
[MEDICAL_REVIEW_CODEX_BACKEND.md](MEDICAL_REVIEW_CODEX_BACKEND.md) for contracts,
limits, authorization, recovery and rollback. Remaining gates: fresh final-commit
CI/artifact receipts, review of this PR, an enforceable CLI capability/context
configuration with requalification, separate source approval/smoke testing and
medical performance validation. Do not waive the failed live gate.


## 2026-10-07 Accepted offline checkpoint and next backend plan

The user said to consider the preceding checkpoint done and continue. This accepts
the offline intake/planning checkpoint; no model execution, source-semantic human
verification, human disposition or medical qualification was performed or inferred.
Documentation PR #14 is now ready for review at
`7eae29cfcab86c168b87d5561cbac871a96e7b22`; it has not been merged. Both push and PR
checks passed. Downloaded PR-run 37586746980 receipts confirm 446 Python, 24
native-R and 8 report tests, zero skips/errors/failures, required regressions,
pinned source hashes and 21 companion hashes. Ignored acceptance evidence is in
`reports/diagnostics/medical_review_walkthrough_hosted/`.

Continue from [MEDICAL_REVIEW_LIVE_BACKEND_PLAN.md](MEDICAL_REVIEW_LIVE_BACKEND_PLAN.md).
It defines the next backend contract, source packet, adapter, controlled runner,
recovery/import/report path, file map and test gates. A backend-selection question
is pending: Codex CLI with existing account access, or a tool-free Responses API
adapter. No backend/model, runtime or transmission approval is inferred. Core
implementation awaits the concrete choice; no dependency or CLI change is proposed.

Read-only CLI help/version and official documentation inspection found
`codex-cli 0.157.0`, named permission profiles and separate search/capability
controls. A synthetic command-sandbox probe used temporary files only. Its first
attempt failed configuration parsing and is preserved separately; corrected TOML
overrides allowed an approved text read while blocking an outside read, symlink
escape, source modification and workspace modification. A listening local TCP
socket observed no sandboxed connection. No model process or study input was used.
This is command-sandbox evidence only; complete live-backend isolation and spending
controls are unqualified. The probe and both receipts remain ignored in
`reports/diagnostics/medical_review_backend_preflight/`.

Executed verification commands for these receipts:

```bash
gh run download 37586746980 --dir reports/diagnostics/medical_review_walkthrough_hosted
PYTHONPATH=src uv run --offline --locked python reports/diagnostics/medical_review_walkthrough_hosted/verify_pr.py
uv run --offline --locked python reports/diagnostics/medical_review_backend_preflight/isolation_probe.py
```

The next plan preserves the original Reviewer comparator as a separate fidelity
gate, and requires exact source/model/runtime authorization before any real smoke
test. Human source adjudication, frozen evaluation criteria and untouched held-out
medical evidence remain pending. Historical acceptance records were not rewritten.

## 2026-10-07 Merge completed and development intake checkpoint

The user explicitly authorized merging PR #13 and proceeding. GitHub reports
it merged at `2026-10-07T07:03:59Z`, with merge commit
`a26c2f4e45734861618d7f1bf53ec6d1eefb4ff4`. Local `main` fast-forwarded to the
same commit as `origin/main`; its tree matches the verified integration head
`0f3f8a0b6967ef4c02d47b03416a4b110ee4e7e3`. All five original branch tips and
the integration branch were retained. GitHub automatically marked ancestor PR #8
merged two seconds after #13; #9–#12 remain open drafts. Fresh main CI is
[run 37585070132](https://github.com/reblocke/forensic_metascience/actions/runs/37585070132);
its terminal receipts are retained separately once available, rather than
repeatedly creating documentation commits to record CI.

The next branch, `codex/medical-review-development-walkthrough`, records operator
instructions and this checkpoint. Production code/configuration are unchanged.
The selected CRASH-3 case is development data, ineligible for untouched held-out
qualification. The ignored `data/private/medical_reviews/crash3-development/`
contains the real bundle, original XML snapshots, cloud metadata, four supplied
source representations and parsed evidence. Separate DOI-derived report IDs
identify the main publication, 2012 protocol and revised analysis plan.

Direct PDF requests returned 403; the discontinued PMC OA API returned 404.
These attempts remain recorded. NLM's current supported cloud dataset supplied
licensed manuscript text, supplement, protocol PDF and version-2 analysis-plan
PDF. All four match metadata MD5 checksums and recorded SHA-256 hashes. The
publisher manuscript PDF, later protocol v2.2 and registry snapshot/history are
explicitly unavailable. Correction searching was not performed.

Bounded `pdf-inspector==0.2.6` routing passed for all 39 PDF pages. Five selected
pages were rendered and visually inspected: supplement 2/7, protocol 9, SAP 3/4.
Table flattening and multi-column extraction remain semantic limitations. The
supplement's sparse final page is a genuine abbreviation-only continuation.
Eight source-reported reconstruction fields are evidence-linked to inspected
SAP pages; independent human semantic verification remains pending. Other
reconstruction fields stay unknown.

The actual offline CLI plan ran twice with identical output: 23 comparison-scoped
checks, zero model calls, unexecuted coverage and `status=incomplete`. The supplied
roles satisfy the plan's role groups; this does not certify amendment completeness,
registry history or source fidelity. There is no compatible Reviewer output here,
so no import, model execution, verification/adjudication or standard medical-review
report was fabricated. The local readiness report is explicitly intake/planning
only. Its actual render/QC and hash receipts are retained with the diagnostics.
HTML and four-page PDF renders succeeded; all four report pages were visually
inspected without observed clipping or overlap. Source targets/page labels and
six companion artifact hashes were checked. PDF viewer page-jump behavior was
not tested. Two auxiliary assertions were corrected to account for PDF line
wrapping and GoToR remote-file annotations; the rendered artifact was unchanged.
Whole-repository Ruff check/format and Git diff checks passed.

Reproduction with already prepared environments and retained immutable inputs:

```bash
PYTHONPATH=src uv run --offline --locked python reports/diagnostics/medical_review_crash3_walkthrough/prepare_case.py
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py plan --bundle data/private/medical_reviews/crash3-development/bundle.json --profile clinical_trial --dry-run --offline
uv run --offline --script /Users/reblocke/.codex/skills/pdf/scripts/pdf_route_extract.py data/private/medical_reviews/crash3-development/sources/supplement.pdf --mode pages --output-dir reports/diagnostics/medical_review_crash3_walkthrough/pdf-routing/supplement --max-pages 100 --max-file-mb 10 --max-output-mb 10 --timeout-seconds 45
quarto render reports/diagnostics/medical_review_crash3_walkthrough/walkthrough.qmd --to html
quarto render reports/diagnostics/medical_review_crash3_walkthrough/walkthrough.qmd --to pdf
```

The skill path records the actual local verification tool, not production config.
The ignored `reports/diagnostics/medical_review_crash3_walkthrough/` retains
retrieval failures/successes, cloud metadata, immutable-source preparation code,
bounded extraction receipts, page images, deterministic plan and verification
receipt, and readiness Markdown/Quarto artifacts. The remaining walkthrough needs
a genuine compatible Reviewer output or an explicitly selected, implemented and
qualified live backend, followed by real human review. See
[MEDICAL_REVIEW_WALKTHROUGH.md](MEDICAL_REVIEW_WALKTHROUGH.md).

## 2026-10-06 Integration review fixes and merge readiness

The user approved one integration PR against `main`, retaining draft PRs #8–#12
and their branch history. `codex/medical-review-integration` starts from reviewed
head `cca0efabee4b94a9ecc056563ee74908b728a56a`. Main was still at
`b629cab67ac8ee8c705a068ea81f5b849e095a26`. No merge is authorized by this milestone.

Both review findings are corrected. Empty comparison profiles now inherit the
plan's selected profiles exactly like an omitted list, preserving explicit
comparison scopes and unsupported/unknown behavior. Reconstruction now labels
each study and each comparison's parent study before the original fields and
unknown summary, using the existing escaping and wrapping formatter. No
dependency, scientific criterion, record schema or CLI argument changed.
Historical plans/reports and acceptance receipts remain untouched.

Test-first reproduction selected six cases: all six failed before the fixes,
showing missing specialist checks and missing scope labels. The corrected focused
suite passed 42 cases in 27.52s, with two unrelated native/report cases deselected.
This includes four long/active scope-ID cases and mixed explicit/unspecified
comparison controls. The actual prepared Quarto/R integration case passed in
11.49s: two studies and three comparisons retain distinct populations/estimands
in Markdown/HTML/PDF, with original context values, source links, caveats, pending
labels and authority boundaries intact.

The same independent reviewer completed a focused read-only review with no
actionable issues. Its no-write checks compared 64 routing combinations against
the previous implementation and confirmed preserved explicit/unknown/unsupported
behavior, plus unchanged report values/evidence/order and escaped scope identities.
The reviewer inspected tests/documentation and syntax/diff checks; it did not rerun
pytest or Quarto under the read-only review constraint.

All 19 synthetic PDF pages were visually inspected, including individual checks
of changed reconstruction pages 2–5. No clipped text, overlap or missing glyphs
was observed. An auxiliary strict margin check found one provenance path extending
into the margin; the retained `cca0efa` baseline has the same existing field/layout
limitation. Neither PDF exceeds the physical page boundary, and no new scope label
exceeds the margins. The first auxiliary check used system Python without
pdfplumber; it was rerun in the existing locked project environment. No dependency
was installed. This existing provenance-path layout limitation was not expanded
into an unrelated formatter change.

Executed local verification (the report artifact destination is shown in its
equivalent repo-relative form):

```bash
PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_planning.py tests/medical_review/test_reporting.py -k 'empty_comparison_profiles or empty_profile_fallback or reconstruction_keeps_each' --tb=short --junitxml=/tmp/fm-med-integration-regressions-before.xml
PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_planning.py tests/medical_review/test_reporting.py -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-integration-focused-final.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH FM_TEST_ARTIFACT_DIR=reports/diagnostics/medical_review_integration_local UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_reporting.py::test_medical_current_model_renders_major_concern_and_caveat_html_pdf --tb=short --junitxml=/tmp/fm-med-integration-report.xml
pdftoppm -r 70 -png reports/diagnostics/medical_review_integration_local/medical-review.pdf reports/diagnostics/medical_review_integration_local/page
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
git diff --check
```

R/TeX paths identify the existing local verification environment, not production
configuration. Ruff was clean across all 116 files; diff checks passed. The ignored
`reports/diagnostics/medical_review_integration_local/` retains local JUnit
receipts, the four synthetic report/model artifacts with verified companion hashes,
page images/contact sheets and `visual-qc-receipt.json`.

Final software acceptance must be recorded on the new integration PR against its
actual final commit: all three hosted lanes, nonempty zero-failure/error/skip JUnit
receipts, required runtime/report artifacts and matching companion hashes. Finish
documentation before that gate and record terminal receipts in the PR rather than
creating a new source revision merely to record CI. Earlier `cca0efa` passes are
historical and do not clear these review findings. A focused fix review and those
new receipts are required before marking the integration PR ready for review.
Live execution remains blocked, medical qualification pending, and the feature
opt-in. No real source transmission/search, human medical approval or merge occurred.

## 2026-10-06 Final offline requirement, rollback and visual checkpoint

This section supersedes older incomplete WP5 checkpoint descriptions below.
WP1–WP5 offline engineering deliverables are implemented and the complete
ticket is mapped in `MEDICAL_REVIEW_REQUIREMENTS.md` and the 27-scenario matrix.
Final software acceptance still requires the correction/rollback revision's
delivered-head Python/native-R/report receipts. Consult draft PR #12 for that
external gate; do not confuse an earlier head's pass with the latest changes.

Visual inspection of the completed 3f2a291 synthetic report found six clipped
identifier labels despite passing text/links/render tests. A failing display
regression preceded narrower evaluation wrapping and separate view/attempt
ID/label values. Exact JSON identities remain intact and shared appraisal
formatting retains its existing default. The corrected canonical suite passed
5 cases in 495.55s, including real CLI, R analysis, Quarto HTML/PDF, source
links, caveat retention, pending labels and every-page text bounds. All 70 PDF
pages were visually inspected using `pdftoppm`/Pillow contact sheets plus a
single-page check. No clipped/overlapping text, missing glyphs or unusable tables
were observed. This is synthetic report QC, not source-fidelity/medical proof.

The expanded rollback drill passed 2 cases in 4.09s: scoped code/config/prompt/CLI
disablement preserves every existing data byte and both legacy CLI boundaries;
finalized two-reviewer/adjudicated synthetic INSPECT-SR history still builds its
original report. Actual pinned R outputs still qualify through the unchanged
adapter after the new package is removed, while rounding-bias remains blocked.
Two required-runtime refusal tests passed in 0.50s: actual required R/Quarto
tests with an empty executable search path fail (one failure, zero skips each),
and the acceptance checker rejects both receipts. Twenty existing private report/
source-navigation compatibility cases passed in 31.17s (2 unrelated native/report
cases deselected). No production/source papers were analyzed.

Executed reproductions, with prepared dependencies and no installation:

```bash
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-evaluation-report-artifacts-3 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reporting.py --tb=short --junitxml=/tmp/fm-med-wp5-evaluation-report-layout.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_rollback.py --tb=short --junitxml=/tmp/fm-med-wp5-rollback-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_required_runtimes.py --tb=short --junitxml=/tmp/fm-med-wp5-required-runtimes.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_reporting.py tests/medical_review/test_source_navigation.py -m 'not native_r and not report_integration' --tb=short --junitxml=/tmp/fm-med-wp5-report-compatibility.xml
pdftoppm -r 60 -png /tmp/fm-med-wp5-evaluation-report-artifacts-3/medical-evaluation.pdf reports/diagnostics/medical_evaluation_qc_final/page
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
```

R library/tool paths above are the prepared local verification environment,
not production configuration. Use the CI preparation manifests for other hosts.
Final local JUnit hashes: layout
`1a5202f8afe40a9b14d25683c3a62890f428e2dae9bebbf087e168c27a42e8c8`,
rollback `6b059293f97892b48130564570ca44b796dbd384eeec457af588eb83a7ebc36e`,
required runtimes `b78448b609860f069863ec0bea14fcb66bfcaed620acd944d34364227b33fa4a`,
compatibility `7a64f151f1385b4570b75091200e4de9b02ddcde9b007399b5e9afb72b1034e0`.
All have zero failures/errors/skips. The five saved report/model/qualification
companion hashes were verified. Corrected PDF SHA-256 is
`cc12a309bb214bf09dbfc346a386d4ab3b480f8da96f56501b9f50e2efb3b0c3`;
the ignored QC receipt binds all pages and contact-sheet hashes.

Prior source head `3f2a2914404e656a6e0da8db7237955c4c589967` passed PR Actions
`37556005491` and push `37556001049` in all three lanes. Downloaded PR receipts
contain 432 Python, 23 native-R and 8 report tests, no failures/errors/skips.
The actual required-lane checker accepted all receipts/runtime/artifact inputs;
21 companion artifact hashes match. JUnit hashes are Python
`bc4b3fa61e10f9c2f28c1e56471c4c22ac178f81bbc8f029e207faa3dab8e7d6`,
native `31506fb6b3a0d188b271b1063ccbcc08578569aafbf04aba144086dfa2a53367`,
report `98320dddc939eb1cb693f5c93347823f180a209c2dffcb72dbe1f8a564d28d5a`.
These are prior-head evidence; the presentation correction must pass separately.

Read-only baseline checks confirmed unchanged `inspect_sr/`, run-manifest helper,
old manuscript runner, credibility/INSPECT-SR contracts and Python manifests/lock.
The original R engines/package versions/archive hashes are unchanged; only the
earlier documented hash-preserving download fallbacks differ. The immutable ticket
and all four attributed upstream originals match their hashes. Some audit lookups
used proposed filenames that do not exist; corrected inventory-based reads used
the actual routing/numeric/handoff and existing test modules. The first rollback
Ruff pass found long strings; splitting them restored whole-repository clean checks.

Operational/scientific gates remain unestablished: live backend isolation/smoke
testing, actual pinned executable upstream comparator, real domain source
adjudication/blinding, human criteria approval and held-out evaluation/promotion.
The ticket expressly permits blocked live execution and pending qualification
while offline functionality remains usable. No source transmission/search/model
run, new dependency, real human disposition/approval, INSPECT-SR write, default
enablement or merge occurred. All five draft PRs remain open and unmerged.

## 2026-10-06 WP5 source-bound tables, native analysis and evaluation reports in progress

The full FM-MED-01 goal remains active. This increment adds canonical
`evaluation-tables --unblinding-run`, `evaluation-analyze --tables-run` and
`evaluation-render --analysis-run [--html --pdf]` operations. Seven fixed private
CSV tables bind the completed threshold/release/reference/source/human chain.
Actual base-R execution preserves attempt-level outcomes and all declared
within-case/track/repetition pairs; the retained artifact union is explicitly
not single-run performance. Model-selected source hashes determine input
equivalence, independently of full-case source access for human review. Unknown
values, reported failure resources, separate currencies, study units/profile
tags, assessment phases and unreported stages remain explicit.

Native execution archives reviewed code and inputs, binds actual runtime/base/
platform/interpreter/input/output checksums and duration, and refuses source
drift or missing R. Private evaluation models retain every candidate and human/
synthesis disposition, groups/caveats, original-source navigation and lineage.
The Quarto notebook reads an explicit current-run JSON; no numerical recompute or
latest-run discovery occurs. Separate qualification stays pending; free-text
human criteria are not automatically interpreted, and no live execution,
credentials, actual blinding, held-out success or default enablement is inferred.

Fixed a reproduced recovery-index publication bug: the original handler tried
to fail an already completed recovery manifest, masking the OSError with a
terminal-state ValueError. The regression failed in 209.06s, then passed in
292.79s after moving index publication outside the mutable-attempt handler.
Original failures and the completed recovery remain unchanged/readable.

Verification already completed (zero failures/errors/skips for final receipts):

- Source-bound table/storage tests: 3 passed in 391.24s.
- Actual table CLI / unauthorized search flag: 1 passed, 3 deselected in 330.19s.
- Actual native R execution / post-execution code drift: 2 passed in 437.40s.
- Expanded base-R contracts including explicit attempt comparisons: 5 passed in 1.48s.
- Actual analysis CLI / unauthorized model flag: 1 passed, 2 deselected in 392.03s.
- Existing real offline import/replay/help/live-refusal CLI boundaries: 2 passed in 1.61s.
- Explicit textual locator/PDF-page and renderer-timeout log/artifact guards: 2 passed, 2 deselected in 0.06s.
- Whole-repository Ruff check/format and diff check passed (114 Python files).

Test-first collection for table/native/report modules failed while those modules
were absent; these are red-phase evidence, not passing runtime tests. The new
report module's first Ruff check found one overlong string; it was split and the
whole check passed. The first report integration run failed both cases in
425.83s because source locators are text, not dictionaries. The focused regression
reproduced that error, then passed after source links used the separately declared
page index and only PDF sources received fragments. Human textual locators do not
invent page numbers. A new timeout guard preserves partial Quarto stdout/stderr
and produced artifacts before failure; its first fixture used a string where the
existing helper requires a Path, corrected before the implementation. The focused
guard run passed. The corrected integration run completed 3 passing cases and
one failed presentation assertion in 546.21s: Markdown escapes underscores, so
semantic text assertions now decode entities. Actual HTML/PDF CLI rendering,
source links/annotations and pending qualification passed in that run. Its
initial fully expanded PDF was 227 pages for the synthetic case, exposing an
unusable presentation. Compact metrics, local display labels, a finding overview
and selected human-readable finding/provenance fields now reduce the formatting
preview to 69 pages; all complete original records remain in the linked model.
Critical caveats and every candidate retain individual accounting. The preview
is explicitly a synthetic formatting preview, not a completed canonical run or
acceptance receipt. `pdftoppm` and bundled Pillow are available for visual QC;
bundled PyMuPDF is absent, and no dependency was added. Actual private
Markdown/Quarto HTML/PDF tests are now running
with synthetic artifact retention; preserve their handles and inspect terminal evidence
before editing source closures. Delivered-head CI and the full requirements/
rollback audit remain required. Do not claim this checkpoint finishes WP5.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py -k completed_recovery --tb=short --junitxml=/tmp/fm-med-wp5-recovery-index-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_tables.py --tb=short --junitxml=/tmp/fm-med-wp5-tables-initial.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_tables.py -k table_cli --tb=short --junitxml=/tmp/fm-med-wp5-tables-cli.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_native_analysis.py --tb=short --junitxml=/tmp/fm-med-wp5-native-analysis-initial.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_native_analysis.py -k actual_analysis_cli --tb=short --junitxml=/tmp/fm-med-wp5-analysis-cli.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py --tb=short --junitxml=/tmp/fm-med-wp5-r-attempts-final.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reporting.py --tb=short --junitxml=/tmp/fm-med-wp5-evaluation-report-initial.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reporting.py -k 'text_locators or render_timeout' --tb=short --junitxml=/tmp/fm-med-wp5-evaluation-report-guards.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_importer.py::test_cli_plan_help_and_import_replay_are_real_boundaries tests/medical_review/test_execution.py::test_replay_cli_is_offline_and_blocked_live_returns_nonzero --tb=short --junitxml=/tmp/fm-med-wp5-analysis-existing-cli.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-evaluation-report-artifacts-1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reporting.py --tb=short --junitxml=/tmp/fm-med-wp5-evaluation-report-final.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library PATH=/Applications/quarto/bin/tools:$PATH FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-evaluation-report-artifacts-2 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reporting.py --tb=short --junitxml=/tmp/fm-med-wp5-evaluation-report-compact.xml
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
```

Revalidated the prior delivered head `dd10869a4856e980cec952fae4623edfb3b3ae5c`:
PR Actions run `37550507631` and push run `37550503574` completed successfully in
all three required lanes. Downloaded PR JUnit receipts under
`/tmp/fm-med-wp5-hosted-dd1-pr/` contain 425 Python, 18 native-R and 7 report tests,
all with zero failures/errors/skips. Their SHA-256 values are respectively
`09e81bfbaaeba17c5220888a07e350b03e1ab218dc8e0226d96eec87007d4bba`,
`4c9021cd6fb8af85833fd87db9dfd7de115d2d683c7ab35ec3713a2ad76eba26`,
`6c5cb8466ec316f75bc9d9abcbcb6c72c0b13451905ee8c1bbb328d4ef462dfe`.
All seven medical report companion hashes were checked against downloaded bytes.
These are prior-head receipts, not acceptance of the current increment.

The report CI lane now explicitly selects the evaluation report test and requires
its synthetic Markdown/HTML/PDF/model/qualification artifacts. The existing
synthetic allowlist preserves each with a companion checksum. PyYAML was absent
for a local workflow-structure check; no dependency was added. Ruby's installed
standard YAML reader successfully parsed all three jobs. A baseline diff against
the ticket's inspected revision found no change to `inspect_sr/adapters.py`, the
old manuscript runner, run-manifest helper, INSPECT-SR contracts or credibility
criteria. The pinned R lock's only changes remain documented, hash-preserving
source-download fallbacks from the earlier hosted setup correction.

Final local JUnit checksums (parsed counts above; no failures/errors/skips):

- Recovery index: `5389b270d917e0ac25a861954aa9bf1fbe0f95d403649bfda9795228566b5309`.
- Table/storage initial three: `8d175c1faca943dc3329f4d851b7975d8e15a037aac0493e64a77f6e3fe3764e`.
- Table CLI: `816ec4df682eaeebdb4b452009d3c127a43339906a737a4e37c72ab53682b189`.
- Native analysis initial two: `fdeaddd04ee16f8f3ed19fe16e560bfc34500bab8e31e8ac034694f86da88160`.
- R contracts five: `5fc324a723c5b5bc224c4d985a3d91dd41d6d332ac30597eae3b1dce6e12d126`.
- Actual analysis CLI: `06e2c58554a23c990a812a8f100db1364d9f9822fa1dc4774ef21e197124525b`.
- Existing CLI two: `d0d5aa6f5e1a446ea2feb76a8eaa3c5952ca3652e436048a85da9a5527a76dbd`.
- Report guards two: `64e294569291e538582f16af13ffe7392a668b3e38f3ac83416eeeae69e224bd`.

No real human criteria/approvals/dispositions, source transmission, model/search
run, dependency addition, method qualification, INSPECT-SR write, default
enablement or main merge occurred. Draft PR #12 and earlier draft stack stay open.

## 2026-10-06 WP5 threshold governance and descriptive R-core checkpoint

The active goal remains the full FM-MED-01 sequence. This increment adds
`evaluation_governance.py`, focused tests, and the offline `evaluation-thresholds`
and `evaluation-unblind` commands. Human-supplied criteria retain definitions,
units, denominator, aggregation, scope, direction and unknown values; approval
requires the four ticket domains. Unblinding binds completed thresholds/synthesis
to the exact frozen reference and preserves a write-once plan-scoped receipt.
Published-release failures retain their original raw/code/parent archives and
permit an identical recovery without changing the original attempt.
Approval/release operations share a persistent plan lock. A separate exclusive
recovery receipt makes another identical retry return the completed recovery run.
Original failures and interrupted manifests remain unchanged.

No real human criteria, approvals, credentials or dispositions were supplied.
Test approval identities/values are explicitly synthetic. No source transmission,
live model/search run, dependency addition, numerical qualification, INSPECT-SR
write, default enablement or main merge occurred. R-first outcome analysis,
qualification reporting and the final requirement/rollback audit remain required.

The pre-implementation command below failed collection with missing
`evaluation_governance` (exit 2; 0.04s). The first Ruff check found one import-order
issue; `ruff check --fix` corrected it, and the scoped check passed. Both new CLI
help commands ran successfully. The initial five integration cases passed in
602.16s. A focused regression then reproduced `OverflowError: int too large to
convert to float` (one failure; 0.03s) from an unnecessary conversion in finite
threshold checking. The fix preserves integers and checks finiteness only for
floats. Expanded tests passed **11 in 786.05s**, with zero failures/errors/skips,
including real CLI operation, changed-request refusal, post-publication recovery
and its idempotent retry, input drift, foreign reference binding, exclusive
publication and a competing plan-lock transaction. Existing offline/replay CLI
tests passed **2 in 1.56s**. Whole-repository Ruff check and format check passed
(108 Python files); `git diff --check` passed.

Added the base-R functional core `R/medical_evaluation.R` and explicit CSV helper
`scripts/analyze_medical_evaluation.R`, with no new package. Test-first native
checks failed because the R source was absent (three failures; 0.41s); after
implementation three passed in 0.53s, then three in 0.56s. Expanded native checks
passed **4 in 1.16s**: source-case matching, unavailable outputs/unknown totals,
failed-attempt usage/separate currencies and actual CSV I/O/overwrite refusal.
Two overlong R fixture-string lines and one import-order issue were corrected;
lint subsequently passed. A final driver-only variable rename was verified by
the affected CSV test (**1 passed, 3 deselected; 0.56s**). All native receipts have
zero failures/errors/skips. Counts describe supplied artifacts, not medically
qualified performance or every scientific defect.

The R core is not yet integrated into the governed canonical pipeline. In
particular, current packet-level detection across supplied artifacts can pool
attempts: the integrated analysis must preserve explicit attempt-level outcomes
and comparisons, rather than treating this union as a single-run performance
estimate. Preserve failed-attempt resource accounting and study/repetition
dependence. Do not choose cutoffs, successful attempts, semantic groups, runtime
equivalence, or actual-human credentials from missing evidence. The next
increment must bind exported tables, actual R runtime/code/input/output receipts,
governed Markdown/Quarto reports and an honest pending qualification record to
the completed unblinding chain, then finish the full requirement/rollback audit.
No `evaluation-analyze` command exists yet. This checkpoint does not finish WP5.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py
UV_OFFLINE=1 uv run --offline --locked ruff format src/research_project/medical_review/evaluation_governance.py tests/medical_review/test_evaluation_governance.py scripts/medical_review.py
UV_OFFLINE=1 uv run --offline --locked ruff check --fix src/research_project/medical_review/evaluation_governance.py
UV_OFFLINE=1 uv run --offline --locked ruff check src/research_project/medical_review/evaluation_governance.py tests/medical_review/test_evaluation_governance.py scripts/medical_review.py
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py --junitxml=/tmp/fm-med-wp5-governance-initial.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py -k finite_integer
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py -k 'finite_integer or receipt_publication'
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_governance.py --junitxml=/tmp/fm-med-wp5-governance-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_importer.py::test_cli_plan_help_and_import_replay_are_real_boundaries tests/medical_review/test_execution.py::test_replay_cli_is_offline_and_blocked_live_returns_nonzero --junitxml=/tmp/fm-med-wp5-governance-existing-cli.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py --tb=short --junitxml=/tmp/fm-med-wp5-r-outcomes-initial.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py --tb=short --junitxml=/tmp/fm-med-wp5-r-outcomes-final.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py --tb=short --junitxml=/tmp/fm-med-wp5-r-outcomes-boundary.xml
FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_r.py -k csv_boundary --tb=short --junitxml=/tmp/fm-med-wp5-r-outcomes-boundary-final.xml
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-thresholds --help
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-unblind --help
git diff --check
```

Revalidated the existing synthesis head
`7539ac60a2376950b79797c16f904dd838088164`: PR Actions run `37546734443` and
push run `37546729562` both completed successfully with all three required lanes.
Downloaded the PR artifacts to `/tmp/fm-med-wp5-hosted-753-pr/`, parsed JUnit and
checked all seven medical report companion hashes against actual downloaded
bytes. Python: 414 tests, JUnit SHA-256
`41a46d6c3420bd7e3622be4f02ac331c747e589fd4b4c06dc5d047888130a2d3`;
native R: 14,
`5ee196f1c32a8334d639b28cf02c11e98b0b890842dd4a1a56d30e3320f75e2e`;
report integration: 7,
`151e9f4d79fcb5b7319a212677b764c4e6503413359d576b561f15073b9cbdcf`.
All receipts have zero failures, errors and skips. These are prior-head evidence,
not acceptance of this governance/R-core increment. New delivered-head lanes
remain required. Draft PR #12 and the earlier draft stack remain open.


New local receipt SHA-256 values (parsed JUnit; zero failures/errors/skips):

- Governance initial five: `4053ea67310d23a671c9d49c708b06240cd6df2f0a8cbd2fc82c8b5f43875180`.
- Governance final eleven: `5437081493306a004e30396e439dde2c48b730a151ef371cbad371c62637afbc`.
- Existing CLI two: `62b287e3b06752f8a3fb82843b0891ca1aedf0aa5fe0064490556881d0f01266`.
- Native R expanded four: `0a187ec8c53806ec0a2f983247347797bd9b92f767186037b19a9e29677131c6`.
- Final affected CSV test: `31cf26e134bb09abb9d85970c55f2eb1ea2007626715cff812c4468237a9f525`.

## 2026-10-06 WP5 explicit synthesis-accounting checkpoint

The preceding goal turn made concrete progress in `618aec8eb9da242841cd732156479baec7c29227`,
adding immutable candidate assessment. This turn revalidated its live hosted
handles, then continued the approved scope with `evaluation_synthesis.py`,
focused tests and explicit offline stage-packet/assessment CLI commands.
Threshold adoption, R analysis, qualification reports and the full ticket audit
remain engineering work. No actual clinical adjudication, live source transmission,
reviewer execution, search, new package or main merge occurred.

Synthesis packets preserve original stage roles, summaries/notes, global numerical
caveats, full case source bytes and model access separately, while withholding
condition/runtime metadata, original output names, benchmark answers and human
identities. Their stage structure/source access/style may reveal origin; no
blinding proof is claimed. Existing candidate packets/records remain unchanged.
Humans supply every group membership and item disposition, with source evidence,
critical caveat quotes, error-stage labels, timing, disagreement, shortfalls and
immutable explicit supersession. Group members cannot cross packet/attempt
scopes. Unknown distortion remains null. A missing stage is unavailable; a
supplied empty synthesis may have explicitly judged losses but cannot establish
clean coverage. Declared completed pairs are operator reports, not runtime or
qualified numerical receipts. Medical qualification stays false; official
assessment stays null and INSPECT-SR stores remain separate.

Test-first collection failed as expected with missing
`research_project.medical_review.evaluation_synthesis` (exit 2, 0.07s).
Ruff's first check encountered long generated lines and blocked its chained
formatter; formatting first left three overlong literals, then wrapping them
passed. Initial five real storage/CLI/pure-contract cases passed in 246.27s.
Added an empty-synthesis distinction, exact workspace drift/restoration and
raw-input drift recovery; all eight passed in 388.17s.
Review then found that an unresolved item could report a lost caveat without
any supplied synthesis. A direct assertion over the actual completed synthetic
packet fixture reproduced this (`Missing synthesis stage was accepted as
observed critical-caveat loss`, exit 1). Initial fixture location inspection
encountered two symlink aliases; resolving/deduplicating the physical root fixed
the diagnostic, without changing production selection rules. The validator now
requires a declared completed pair for caveat loss as well as whole-finding
loss. A focused ninth regression was added; the final nine-case selection
passed in 374.10s, with zero failures/errors/skips. Existing importer/replay CLI
compatibility passed both cases in 1.74s, also without failures/errors/skips.
The final nine-case JUnit SHA-256 is
`bbedfad08d54e3f9334d094a8a9a609c3100f22209ad0b3c22fac80cba20777c`;
the existing CLI receipt is
`c6126cde0315d8041e5315f6804dd90aaa02824ffb6cef8590edbf5a2102f000`.
Earlier five/eight-case receipt hashes are
`55f4bd34e71673d99c4b298d0da3feebb9ed955a7de4494c276ddd96eaa8b926` and
`c51d63ab55ab2fea27eb4c722e8da108c4ed20ce532a82c4fbf0696b0a9f4575`.
Ruff/format/diff checks passed with 105 formatted Python files.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_synthesis.py
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_synthesis.py --junitxml=/tmp/fm-med-wp5-synthesis-initial.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_synthesis.py --junitxml=/tmp/fm-med-wp5-synthesis-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_synthesis.py --junitxml=/tmp/fm-med-wp5-synthesis-final-guard.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_importer.py::test_cli_plan_help_and_import_replay_are_real_boundaries tests/medical_review/test_execution.py::test_replay_cli_is_offline_and_blocked_live_returns_nonzero --junitxml=/tmp/fm-med-wp5-synthesis-existing-cli.xml
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-synthesis-packets --help
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-synthesis --help
```

Source head `618aec8` passed PR run `37543357162` and push `37543351417` in all
three lanes. The same handles were resumed without restarting jobs after waits.
Downloaded PR JUnit receipts under `/tmp/fm-med-wp5-hosted-618-pr` contain
405 Python, 14 native-R and 7 Quarto tests, zero failures/errors/skips. SHA-256
values respectively are
`5f0c1d19be1f48840f935610407454721869136f71e5d36da3d6649c29426f64`,
`f93f2cddf8ce6d005c9eecb51aa9a2851d46992f6d91afc17299da8195d719b3`,
`eb7d81bdf2b1a052279eceb26fc887a05c57061f991f3015abfc71cccb497daf`.
Eight downloaded medical artifacts with companion hashes matched actual bytes.
These are prior-head required-lane evidence, not this new synthesis head's
acceptance or medical performance proof. New delivered-head full Python/native-R/
report checks remain required. No R or Quarto source was changed here.

```bash
gh run view 37543357162 --json headSha,status,conclusion,jobs
gh run view 37543351417 --json headSha,status,conclusion,jobs
gh run download 37543357162 --name inspect-sr-python-37543357162 --dir /tmp/fm-med-wp5-hosted-618-pr/python
gh run download 37543357162 --name inspect-sr-native-r-37543357162 --dir /tmp/fm-med-wp5-hosted-618-pr/native-r
gh run download 37543357162 --name inspect-sr-report-review-37543357162 --dir /tmp/fm-med-wp5-hosted-618-pr/report-review
```

Next: freeze human-approved threshold adoption and an explicit pre-unblinding
gate without inventing threshold values; then R-first descriptive paired outcome
analysis retaining study/repetition units, unknown resources and failure
denominators; then qualification reports, full requirement audit and rollback
verification. Actual corpus/assessor approval, source-specific live permissions,
held-out evaluation and promotion remain separate gates. The goal remains active.

## 2026-10-06 WP5 candidate-assessment checkpoint

Resumed the active approved goal from `ebd64b4d61858ab99f6a13fe5ab16f52f85603d4`.
This increment adds `evaluation_assessment.py`, its focused tests, and explicit
offline `evaluation-blind --candidates-run` / `evaluation-assess --packets-run
--input` commands. It does not finish WP5 or change numerical/INSPECT-SR authority.
Human workspaces preserve substantive candidate content and full supplied source
bytes, separately list model source access, and withhold condition/runtime,
benchmark annotations and private human metadata. Metadata removal is not proof
of effective blinding; source fidelity and human credentials remain unverified.
Operator-attested source judgments preserve primary disagreement, adjudication,
case-local reference IDs, per-view human verification/revision times, assessor
shortfalls and immutable explicit supersession. Unknown measurements stay null.
Empty views never establish reassuring coverage. All records remain medically
unqualified; no live execution, source transmission, search or real clinical
adjudication occurred. No dependency or scientific threshold changed.

The initial six new assessment tests passed in 428.03s. A test-first extension
with timing fields failed as expected at the strict prior assessor contract
(`Unsupported evaluation human assessor contract fields`, one failure in
102.55s). Timing validation was then added. The isolated two-case regression
reproduced the local-reference shadowing bug (`Reference membership is outside
its predeclared case scope`, one failure in 103.81s). Lookup now uses the case
and reference ID together. The existing Python baseline passed 395 tests,
21 deselected, in 934.67s. No failures, errors or skips occurred in that selection;
actual native-R integration passed 14 tests, 412 deselected, in 31.80s. Actual
Quarto integration then passed 7 tests, 419 deselected, in 73.46s. Their parsed
JUnit SHA-256 values are
`39f3b6e970f322b797d2366b78608b36bf35898662b50ecaa2f6940138ebd3ff` and
`3b076c6d69e50d72e15584c54428f1d1c4bbb30d7b658ea4cff2768b3c73ec0c`.
The seven medical report/model artifacts with companion hash receipts were
verified against actual bytes. These render the existing WP4 surfaces; no new
evaluation report or medical performance estimate is implied.
Ruff initially found four overlong literals; those were wrapped and the focused
format/lint checks passed. One read attempted a nonexistent workflow filename;
`rg --files .github/workflows` resolved the actual workflow to `ci.yml`.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_assessment.py --junitxml=/tmp/fm-med-wp5-assessment-initial.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_assessment.py -k case_local --junitxml=/tmp/fm-med-wp5-assessment-case-red.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_assessment.py -k case_local --junitxml=/tmp/fm-med-wp5-assessment-case-red2.xml
UV_OFFLINE=1 uv run --offline --locked ruff format src/research_project/medical_review/evaluation_assessment.py tests/medical_review/test_evaluation_assessment.py scripts/medical_review.py
UV_OFFLINE=1 uv run --offline --locked ruff check src/research_project/medical_review/evaluation_assessment.py tests/medical_review/test_evaluation_assessment.py scripts/medical_review.py
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_assessment.py --junitxml=/tmp/fm-med-wp5-assessment-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --ignore=tests/medical_review/test_evaluation_assessment.py --junitxml=/tmp/fm-med-wp5-assessment-baseline-python.xml
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-assessment-native-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp5-assessment-native.xml
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-assessment-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp5-assessment-report.xml
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-blind --help
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-assess --help
```

Final format/lint/diff checks passed (103 Python files formatted). Both actual
CLI help commands exit 0 with only explicit parent/input options and no live or
official-judgment flags. New tests also exercise source/input drift recovery and
empty candidate views. Full Python checks use two nonoverlapping selections,
with independent temporary workspaces; do not present them as one executed
pytest command. Delivered-head hosted checks remain a separate gate.

The expanded local assessment selection reported a timing assertion failure:
the test fixture reused the same mutable `view_timings` object for its separate
people. A direct helper inspection reproduced one reader's value overwriting
another's unknown time. The fixture now deep-copies common person data;
production code did not change. The expanded selection completed with nine
passed and that one fixture assertion failure in 747.49s. The corrected
storage/supersession case passed in 146.36s (one passed, nine deselected).
The other nine cases exercised unchanged production code, including the
case-local reference regression, empty views, both failed-attempt recoveries,
inventory drift and the real CLI. These local results are separate from a full
delivered-head hosted selection using the corrected fixture.
The baseline JUnit SHA-256 is
`670c6e177573a2a59bf98a51bbb4ec3abec0f30ba394cf85e739844e12611cf1`;
the expanded selection's retained failure receipt is
`394a5908e2c84ed105826f72a645e8a71d25087c28c3e565487e1db68dee33d4`;
the corrected case's passing receipt is
`d498dc0e53e1416116135e8a3f06f27c63fd7ddf6808131aa33f12d938374019`.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_assessment.py -k private_history --junitxml=/tmp/fm-med-wp5-assessment-history-corrected.xml
```

Prior-head hosted PR run `37539006029` and push `37538999795` both completed
successfully in Python/native-R/report lanes at exact source head `ebd64b4`.
Downloaded PR JUnit receipts under `/tmp/fm-med-wp5-hosted-ebd-pr` contain
395 Python, 14 native-R and 7 actual report tests, with zero failures/errors/skips.
SHA-256 values respectively are
`8f49081b55dca178cf49fa50d10aa9cefcbb4e8fc1aa9c7a76d4ae84d9cd9cdc`,
`cac2619daf4a247da3dc14b22685ea1884a2ef9f4a9077a686a52361cc3b6c6e`,
`67f6a9cd5eae064130c711f522d5ea2ad210588a4dbab0c34e368fac85e650f3`.
Existing observation handles were resumed; no run was restarted after output
truncation. These are prior-head results, separate from this new increment.

```bash
gh run view 37539006029 --json headSha,status,conclusion,jobs
gh run view 37538999795 --json headSha,status,conclusion,jobs
gh run download 37539006029 --name inspect-sr-python-37539006029 --dir /tmp/fm-med-wp5-hosted-ebd-pr/python
gh run download 37539006029 --name inspect-sr-native-r-37539006029 --dir /tmp/fm-med-wp5-hosted-ebd-pr/native-r
gh run download 37539006029 --name inspect-sr-report-review-37539006029 --dir /tmp/fm-med-wp5-hosted-ebd-pr/report-review
```

Remaining engineering: explicit synthesis membership/loss/distortion accounting,
approved-threshold adoption before unblinding, R-first descriptive paired analysis
with study/repetition units, qualification reports and complete ticket/rollback
audit. Actual human source adjudication, authorized live comparator execution,
held-out medical evaluation and an approved promotion decision remain separate
operational/scientific gates. The goal remains active.

## 2026-10-06 WP5 source-bound candidate-ingestion checkpoint

The previous goal turn made concrete progress in `1740206`, delivering offline
source packets. This turn resumed from that clean source head and continued
WP5 with `evaluation_candidates.py`, focused boundary/storage tests and the
offline `evaluation-candidates --packets-run --input` CLI. The goal remains
active; candidate ingestion does not finish WP5 or qualify medical performance.

Candidate inputs bind an explicit completed source-packet record, retain every
declared attempt and supplied output, and separately identify unreported packets.
Exact staged citations resolve through existing source/evidence identities using
only the packet's selected versions. A supplement's administrative annotation
cannot establish evidence when that supplement was not supplied in this track.
Original model fields and raw bytes are preserved. Reviewer and synthesis
findings remain separate; semantic deduplication, source memberships and loss/
distortion judgments are not inferred. Empty findings do not establish coverage.

All ingestion is offline. Declared runtime, upstream revision and attempt status
are operator-reported data, not verified execution, actual source access,
unmodified-comparator fidelity, permission or a backend-isolation receipt.
Unknown resource measurements remain null; explicitly reported zero and failed-
attempt cost remain distinguishable. Candidates retain human-pending status,
empty qualified-result IDs and null official assessment. Existing medical
imports, method receipts, INSPECT-SR stores and human decisions are unchanged.

New canonical private runs retain exact input/output snapshots, code, and parent
manifest binding. Invalid model schemas/forged authority preserve a failed raw
attempt without publishing candidate findings. Unsafe operator input identities,
resource values or paths reject before creating a run. Bounded reads/serialized
record limits refuse large inputs rather than truncate them. Mid-freeze drift
preserves failure; loaders verify registered raw/code/parent/source semantics.

Test-first collection failed as expected with
`ModuleNotFoundError: research_project.medical_review.evaluation_candidates`
(exit 2, 0.05s). The first nine real storage/CLI/negative tests passed in 217.19s.
The source fixture was corrected to give distinct source-object IDs to different
main/supplement references, preserving the pinned schema's identity contract.
Added two input/output-drift cases and an empty/repeat-import coverage case.
Ruff/format/diff checks passed (101 Python files formatted). Current checks use
two nonoverlapping Python selections in independent temporary workspaces:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_candidates.py --junitxml=/tmp/fm-med-wp5-candidates-focused-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --ignore=tests/medical_review/test_evaluation_candidates.py --junitxml=/tmp/fm-med-wp5-candidates-baseline-python.xml
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-candidates-native-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp5-candidates-native-final.xml
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-candidates-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp5-candidates-report-final.xml
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
```

Pre-guard candidate tests passed all 12 cases in 367.61s; the nonoverlapping
baseline Python selection passed 382 with 21 deselected in 503.60s. The parsed
JUnit SHA-256 values are `234cf9b3a2e5bb21dca3f9315297392fc65114d2c3c8cd77efedb9f550cb65cb`
and `c186bfc4bfed03292d3e374a5321540101a73a1291ca1a865049d396b5a97306`.
These 394 passing Python cases precede the final schema-less source privacy
guard described below. Current native-R passed
14 tests with 401 deselected in 29.54s, and actual Quarto report integration
passed 7 with 408 deselected in 70.19s. Packet-head PR `37535631576` and push
`37535626143` were monitored by their existing handles without restarting. The
PR and push completed successfully in all three lanes at exact head
`17402069cba1721c36e679dff4eb4b8c0e296b60`. Its downloaded receipts were parsed:
382 Python, 14 native-R, 7 report tests, zero failures/errors/skips. JUnit SHA-256
values respectively are `3aa748d3c69a99561484da68a009ce9bcab54f248cedca48eabfa4e489caf4d3`,
`595976af1af09dda11c68dd1d7333483247b6ab55ec25d0560f4c822ff82b424`,
`1405c72681b453a7af2f115be6a7cbeab134117b7f03914a627587c00c3ef6a4`.
The eight downloaded medical handoff/report/model artifacts with companion
hash receipts were verified against their actual bytes; no new PDF layout change
or clinical source-fidelity claim is implied.
Current native/report JUnit SHA-256 values are
`f85863b051c8d8e090b5a6703e24795b2e903e7c50c0b4881839277e910fdf9e` and
`0e4e1e5e9c3c546df851a952818eca9f80aa0318929ead795afae59d7f502924`.
New candidate-increment delivered-head gates remain separate from this prior-head evidence.

```bash
gh run view 37535631576 --json headSha,status,conclusion,jobs
gh run view 37535626143 --json headSha,status,conclusion,jobs
gh run download 37535631576 --name inspect-sr-python-37535631576 --dir /tmp/fm-med-wp5-hosted-174-pr/python
gh run download 37535631576 --name inspect-sr-native-r-37535631576 --dir /tmp/fm-med-wp5-hosted-174-pr/native-r
gh run download 37535631576 --name inspect-sr-report-review-37535631576 --dir /tmp/fm-med-wp5-hosted-174-pr/report-review
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-candidates --help
# Exit 0; only explicit packets-run/input arguments, no live flags.
```

Final review identified that pinned Reviewer outputs have no `schema_version`.
A real bundle/source-packet regression reproduced accepting one as an analysis
source (`DID NOT RAISE`, 1 failure, 9.21s). Bounded JSON source privacy preflight
now rejects the recognizable Reviewer record vocabulary, including nested
copies, without changing raw sources or calling it a manuscript defect. The
source-packet and candidate-ingestion suites passed after that fix:
23 packet cases in 292.99s and 12 candidate cases in 349.10s, both with zero
failures/errors/skips. The packet JUnit SHA-256 is
`64f6b34b3273e72e7c3fc06dc4dfce010c718abb81e70a77c326f4f0a83bb422`.
The post-guard candidate JUnit SHA-256 is
`3b7bec217fe5b9e60b879a446012a9be6691a4bf3713f409c9eeb45ed6001814`.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_packets.py -k schema_less
# Expected RED: 1 failed, 22 deselected, 9.21s before the guard.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_packets.py --junitxml=/tmp/fm-med-wp5-candidates-packets-final.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_candidates.py --junitxml=/tmp/fm-med-wp5-candidates-guard-final.xml
```

Only those two test modules call source-packet preparation/reuse, as checked by
`rg -n 'load_source_packets|prepare_source_packets' tests --glob '*.py'`. Native
engines and Quarto/report code are unchanged by the final guard; earlier native/
report passes retain that compatibility scope. Exact new-head hosted full lanes
remain required and cannot be replaced by prior-head results or scoped tests.

Next: blinded candidate-assessor packets and write-once source assessment/
adjudication with complete finding/synthesis accounting; pre-unblinding threshold
adoption; actual R evaluation analysis; explicit qualification reporting; the
full requirement/rollback audit. No live reviewer, clinical transmission/search,
actual independent human clinical adjudication, new dependency or merge occurred.

## 2026-10-06 WP5 offline source-packet checkpoint

The preceding response was planning-only. This turn revalidated the active goal,
the authoritative checkout at `e94f53e` and its existing uncommitted source-packet
work, then completed the staging privacy regressions. The full objective remains
active: source packets are one increment, not full WP5 completion.

Both hosted runs for ledger head
`e94f53e87639ef11aa4e0149992d9f1ec1439fab` completed successfully: PR
`37527885830`, push `37527878923`. Their actual states and all job conclusions
were rechecked. The downloaded PR JUnit receipts were parsed and hashed: Python
360, native-R 14, report 7, all with zero failures/errors/skips. Their respective
SHA-256 values are `fd3f08e1f700d6609c46bd171049cea3463df341aa174a3cd0dcb8cb701ac4ef`,
`4fae68c6244afdfed5f53dfa2ba5b11b1e5f30830528edfadda4fa5101536061`, and
`88c0d9abd6c15e48491a34ae0d5ec40fdde32707547c5e4bfc84ae7f2e27f7d4`.

```bash
gh run view 37527885830 --json headSha,status,conclusion,jobs
gh run view 37527878923 --json headSha,status,conclusion,jobs
```

Added `evaluation_packets.py` and the offline `evaluation-packets` CLI. It binds
an explicit completed source-reference ledger, retains raw request/code and
parent manifests in a new canonical private run, and copies exact selected
source bytes plus public instructions into read-only per-reviewer roots. All
three conditions, both tracks and repetitions remain explicit in the separate
private administrative map. Original path aliases never rewrite bundles or raw
outputs. Reviewer roots exclude reference answers, private human metadata,
document-derived context and benchmark evidence annotations. Mixed aims retain
the review plan's profile union. The original comparator receives its exact
retained upstream reference files, not substituted medical prompts; those files
are not the full executable Reviewer workflow.

Staging/reuse validates exact inventories, modes, registered bytes and source/
prompt/reference lineage. Explicit file/packet/JSON and streaming byte bounds
refuse over-limit preparation without truncation. Mid-copy drift preserves a
failed attempt and partial files without publishing a completed packet record.
No live backend, search, transmission, model output, clinical adjudication,
dependency addition or merge occurred. File modes and minimum-content staging
are not proof of a backend sandbox or successful candidate-assessor blinding.

Test-first privacy checks reproduced two ways a private reference record could
be mislabelled as an analysis output (`DID NOT RAISE`, 2 failures), and an
execution-attempt variant reproduced the missing record-family guard (1 failure,
9.10s). Staging now rejects protected private locations and recognized private/
control JSON schemas, including copied/nested records, before creating a run.
Ordinary scientific analysis JSON remains admissible and byte-preserved. This is
a bounded staging floor; arbitrary prose/unknown formats still need operator
corpus review and source-specific transmission approval. Existing bundles and
historical records are unchanged.

The two initial privacy cases passed in 9.66s. The expanded nested-record and
ordinary-analysis command passed 4 cases in 29.04s before the additional
execution-attempt regression. Ruff caught one 101-character error-message line;
it was wrapped without changing behavior, then all checks passed (99 Python
files formatted). An earlier full Python run passed 377 cases before the final
privacy guard; that result is not evidence for the final guarded increment.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_packets.py -k mislabelled
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_packets.py -k 'mislabelled or ordinary_analysis' --junitxml=/tmp/fm-med-wp5-packets-privacy.xml
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_packets.py -k 'mislabelled and execution'
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-packets --help
# Help exits 0 and has no live execution options.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp5-packets-python-final-v2.xml
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-packets-native-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp5-packets-native-final.xml
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-packets-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp5-packets-report-final.xml
```

Final guarded-increment Python passed 382 tests with 21 deselected in 460.34s;
all 22 source-packet cases passed. Its parsed JUnit has zero failures/errors/skips
and SHA-256 `7f9a0fc186d33b63495daea3608ad6660c8790edb18f3da6b0b6e9d85351865a`.
Native-R passed 14 tests with 389 deselected in 28.46s; actual Quarto report integration passed 7
with 396 deselected in 68.78s. Both JUnit receipts have zero failures/errors/skips;
their SHA-256 values are `193ea79456e7e998a482f704b88047bab95ad94ccdec7f3890fe3ebe11e5bc6d`
and `e97f71286c9833eb1692c06722579fb7cc4b62e6dad340526fd8b39b85f28d78`.
New delivered-head hosted gates remain required; prior-head CI is not a
substitute.

Next: source-packet-bound candidate ingestion with exact citation alias mapping;
blinded candidate assessment/adjudication and complete finding accounting;
pre-unblinding threshold adoption; actual R evaluation analysis; explicit
qualification reporting; final requirement/rollback audit. These engineering
deliverables remain required even while live execution and medical performance
qualification await separate authorization/evidence. Draft PR12 is stacked above
WP4; no earlier PR was merged or promoted.

## 2026-10-06 WP5 source-reference ledger checkpoint

The preceding goal turn was planning-only, with no implementation progress. This
turn resumed from the authoritative worktree at `f78fe9d`, using the existing
untracked reference tests as test-first work. The goal remains active and its
full scope is unchanged.

Both hosted runs for plan head `f78fe9d9eb0ed2c9c4ea8d0ce9771121a7ad07db` completed
successfully: PR `37524362946`, push `37524320291`. The PR artifacts were retrieved
and their actual JUnit receipts parsed: 338 Python, 14 native-R and 7 Quarto report
tests with zero failures/errors/skips. Their respective SHA-256 values are
`ba26a71682f4181d8532ee84475799f4034c583691a441aa2c3f800d54fce897`,
`307bb62ffd5ba04ce732aba253f02b0e48aaabf97adc8b6378d78a91f1429b53`,
`29e88a53c3363eb9fe21b85a8dd14b553e201be38ed9f38c36ed98307491bebb`.

```bash
gh run view 37524362946 --json headSha,status,conclusion,jobs
gh run view 37524320291 --json headSha,status,conclusion,jobs
gh run download 37524362946 --name inspect-sr-python-37524362946 --dir /tmp/fm-med-wp5-hosted-f78-pr/python
gh run download 37524362946 --name inspect-sr-native-r-37524362946 --dir /tmp/fm-med-wp5-hosted-f78-pr/native-r
gh run download 37524362946 --name inspect-sr-report-review-37524362946 --dir /tmp/fm-med-wp5-hosted-f78-pr/report-review
```

Added `evaluation_reference.py`, an explicit `evaluation-reference --plan-run
--input` CLI, focused integration/negative tests and reference contract docs.
The ledger retains exact original observations and source evidence, disagreement,
wrong/unresolved criticisms, study analysis units and required-source gaps. All
assessor observations must be accounted for exactly once in adjudication. An
empty ledger is only a bounded reviewed-source statement, never universal
reassurance or medical qualification. Identities, credentials, independence,
source-byte review and blinding are operator attestations, not authenticated
facts. Single-assessor shortfalls remain explicit.

Freezing uses a new canonical private run, retains raw input and code, binds the
parent plan manifest, and registers the ledger. Repetition creates a separate
attempt. Input/parent/source/code drift preserves failure rather than overwriting
the plan or earlier ledger. Loader tests exercise actual registered artifact
checks. Neither source-reference input nor its CLI writes INSPECT-SR records,
invokes a model, retrieves a source, or authorizes transmission/search.

The initial focused command failed collection with
`ModuleNotFoundError: research_project.medical_review.evaluation_reference`.
After implementation its initial 13 cases passed in 21.51s; the expanded plan
and reference suite passed 40 cases in 54.18s. Ruff then found an import-order
issue and two overlong synthetic literals; these were corrected without ignores.
Code review identified serialized-size guards that omitted indented output or
the final record identity/newline. Both new regressions failed with `DID NOT
RAISE`, then passed after correcting the plan and ledger guards. No ordinary
plan identity or scientific content changed.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_reference.py tests/medical_review/test_evaluation_plan.py --junitxml=/tmp/fm-med-wp5-reference-focused-final.xml
# 42 passed, 60.97s, zero failures/errors/skips after both size fixes.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 97 Python files formatted at this checkpoint.
UV_OFFLINE=1 uv run --offline --locked python scripts/medical_review.py evaluation-reference --help
# Exit 0; only explicit plan-run/input arguments, no live operation.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-reference-native-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp5-reference-native-final.xml
# 14 passed, 365 deselected, 29.99s; zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp5-reference-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp5-reference-report-final.xml
# 7 passed, 372 deselected, 70.40s; zero failures/errors/skips.
```

The native/report commands ran before the final two Python serialization guards;
no R engines or Quarto/report code changed afterward. Their JUnit SHA-256 values
are `4c625b8b203eecc68342e6d8c8953ec8ddc7813d0ce78305007acc80ed64e7ab` and
`57a58eb5207ab8522cf7639b0a46505ac5959d3d3595c7ff44abf409fc557563`.
The pre-guard full Python suite passed 358 cases in 213.72s with 21 deselected.
The final Python regression passed after both guard corrections:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp5-reference-python-final.xml
# 360 passed, 21 deselected, 210.57s; zero failures/errors/skips.
```

The four original runtime/qualification assertions were restored to their
original common/full-input test after inserting the size regression, then both
affected plan tests were rerun: 2 passed in 0.30s. No production change followed
the final Python suite. The focused JUnit SHA-256 is
`6acd90c36e0ae494d18c173c9d789da980f4439df516d2332507c0b79764b8ce`.
The final Python JUnit SHA-256 is
`ae9499c34fe8be9403e0040fdd732431ab5add264d30d1227c3768f78d9f5c4a`.
An initial handoff hash insertion missed the current line context and made no
change; the insertion was reapplied against the inspected text.
Delivered-head hosted evidence remains outstanding; do not substitute the
prior-head hosted results for the new increment.

Next WP5 work: minimum-access model source packets that exclude the ledger,
private human metadata and unselected supplemental/context material; blinded
candidate-output adjudication; pre-unblinding threshold adoption; actual R
analysis; explicit qualification reporting and the final scope audit. Source
packets alone will not prove actual backend restrictions or successful assessor
blinding. No live reviewer run, actual human source adjudication, clinical
transmission, dependency change, or merge occurred in this checkpoint.

## 2026-10-06 WP4 gate passed; WP5 source-bound planning checkpoint

Previous goal turn made concrete progress in `83e6252`. Both hosted runs for that
exact source head subsequently completed successfully: PR `37519984240`, push
`37519977156`. Each has 318 Python, 14 actual native-R and 7 actual Quarto report
tests with zero failures/errors/skips. Downloaded receipts were parsed and the
required medical report artifacts were checked against their saved hashes.
Native package versions and the source-lock hash matched the checkout. WP4's
requirement audit is satisfied at this head; overall software acceptance still
requires WP5. No earlier PR was merged or promoted.

Exact observation/retrieval commands used:

```bash
gh run view 37519984240 --json headSha,attempt,status,conclusion,jobs
gh run view 37519977156 --json headSha,attempt,status,conclusion,jobs
gh run download 37519984240 --name inspect-sr-python-37519984240 --dir /tmp/fm-med-wp4-hosted-83e6252-pr/python
gh run download 37519984240 --name inspect-sr-native-r-37519984240 --dir /tmp/fm-med-wp4-hosted-83e6252-pr/native
gh run download 37519984240 --name inspect-sr-report-review-37519984240 --dir /tmp/fm-med-wp4-hosted-83e6252-pr/report
gh run download 37519977156 --name inspect-sr-python-37519977156 --dir /tmp/fm-med-wp4-hosted-83e6252-push/python
gh run download 37519977156 --name inspect-sr-native-r-37519977156 --dir /tmp/fm-med-wp4-hosted-83e6252-push/native
gh run download 37519977156 --name inspect-sr-report-review-37519977156 --dir /tmp/fm-med-wp4-hosted-83e6252-push/report
gh run view 37519984240 --job 112462615787 --log > /tmp/fm-med-wp4-hosted-83e6252-pr-native.log
```

The PR Python/native/report JUnit hashes are
`0981c45b44137a0ce60659e8c9b8f06adf9fc862de84ba4b68d3257596c400a3`,
`7834c55fd189242817a4238df95f15a1907d87ee96684a0d1df31bb904929d0b`,
`5d72d8bb14657a1e8902fbcf281b52a46205b2bf874bb5232a3b97c94d595885`.
An attempted push-job log read while the overall run was still live correctly
reported logs unavailable; it was not treated as terminal or restarted. The
terminal PR native log shows the primary CRAN URLs succeeded. Thus fallback-
specific evidence remains the configured-URL synthetic recovery tests and actual
local canonical-archive byte verification, not a claimed hosted fallback use.

WP5 started on `codex/medical-review-evaluation-readiness`, stacked above WP4.
The first increment adds `medical_evaluation_plan_input_v1` and frozen plan v1,
an output-free `evaluation-plan` CLI plus explicit `--freeze`, a strong single
reviewer comparator template and a clearly synthetic placeholder example.
It retains all three conditions, separates common-input/full-bundle source sets,
labels main-only upstream access unmatched when needed, and refuses fabricated
multi-document support. Declared runtime equality remains unobserved metadata.

Study/report IDs, declared families and exact source content connect dependent
cases. Development/held-out splits cannot cross a group, analyzed/synthetic cases
cannot become held-out, and renamed copies do not evade the source-hash guard.
Freezing reuses canonical private runs, retains exact raw bytes, prompts/config,
upstream attribution and code, and preserves failed attempts on mid-freeze drift.
Registered artifact and archived-code bindings are checked on dependent reuse.
Planning or freezing grants no model/search permission and keeps qualification
pending/default enablement false.

Test-first collection initially failed because the module did not exist; after
implementation 13 cases passed. Three further regressions failed on missing
prompt archives, missing archived-code binding and absent CLI, then passed after
correction. Ruff reported two overlong literals, which were corrected. Final
focused tests also exercise copied-source relabeling, mid-freeze source drift
and retained historical comparator bytes.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_evaluation_plan.py
# 20 passed, 8.61s.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp5-plan-python-final.xml
# 338 passed, 21 deselected, 138.66s; zero failures/errors/skips.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 95 Python files formatted.
UV_OFFLINE=1 uv run --offline --locked python -m json.tool config/medical_review/evaluation_plan.example.json > /tmp/fm-med-wp5-plan-example-validated.json
# Valid JSON; intentionally not an executable corpus without actual sources.
```

WP5's local Python JUnit SHA-256 is
`96b726716ab5602262ee781c976ab2742aba97187f8394d3c1a0718115eba7fc`.

No R engines/INSPECT-SR interfaces, old manuscript runner, dependency manifests
or Quarto sources changed in this increment. Their actual native/report receipts
above belong to the WP4 head; new WP5 hosted lanes must run on its delivered head.
Threshold adoption is refused until implemented, rather than inferred from a
flag. Full WP5 remains unfinished: blinded packet creation, source-reference
ledger/adjudication tooling, threshold adoption, real R analysis and explicit
qualification reporting. Real sources/assessors, live operational testing and
held-out medical qualification still need their separate approvals and evidence.
Keep the full goal active; this planning checkpoint is not evaluation readiness
or medical validation.

## 2026-10-06 WP4 required-source guard and hosted preparation recovery

The active full FM-MED-01 goal was revalidated after the planning-only turn.
No new goal was created and the implementation scope was not reduced. WP4 remains
incomplete until delivered-head hosted gates pass; WP5 tooling has not started.
The added requirement audit in `MEDICAL_REVIEW_ACCEPTANCE.md` covers the ticket's
verification/reporting obligations beyond its 27 scenarios.

At head `0db23ea`, push run `37518399223` and PR run `37518419546` both ended
failed on attempts 1 and 2. Their Python jobs passed, but native/report setup
received HTTP 429 before executing the required tests. Failed jobs were retried
once, not indefinitely; absent receipts correctly kept acceptance failed.
Logs were inspected, including the terminal second-attempt PR log at
`/tmp/fm-med-wp4-pr-attempt2-failed.log`. Another unchanged rerun was not launched.

Two focused corrections followed:

- The existing no-issue validator now checks the actual planned/imported
  `required_source_gaps` as well as legacy `unresolved_required_sources`.
  A real-import regression first reproduced the false reassurance, then passed
  after the one-line correction with gap-free and legacy-gap controls. Imported
  historical bytes are preserved and the fixture's actual coverage is not promoted.
- Canonical CRAN URLs were appended for the same statcheck/simdistr archives.
  The prior live retrieval session `66773` was polled to completion, not restarted;
  both canonical archives matched the existing lock hashes. Configuration-based
  tests first failed on the missing URLs, then passed using two simulated HTTP429
  failures followed by identical synthetic bytes. Exact lock comparison proved
  these two URL additions are the only manifest changes; no version, hash,
  dependency, R engine or qualification requirement changed.

Test-first command (three expected failures, then corrected):

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_importer.py::test_no_issue_rejects_required_source_gaps_from_imported_plan tests/test_ci_acceptance.py::test_pinned_cran_source_uses_canonical_fallback_after_two_rate_limits
```

Focused and final local commands, after all code/test corrections:

```bash
UV_OFFLINE=1 uv run --offline --locked ruff format tests/test_ci_acceptance.py tests/medical_review/test_importer.py src/research_project/medical_review/records.py
# Three files unchanged.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/test_ci_acceptance.py tests/medical_review/test_importer.py
# 35 passed, 6.20s.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-gap-python-final.xml
# 318 passed, 21 deselected, 143.59s.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-gap-native-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-gap-native-final.xml
# 14 passed, 325 deselected, 28.23s.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-gap-report-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-gap-report-final.xml
# 7 passed, 332 deselected, 68.49s.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 93 Python files formatted. All three JUnit lanes have zero failures/errors/skips.
```

The local Python receipt hashes to
`ad18cd318ccc7a3bc8a30b118f03dca9edbad9dc1a942563d1cf8ca11bc31be3`.
The local native/report receipts hash to
`a1d1d2eef13fcbe61ed967c23ef2836eec482dd1859fc64084ab37f2cf472c1f` and
`4266cb99f44ee15e90c9c4f7d8a0bb01e8a8fef7da44b3be455808d121f24cc2`.
Actual new Quarto outputs live in the corresponding temporary artifact directory;
no renderer/layout code changed since the fully inspected navigation checkpoint.
Visual inspection was not represented as newly rerun. Two exploratory reads
guessed nonexistent test/verification filenames; inventory located the actual
`test_ci_acceptance.py` and `audit.py`, which were then inspected. Those read
errors made no changes. No clinical transmission/search, live model run,
independent human adjudication, main merge or medical qualification occurred.

## 2026-10-06 WP4 original-source navigation checkpoint (milestone still incomplete)

After safeguard checkpoint `30cbeeb`, reports now contain protected links to the
exact original document versions and exact cited evidence. The additive
navigation record stores repo-relative targets, version/hash, availability and
the private output root. Links are encoded and resolve correctly from default
and nested private report roots. Known zero-based PDF page indices become
one-based navigation targets; unknown pages/non-PDF files receive no invented
page target. Sources are hash/containment-rechecked; no lookup, transmission or
extra filesystem access is authorized by a link. Missing sources have no link.
Historical renderer-bound reports may lack navigation and remain unmodified on
read. The report loader checks its navigation base against the actual run root.

Five navigation cases failed before implementation (missing navigation contract
and unsupported link-base argument). After implementation, nine focused cases
passed in 8.37s, including changed-source/symlink refusal, encoded Unicode/reserved
filenames, custom output depths and historical-field compatibility. The earlier
combined report/navigation reproduction passed 18 cases, two report integration
cases deselected, in 28.15s. One search referenced a nonexistent test filename;
the actual inventory identified the existing modules and the new focused file.

Final local gates, after all code/test changes and without added dependencies:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-navigation-python-final.xml
# 315 passed, 21 deselected, 158.11s; zero failures/errors/skips.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-navigation-native-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-navigation-native-final.xml
# 14 passed, 322 deselected, 30.20s; zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-navigation-report-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-navigation-report-final.xml
# 7 passed, 329 deselected, 76.74s; zero failures/errors/skips.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 93 Python files formatted.
pdftoppm -scale-to 1200 -png /tmp/fm-med-wp4-navigation-report-artifacts-final/medical-review.pdf /tmp/fm-med-wp4-navigation-report-qc-final/page
pdftoppm -scale-to 1200 -png /tmp/fm-med-wp4-navigation-report-artifacts-final/medical-native-review.pdf /tmp/fm-med-wp4-navigation-native-qc-final/page
# Output directories were created first; all 13/23 actual PDF pages inspected.
```

Actual HTML contains the expected source hrefs and PDF annotations contain the
same destinations; source-link text is visible. All final pages were inspected,
including full-size checks where contact-sheet resizing was ambiguous. No clipped
values were observed in these synthetic reports; this is layout/navigation QA,
not evidence of medical source fidelity or clinical performance. The WP4 diff
against WP3 leaves R engines, INSPECT-SR adapters/records, the old manuscript
runner and dependency manifests unchanged. Final delivered-head hosted gates
and the full WP4 requirement audit remain required, followed by WP5 evaluation
readiness. No live run/search, human adjudication, new qualification or main merge
occurred. Keep the full goal active.

## 2026-10-06 WP4 safeguard/report checkpoint (milestone still incomplete)

The active goal and `codex/medical-review-verification-reporting` checkout were
revalidated before continuing. This checkpoint pins counterevidence/editor
templates in new plans and tests changed hashes/missing provenance. No stage
backend is enabled: counterevidence remains supplied offline and report assembly
remains deterministic. Historical plans retain their recorded prompt hashes.

Ten paired problem/control supplied-response replays exercise time-zero,
subgroup, precise-nonsignificance, development/deployment and harms safeguards.
Two dated-amendment/missing-amendment cases retain original SAP versions,
chronology and footnotes, demoting explained criticism without erasure while
missing evidence stays unresolved. These are real replay/import/storage/report
boundary tests, not model reasoning or medical-performance evidence. Source
locations and generating identities are synthetic and no human adjudication is
claimed. All proposals retain pending human status and unknown review coverage.

Actual pinned R numerical production is shared between the existing native
handoff test and a new Quarto integration test. Qualified GRIM, source-unbound
unqualified statcheck and blocked rounding-bias references survive actual
HTML/PDF without changing the original numerical outputs or qualification
rules. The synthetic native report artifacts are allowlisted and mandatory in
CI. Explicit supplied reporting gaps and optional improvements have separate
report sections; original proposal/category/group values remain unchanged.

Executed after all current code/test changes, using synthetic sources only:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-safeguards-python-final.xml
# 306 passed, 21 deselected, 154.94s; zero failures/errors/skips.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-safeguards-native-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-safeguards-native-final.xml
# 14 passed, 313 deselected, 32.20s; zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-safeguards-report-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-safeguards-report-final.xml
# 7 passed, 320 deselected, 80.24s; zero failures/errors/skips.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 92 Python files formatted.
```

Visual QA used the PDF skill and existing Poppler/Pillow; no dependency was
installed. A prior passing text-extraction assertion concealed clipped hashes.
A red regression preceded hash wrapping, and a second red regression reproduced
long field labels consuming value width. Long labels/values now use separate
paragraphs while every machine-readable identity remains exact. The focused
regression passed, then all three lanes above passed. Both actual medical PDFs
were rendered and every page inspected: generic 13 pages, native-reference 23
pages, including full-size source-version/qualification inspection. No remaining
clipped values were observed in these fixtures; future changes need fresh QA.

```bash
pdftoppm -scale-to 1200 -png /tmp/fm-med-wp4-safeguards-report-artifacts-final/medical-review.pdf /tmp/fm-med-wp4-safeguards-report-qc-final/page
pdftoppm -scale-to 1200 -png /tmp/fm-med-wp4-safeguards-report-artifacts-final/medical-native-review.pdf /tmp/fm-med-wp4-safeguards-native-qc-final/page
# Existing task-owned output directories were created first; both commands succeeded.
```

These are local checkpoint receipts, not final delivered-head hosted acceptance.
MED-11/12/16/17 now map to their supplied-response fixtures; MED-20 retains the
actual native/report evidence and explicit remaining gate. Current reports retain
source/evidence IDs and locators, but original-source clickable navigation remains
a WP4 requirement gap. Next implement and test protected source links, including
nondefault private output depth, encoded filenames, missing sources and historical
report compatibility; then finish the requirement/coverage/layout audit and WP4
draft PR with exact-head hosted receipts. WP5 still requires blinded paired
packet preparation/analysis, predeclared approval gates and honest pending
qualification artifacts. Do not mark WP4 or the full goal complete.

No live reviewer run, source transmission, web search, real human adjudication,
dependency change, INSPECT-SR assessment write or main merge occurred. All live
backends remain blocked. Operational and medical qualification remain pending;
the full sequential engineering goal remains active.

## 2026-10-06 WP4 qualified-reference checkpoint (milestone still incomplete)

On `codex/medical-review-verification-reporting`, the optional verification input
now links existing same-study terminal numerical runs through their registered
v4 receipt/v2 result artifacts. It invokes the unchanged existing qualifier
against scoped bundle evidence; original numerical files, proposals and human
stores remain untouched. Native outputs are hash-bound, explicitly distinguishing
an existing artifact receipt from a hash captured at handoff. Source-unbound
results stay unqualified, partial/zero-evaluated coverage remains visible and
rounding-bias stays blocked. Verification archives the qualifier/identity code,
adapter and request. CI requires the allowlisted synthetic handoff artifact.

New passes keep identical arithmetic/method references once and retain every raw
attempt/lineage. An initial regression reproduced duplicate references preventing
numeric-input review; the fix is explicit in new run settings. Historical passes
and reports retain their original representation; compatibility is exercised.
The manual packet now includes numerical/input-review IDs. Report tests show
proposed-transcription and unqualified arithmetic status in actual HTML/PDF.

Executed after the implementation changes (synthetic sources only):

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-handoff-python-final.xml
# 288 passed, 20 deselected, 113.97s; zero failures/errors/skips.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-handoff-native-artifacts-final-v3 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-handoff-native-final-v3.xml
# 14 passed, 294 deselected, 26.00s; zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-handoff-report-artifacts-final UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-handoff-report-final.xml
# 6 passed, 302 deselected, 50.97s; zero failures/errors/skips.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Clean; 89 Python files formatted.
```

The native lane executes actual pinned GRIM, GRIMMER, DEBIT, duplicate and
statcheck engines, then sends explicit handoffs through the real medical CLI.
GRIM's positive/negative controls preserve their flags; source-unbound statcheck
references stay unqualified and blocked rounding-bias has no results. Controlled
partial/zero-evaluated receipts are synthetic contract-negative fixtures, not
empirical qualification evidence. A changed native output refuses later reuse.
The Python lane precedes the final native-only CLI test edit; that native edit
is covered by the final native lane and focused contract rerun. Full final
delivered-head hosted gates remain required.

An initial real Quarto run had one failing assertion: it searched the machine
key `qualified_method_result` rather than the displayed label `qualified method
result`. Inspection confirmed the label and false value existed. The assertion
was corrected; all six report tests passed on rerun. No failing/skipped lane is
presented as accepted. Two guessed test/module read paths were absent; actual
repository inventories resolved the filenames without changing implementation.

Remaining WP4: paired semantic fixtures and dated supplement/amendment
counterevidence for MED-11/12/16/17, explicit counterevidence/editor prompt
provenance, final requirement/layout audit and draft-PR/hosted delivered-head
receipts. Then implement WP5 blinded paired evaluation preparation/analysis,
predeclared approval gates and pending qualification record. No WP4 milestone
acceptance is claimed. All live backends stay blocked. No source transmission,
search, real human adjudication, medical-performance claim, dependency change
or main merge occurred; the full sequential goal remains active.

## 2026-10-06 WP4 verification/reporting checkpoint (milestone still incomplete)

On `codex/medical-review-verification-reporting`, bounded arithmetic now connects
to offline verification storage, separate write-once human/source-input review,
compatible named-run consolidation and deterministic private Markdown/Quarto
HTML/PDF reports. Original proposal hashes/runs, raw input/code snapshots,
counterevidence histories and human supersession are preserved. Model-supported
or demoted proposals never become human/official judgments. Human declarations
are operator attestations, not software proof of independent reading. The manual
INSPECT-SR packet creates no assessment writes or synthesis/export disposition.

WP4 is still incomplete: connect existing qualified numerical result/receipt/native
references, audit remaining MED scenarios and repeat the final delivered-head
gates. WP5 blinded evaluation preparation/analysis and held-out qualification
remain required. No WP4 PR or milestone acceptance is claimed at this checkpoint.
All live backends remain blocked; no source transmission/search, live model run,
real human adjudication, dependency change or main merge occurred. Goal is active.

Executed commands (all synthetic sources; actual local runtime lanes):

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-verification-python.xml
# 273 passed, 19 deselected, zero failures/errors/skips; final consolidation checks follow separately.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-verification-python-final.xml
# 275 passed, 19 deselected, zero failures/errors/skips, including actual two-import consolidation.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-verification-native.xml
# 13 passed, 279 deselected, zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-full-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-verification-report.xml
# 6 passed, 286 deselected, zero failures/errors/skips; actual medical HTML/PDF included.
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# Pass, 87 Python files formatted at this checkpoint.
```

Native/report execution preceded the final consolidation-only addition. The
final Python receipt above includes that boundary; full final-head hosted gates
remain required. The render test initially caught non-deterministic JSON-key
display order and a missing synthetic artifact allowlist entry; both were fixed.
Visual PDF inspection found clipped identifiers and excessive repeated metadata;
compact summaries and wrapped display identifiers preserve exact JSON values and
the full finding appendix. Major concerns/caveats survive real Markdown/HTML/PDF;
malicious imported text stays inert. Synthetic artifacts are allowlisted in CI.

Final checkpoint reran all three lanes after consolidation and the study-directory
boundary repair. A misplaced source bundle is now refused before another study's
source files are read; the regression reproduced the earlier read-before-refusal.
No change to numerical engines, qualified receipt semantics or scientific defaults.

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-checkpoint-python.xml
# 276 passed, 19 deselected; zero failures/errors/skips.
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp4-checkpoint-native.xml
# 13 passed, 282 deselected; zero failures/errors/skips.
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 FM_TEST_ARTIFACT_DIR=/tmp/fm-med-wp4-checkpoint-report-artifacts UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp4-checkpoint-report.xml
# 6 passed, 289 deselected; zero failures/errors/skips. Real R/Quarto, not mock substitutes.
```

Final Ruff lint/format and `git diff --check` also passed. These are local
checkpoint receipts, not complete WP4 acceptance or delivered-head hosted proof.

WP3 `8602714` is now green on PR run
[37500860476](https://github.com/reblocke/forensic_metascience/actions/runs/37500860476)
and push run [37500753966](https://github.com/reblocke/forensic_metascience/actions/runs/37500753966).
PR JUnit receipts downloaded and inspected: Python220/native13/report5, zero
failures/errors/skips. JUnit SHA-256 values, respectively:
`0acc93af1177d50af2b58d014039d58edf9e649b3963a560a133a76d20882c37`,
`fcca2e865fbbf7d6c93e330cca64229844c1eafc0a190c9a4145a65778b1bd1e`,
`e6c915414d6359a8218141191bff9fa85962e21ad3e414183e2e416324bf9834`.
This supersedes the earlier pending/rate-limit notes below. Each failed setup
received one failed-job rerun; no package pins, mirrors or acceptance rules changed.

Next: qualified R-reference handoffs with actual native integration; remaining
scientific safeguard/paired-fixture audit; complete WP4 draft PR/receipts; then
WP5 evaluation readiness. Preserve all existing stacked draft PRs and runs.

## 2026-10-06 WP4 arithmetic-core progress (not milestone acceptance)

Current branch: `codex/medical-review-verification-reporting`, based on WP3
`8602714` / draft [PR #10](https://github.com/reblocke/forensic_metascience/pull/10).
The pure bounded arithmetic transform and 22 tests are implemented. No new CLI
operation, arithmetic storage integration or human input-verification authority
is advertised. WP4 remains incomplete: qualified same-run reference handoffs,
counterevidence, write-once human dispositions, lossless grouping/report model,
private Markdown/Quarto HTML/PDF and manual adoption packets are still required.
WP5 evaluation tooling remains required. Goal stays active; do not mark complete.

Executed:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_numeric.py
# Initial core: 15 passed; seven additional controls included in the full lane below.
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp4-numeric-python.xml
# 242 passed, 18 deselected, no failures/errors/skips
UV_OFFLINE=1 uv run --offline --locked ruff check .
# Pass after fixing reported long-line errors.
```

WP2 head `54b94c6` passed all six hosted PR/push checks. Downloaded PR
[run 37499304244](https://github.com/reblocke/forensic_metascience/actions/runs/37499304244)
JUnit receipts confirm Python197/native13/report5, zero failures/errors/skips.
This supersedes earlier WP2 pending notes. WP3 Python passed, but PR/push native
and report setup failed before tests with HTTP429 from configured CRAN sources;
missing receipts correctly failed acceptance. One rerun of failed PR jobs in
[run 37500860476](https://github.com/reblocke/forensic_metascience/actions/runs/37500860476)
was requested. No package versions/hashes changed, no gate was waived. Attempt 2 was confirmed
in_progress with native/report job handles 112399955878/112399955616. Canonical
cran.r-project.org statcheck/simdistr archives were also independently retrieved
and matched existing pins; no additional mirror/config changes were made. Inspect
that exact run before retrying; a queued/in-progress handle is not a stopped job.

No live medical model calls, source transmission/search, real human adjudication
or main merges occurred. Operational and held-out medical qualification remain
pending; all live backends stay blocked for unqualified restrictions. Preserve
all three stacked draft PRs (#8/#9/#10) and historical attempts.


## 2026-10-06 WP3 replay and execution-boundary checkpoint

WP3 implements a thin `run` interface for bounded offline replay and auditable
blocked live requests. Every attempt uses existing canonical run helpers and
immutable request/result sidecars. Exact bundle/context/plan/code/raw/runtime/
authorization/permission/limit dependencies gate resume. Real worker timeout,
explicit incomplete-import recovery, changed dependencies and missing receipts
are tested. Previous imports and stopped attempts remain historical.

No live backend is qualified or started. Source-specific authorization validation
is implemented, but it cannot activate a backend whose filesystem/tools/egress
restrictions are unavailable. Live operational smoke/sentinel tests are pending;
no prompt or staging directory is claimed to provide an enforced model sandbox.
This is the ticket's blocked-live engineering alternative. All model calls/search
counts remain zero. No packages, scientific assumptions, candidate routes, human
judgments or main merges changed. WP4 and WP5 remain required; the goal is active.

Executed local checks:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp3-python.xml
# 220 passed, 18 deselected; no failures/errors/skips
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp3-native.xml
# 13 passed, 221 deselected; no failures/errors/skips
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp3-report.xml
# 5 passed, 229 deselected; no failures/errors/skips
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# lint/format/diff pass after fixing reported formatting/import-order errors
```

Native/report counts reflect their actual executions before four final Python-only
regressions were added; execution code did not change afterward. The final Python
receipt includes all 23 new WP3 tests. Fixtures and private human/authorization
identities are synthetic. The CLI returns 3 for failed/blocked attempts and 2 for
validator/path errors; exit 0 for replay is not medical review completion.

WP2 is committed as `54b94c6`, draft [PR #9](https://github.com/reblocke/forensic_metascience/pull/9)
stacked on WP1 #8. Its hosted Python lanes passed; native/report jobs were still
live at this checkpoint. Final hosted receipts for each delivered head remain
required and will be recorded when available. No CI failure/skip may be waived.

Next WP4: typed bounded arithmetic with verified-input status and estimand guards;
qualified same-run numeric reference handoff; append-only counterevidence and
write-once human disposition history; lossless grouping/report model; private
Markdown and real Quarto HTML/PDF plus manual adoption packet. No automatic
INSPECT-SR assessment writes. WP5 then delivers blinded evaluation tooling and
an honest pending qualification record.


## 2026-10-06 WP2 study-planning checkpoint

The full FM-MED-01 goal remains active. WP2 adds version/chronology validation,
local structural extraction, evidence-linked study and independent comparison
reconstruction, four medical planning profiles, a versioned check catalogue and
hash-checked narrow prompt adaptation. Shared reported facts, interpretation and
preferred design remain separate. Unknown/unsupported scope and missing sources
are explicit; all model/search permissions remain disabled.

No manuscript source analysis, live model calls, transmission, searches, new
packages, official INSPECT-SR writes or main-branch merges occurred. Medical
performance and live operational qualification remain pending. WP3–WP5 remain
required, including counterevidence, human dispositions and medical report renders.

Focused tests added during WP2 reproduced changed prompts/catalogues, unresolved
comparison routing, sources borrowed across report scope, disappearing planned
checks, invented text-page counts and interpretations from another study before
fixes. Final local checks (same code state):

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-wp2-python.xml
# 197 passed, 18 deselected, no failures/errors/skips
R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-wp2-native.xml
# 13 passed, 202 deselected, no failures/errors/skips
PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools R_LIBS_USER=/tmp/fm-med-r-library FORENSICS_REQUIRE_REPORT_INTEGRATION=1 UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-wp2-report.xml
# 5 passed, 210 deselected, no failures/errors/skips
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
git diff --check
# lint/format/diff checks pass
```

These temporary paths describe executed local verification only; committed
production code uses repository-relative paths/configuration. Local R uses the
existing pinned method library; the Quarto tool path avoids an incompatible
system Pandoc. No environment workaround changes production results.

WP1 corrective head `632ebe0` passed all three hosted lanes in PR
[run 37494662155](https://github.com/reblocke/forensic_metascience/actions/runs/37494662155):
Python 175, native R 13, report/review 5, all zero failures/errors/skips. Downloaded
JUnit receipts were inspected locally. This supersedes the earlier pending
hosted note below, and does not establish WP2 hosted acceptance or medical quality.
Draft PR #8 remains separate from unmerged main. WP2 is delivered as the next
stacked draft, retaining that history. Do not merge without user authorization.

Next: enforce source-specific execution/replay permissions, immutable attempt
recovery and fail-closed backend restrictions (WP3). A backend lacking verifiable
isolation must remain explicitly blocked while offline functionality stays usable.


### WP1 hosted follow-up: pinned-source server rate limiting

Draft PR #8 is open against `main`; initial head `7e77e4b` passed hosted Python
but both required native/report setup jobs failed with HTTP 429 before any tests
ran. The gate remained failed. Official CRAN cloud mirrors were verified to
return exactly the existing pinned statcheck/simdistr archive hashes.

A focused setup-only helper now tries each locked URL once, preserves the exact
expected hashes, aborts on content mismatch, and refuses output overwrite. No
package version, dependency list, native method or production behavior changed.
Three new download regressions failed before the fix, then all six CI acceptance
tests passed. Real source downloads also passed all three existing package pins.

Executed follow-up checks:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/test_ci_acceptance.py
# 6 passed
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration'
# 175 passed, 18 deselected
bash -n scripts/install_inspect_sr_r_methods.sh
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
```

The corrective head requires fresh hosted native/report receipts. WP2 starts
after this gate is resolved or with the external blocker explicitly retained.


## Medical review goal — 2026-10-06 WP1 checkpoint

The approved FM-MED-01 goal remains active. Baseline verification and the first
offline work package are implemented on `codex/medical-review-offline-boundary`.
WP2–WP5 remain required. No live model calls, source transmission, web search or
source-paper analysis were performed. Live operational and medical performance
qualification remain pending; the feature remains opt-in.

### Delivered

- Retained the supplied ticket verbatim as `MEDICAL_REVIEW_TICKET.md`; SHA-256
  `942cd4635c3d7cc1d19e0dbe3c0ee3a984ba399d5f6d6cbfc411b1c5957ad44b`.
  Baseline checkout matched its inspected target revision `b629cab`.
- Added the MED-01–27 acceptance map and separate evaluation-status document.
- Pinned the upstream Reviewer schema and MIT notice with verified provenance.
  No upstream runtime, parser, model defaults or new dependency was imported.
- Added output-free planning preflight and a real offline import CLI. Exact raw
  bytes and every original finding field are retained. Exact anchor mappings
  reuse source/evidence identities but remain proposed transcriptions.
- Added private, run-scoped coverage/proposals/report-model artifacts using
  existing manifest helpers. Completed import never implies substantive review
  coverage. No qualified numerical result or official/human judgment is created.
- Added immutable replay/conflict references and source/input/code/hash/path
  checks. Failed attempts retain raw bytes; recovery beyond explicit refusal is
  pending WP3. No existing runner, R engine or INSPECT-SR adapter was edited.

### Executed verification

The initial locked offline commands failed because dependencies were absent
from the local cache. `uv sync --locked` prepared the existing lock without
manifest/lock edits. Existing native dependencies were prepared with
`R_LIBS_USER=/tmp/fm-med-r-library bash scripts/install_inspect_sr_r_methods.sh`.
The pinned methods loaded at scrutiny 0.6.2, statcheck 1.5.0 and simdistr 1.0.1.

The baseline Python suite passed before implementation. New importer tests first
failed because the package did not exist. Further regressions reproduced input
changes during import, stale adapter reuse, manifest/directory symlink traversal,
tracked private inputs and tampered import origins before their fixes. The final
Python lane passes 172 tests, including 25 medical import/CLI tests.

The first report run failed all five tests because R discovered a wrong-CPU
Anaconda Pandoc binary. Selecting Quarto's working bundled Pandoc through the
test process PATH and RSTUDIO_PANDOC resolved this; no report code was changed.

Final executed commands and results:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration' --junitxml=/tmp/fm-med-python.xml
# 172 passed, 18 deselected

FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library FM_TEST_ARTIFACT_DIR=/tmp/fm-med-baseline-artifacts/native UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m native_r --junitxml=/tmp/fm-med-native.xml
# 13 passed, 177 deselected

PATH=/Applications/quarto/bin/tools:$PATH RSTUDIO_PANDOC=/Applications/quarto/bin/tools FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-med-r-library FM_TEST_ARTIFACT_DIR=/tmp/fm-med-baseline-artifacts/report UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m report_integration --junitxml=/tmp/fm-med-report.xml
# 5 passed, 185 deselected; synthetic native/report artifacts retained

UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh
bash scripts/run_pipeline.sh --forensics all --dry-run --offline
bash scripts/run_manuscript_review.sh --study-id private_x --report missing.pdf --review-type prediction_validation --dry-run --offline
git diff --check
# All passed; dry-runs created no analysis run
```

The runtime paths above describe this local test environment; use configured
isolated library/Pandoc/artifact paths on another host. They are not production
configuration. All three executed lanes had zero failures, errors or skips.
Marker deselection assigns tests to their correct lane and is not skipped
required coverage. Hosted checks on the delivered head remain pending.

### Next steps and remaining gates

1. Review the WP1 diff and hosted checks; preserve the sequential delivery history.
2. Implement WP2 chronology/source versions, structural extraction preflight,
   study reconstruction, mixed-aim routing, approved guidance and four profiles.
3. Implement WP3 permission enforcement, staging/isolation, limits and immutable
   recovery attempts. An approved live backend and source-specific authorization
   remain external decisions; offline work continues independently.
4. Implement WP4 numerical handoffs, counterevidence, write-once human decisions,
   conservative synthesis and current-run Markdown/Quarto reports.
5. Implement WP5 blinded common-input/full-bundle evaluation tooling and a frozen
   protocol/ledger. Actual live tests, human adjudication and held-out medical
   qualification require their separate approvals and evidence.

Rollback preserves private medical runs/import origins and all existing human
records; revert only scoped code/config/docs. WP1 tests alone do not satisfy
all MED-01–27 scenarios or establish clinical detection performance.


## Current status — 2026-09-29

### Post-merge verification of PR #7

PR [#7](https://github.com/reblocke/forensic_metascience/pull/7) merged with
history preserved at `a5ea62a37b996f7c41080bee78abb36e3ad51c2c`, matching
verified final head `5b2d18a31e8ed3516c3dfe81330f3b9043d7a5da`.
That exact head passed all three jobs in
[run 36620814836](https://github.com/reblocke/forensic_metascience/actions/runs/36620814836).
The merged commit passed [run 36622448626](https://github.com/reblocke/forensic_metascience/actions/runs/36622448626):
[Python](https://github.com/reblocke/forensic_metascience/actions/runs/36622448626/job/109590974435),
[native R](https://github.com/reblocke/forensic_metascience/actions/runs/36622448626/job/109590974627),
and [report/review](https://github.com/reblocke/forensic_metascience/actions/runs/36622448626/job/109590974691).
Downloaded JUnit receipts on merged `main` showed 147 / 13 / 5 tests, each
with zero failures, errors, or skips. Their SHA-256 values were
`359fa5630426dc2f811496cd3bf996e0131d3886ec33236d8662014361dc1395`,
`fa61418001703eeda8cdd9fbb046fc7e1d151215a498554cfe32734c050436c8`,
and `82220f845e5ef0ab781a4d4008207ef2f33b732e638c1c1159119b2e0ab9bd7c`.
Allowlisted artifact IDs/digests were Python `11059595846` /
`a738159fc281852019c36446ff4cf8541591f5b30a0845d842b46f829593eaa8`,
native R `11059457829` /
`e2b5016da9812dbb199968877b3b5daaa5e7664ba401e0dd65f5ab274f99791e`,
and report/review `11059058505` /
`122607035819d209277e39842fc9075c453a8736a45d444194ac2019ddc9f36b`.
No private working store was uploaded. The primary checkout and remote have
only the `main` branch head, and `run-b2.html` retains the hash below. This
receipt-only documentation update introduces no method or output change; its
new commit must also pass all three hosted lanes before final handoff.

PR [#5](https://github.com/reblocke/forensic_metascience/pull/5) merged as
`ee121274f093df984803479fdce92385a9ad4596`. The final PR head
`3c37db62f31be421fa83f9721ec7907b1d9bfe25` passed the
[push run 36327764042](https://github.com/reblocke/forensic_metascience/actions/runs/36327764042)
and [PR run 36327766774](https://github.com/reblocke/forensic_metascience/actions/runs/36327766774).
All three required jobs passed again on merged `main` in
[run 36328679295](https://github.com/reblocke/forensic_metascience/actions/runs/36328679295):
[`python-fast`](https://github.com/reblocke/forensic_metascience/actions/runs/36328679295/job/108646284009),
[`native-r`](https://github.com/reblocke/forensic_metascience/actions/runs/36328679295/job/108646283833),
and [`report-review`](https://github.com/reblocke/forensic_metascience/actions/runs/36328679295/job/108646283969).
FM-01–FM-12 and FM-14 are closed against that acceptance map and hosted gate.
FM-13 remains deferred. The 2026-09-27 checkpoints and older open-status
statements below are historical; they do not describe the current release.

This follow-up consolidates checkout/branch state and corrects the two shell
launchers to use locked offline `uv` Python for every Python stage. The focused
regression first failed twice (`incidental-python-invoked` from a simulated
system Python), then passed twice after the fix:

```bash
PYTHONPATH=src UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' tests/test_pipeline.py::test_shell_entrypoints_use_locked_python_instead_of_incidental_system_python
bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh
```

No scientific method, schema, or historical result changed. The affected
outputs are only new runs made through those entrypoints; their Python stages
now consistently use the locked environment. `run-b2.html` remains untracked;
its starting SHA-256 is
`2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.
The clean detached baseline worktree was removed. Merged branch heads were
retired; the nonancestor patch-equivalent PR #1 head remains reachable through
`archive/llm-readiness-pr1-0d46330` (peeled commit
`0d46330878640847abb51d255f5c96b87d55c9d3`). See `docs/TODO.md` for
deferred work. A recheck after the branch cleanup found only `main` and the
temporary correction branch on the remote, and one active local worktree.

### Correction PR #7 verification checkpoint

The first correction head `2d19a08df4209f2ba79df29d7dcd3a10c331ac37`
passed all three hosted jobs in
[PR run 36619195602](https://github.com/reblocke/forensic_metascience/actions/runs/36619195602):
[Python](https://github.com/reblocke/forensic_metascience/actions/runs/36619195602/job/109579931588),
[native R](https://github.com/reblocke/forensic_metascience/actions/runs/36619195602/job/109579932060),
and [report/review](https://github.com/reblocke/forensic_metascience/actions/runs/36619195602/job/109579932111).
The allowlisted artifacts were Python `11058081176` (archive SHA-256
`241c6e1e7462f56cd9165fcdded23b878d064a0fda3c2161113e0d7998dec5d1`),
native R `11058222889` (`9c7fe9faa115002d981e7c5e034e1a89ee56efe2bd44a46f0da257fdf37503bf`),
and report/review `11058277730` (`a31007eaee7137689e9a895649e8931d9121a68c9c462d02f366f451e894f327`).
Downloaded JUnit receipts showed 147 / 13 / 5 tests respectively, with zero
failures, errors, or skips. JUnit SHA-256 values were Python
`8dc50156bb083b51ba2d94bb4319b767876164b87ee057f0b3149d6d1078ef08`,
native R `8438e5a3349c1caf861ba821818e016d91f204d7c089115d13df3160fe3504f4`,
and report/review `17800cff0b6249fdac16481856c0800d1808a951ae50700115dcbc5abbdfb728`.
Hosted runtimes were Python 3.11.16, R 4.6.0, Quarto 1.9.37; method packages
were `scrutiny` 0.6.2, `statcheck` 1.5.0, and `simdistr` 1.0.1. Source SHA-256
values were `b0826ae470e0a009c6fce9486500a1a7232ff9bc87203c0d71d38206da839619`
for the R lock file and `76de5b5be8938b2329439f78c86ac4debe32f0fc7e42f843a8ead8ea9aae9c56`
for the guidance sums. Native receipt/result SHA-256 values were
`1c28fd26544c42a0057beeaf928e8e5c038a8596b8cdf952edfa6bafd1fe6dfa`
and `4eaf89de97750e10cbdc6cdc29a5fa7efecdedfcd2a86da705e703e025b8801e`.
Finalized INSPECT-SR HTML/PDF hashes were
`904863de7d8bf0cb3f0496a3816ecb5d086e5d10fb3e5b4ee2d9e665e30d6332`
and `9148c5482741d3bd5194ea71592f91ffe943eb91b4b126dcd2aa915856bc81c4`;
private prediction-review HTML/PDF hashes were
`670130a59e289988ef4ad8798101be96a42e3f33fc048c8168e37b5ee2f80e60`
and `85b2a7cbb43d5d03a8a938dd55b792b8dc26a63b99bc048f03e5c36da7f1aaac`.
No private working store was uploaded.

Local commands on that head, without source-paper analysis:

```bash
PYTHONPATH=src UV_OFFLINE=1 uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration'   # 147 passed, 18 deselected
FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library PYTHONPATH=src UV_OFFLINE=1 uv run --offline --locked pytest -q -o addopts='' -m native_r   # 13 passed, 152 deselected
FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library PYTHONPATH=src UV_OFFLINE=1 uv run --offline --locked pytest -q -o addopts='' -m report_integration   # 5 passed, 160 deselected
UV_OFFLINE=1 uv run --offline --locked ruff check .   # passed
UV_OFFLINE=1 uv run --offline --locked ruff format . --check   # 63 files already formatted
bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh   # passed
bash scripts/run_pipeline.sh --forensics all --dry-run --offline   # passed, no run created
bash scripts/run_manuscript_review.sh --study-id private_x --report missing.pdf --review-type prediction_validation --dry-run --offline   # passed, no run created
git diff --check main...HEAD   # passed
```

The local default R library did not contain `scrutiny`; selecting the existing
isolated library loaded the approved package versions and all native tests
passed. GitHub action/runner migration warnings are recorded in `docs/TODO.md`.
This receipt is a checkpoint for the code head above. The documentation-only
receipt update requires all three hosted lanes on its new exact head and again
after merge to `main`.

## Current release status — 2026-09-27

### Verified hosted checkpoint

The exact push run on commit `51fa32a19e069eaf6e10e0c61620e419cd629ae2`
([run 36302854692](https://github.com/reblocke/forensic_metascience/actions/runs/36302854692))
completed successfully. Each required lane ran with network isolation, zero
skips, and required artifacts:

| Lane | Tests | Failures / errors / skips | Job |
|---|---:|---:|---|
| Python | 133 | 0 / 0 / 0 | [python-fast](https://github.com/reblocke/forensic_metascience/actions/runs/36302854692/job/108573679195) |
| Native R | 13 | 0 / 0 / 0 | [native-r](https://github.com/reblocke/forensic_metascience/actions/runs/36302854692/job/108573679361) |
| Report/review | 4 | 0 / 0 / 0 | [report-review](https://github.com/reblocke/forensic_metascience/actions/runs/36302854692/job/108573679390) |

A duplicate `pull_request` event run, [36302857364](https://github.com/reblocke/forensic_metascience/actions/runs/36302857364), also passed. Hosted runtimes in the primary run: Python **3.11.16**, R **4.6.0**, Quarto **1.9.37**, TinyTeX **v2026.09 / LaTeX 2026**; `scrutiny` **0.6.2**, `statcheck` **1.5.0**, `simdistr` **1.0.1**, `cpp11` **0.5.5**, `progress` **1.2.3**, `knitr` **1.52**, and `rmarkdown` **2.32**. The report lane prepared TeX before isolation and rendered both INSPECT-SR and private prediction-review HTML/PDF.

The uploaded allowlisted artifacts are `inspect-sr-python-36302854692`
(artifact ID `10926575396`), `inspect-sr-native-r-36302854692` (`10926177797`),
and `inspect-sr-report-review-36302854692` (`10926601312`). JUnit SHA-256:
Python `fa826a2139e65f339019567204483319a3d34032af95c83344b5da02bf8030f0`,
native R `0c6763f3e7a856581d8cc884087fded5230637f3bc9cd956e8cfce6c1d7c425e`,
report/review `c65b6c96cde04e61d8a1d77703a716bbc2a0704b01bb88aa52cbe26dcf518841`.
Native receipt/result hashes are `757e42dcb558ecd1f5355987d2919d4df118a1bf3568a2f7def13b7b33e16566`
and `4eaf89de97750e10cbdc6cdc29a5fa7efecdedfcd2a86da705e703e025b8801e`.
Rendered hashes: INSPECT-SR HTML `f3f411e651e04dacf52eeb1a14811dd93277cd032de1f070b8922924781b4dad`,
PDF `0354d54a4a070309c17860dad98e3e1c2401d796385a53b7245c848c640ba67a`;
private prediction HTML `670130a59e289988ef4ad8798101be96a42e3f33fc048c8168e37b5ee2f80e60`,
PDF `f889f37a29e55b32727fb230e1b3de383ab42bc7a6fb619c45f1e6adf4b9491d`.
The runtime and source-hash inventory hashes are recorded in the hosted artifacts;
private working stores were not uploaded.

The earlier run on `fd0212f` failed receipt enforcement because YAML folded a
continued command argument into a path with leading whitespace. Commit `51fa32a`
changed the workflow command to a literal block; the run above verifies that fix.
These hosted results are a checkpoint for `51fa32a`, not acceptance evidence for
the subsequent changes below.

### Follow-up audit and active work

A follow-up audit at the same head opened [FM-14](https://github.com/reblocke/forensic_metascience/issues/6)
with five P1 findings. The current branch changes address result retention/report
visibility, duplicate count reconciliation, strict receipt semantics, human-record
load validation, and randomized/registry ambiguity. Candidate, dossier, report,
and registration claim outputs are versioned; no historical files are rewritten.
Local acceptance for these changes passes in all three lanes. Hosted run
`36326885997` also passed all three lanes on documentation head
`3365cbc74ba33543dd1341fae61893f1d37d21e7`, as recorded below. The hosted
`51fa32a` run remains historical and does not close FM-12. FM-12 stays open
until all lanes pass on the final PR head and merged `main`.

| Ticket | Current status |
|---|---|
| FM-01–FM-02 | Complete against mapped evidence. |
| FM-03 | Complete against M3 receipt state/count regressions and native CSV boundary checks. |
| FM-04–FM-05 | Complete against M1 result identity, candidate visibility, and rendered-evidence regressions. |
| FM-06 | Complete; design-qualified seeded simdistr evidence remains mapped. |
| FM-07 | Complete against M5 non/quasi-randomized and ambiguous registry regressions. |
| FM-08 | Complete against pinned v1.1.2 snapshot and hashes. |
| FM-09–FM-11 | Complete against M1 report fidelity and M4 record-load invariants. |
| FM-12 | Open until all three hosted lanes pass on the final PR head and merged `main`. |
| FM-13 | Deferred; R33–R34 remain out of scope. |
| FM-14 | M1–M5 implemented; all local lanes and hosted run `36326885997` pass on documentation head `3365cbc`; final handoff receipt update requires fresh hosted checks. |

### FM-14 local acceptance receipts

Verified on the complete working tree at base `51fa32a19e069eaf6e10e0c61620e419cd629ae2`.
Python, native R, and report/review commands ran offline after environment
preparation. No test was skipped within a required lane; deselections are tests
belonging to the other lanes.

| Lane | Command summary | Result | JUnit SHA-256 |
|---|---|---|---|
| Python | `PYTHONPATH=src UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m 'not native_r and not report_integration'` | 145 passed, 18 deselected | `07958b31c2d3a9fddce62d45c2f80b406bc0aa38993d6b9b5595d4874116f213` |
| Native R | `FM_TEST_ARTIFACT_DIR=/tmp/fm14-release/native PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m native_r` | 13 passed, 150 deselected | `fc0a6949f1eb39fbe11d09b7c529ef6fb945ad8b9ce9052c084a56d309d8e5d0` |
| Report/review | `FM_TEST_ARTIFACT_DIR=/tmp/fm14-release/report PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m report_integration tests/test_inspect_sr_reporting.py tests/test_inspect_sr_cli_workflow.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs` | 5 passed, 7 deselected | `d5bda87ab07ddffec895b27a8cff40bbf116be8b996374dd0f148bc51be25ebf` |

Each JUnit gate passed with zero skips, failures, or errors and the required
artifacts present. The report lane rendered finalized HTML/PDF, early-stop
HTML/PDF, and private prediction-review HTML/PDF. Native outputs were
`native-method-receipts.csv` (SHA-256
`1c28fd26544c42a0057beeaf928e8e5c038a8596b8cdf952edfa6bafd1fe6dfa`) and
`native-standardized-results.csv` (SHA-256
`73abf6ff558093218fa7e312bcce489045ea478b1bf80b36f9a863f41c0ec0e2`).
Rendered report hashes: finalized HTML `a4af08c945c47d1f447294f42b383e79abad30ea58781e55295aea830a391b1b`,
PDF `6a8a69d3ef780b2bdd7a8a7eaa842a71df18c94ded01bd3fb09c562e9692cd3c`,
early-stop HTML `f4ff6b2b8105914e0ee0b668d4687b5c58e01147f646c5922216db77548c8a90`,
PDF `fb9b639adb6475309725a5be3a904b98d935cd058dd025f77bb9e175d8c8577a`,
private prediction-review HTML `45eadedb223aeabfb1a1244caf21229a1ea163dacf166ac6122ce868bcb46c0a`,
PDF `dc9badbb3d47724aefe96cfad8493665d659f7870320cee314c044060cb61b18`.
Local runtimes: Python 3.13.0, R 4.6.1, Quarto 1.10.18, TinyTeX v2025.12 /
LaTeX 2025; `scrutiny` 0.6.2, `statcheck` 1.5.0, `simdistr` 1.0.1. These are
local receipts; hosted runtime receipts remain authoritative for release.

### FM-14 hosted implementation receipt

Push run [36325935748](https://github.com/reblocke/forensic_metascience/actions/runs/36325935748)
passed on exact head `c0296ab2c7b5d9258d9d245796d24eccc902b1d1`; the duplicate PR
event [36325938305](https://github.com/reblocke/forensic_metascience/actions/runs/36325938305)
also passed on the same SHA. The primary run completed Python (145 tests),
native R (13), and report/review (5), with zero skips/failures/errors in the
required lanes. Job links: [Python](https://github.com/reblocke/forensic_metascience/actions/runs/36325935748/job/108638584572),
[native R](https://github.com/reblocke/forensic_metascience/actions/runs/36325935748/job/108638584422),
[report/review](https://github.com/reblocke/forensic_metascience/actions/runs/36325935748/job/108638584259).

Allowlisted artifact IDs are Python `10933528452`, native R `10934256724`, and
report/review `10934043246`. Artifact SHA-256 digests are respectively
`31820c48f80fe0453a13174210346ecfb2c26fc0e7c4890d0f600305035a0b59d`,
`152c6326f01145ad29662d44ea3f71bad928f03ffe57394a01816c5d23c50d3c`, and
`1cc9c4197488c709106ff192d533def98d9f20f7500d5063be855e9d9d9bf867`. JUnit
SHA-256 values: Python `9d7b5d11fcdebb8e4048de06050771ca5dbf1493c681d49f6d4f88b197416f43`,
native R `2e69778e0a6bd33234a857090848726338f618ca56eb6d8c2dd4fd41ab78ac99`,
report/review `1252b810202abbdc4d6790b4057f1f4cc17f4a92ad8ea39717481a4d1d8d2169`.
The native receipt and result CSV hashes are unchanged from the verified
fixture hashes above. Hosted versions: Python 3.11.16, R 4.6.0, Quarto 1.9.37,
TinyTeX v2026.09 / LaTeX 2026; `scrutiny` 0.6.2, `statcheck` 1.5.0,
`simdistr` 1.0.1, `cpp11` 0.5.5, `progress` 1.2.3, `knitr` 1.52, and
`rmarkdown` 2.32. The source-hash inventory SHA-256 is
`7d660ee141686f86ed28c4b094013cb7968d9e2f39b72bf0a003571b09de82b6`.
Rendered artifact hashes: INSPECT-SR HTML
`cca17267d4bd0771a087f576be946681a97b0ccadd2844a3326c9ee4351a97de`, PDF
`4ca3a193a5561620f3084c9335f8660c32ff7ae2932e4bc56dc05d44a5eceaeb`,
early-stop HTML `5e3d24758ea7d4456d4a8d1278d588f598c93abfdb41a3b1237f963af84a0ea2`,
PDF `c73feb8fb8bbec730400a3bcf0c2b635753782c9961cb50efe0fcedc3b1add30`,
private prediction-review HTML `670130a59e289988ef4ad8798101be96a42e3f33fc048c8168e37b5ee2f80e60`,
PDF `1db7555a9c4511cd4553c9875633eda6bde89e9e7ef96251ee9dd3605e6bf84f`.
No private working store was uploaded. The duplicate PR event also passed all
three jobs; this run on `3365cbc` verifies that then-current documentation head.

The subsequent documentation-only handoff update records this receipt. It does
not change code or test inputs; the new PR head still requires fresh Python,
native R, and report/review checks before the PR can be marked ready or merged.

Final documentation-head run [36326885997](https://github.com/reblocke/forensic_metascience/actions/runs/36326885997)
passed on `3365cbc74ba33543dd1341fae61893f1d37d21e7`; duplicate PR event
[36326888869](https://github.com/reblocke/forensic_metascience/actions/runs/36326888869)
also passed on that SHA. Counts remained 145 Python, 13 native R, and 5
report/review, with zero skips/failures/errors. Job links: [Python](https://github.com/reblocke/forensic_metascience/actions/runs/36326885997/job/108641248155),
[native R](https://github.com/reblocke/forensic_metascience/actions/runs/36326885997/job/108641248119),
[report/review](https://github.com/reblocke/forensic_metascience/actions/runs/36326885997/job/108641247978).
Artifact IDs: Python `10933524507`, native R `10934725725`, report/review
`10933829730`. Artifact SHA-256 digests: Python
`c4e9ef5a0ca7096c3591a2e646a3cf803ab83d321307a9187354999b0208cdaa`, native R
`41fd80c24e282153674318949fb66a57b64e2e8e43edee1467f620afd0bfff54`,
report/review `e4c3d3e4ddf845d89a7a934ac4d5727bee1b66a61d7954d9d1fc8525d36c230f`.
JUnit SHA-256 values: Python
`ecd19d6fa021caa1b71548669ad822258a1491fe716a90ca23984eba3aa24f9a`, native R
`0c5aa95c4349d4f307f2c79bf3923331d74830200b9dff01168adaa51a0ac772`,
report/review `1031595670ca4f36fe6f386be0bf7280f6ff800604bab507d3b68b5c869a465e`.
Native receipt and result hashes remained
`1c28fd26544c42a0057beeaf928e8e5c038a8596b8cdf952edfa6bafd1fe6dfa` and
`4eaf89de97750e10cbdc6cdc29a5fa7efecdedfcd2a86da705e703e025b8801e`.

`run-b2.html` remains untracked and unchanged at SHA-256
`2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.
No source-paper analysis, historical-results rewrite, deployment, or human
adjudication was performed. The PR remains a draft until the new checks pass.

## Local acceptance checkpoint — 2026-09-26

The authorized repair is continuing on `codex/inspect-sr-resumption` from
`4b2d84bdf35f1b5e4893658026052902b242e524`. Existing uncommitted changes and
`run-b2.html` are preserved; its starting SHA-256 was
`2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.

- Fixed the mixed candidate/evidence table rows in
  `notebooks/inspect_sr_assessment.qmd` by normalizing displayed values to
  scalar text cells. The connected native-to-review CLI workflow now passes
  locally through current evidence, source snapshot, candidate mapping,
  independent submissions, adjudication, finalization, HTML/PDF rendering, and
  allowlisted export.
- Added `scripts/run_offline_test_lane.sh` and wired all three hosted lanes to
  create a network namespace, drop back to the runner account, carry explicit
  runtime variables, and invoke the prepared Python environment by absolute
  path. `scripts/check_pytest_junit.py` is required in each lane to reject an
  empty suite or any skip/failure/error. CI artifacts include JUnit, runtime
  inventories, source hashes, and allowlisted synthetic outputs; private stores
  are not uploaded.
- Added a failing adapter regression, confirmed it failed before the code fix,
  then blocked all rounding-bias candidate mapping. The native receipt remains
  `rounding_bias_blocked_v1` with unknown applicability, blocked execution,
  indeterminate result, zero evaluated units, preserved input count, null
  findings, and no anomaly output. Optional sequence checks remain blocked;
  SPRITE remains unimplemented.
- Replaced one-column private prediction-review fixtures with populated
  contract-shaped synthetic CSVs and added HTML/PDF artifact allowlisting. The
  mixed evidence/candidate report path checks rendered candidate evidence and
  its source locator. Added JUnit and required-artifact gate regressions.
- `docs/INSPECT_SR_ACCEPTANCE.md` maps R01–R32 and subsequent review findings
  to tests and lanes. README, credibility criteria, INSPECT-SR guide, and this
  decision/handoff now describe rounding-bias as blocked. R33–R34 remain
  deferred under FM-13.

### Ticket ledger at this checkpoint

| Ticket | Status against current local evidence |
|---|---|
| FM-01–FM-02 | Complete: eligibility, precision, denominators, source text, and P-value comparator cases pass mapped Python/R boundary tests. |
| FM-03 | Complete: malformed, partial, failed, zero-eligible, missing-dependency, and unknown outputs remain distinct in native receipt tests. |
| FM-04–FM-05 | Complete: no composite judgment; source-bound candidate mapping, current-run isolation, and immutable run-manifest behavior are covered. |
| FM-06 | Complete: design-gated seeded simdistr production path passes with independent numerical expectations. |
| FM-07 | Complete: negation-aware registration claims and malformed history handling pass. |
| FM-08 | Complete: pinned v1.1.2 source files, catalogue, licenses, and hashes are present and validated. |
| FM-09–FM-11 | Complete: source-linked candidates, independent review/adjudication, finalization, rendered reports, and allowlisted export pass connected synthetic CLI/report coverage. |
| FM-12 | Open: hosted Python, native R, and report/review lanes must pass on the same final PR head and merged `main`. |
| FM-13 | Deferred; R33–R34 remain outside this repair. |

“Complete” for FM-01–FM-11 means the implementation and mapped local
acceptance are complete. The all-lanes release/integration claim remains
withheld until FM-12 passes on hosted CI and merged `main`.

### Local acceptance receipts for the current branch tree

- Python passed **133 tests, 17 deselected**; its JUnit gate reported zero
  skipped or failed tests:

  ```bash
  PYTHONPATH=src UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m 'not native_r and not report_integration' --junitxml=/tmp/fm-inspect-final-delivery-0926/python/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/python/junit.xml /tmp/fm-inspect-final-delivery-0926/python/python-version.txt
  ```

- Native R passed **13 tests, 136 deselected**; its JUnit gate reported zero
  skipped or failed tests:

  ```bash
  FM_TEST_ARTIFACT_DIR=/tmp/fm-inspect-final-delivery-0926/native PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m native_r --junitxml=/tmp/fm-inspect-final-delivery-0926/native/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/native/junit.xml /tmp/fm-inspect-final-delivery-0926/native/python-version.txt /tmp/fm-inspect-final-delivery-0926/native/r-packages.csv /tmp/fm-inspect-final-delivery-0926/native/r-session.txt /tmp/fm-inspect-final-delivery-0926/native/source-hashes.sha256 /tmp/fm-inspect-final-delivery-0926/native/native-method-receipts.csv /tmp/fm-inspect-final-delivery-0926/native/native-standardized-results.csv
  ```

- Report/review passed **4 tests, 7 deselected**; its JUnit gate reported zero
  skipped or failed tests. This selection rendered synthetic INSPECT-SR and
  private prediction-review reports in HTML/PDF and completed the CLI workflow,
  early-stop branch, symlink checks, and allowlisted export:

  ```bash
  FM_TEST_ARTIFACT_DIR=/tmp/fm-inspect-final-delivery-0926/report PYTHONPATH=src R_LIBS_USER=/tmp/fm-inspect-r.locked-library FORENSICS_REQUIRE_R_INTEGRATION=1 FORENSICS_REQUIRE_REPORT_INTEGRATION=1 UV_OFFLINE=1 uv run --offline pytest -q -o addopts='' --tb=short -m report_integration tests/test_inspect_sr_reporting.py tests/test_inspect_sr_cli_workflow.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs --junitxml=/tmp/fm-inspect-final-delivery-0926/report/junit.xml
  uv run --offline python scripts/check_pytest_junit.py /tmp/fm-inspect-final-delivery-0926/report/junit.xml /tmp/fm-inspect-final-delivery-0926/report/python-version.txt /tmp/fm-inspect-final-delivery-0926/report/r-packages.csv /tmp/fm-inspect-final-delivery-0926/report/r-session.txt /tmp/fm-inspect-final-delivery-0926/report/quarto-version.txt /tmp/fm-inspect-final-delivery-0926/report/quarto-environment.txt /tmp/fm-inspect-final-delivery-0926/report/source-hashes.sha256 /tmp/fm-inspect-final-delivery-0926/report/inspect-sr-review.html /tmp/fm-inspect-final-delivery-0926/report/inspect-sr-review.pdf /tmp/fm-inspect-final-delivery-0926/report/private-prediction-review.html /tmp/fm-inspect-final-delivery-0926/report/private-prediction-review.pdf
  ```
- Checks: `uv run ruff check .`, `uv run ruff format . --check`, `bash -n
  scripts/run_offline_test_lane.sh scripts/install_inspect_sr_r_methods.sh`,
  Ruby YAML parsing of `.github/workflows/ci.yml`, R parsing of
  `scripts/run_numeric_forensics.R` and `R/method_receipts.R`, and
  `git diff --check` passed.
- Local runtime: Python **3.13.0**, R **4.6.1**, Quarto **1.10.18**, TinyTeX
  **v2025.12** / LaTeX **2025**. R packages: scrutiny **0.6.2**, statcheck
  **1.5.0**, simdistr **1.0.1**, rmarkdown **2.32**, knitr **1.51**, cpp11
  **0.5.5**, progress **1.2.3**. Quarto PDF rendering passed. `pdflatex` is
  not separately available on the local shell PATH; Quarto resolves its bundled
  TinyTeX. Hosted CI records its own Quarto/TeX runtime inventory.
- Local JUnit SHA-256: Python
  `3163516bc48d38e116262fff2fe2dc7280581bfbe66fb32b7105c988a850b0fd`; native
  `72dd45b29fe51f8a32d2ca2383609acf6605a5d999a301b987a85cfe9b785fde`; report
  `1ceaf7d9f0c608292f7fb5fd02f451fef3dcf7748bc2e692e3957fecad5e4145`.
  Synthetic report hashes: INSPECT-SR HTML
  `afe55cfa54a149cf067f0f21479b87ed4bbd3ab736765d41c22572499a1c982d`, PDF
  `4fe7570198aaee722b67e27f9cbcb9bb70b9732cea6ff80640712d4a11b1a007`;
  private prediction HTML
  `45eadedb223aeabfb1a1244caf21229a1ea163dacf166ac6122ce868bcb46c0a`, PDF
  `5364e057575e8aa49c926450d7b195678a1ff460d7f19454d24f0852f3841b62`.
  Native method receipt SHA-256 is
  `757e42dcb558ecd1f5355987d2919d4df118a1bf3568a2f7def13b7b33e16566`; the
  standardized result SHA-256 is
  `73abf6ff558093218fa7e312bcce489045ea478b1bf80b36f9a863f41c0ec0e2`.
- The `run-b2.html` SHA-256 remains
  `2be30454a0a1a24390a18c994fe669dc22682d4a9eda4b074b18351a362f6035`.
  These are local receipts only. The macOS runs do not verify Linux network
  namespace setup; hosted CI must exercise that wrapper before FM-12 can close.

**Still open:** Push the reviewable commits, exercise the exact network-namespace
wrapper on hosted runners, pass all three hosted lanes on the same final PR SHA,
review and mark PR #5 ready, merge with a merge commit, then verify on merged
`main`. FM-12 remains open and no ticket is declared fully integrated yet. No
source-paper analysis, historical-results rewrite, deployment, or human
adjudication was performed.

## Hosted acceptance continuation — 2026-09-25

Draft PR #5 remains open and unmerged. On commit `a353f3d`, hosted Actions
runs `36212282299` and `36212284401` exposed two environment failures:
`python-fast` could not import the local `research_project` package in a
subprocess because the workflow lacked `PYTHONPATH=src`; `report-review`
reached Quarto but R could not load `rmarkdown`. The Python import failure was
reproduced locally without `PYTHONPATH` and corrected in the workflow. Adding
the missing R package to the hosted report environment awaits dependency
approval under `AGENTS.md`; the report lane and FM-12 remain blocked until it
is approved and passes. Both `native-r` jobs then failed during isolated R
setup: `fs` could not find libuv headers and transitive `cpp11`/`progress`
were unavailable, so scrutiny could not be installed. Repair of that hosted
test environment also awaits approval; neither native-R job reached its tests.

An additional failing regression showed that a report could accept candidate
evidence without a matching current method receipt or source evidence. The
report builder now checks candidate routes, evidence IDs and locators against
the receipt inputs, and derives supplied coverage from validated receipts.
New models use `inspect_sr_report_model_v2`; existing v1 models are retained as
historical outputs and must be rebuilt from current records for review.
After that change, `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o
addopts='' -m 'not native_r' -ra` passed **128 tests** with 13 native tests
deselected. The required local report command recorded below passed **11
tests**. The workflow fix and candidate guard require a new hosted run on the
committed head before acceptance.

On commit `b0804de`, the hosted `python-fast` job in run
[`36212736603`](https://github.com/reblocke/forensic_metascience/actions/runs/36212736603)
passed install, Ruff lint, Ruff format, and tests. The same committed head
passed locally with **13 native R tests** (`FORENSICS_REQUIRE_R_INTEGRATION=1
R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run
--offline pytest -q -o addopts='' -m native_r -ra`; 128 deselected) and **11
report/review tests** (`FORENSICS_REQUIRE_REPORT_INTEGRATION=1
R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run
--offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py
tests/test_inspect_sr_cli_workflow.py
tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`).
These local passes do not clear the hosted R/report setup failures.

## Latest repair continuation — 2026-09-25

The prior "FM-01–FM-12 implemented and locally verified" sentence below was
premature. The review of `09a77dc` found invalid hosted CI expressions and
unbound review/source identities. Current branch work merges `main` with its
data-free onboarding and privacy guidance, retains the original untracked
`run-b2.html`, and repairs the reviewed defects. No source-paper analysis,
historical output rewrite, merge to `main`, or deployment has occurred.

FM-03, FM-05, and FM-08–FM-11 are reopened for v4 receipts, source mapping,
private snapshots, v3 human identities, and complete report/export validation.
FM-12 is open. FM-13 remains deferred. The rounding-bias method has a newly
identified input-contract problem requiring a scientific decision: printed
values rerounded at their printed precision produce zero bias by construction.
It is not independently qualified by an execution-only integration test.
### Local acceptance receipts on `a9d3ccb` (before the final handoff edit)

- `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m 'not native_r' -ra`: **127 passed, 13 deselected**. The deselected tests are the separately required native lane.
- `FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m native_r -ra`: **13 passed, 127 deselected**. This includes synthetic expected true/false results for GRIM, GRIMMER, DEBIT, duplicates, and statcheck, plus the exact binary extremes for simdistr. Rounding-bias execution ran, but its scientific input contract remains unqualified as described above.
- `FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py tests/test_inspect_sr_cli_workflow.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`: **10 passed**. This includes actual CLI finalization, HTML/PDF, allowlisted export, and private prediction-review HTML/PDF with current/stale sentinels.
- `UV_OFFLINE=1 uv run --offline ruff check .`: passed. `UV_OFFLINE=1 uv run --offline ruff format . --check`: passed, 59 files already formatted. `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh scripts/install_inspect_sr_r_methods.sh`, `ruby -e 'require "yaml"; YAML.parse_file(".github/workflows/ci.yml"); puts "workflow YAML parses"'`, and `git diff --check`: passed.
- Runtime: local R **4.6.1**, Quarto **1.10.18**, scrutiny **0.6.2**, statcheck **1.5.0**, simdistr **1.0.1**. Hosted pins remain R 4.6.0 and Quarto 1.9.37. The guidance `SHA256SUMS` hash is `76de5b5be8938b2329439f78c86ac4debe32f0fc7e42f843a8ead8ea9aae9c56`; catalogue hash is `313869d190ff35dfa0137559da440a5cc62cfce1d61d8aef23784ce79a2e1395`; R package-lock hash is `dea25709a20bbf923fd7b8e06b8a34a4f980de52ce95c15f72005db941a3af4d`.
- The connected synthetic source at snapshot creation had SHA-256 `1c86db65f48be61e87eeda4680a562a12b527cb2edff35a88f88bea584bd144a`; local snapshot identity was `687915e2475c3dd8e965722b6b798148d26cd35ca2ae637b06a1074c73ca92c8`. The test changed the source afterward and verified that validation failed until source bytes were restored.
- Five synthetic report/model files and `receipt.json` were copied without overwriting existing files to ignored `data/private/inspect_sr/verification/a9d3ccb/`. Their SHA-256 values are `638dc1402a75c244f98702bd95b9080716eefc6408dd2c0e3ee9a5388b9c4239` (INSPECT-SR HTML), `8a1be2a9e12b1a600f97a434c22a3fc22fbdca57f916c54b92081199f4a6ba7b` (PDF), `8844d1036a2ffc1f5db0d3ed7bbc7a88207d45799c7a1c8222b29a14c1037b24` (model JSON), `4f5a3408b202724879ecc7ef9485b4ed8e664a8bebbcbf3a096b4b6b9bcbb3e6` (private prediction HTML), and `4fdceb9b4e1845befe3e8ef9fa9e05ff4419558b12f7ec170ede055bd0111785` (PDF).

Hosted Actions and the scientific rounding-bias decision remain open. No source-paper analysis, production deployment, merge, automatic adjudication, or historical-results rewrite was run.


## Latest status — 2026-09-25

Implementation is on branch `codex/inspect-sr-resumption`, based on current
repository HEAD rather than resetting to the audit commit. The implementation
checkpoint commits are `d8b21a5` (source-linked native outputs), `e9a21ae`
(private review workflow), and `cb77b76` (required CI lanes). The original
untracked `run-b2.html` artifact is preserved and excluded from commits. No
source-paper analysis or historical output regeneration was run.

- **FM-01–FM-12 at this earlier checkpoint:** Claimed implemented and locally
  verified, pending hosted CI. Later review reopened the tickets noted above.
  FM-03–FM-07 corrections had regression-first coverage at that checkpoint.
  FM-08 uses the 26-file official v1.1.2 source snapshot at
  `a349c4f1ddd9d232dfc2632938aad31382a9a770`, with the complete 21-check
  catalogue and per-file hashes. FM-09–FM-11 keep candidate evidence, manual
  observations, reviewer submissions, adjudication, reports, and synthesis
  exports as distinct records.
- **FM-13:** Deferred.

Draft PR [#5](https://github.com/reblocke/forensic_metascience/pull/5) is open.
Hosted run `36205920711` was created for commit `5b3ca7537d483aa2a372e83642d8970eed86d854`
but concluded `failure` with zero jobs; `gh pr checks 5` reported no checks,
the jobs API returned `total_count: 0`, and GitHub provided no run log and refused
to retry it. Therefore hosted Python/native-R/report checks have not passed and
FM-12 remains open for hosted verification. The failure cause is not exposed by
the available run metadata.

### Verification receipts on the implementation code

- `UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m 'not native_r' -ra`
  — passed, 115 passed and 11 deselected (Python lane).
- `FORENSICS_REQUIRE_R_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -m native_r -ra`
  — passed, 11 passed and 115 deselected. Native method package versions were
  scrutiny 0.6.2, statcheck 1.5.0, and simdistr 1.0.1; method receipts showed
  evaluated synthetic coverage for GRIM, GRIMMER, DEBIT, duplicate,
  rounding-bias, statcheck, and seeded simdistr.
- `FORENSICS_REQUIRE_REPORT_INTEGRATION=1 R_LIBS_USER=/tmp/fm-inspect-r.locked-library UV_OFFLINE=1 PYTHONPATH=src uv run --offline pytest -q -o addopts='' -ra tests/test_inspect_sr_reporting.py tests/test_pipeline.py::test_randomization_report_renders_only_current_run_inputs`
  — passed, 8 tests, including current-run HTML/PDF report renders.
- `UV_OFFLINE=1 uv run --offline ruff check .` and
  `UV_OFFLINE=1 uv run --offline ruff format . --check` — passed; 56 files
  formatted. `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh scripts/install_inspect_sr_r_methods.sh`
  and `git diff --check` — passed.
- Local runtime: R 4.6.1, Quarto 1.10.18. CI is configured for R 4.6.0 and
  Quarto 1.9.37. The isolated local method library contains the three versions
  above. The source package archives are hash-recorded in
  `config/inspect_sr/r_method_packages.lock.json`.

Hosted Actions remain the release follow-up. The three jobs are separate Python,
required native-R, and report-review lanes; missing R/Quarto/method execution is
configured to fail or leave the integration gate incomplete. Transitive R
imports are installed from CRAN during test setup and are not independently
locked. Reviewer identities, ambiguous trial/report mappings, and each review's
synthesis policy remain explicit human inputs. No deployment, author contact,
automatic adjudication, or historical-results rewrite is authorized.

### FM-08–FM-12 artifact map

- **FM-08:** Added `config/inspect_sr/v1.1.2/` with 26 retrieved guidance/source files, `catalogue.json`, retrieval/license metadata, and `SHA256SUMS`. Added the persistent record model in `src/research_project/inspect_sr/records.py` and its tests. New record schemas include `inspect_sr_catalogue_v1`, `inspect_sr_assessment_v1`, and `inspect_sr_record_model_v1`. Initial checks are pending with null responses.
- **FM-09:** Added method candidate routes in `src/research_project/inspect_sr/adapters.py` and human observation records in `manual_evidence.py`; tests are in `tests/test_inspect_sr_evidence.py`. Candidate outputs use `inspect_sr_candidate_evidence_v1`; manual observations use `inspect_sr_manual_evidence_v1`. Existing v2 method receipts are required, with same-run and source-version checks. Unvalidated checks remain manual-only.
- **FM-10:** Added independent reviewer submission, disagreement, adjudication, resolution, finalization, and query draft records in `review.py`/`validation.py`; tests are in `tests/test_inspect_sr_review.py`. Schemas include `inspect_sr_reviewer_submission_v1`, `inspect_sr_adjudication_v1`, `inspect_sr_resolved_review_v1`, and `inspect_sr_finalization_v1`. Human records are written separately and are not regenerated from candidates.
- **FM-11:** Added the private review model/report in `reporting.py` and `notebooks/inspect_sr_assessment.qmd`, plus explicit policy validation and export in `synthesis_export.py`; tests are in `tests/test_inspect_sr_reporting.py`. Schemas include `inspect_sr_report_model_v1`, `inspect_sr_synthesis_policy_v1`, and `inspect_sr_synthesis_export_v1`. The QMD accepts only an explicit model path; public export is explicitly allowlisted.
- **FM-12:** Added `tests/test_r_integration.py`, the source/hash manifest `config/inspect_sr/r_method_packages.lock.json`, test-only installer `scripts/install_inspect_sr_r_methods.sh`, and separate CI jobs in `.github/workflows/ci.yml`. The pinned scrutiny adapter affects `numeric_scrutiny_{grim,grimmer,debit}_{raw,audit}.csv`, `numeric_standardized_results.csv`, and `numeric_method_receipts.csv` in new run directories; the statcheck receipt uses report text as its single input/evaluation unit. The seeded simdistr test reads/writes only temporary fixtures and verifies repeatability at a fixed seed.

The earlier notes below are chronological receipts from prior stages. Where they
say FM-08 is blocked by a missing source snapshot or native packages are absent,
those statements are superseded by the current pinned snapshot and the isolated
native test environment recorded in the latest decision entry.

## INSPECT-SR packet — 2026-09-25

### Completed
- **FM-01:** Added `numeric_eligibility_v2`. Baseline median observations remain in evidence and are ineligible for GRIM/GRIMMER/DEBIT. The Python input builders and R execution boundary require documented statistical semantics; absent metadata stays unknown and blocks execution. Method-specific reasons are retained in `scrutiny_cases.csv`.
- Regression coverage first reproduced the prior permissive behavior, then passed after implementation. Focused command: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_forensics_categories.py` (6 passed); full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (41 tests). `ruff check .`, `ruff format . --check`, and `Rscript -e 'invisible(parse(file="scripts/run_numeric_forensics.R"))'` passed.
- Affected generated outputs: `scrutiny_input.csv`, `scrutiny_cases.csv`, and `scrutiny_{grim,grimmer,debit}_input.csv`; stored historical outputs were not regenerated.
- **FM-02:** Advanced the numeric method revision to `numeric_eligibility_precision_v3`. Source cells, statistic text, precision, P-value comparator, and source locator are preserved across extraction/build and Python/R CSV reads. Noninteger/nonfinite denominators and counts are rejected; percentage compatibility is indeterminate without denominator role, unweighted status, and explicit supported rounding convention. The legacy percentage delta remains descriptive only.
- FM-02 verification: `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (46 tests collected); `ruff check .`, `ruff format . --check`, R syntax parse, and the Python→readr→Python string-precision roundtrip passed. Regression cases cover 1/3 as 33% and 33.3%, 34.0% incompatibility under nearest-half-up, unknown denominator status, weighted percentages, invalid counts, P<0.001, P=1.2, and an outcome-specific denominator with unknown role.
- FM-02 affected generated outputs: parsed Table 1 rows, `numeric_checks_input.csv`, `scrutiny_input.csv`, `scrutiny_cases.csv`, and package-specific numeric inputs. No stored historical artifacts were rewritten.
- **FM-03:** Added `method_receipt_v1` execution receipts for GRIM/GRIMMER/DEBIT, duplicate and rounding-bias checks, statcheck, optional sequence methods, and unimplemented SPRITE. Completed no-finding receipts require positive evaluated coverage; zero eligible inputs, missing dependencies, errors, partial evaluation, not-requested methods, and not-implemented methods remain explicit. Fixed trial-ID selection across means-only inputs, preserved case IDs in standardized method rows, stopped mapping package probability to inferential `p_value`, and moved SPRITE candidate differences to a descriptive output without anomaly fields. Summary finding counts remain null when a method is not fully evaluated.
- FM-03 affected generated outputs: adds `numeric_method_receipts.csv` and `numeric_descriptive_arm_differences.csv`; changes `numeric_standardized_results.csv`, `numeric_summary.csv`, and compatibility `numeric_package_status.csv`; updates `notebooks/lungtime_numeric_audit.qmd` and `notebooks/prediction_validation_review.qmd`. Existing outputs and annotations were not regenerated.
- FM-03 verification: regression-first receipt tests and the synthetic runner integration test passed (`PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_forensics_categories.py::test_r_method_receipt_contract_has_truthful_outcomes tests/test_forensics_categories.py::test_numeric_runner_receipts_keep_means_only_trial_and_exclude_sprite_stub`); full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (48 tests); `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parsing of runner and receipt helper, and `git diff --check` passed. The synthetic run used only a temporary directory. R `scrutiny` is absent, so native package execution and Quarto rendering against generated numeric outputs remain unverified; no source-paper analysis was run.
- **FM-04:** Replaced the corrected Python/R weighted meta score with explicit category coverage and source-linked candidate screening signals. Missing-only category metrics are unavailable; failure and unsupported states remain unknown because the current category reports do not distinguish them. Candidate rows come only from existing flagged outputs and preserve source file/unit. Legacy formula reproduction now requires `--legacy-reproduction`, uses `legacy_composite_v1`, is labeled `NOT_INSPECT`, and writes into isolated `inputs/legacy/` and `reports/legacy/` paths. The meta report no longer renders an aggregate score or score plot.
- FM-04 migration: corrected defaults no longer write/read `meta_category_scores.csv`, `meta_overall_seed.csv`, `meta_category_scores_out.csv`, or `meta_overall_summary.csv`; those existing files are preserved. New artifacts use explicit versions: `category_summaries_v2_raw.csv`, `category_coverage_v1_raw.csv`, `candidate_concerns_v1_raw.csv`, `meta_evidence_coverage_v1.csv`, `meta_candidate_concerns_v1.csv`, `meta_evidence_coverage_v1_out.csv`, `meta_candidate_concerns_v1_out.csv`, and `meta_coverage_summary_v1.csv`. The corrected report is `<study>_meta_audit_v2.pdf`; prior source summaries and PDF remain untouched. Legacy mode alone emits the deprecated composite artifacts under `legacy/`.
- FM-04 verification: regression-first coverage and missingness tests, candidate source-link extraction/build tests, direct corrected R runner test, and explicit Python→R legacy fixture reproduction passed. Full `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (52 tests); `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parse, Python byte-compilation, and `git diff --check` passed. All execution used synthetic temporary fixtures; no real category reports were processed and no Quarto render was run.
- **FM-05:** Each forensics or private manuscript-review execution now gets a fresh `forensics_run_v1` directory, input/config fingerprints, stage statuses, and SHA-256 artifact receipts. The category runner fingerprints only selected-stage sources; missing optional inputs are recorded as unavailable. Extraction and report rendering are separate opt-ins, network access is off unless `--allow-network` is explicit, and `--offline` overrides it. Help/dry-run are output-free; numeric-only runs extract the baseline table without invoking simdistr or Quarto; category aggregation validates active-run inputs, stage receipts, artifact hashes, and report-root ownership. Shared human manifests are not updated by these runners. Historical meta report layout is available only with `extract_meta.py --legacy-layout`; it cannot be combined with a run manifest.
- FM-05 affected outputs: new run directories under `data/processed/forensics_runs/<study>/<run-id>/` (or the explicit repository-contained `--output-root`), including `run_manifest.json`, `processed/`, and `reports/`; private manuscript review outputs are similarly isolated under `data/processed/reviews/<study>/<run-id>/`. Existing shared outputs and human annotations were not regenerated.
- FM-05 verification: run/input-isolation and run-scoped digitizer path checks passed; `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (59 tests); scoped Ruff check and format check, `bash -n scripts/run_pipeline.sh scripts/run_manuscript_review.sh`, Python byte-compilation of changed entrypoints/modules, and `git diff --check` passed. The no-network transport stub, output-free help/dry-run, and private-review dry-run tests passed. No source-paper analysis or Quarto render was run. Native `scrutiny` package execution remains unavailable, so FM-12 is not qualified.
- **FM-06 implementation:** Reported variable tests now have separate `reported_test_v1` records with stable IDs, parent-variable links, raw P text/comparator, and unknown scope/method/tail/population left explicit. Recalculated one-versus-rest rows use stable IDs and canonical ordering, but no reported-versus-recalculated difference flag is emitted when test definitions are unknown. Inferential Pearson/simdistr outputs require explicit `unrestricted_individual_1to1` design plus expert opt-in; simdistr also requires a seed and source-reported percentage precision. Unknown dependence keeps pooled outputs descriptive and uncalibrated. A separate fixed-block-4 arithmetic result accepts only explicit randomized counts for one unstratified list; post-exclusion counts and multiple strata are unsupported.
- FM-06 affected-output map: input artifacts are versioned as `csf_input_v2.csv`, `reported_tests_v1.csv`, and `simdistr_input_v2.csv`; R outputs are `row_level_results_v2.csv`, `reported_test_records_v1.csv`, `pooled_descriptive_v2.csv`, `allocation_arithmetic_v1.csv`, `randomization_run_receipt_v1.csv`, `simdistr_variable_pvalues_v1.csv`, and `simdistr_combined_descriptive_v1.csv` (plus `simdistr_runtime_input_v1.csv` and raw stdout only when explicitly opted in with source precision). Older unversioned files and reports remain untouched in prior run directories.
- FM-06 verification: `PYTHONPATH=src .venv/bin/python -m pytest -q` passed (64 tests), including the production R runner integration for three-level tests, MRN-parity gating, valid incomplete blocks, post-exclusion rejection, multiple-strata rejection, seed receipt, and precision preservation. `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, R parsing, `bash -n scripts/run_pipeline.sh`, and `git diff --check` passed. Synthetic Quarto HTML and PDF smoke renders passed using temporary inputs; no source-paper analysis ran. **The simdistr package is not installed**, so actual seeded simdistr numerical reproducibility remains open; no install or network request was made.

### Open gates and next work
- FM-01 through FM-05 are complete. FM-06 implementation is in place, with its simdistr reproducibility gate open; FM-07 through FM-12 remain open; FM-13 remains deferred.
- R 4.6.0, Quarto 1.9.37, `readr`, and `dplyr` are installed. R package `scrutiny` is unavailable, so package-native method execution and the assembled release gate remain unverified.
- The audit commit `30b3fc2c9ba11b0a89e62f911043f2ca2ab5917a` is absent from the local object database. Work continues from clean current head `805cb282ed0f9f974f5d977592bbf95b419fd022`; no reset or fetch was performed.
- The disposable baseline worktree passed 39 pytest tests, Ruff check, and Ruff format check using the existing local Python environment. Offline `uv run --frozen pytest -q` could not provision uncached `ruff==0.15.0`; network access is prohibited by the packet.

## 2026-09-24 README-13 documentation check

This check used default `main@805cb282ed0f9f974f5d977592bbf95b419fd022`
and existing README PR #4 at `298c80c82ffc02738799adeb9aa1129ba63da4f1`
in an isolated checkout. On 2026-09-24 MDT, `uv sync --locked` and
`uv run --frozen pytest -q tests/test_pipeline.py` completed with one passing
four-row fake-CSV test under CPython 3.14.4. The uv cache and Python installation
directory were redirected to isolated scratch; no study source PDF, registry,
private manuscript, R method, or Quarto report was opened or run. This checks
the Python fixture path only. The former README's R 4.5.x testing statement
has no retained runtime receipt here, and this documentation check did not
qualify an R, Quarto, PDF, or optional-package environment. Source findings
and status interpretation remain subject to the contracts below.

## Current state
- Multi-category forensic scaffold is implemented and runnable through a single pipeline entrypoint.
- A separate private manuscript-review path exists for nonrandomized prediction-validation reviews.
- Public trial runs can now be selected with `bash scripts/run_pipeline.sh --study-id <study_id> ...` using configs under `config/studies/`.

## What changed
- Added shared manifest helper and category modules:
  - `src/research_project/forensics_manifest.py`
  - `src/research_project/numeric_integrity.py`
  - `src/research_project/registration_forensics.py`
  - `src/research_project/visual_forensics.py`
  - `src/research_project/transparency.py`
  - `src/research_project/meta_forensics.py`
- Added category scripts (`extract -> build -> run`) and manifest updater:
  - `scripts/extract_numeric.py`, `scripts/build_numeric_inputs.py`, `scripts/run_numeric_forensics.R`
  - `scripts/extract_registration.py`, `scripts/build_registration_inputs.py`, `scripts/run_registration_forensics.R`
  - `scripts/extract_visual.py`, `scripts/build_visual_inputs.py`, `scripts/run_visual_forensics.R`
  - `scripts/extract_transparency.py`, `scripts/build_transparency_inputs.py`, `scripts/run_transparency_forensics.R`
  - `scripts/extract_meta.py`, `scripts/build_meta_inputs.py`, `scripts/run_meta_forensics.R`
  - `scripts/mark_forensics_ready.py`
- Added plot-digitization pilot workflow:
  - `scripts/init_plot_digitization_targets.py`
  - `scripts/run_plot_digitization.R`
  - target manifest contract under `data/raw/figures/<study>/plot_digitization_targets.csv`
  - standardized digitized-point input `data/processed/visual/<study>/inputs/plot_digitized_values.csv`
- Extended orchestration:
  - `scripts/run_pipeline.sh` now supports `--forensics randomization,numeric,registration,visual,transparency,meta`, `all`, and optional `--digitize-plots true|false`.
- Added PDF report notebooks:
  - `notebooks/lungtime_numeric_audit.qmd`
  - `notebooks/lungtime_registration_audit.qmd`
  - `notebooks/lungtime_visual_audit.qmd`
  - `notebooks/lungtime_transparency_audit.qmd`
  - `notebooks/lungtime_meta_audit.qmd`
- Added tests for new core logic:
  - `tests/test_forensics_categories.py`
- Deepened numeric forensics execution:
  - `scripts/extract_numeric.py` now emits `statcheck_text.txt` from report PDF text.
  - `scripts/run_numeric_forensics.R` now runs package-native `scrutiny` methods (`grim_map`, `grimmer_map`, `debit_map`, duplicate checks, rounding-bias checks) and `statcheck::statcheck` when installed.
  - Numeric outputs now include package raw tables, audits, and `numeric_standardized_results.csv`.
- Updated docs/contracts:
  - `README.md`, `docs/CREDIBILITY_CRITERIA.md`, `docs/DECISIONS.md`
- Added a ScienceVerse-informed transparency layer:
  - `research_object_lite.json` records source PDFs, file hashes, text refs, URLs, open-practice evidence, repository/preregistration links, and offline provenance.
  - v1 is offline by default with no LLM calls, no live repository/citation-risk API checks, and no direct `metacheck` dependency.
  - software-use and package/vendor documentation links are provenance context, not open-code evidence unless paired with explicit code/script availability language.
  - meta aggregation now exposes `evidence_burden_score` and `review_priority` while preserving `overall_score` and `risk_tier` for compatibility.
- Added study-config-driven public trial support:
  - `config/studies/lungtime.sh`
  - `config/studies/pronto.sh`
  - staged PRONTO source PDFs under `data/raw/studies/pronto/`
  - `scripts/run_pipeline.sh` now accepts `--study-id <study_id>`
  - public report renders now land in `reports/<category>/<study_id>/`
  - `src/research_project/randomization.py` now parses both original Table 1 layouts and supplement-style hierarchical baseline tables
  - `src/research_project/registration_forensics.py` now recognizes `ISRCTN` and UK trial phrasing (`randomisation`, `masked`, `open-label`)

## How to reproduce
```bash
# from repo root
uv sync
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh
bash scripts/run_pipeline.sh --study-id pronto --forensics all
bash scripts/run_pipeline.sh --forensics visual
bash scripts/run_pipeline.sh --forensics visual --digitize-plots false
quarto render notebooks/lungtime_visual_audit.qmd --to pdf
```

## What I verified
- `uv run ruff check .` passes.
- `uv run ruff format . --check` passes.
- `uv run pytest -q` passes.
- `uv run pytest -q tests/test_transparency.py tests/test_forensics_categories.py` passes.
- `bash scripts/run_pipeline.sh --forensics transparency` passes and renders transparency PDF.
- `bash scripts/run_pipeline.sh --forensics all` passes.
- `bash scripts/run_pipeline.sh` passes.
- `bash scripts/run_pipeline.sh --study-id pronto --forensics all` passes.
- `bash scripts/run_pipeline.sh --forensics visual` passes and renders visual PDF.
- `bash scripts/run_pipeline.sh --forensics visual --digitize-plots false` passes and remains non-interactive.
- `quarto render notebooks/lungtime_visual_audit.qmd --to pdf` passes.

## What remains / next steps
- Deepen package-native execution for `scrutiny`, `rsprite2`, `statcheck`, `metafor`, and `meta` once assumptions/parameter policies are locked.
- Implement package-native `rsprite2` execution (currently stub metric only) once method assumptions are fixed.
- Expand plot digitization beyond pilot one-figure target and add dual-rater concordance checks.
- Add fixture-based integration tests for each category CLI.

## Gotchas
- The public `scripts/run_pipeline.sh` entrypoint runs Python stages through `uv run python`; run `uv sync` first so declared PDF dependencies are available.
- Visual caption extraction can be sparse depending on PDF text quality; empty extraction is handled and still produces schema-valid outputs.
- Plot digitization is intentionally human-in-loop: it runs only when `--digitize-plots true` is set, and requires local figure image files matching the target manifest.

## 2026-03-19 manuscript-review addition

### What changed
- Added a nonrandomized manuscript-review path for prediction-model validation papers:
  - `src/research_project/prediction_review.py`
  - `scripts/extract_prediction_review.py`
  - `scripts/build_prediction_review_inputs.py`
  - `scripts/run_prediction_review_forensics.R`
  - `scripts/run_manuscript_review.sh`
  - `notebooks/prediction_validation_review.qmd`
- Review inputs and outputs are local-only artifacts under:
  - `data/processed/reviews/<study>/`
  - `reports/reviews/<study>/`
  - `reports/reviews/<study>/<study>_prediction_validation_review.pdf`
  - `notebooks/reports/<study>/` (local rerender byproduct only)
  - these paths are gitignored and should not be used for sharing source-manuscript contents
- Added focused unit coverage:
  - `tests/test_prediction_review.py`
- Updated docs:
  - `README.md`
  - `docs/DECISIONS.md`

### What was verified
- `uv run ruff check .`
- `uv run ruff format . --check`
- `uv run pytest -q`
- `PYTHONPATH="$PWD/src" python3 scripts/extract_prediction_review.py --report "<local_pdf>" --study-id <study_id> --review-type prediction_validation --out "$PWD/data/processed/reviews/<study_id>"`
- `PYTHONPATH="$PWD/src" python3 scripts/build_prediction_review_inputs.py --in "$PWD/data/processed/reviews/<study_id>" --out "$PWD/data/processed/reviews/<study_id>"`
- `bash scripts/run_manuscript_review.sh --study-id <study_id> --report "<local_pdf>" --review-type prediction_validation`
  - analytic stages completed
  - sandboxed Quarto render failed on `sysctl ... Operation not permitted`
- `quarto render notebooks/prediction_validation_review.qmd --to pdf --output-dir "$PWD/reports/reviews/<study_id>"`
- `PYTHONPATH="$PWD/src" python3 scripts/mark_forensics_ready.py --study-id <study_id> --category review_prediction_validation --source-pdf <local_pdf_name> --extract-confidence medium --page-ref "table2|table3|tablee2|figure1" --table-ref prediction_validation_review --ready`

### Privacy / sharing note
- Do not store manuscript-specific findings, source file names, or transcribed source statistics in tracked docs.
- Keep those outputs confined to the gitignored review artifact paths above.

### Gotchas
- The new manuscript-review scripts also use system `python3` so they can reuse the user-level PDF libraries already present on this machine.
- In sandboxed environments, `quarto render` may fail on an architecture probe; rerun the render outside the sandbox if the analysis files already exist and only PDF generation failed.

## 2026-04-21 ClinicalTrials.gov registration audit addition

### What changed
- Added ClinicalTrials.gov registry-aware registration screening:
  - `src/research_project/clinicaltrials_registry.py`
  - expanded `scripts/extract_registration.py` CLI inputs for NCT IDs, local current-record JSON, optional history files, publication identifiers, network control, and explicit as-of date
  - updated `scripts/build_registration_inputs.py` to prefer `registration_claims_expanded.csv` while preserving legacy claim compatibility
  - updated `scripts/run_registration_forensics.R` to summarize only assessed claims for mismatch rates and to copy registry-history events into report outputs
  - updated `scripts/run_pipeline.sh` to pass optional registry config fields and to run registration Python scripts through `uv run python`
- Added optional study-config fields in `config/studies/*.sh`:
  - `REGISTRY_ID`, `REGISTRY_URL`, `REGISTRY_CURRENT_REL_PATH`, `REGISTRY_HISTORY_REL_PATH`, `REGISTRY_ALLOW_NETWORK`, `REGISTRY_AS_OF_DATE`, `PUBLICATION_URL`, `PUBLICATION_DOI`, `PUBLICATION_PMID`
- Added registration report sections for registry source metadata, current-record claims, history events, and interpretation labels.
- Added `pypdf` to Python dependencies because registration extraction already required it but it was not declared in `pyproject.toml`.

### New outputs
- `data/processed/registration/<study>/inputs/registration_claims_expanded.csv`
- `data/processed/registration/<study>/inputs/registration_registry_current.csv`
- `data/processed/registration/<study>/inputs/registration_registry_current.json`
- `data/processed/registration/<study>/metadata/registration_registry_fetch_metadata.csv`
- `reports/registration/<study>/registration_history_events.csv`

### What I verified
```bash
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh --forensics registration
quarto render notebooks/lungtime_registration_audit.qmd --to pdf
```

### Notes
- Tests use local fixtures only and do not require live ClinicalTrials.gov network access.
- Normal pipeline runs may fetch ClinicalTrials.gov API v2 current records when a unique NCT ID is available and `REGISTRY_ALLOW_NETWORK="true"`.
- Registry history is local-input only for now; no stable live history endpoint is assumed.

### 2026-04-21 review-fix follow-up
- Fixed ClinicalTrials.gov helper missing-value handling so CSV blanks do not become literal `nan` strings in claims or history comparisons.
- Changed missing local registry-history files to informational sentinel rows and updated the R summary to count only substantive `value_changed` medium/high events as major history changes.
- Changed partial registry-date adjudication to interval-based logic for prospective-registration and results-overdue screens.
- Added unit tests covering missing values, missing history files, partial registration dates, and partial primary-completion dates.

## 2026-06-05 public pipeline Python environment stabilization

### What changed
- Added `pdfplumber` to declared Python dependencies because existing randomization and numeric-summary extraction already import it.
- Changed the public `scripts/run_pipeline.sh` Python stages to run through `uv run python` instead of system `python3`.
- Updated PDF dependency error messages to direct users to `uv sync`.
- Left `scripts/run_manuscript_review.sh` on system `python3` as a deliberately separate follow-up scope.

### What to verify
```bash
uv sync
uv run python -c "import pandas, pypdf, pdfplumber"
uv run ruff check .
uv run ruff format . --check
uv run pytest -q
bash scripts/run_pipeline.sh --forensics transparency
bash scripts/run_pipeline.sh --forensics all
```

## 2026-09-25 INSPECT-SR packet progress: FM-07

### Completed in this ticket
- Added v2 source claim records that carry the matched statement, page, explicit negation, population, and masking role through expanded claims. Allocation ratios now require nearby allocation/randomization context, so a time such as `12:30` is not extracted as an allocation ratio.
- Kept treatment, participant, care-provider, and outcome-assessor masking claims separate. Unmentioned or ambiguous evidence remains indeterminate.
- Added exact-byte SHA-256 and source-version status to current-registry fetch metadata; retain the exact bytes in `registration_registry_current_raw.json` alongside normalized JSON. Local JSON is explicitly labeled with unverified upstream version.
- Distinguished documented HTTP 404 from fetch failure and changed direct extraction to require explicit network opt-in.
- Normalized first-submitted, first-posted, registered-start/type, and actual recruitment-start dates separately. Prospective timing, the 365-day results-posting heuristic, and publication linkage are reported as metadata screens, never mismatch judgments.
- Separated history status from detected change events. Missing, malformed, undated, unchanged, and interval-overlapping sources do not generate synthetic changes. Receipts include source hash, date counts, chronology, detected events, and unknown completeness.
- Changed mismatch flags to three-state values; only `match`/`mismatch` contribute to the assessed denominator. Updated `notebooks/lungtime_registration_audit.qmd` to explain and display the v2 evidence and status fields.
- Updated tests in `tests/test_clinicaltrials_registry.py`, `tests/test_registration_forensics.py`, and `tests/test_forensics_categories.py`.

### Verification receipts
- `PYTHONPATH=src .venv/bin/python -m pytest -q` — passed (full suite).
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — passed (41 files already formatted at last check).
- `git diff --check` — passed.
- `Rscript -e 'invisible(parse(file="scripts/run_registration_forensics.R"))'` — passed.
- Synthetic R runner integration — passed: assessed denominator 2, mismatch count 1, unassessed mismatch flag remained NA; screen and history statuses survived into the summary.
- Synthetic Quarto report render — HTML and PDF both passed using temporary `fm07_fixture` data, removed after rendering. The initial HTML invocation used an unsupported `--output-file` option; retry with `--output` passed.
- `bash -n scripts/run_pipeline.sh` and Python `py_compile` for changed helpers — passed.
- No live registry request or source-paper analysis was run. HTTP 404 coverage uses a mocked transport. No dependencies were added.

### Open gates and next work
- FM-07 is complete and committed after final verification.
- FM-06 still has an open seeded `simdistr` numerical-reproducibility gate because `simdistr` is unavailable locally; no installation/network access was attempted. The API gate itself safely reports the dependency as missing.
- Continue with FM-08 next, following the packet dependency order. Do not call the packet integrated until FM-12 and native R/report verification are complete.

## Historical checkpoint (superseded): INSPECT-SR snapshot blocker

- **FM-08 open:** No implementation edits made. The ticket requires exact official v1.1.2 check wording, an immutable snapshot/hash, retrieval date, citation, and license/terms. The supplied ZIP has no guidance snapshot; its `SOURCES.md` only points to the live site and changelog. The local FM-08 target paths do not exist.
- **Network boundary:** User instruction requires explicit opt-in before network or interactive work. No retrieval was attempted and no check wording or hash was fabricated.
- **Action to unblock:** Provide the exact v1.1.2 snapshot and license/terms locally, or explicitly opt in to retrieving them. Resume FM-08 only after the exact content and hash can be verified.
- **FM-09, FM-10, FM-11 open:** Not implemented because their declared dependencies require FM-08, then FM-09, then FM-10. Building those records without a frozen catalogue would violate the packet contract.
- **Verification:** Read FM-08 and FM-09 through FM-11 tickets, FM-08 shared contract, source register, and the source files explicitly named by FM-08. No tests were run for these blocked tickets because no code changed.
- **Next after unblock:** FM-08 catalogue/records; FM-09 evidence mapping/manual routes; FM-10 independent review/adjudication; FM-11 report/synthesis export; then FM-12 integration/release gate. FM-13 remains optional/deferred.
