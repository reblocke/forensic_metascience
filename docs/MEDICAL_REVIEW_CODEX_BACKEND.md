# Controlled Codex medical reading

## Current status

The opt-in `codex_cli` software path is implemented. Live operational acceptance
is **blocked** for the inspected Codex CLI 0.157.0 and isolated official releases
0.161.0 and 0.160.0. Explicit skill/agent/instruction controls exclude inherited
context, but actual loopback requests still expose the native `functions`
namespace. The supported code-mode namespace exclusion setting also leaves that
wrapper exposed. Earlier v2 receipts recorded 18 of 19 mandatory checks for each
release; none qualified.
A failed qualification cannot enable
preparation or execution through the CLI. No real study transmission is part of
software acceptance, and no medical performance is established.

The isolated 0.161.0 source assessment required a user-approved local-version-only
lockfile normalization: upstream manifests use 0.161.0 while the original lockfile
records 0.0.0 for workspace packages. Original bytes and all third-party pins are
preserved. The normalized baseline now builds; a preserved actual synthetic
request reproduces native-tool exposure. The isolated native patch now builds and
passes all 20 mandatory actual CLI assessment checks, including rejection of 12
unsolicited tool-call cases. Retained evidence reauditing passes; baseline and patched
default controls retain identical tool declarations. The passing executable hash is
`8229baba8ad7387cbf2636b0116c8abd6d94cf87f503b327c78abc47b44c619a`.
Its receipt remains assessment-only and cannot prepare sources or authorize a run.
No source-built runtime is adopted or operationally qualified. An explicit decision
on the exact patched candidate, operational binding and fresh eligible qualification
are required before packet preparation and separate source-specific authorization.
See [the source-assessment materials](../tools/codex-no-tools/README.md).

The user selected `gpt-6-astra`, reasoning `max`, existing ChatGPT authentication,
one concurrent session, a 600-second generation deadline and zero automatic
request/stream retries. There is no provider/model fallback, search or specialist
session orchestration. This workflow does not execute the original Reviewer;
that comparator remains a separate fidelity gate.

## Offline qualification

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py \
  qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE"
```

`MEDICAL_CODEX_CATALOGUE` names the operator's local Codex model catalogue JSON.
The command resolves `codex` through PATH. It initially supports macOS and
`codex-cli 0.157.0`; other versions or platforms produce failed private receipts.
It uses synthetic source/context canaries, synthetic ChatGPT tokens and a local
fake provider. The entire probe controller's network access is restricted to its
loopback server. It does not read the operator's authentication file or use a real
provider. Receipt JSON, wire requests and received streams are retained beneath
the ignored private runtime-qualification boundary. For the default executable,
exit 0 means qualified; exit 3 means failed qualification, never reassuring coverage.

Synthetic candidate assessment is explicit:

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py \
  qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE" \
  --probe-executable "$MEDICAL_CODEX_CANDIDATE"
```

The optional path permits assessment of 0.157.0, 0.161.0 or 0.160.0 on macOS;
it does not replace the installed CLI. Candidate receipts have
`assessment_only: true` and `qualified: false` even if `all_checks_passed: true`
(exit 0). They cannot prepare a packet or authorize execution. CLI preparation/run
still requires the PATH-resolved pinned 0.157.0 runtime and a passing default
qualification. Adopting another version requires a subsequent explicit decision.

For the isolated patched source build, provide its retained build manifest:

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py \
  qualify-codex --offline --catalogue "$MEDICAL_CODEX_CATALOGUE" \
  --probe-executable "$MEDICAL_CODEX_CANDIDATE" \
  --probe-build-manifest "$MEDICAL_CODEX_BUILD_MANIFEST"
