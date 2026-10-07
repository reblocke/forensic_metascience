# Next milestone: qualify one live medical-reading backend

## Goal and boundary

Deliver one opt-in backend that produces genuine, source-linked reading proposals
through the existing private run/import/report workflow. Preserve offline replay,
source identities, qualified numerical receipts and human adjudication. Successful
generation does not establish completed medical coverage or medical qualification.

The user accepted the offline intake/planning checkpoint and requested continued
work. This plan is the next implementation proposal. Backend selection is pending;
the two concrete choices are local Codex CLI or a tool-free OpenAI Responses API
adapter. Implement only the selected choice. Do not silently substitute a backend,
model, authentication method or execution environment.

## Current evidence

- PR #13 merged the offline foundation. Documentation PR #14 is ready for review
  at `7eae29cfcab86c168b87d5561cbac871a96e7b22`. Its
  [PR CI run](https://github.com/reblocke/forensic_metascience/actions/runs/37586746980)
  passed 446 Python, 24 native-R and 8 report tests with zero skips/errors/failures.
  Downloaded receipts passed the repository acceptance checker, required regression
  checks, pinned source checks and 21 companion artifact hashes.
- The installed CLI is `codex-cli 0.157.0`. Its help exposes strict config,
  ignored user config/rules, ephemeral execution and structured JSON output.
  Local availability is not account, model, transmission or isolation approval.
- A synthetic command-only probe allowed a staged text read and denied an outside
  read, a symlink escape, source modification and workspace modification. A local
  TCP listener received no sandboxed connection. No model or study input was used.
  The first attempt failed config parsing; the corrected attempt and original
  failure are retained separately. This is not complete live-backend qualification.
- [Official permissions documentation](https://learn.chatgpt.com/docs/permissions)
  describes named filesystem profiles, minimal runtime access and platform
  enforcement. [The config reference](https://learn.chatgpt.com/docs/config-file/config-reference)
  documents separate search settings and command-network controls. Treat capability
  availability as version-specific; verify the installed runtime's behavior.

Private receipts are in ignored
`reports/diagnostics/medical_review_walkthrough_hosted/` and
`reports/diagnostics/medical_review_backend_preflight/`. The synthetic probe uses
temporary files and does not change production configuration.

## Sequential implementation

1. **Freeze the chosen execution contract.** Specify provider/backend, exact model,
   authentication method and supported runtime/version. Define an explicit
   capability receipt bound to the executable/code/config hashes and OS. A missing,
   changed or failed qualification must keep live execution blocked. Record the
   selected contract and compatibility behavior in `docs/DECISIONS.md`.
2. **Build the minimum source packet, test first.** Stage only explicitly permitted
   sources and deterministic parsed representations, public instructions and a
   canonical source/page index. Hash raw inputs, parsed content and complete prompt.
   Preserve missing documents, extraction/fidelity limits and stable publication
   identities. Reject traversal, symlink escapes, protected private/control records,
   oversized inputs and mid-copy drift. Keep approver identities, dispositions,
   evaluation answers, original private paths and credentials outside the packet.
   Reuse existing privacy/source validation where its contract applies. Do not
   truncate a bundle silently to fit a model.
3. **Implement the selected adapter, test first.** Keep one bounded generation
   attempt initially, with search and model command execution disabled. For Codex,
   use an explicit private config, a restricted permission profile, no inherited
   hooks/skills/plugins/MCP/browser capabilities, no shared session history and no
   approval/sandbox bypass. Supply only the reviewed packet; do not grant arbitrary
   shell access to read it. For Responses, expose no tools and keep transport and
   credentials in the trusted controller. Verify provider transport separately from
   model tool egress in either case. Refuse the selected version if any required
   restriction cannot be enforced. An API implementation must follow fetched
   official endpoint/schema documentation before coding; no new SDK is presumed.
4. **Integrate authorization, limits and recovery.** Reuse exact bundle/source/model
   authorization and application-level offline precedence. Enforce one concurrent
   session, one attempt, zero retries, source/prompt/output byte limits and a finite
   deadline. Terminate the complete worker process group and retain partial logs
   on cancellation/timeout. Bound internal retries too; never infer a single model
   request from a single CLI session. Require an explicit spend policy; record
   usage/cost as unknown when unavailable. Refuse a requested hard monetary cap
   unless it can actually be enforced. Keep credentials out of logs and manifests.
5. **Preserve and import actual output.** Retain raw event/final-output bytes before
   validation. Derive effective model, tool availability, usage and completion from
   supported runtime evidence; do not echo requested settings as observed facts.
   Validate schema/source references before invoking the existing importer. Bind
   attempt reuse to sources, packet, prompt, plan/profiles, model, permissions,
   adapter and qualification. Failed or interrupted attempts remain immutable.
   Reject forged human dispositions, official judgments and qualified results.
6. **Verify and deliver a focused PR.** Run synthetic denial, timeout, output and
   recovery tests plus the existing offline suite. Verify fresh Python/native-R/
   report receipts and hashes on the final head. Review the small diff and update
   `docs/HANDOFF.md`. Do not use provider credentials or real sources in CI.
7. **Run one separately authorized operational smoke test.** After backend
   qualification and the concrete source authorization, use the development bundle
   once, preserving actual runtime/output receipts. Import the output and render
   the standard report. Obtain real human source verification, counterevidence and
   dispositions before representing the walkthrough as a completed review.

Initial generation is a backend/walkthrough test. It is not the full specialist
orchestration, the strong evaluation comparator, or the pinned original Reviewer
workflow. Subsequent multi-session orchestration needs a separately bounded plan;
comparator fidelity and medical qualification retain their existing gates.

## Proposed file map

| File | Focus |
| --- | --- |
| `src/research_project/medical_review/runner.py` | Selected backend gate, authorization, immutable attempt records, effective execution status and recovery bindings; retain replay defaults. |
| `src/research_project/medical_review/source_packet.py` (new) | Small, deterministic allowlisted source/prompt packet builder with provenance and privacy checks. |
| `src/research_project/medical_review/codex_backend.py` **or** `responses_backend.py` (new) | Only the selected adapter: qualification, explicit configuration/transport, bounded execution, raw output and observed runtime metadata. |
| `tests/medical_review/test_source_packet.py` (new) | Source/privacy/size/hash regressions with synthetic files. |
| `tests/medical_review/test_live_backend.py` (new) | Selected adapter tests against fake transport/processes; no provider calls. |
| `tests/medical_review/test_execution.py` | Authorization/offline precedence, limits, actual process-group timeout and recovery regressions. |
| `tests/medical_review/test_reporting.py` | Pending/partial coverage and genuine import lineage remain visible in the standard report. |
| `docs/MEDICAL_REVIEW.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md` | Operator contract, chosen boundary, verification and remaining gates. |

Inspect `records.py`, `preflight.py`, `evaluation_packets.py` and `importer.py`
before editing. Change a shared helper only when required by the selected adapter;
do not broaden the old private runner, evaluation contracts or numerical engines.
No dependency or CLI change is proposed. If the selected runtime requires one,
present the concrete manifest/interface change before implementation. New runtime
evidence belongs in a versioned sidecar; never rewrite historical records.

## Acceptance checks

Tests must exercise behavior, not merely requested flags or subprocess mocks:

- Invalid/expired authorization, changed source/model and `--offline` precedence
  cause zero provider/process starts. Installation/authentication cannot authorize.
- Actual synthetic sentinels outside the permitted packet cannot be read; sources
  cannot be changed; symlink/traversal escapes fail; private records stay excluded.
  Configuration/startup failure cannot count as successful isolation: an allowed
  read must succeed as the positive control.
- Effective search, shell, connectors and other tools are absent/denied, with
  provider transport distinguished from command egress. An unsupported restriction
  refuses the mode rather than falling back to a broader setting.
- Oversized prompts/output, internal retries, duplicate concurrent sessions,
  timeout/cancellation and child processes respect enforced limits. Partial output
  stays preserved and cannot become a completed stage.
- Schema/source failures, empty findings and unresolved checks retain incomplete
  coverage. Model numbers remain proposals; official/human fields cannot be forged.
- Recovery with matching dependencies preserves prior success; changed packet,
  model, code or permissions requires a new attempt without overwriting history.
- Genuine imported findings render with correct study/comparison scope, source
  links, caveats and unknown states in Markdown and actual Quarto HTML/PDF.

Planned commands after the selected adapter exists:

```bash
PYTHONPATH=src uv run --offline --locked pytest -q tests/medical_review/test_source_packet.py tests/medical_review/test_live_backend.py tests/medical_review/test_execution.py tests/medical_review/test_reporting.py -m 'not native_r and not report_integration'
uv run --offline --locked ruff check .
uv run --offline --locked ruff format . --check
git diff --check
```

The final PR also needs the existing three hosted lanes with downloaded,
hash-verified receipts. A CLI qualification on this Mac does not qualify a Linux
worker or a different executable version.

## Decisions and stop points

**Before core implementation:** select one backend and approve its concrete
execution contract. The existing runner intentionally refuses all live backends;
changing that boundary requires the repository's plan/approval step. Backend
selection does not authorize transmitting a document.

**Before any real run:** exact model/runtime/account, permitted source and derived
packet hashes, transmission purpose, private approver and validity, search choice
(initial proposal: disabled), explicit duration/session/retry/byte/spend limits.
Prepare these records for human approval; never manufacture the approver decision.

**Before medical evaluation:** approved development/untouched held-out families,
qualified assessors/adjudicator and time, faithful comparator execution, equal-source
versus full-bundle tracks, and frozen human-approved criteria before unblinding.
Engineering acceptance cannot close these scientific decisions.