```

The manifest requires an explicit candidate executable. Before any runtime probe,
validation binds the upstream commit, original and normalized lockfiles, toolchain,
reviewed native patch, build command/log, source ledger and executable hash. Only
this assessment path adds `tools.enabled=false`; ordinary/live invocation is
unchanged. Invalid provenance cannot start a provider. The 19 existing checks and
one aggregate native-dispatch check are all mandatory. Direct, namespaced, freeform,
Code Mode, wait, patch, user-input, nested, post-final, malformed tool-search and
hosted search/image probes require a fatal startup-policy error and exactly one
request. Configuration errors, timeouts and parser errors cannot substitute for
that evidence. Validation rechecks issued calls and raw rejection streams.
`validate_assessment` reaudits a passing candidate while keeping `qualified: false`;
source preparation and live execution still reject it.

Obtain candidates from official release assets in an isolated directory, verify
the archive against the publisher's SHA-256 digest before extracting/executing,
and retain the release metadata, archive and executable hashes. An adjacent
`distribution.json` (one directory above the executable's directory) is retained
in the candidate receipt when supplied. It records operator intake provenance;
assessment does not certify arbitrary supplied executables as official releases.
Keep the catalogue bytes identical across comparisons. Do not change global
installation, PATH, user configuration or app settings.

Checks include an allowed-read positive control and denied outside/symlink reads,
source/workspace writes and network access. A reachable unsandboxed socket is the
network positive control. Actual wire data must show Astra/max, no top-level or
nested tools, no inherited skill/agent/operator context and synthetic ChatGPT
authentication. Successful completion, server errors, context-length errors and
cancellation exercise real CLI transport. Reduced event/final/stderr caps exercise
bounded-output failures. A deliberate unknown configuration key must fail before
any provider request. Configuration errors are failures,
not successful denials. The qualification rejects exposed tools even when the
code-mode host cannot execute them.

Receipts bind the executable bytes, OS, Python/parser versions, pinned catalogue,
entrypoint, medical/forensic code and effective policy. Live use copies the pinned
catalogue into the dedicated runtime; it does not adopt later model discovery.
Version-3 receipts bind the configuration and audit rules through policy/code
hashes. They retain raw request bodies/headers, issued fake-provider responses, all probe streams and raw sandbox
return codes/stdout/stderr. Validation verifies every artifact, reconstructed
invocation, source bytes and runtime metadata, then recomputes acceptance across
every outgoing request, including errors and cancellation. Only explicit medical
instructions, the exact synthetic source and narrow temporary-workspace metadata
are allowed. Source text mentioning tools remains source data. Complete prompt
budgets include runtime context and the structured output contract.

Changes require requalification. Historical version-1 and version-2 receipts remain preserved
but cannot authorize execution under this implementation. Changing booleans in a
receipt cannot bypass reauditing the raw wire/context/sandbox evidence. Catalogue
masking, tool-declaration removal or instructions not to call tools cannot prove
isolation. Receipts are local trusted operator
artifacts, not cryptographic protection against an operator who rewrites code.

The [Codex execution documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and [permission documentation](https://learn.chatgpt.com/docs/permissions) describe
the underlying controls. The runtime probes establish what this implementation
can actually enforce.

## Prepare a packet only after qualification passes

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py \
  prepare-codex --bundle data/private/medical_reviews/example/bundle.json \
  --qualification "$MEDICAL_CODEX_QUALIFICATION" --profile clinical_trial
```

The deterministic preparation directory contains a new indexed bundle revision,
packet, extracted artifacts and authorization template. Existing source bytes,
publication identities and original bundle files are retained. Exact bounded text
units retain parser provenance, zero-based PDF page indices and one-based physical
PDF page locators. Text sources have no invented page numbers. Findings must quote
whole units exactly; inexact or ambiguous citations remain unresolved.

The packet allowlists source text, source/version identities, scope IDs and public
catalogue questions/safeguards. Operator reconstruction annotations, human
identities, dispositions, private filesystem paths and benchmark records are not
copied into model context. Existing source-document privacy checks run before
extraction. Missing sources, unsupported profiles and parser/visual limitations
remain explicit. Packet validation re-extracts the supplied sources and checks
public scope/questions, rather than trusting packet claims. Preparation and exact
quote matching do not verify source semantics, tables, figures or reading order.

An absent qualification can be used only through the Python helper for offline
synthetic packet tests. It does not qualify a packet for the CLI/live runner.
Incomplete preparation directories are preserved and rejected; do not repair or
reuse their artifacts by overwriting them.

The authorization template uses `medical_source_authorization_v2`, extending the
existing source contract with exact packet and execution-policy hashes. Its human
approver, rationale and validity dates are unset. An operator must separately
approve the exact indexed bundle, source versions/classifications, transmission
purpose, provider, backend and model, then store that approval in the study's
private `authorizations/` directory. Login or successful network access is not
transmission permission. Version-1 replay/import records remain unchanged.

## Execute only an explicitly authorized attempt

```bash
PYTHONPATH=src uv run --offline --locked python scripts/medical_review.py run \
  --bundle "$MEDICAL_CODEX_INDEXED_BUNDLE" --backend codex_cli \
  --qualification "$MEDICAL_CODEX_QUALIFICATION" \
  --authorization "$MEDICAL_CODEX_AUTHORIZATION" \
  --provider openai --model gpt-6-astra --allow-llm
```

Application `--offline` overrides every allow flag. Search is refused even with
source permission. Each attempt rechecks qualification, source/packet/plan hashes,
source authorization and resource limits inside a kernel concurrency lock before
launching. The generation worker has a dedicated temporary workspace, explicit
instructions and a separate private authentication home. It uses strict config,
stdin, structured output, JSON events, ephemeral execution, ignored user
configuration/rules and no shared daemon. Authentication must be file-backed
ChatGPT; API-key fallback is refused. Global user configuration is not modified.

The source-byte cap is 64 MiB. The 512 KiB complete-input budget includes packet,
medical instructions, output schema and a qualified 64 KiB CLI-context reserve.
It is not a token-window guarantee. Automatic compaction is disabled by a
threshold above the pinned catalogue's context window; context failures fail the
attempt. Final JSON, event log and stderr caps are 2 MiB, 8 MiB and 1 MiB.
Oversize input is refused before transmission. Stream limits terminate generation
and retain received partial bytes, including the block that crossed the limit.
They never silently truncate a successful result or continue automatically.

Timeout, interruption or output failure terminates the process group. A separate
guardian holds the session lock and stops orphaned generation if the controller
dies; it removes the dedicated temporary credential directory. Partial artifacts
remain in the private attempt. A new explicit attempt is required after failure.
`--resume` reuses only a validated success with identical dependencies; it neither
regenerates nor overwrites history. Replay retains its existing 120-second default.

Usage is recorded when emitted by CLI events. Cost, effective model identity and
provider request count remain unknown when not observed. One CLI session is not
an assertion of one billable request. ChatGPT account limits still apply; there
is no guaranteed monetary spending cap.

## Import, verify, decide and report

The original generation envelope/events remain registered and byte-preserved.
The envelope uses the pinned upstream finding vocabulary with explicit study,
comparison and check associations. Unknown authority fields fail validation.
A deterministic derived payload namespaces model-local finding IDs before the
existing importer runs. Transformation hashes and import-manifest bindings are
registered; no upstream generating revision is asserted.

A separate scoped reading layer references the immutable import. Dossier loading
reconstructs that layer from original generation bytes and scope associations;
historical import proposals are not rewritten. Numerical claims remain proposals,
qualified-result IDs remain empty and human dispositions remain pending. Empty
findings and process success leave check coverage incomplete.

Use the existing `verify`, `verify-inputs`, `decide`, `consolidate` and `render`
commands on the execution run. Human decisions bind the exact scoped reading
layer and require independent source/locator attestations. Markdown and actual
Quarto HTML/PDF reports retain source links, uncertainty and separate requested
versus observed Codex provenance. These outputs cannot become qualified numerical
receipts or official INSPECT-SR judgments through generation/import.

## Acceptance and rollback

Python CI tests the policy, gate denials, bounded processes, actual child-group
cancellation, controller-crash recovery, exact evidence, scope, authority, replay
compatibility and human-disposition provenance. Its synthetic transport substitute
is explicitly not runtime qualification. The report CI lane additionally requires
Codex generation/import Markdown, HTML/PDF and model artifacts with companion
hashes; native-R receipts remain required independently. Real CLI qualification
runs separately on macOS against the final adapter revision, without pytest skips.

A reviewable software PR does not waive failed runtime qualification. Enabling
live use requires an enforceable tool-free/context-isolated CLI configuration and
fresh qualification under an explicitly reviewed runtime policy. Do not edit the
receipt, substitute a model/provider or relax restrictions to make it pass.

Rollback means stop new Codex attempts and retain their private original outputs,
imports, manifests, approvals and human records. Existing offline replay/import,
qualified forensic method receipts and historical reports remain available.
Merging, real-study smoke testing and medical qualification are separate gates.
