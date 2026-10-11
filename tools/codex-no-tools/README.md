# Isolated Codex native-tool assessment

These materials support a synthetic assessment of a local source-built Codex
candidate. They do not install a CLI or authorize medical source preparation or
transmission. Candidate adoption requires a separate decision.

The user subsequently adopted the exact passing build for the medical backend.
These source materials and historical assessment receipts do not grant operational
eligibility: use the paired runtime arguments and fresh qualification described in
[the operator workflow](../../docs/MEDICAL_REVIEW_CODEX_BACKEND.md). The global
CLI remains unchanged.

## Authentication recovery assessment

The revised qualification includes an actual 401 response. The previously adopted
build sends three requests on that response despite explicit zero request and
stream retries, so its historical passing receipts cannot clear the revised gate.
The user authorized assessment of an isolated remedy; adoption remains a separate
decision on the exact passing executable hash.

`native-tools-no-auth-recovery.patch` retains the native-tool ceiling and adds a
guard at the shared unauthorized-response handler. Only providers explicitly
setting both retry limits to zero bypass authentication recovery. Defaults and
partially specified limits preserve upstream behavior. It introduces no new
configuration key, dependency or catalogue change. Apply this combined patch
instead of `native-tools.patch` to a separate normalized checkout.

Run the `explicit_zero_retries_disable_authentication_recovery` and
`provider_owned_auth_recovery_is_bounded_and_preserves_unauthorized_failures`
native regressions, then repeat the tool regressions and actual CLI qualification.
On a memory-limited host, add
`--config 'profile.release.package.codex-core.opt-level=0'` to the native unit-test
commands and record that override. This reduces optimization memory for the large
test crate; it does not change source or dependency pins. Build the production CLI
without that test override and qualify its actual resulting bytes.
The build recorder accepts this additional retained patch only with an explicit
`--native-patch` selection; arbitrary patches remain rejected. Source-build
validation establishes assessment provenance, while the adopted-runtime checks
continue to require the original executable and original patch hashes.

Keep build caches, outputs and temporary test workspaces on the external working
volume. For a memory-limited host, record `CARGO_BUILD_JOBS=1`,
`CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1` and `CARGO_PROFILE_RELEASE_LTO=false` in
the retained build log. These build controls change executable bytes and require
fresh assessment; they do not change third-party dependency pins. Preserve failed
or interrupted build attempts as such, without counting them as native test results.

Use `qualify-codex --offline --probe-executable` and `--probe-build-manifest` with
the same immutable Astra catalogue. A successful candidate receipt remains
assessment-only and cannot prepare a packet or permit live execution. Never
replace the installed or adopted executable during this assessment.

## Source baseline

`baseline.json` pins official `rust-v0.161.0`, commit
`979011409de0a60b52f179721948e65531d26144`, Rust 1.95.0 and the original lockfile.
Upstream Codex source is Apache-2.0 licensed. Preserve the original checkout and
source bytes; make a separate build checkout.

The published source manifests set local workspace packages to 0.161.0, while
the published lockfile records them as 0.0.0. Therefore the original
`cargo fetch --locked --target aarch64-apple-darwin` fails before compilation.
The user explicitly authorized the bundled `workspace-versions.patch`, which
changes only local package versions and preserves every third-party lock record.
The original and normalized lockfile hashes are recorded in `baseline.json`.
Do not regenerate or update third-party dependencies to make a build pass.

With a clean, separate build checkout at the pinned commit:

```bash
git apply --check "$MEDICAL_CODEX_PATCH_ROOT/workspace-versions.patch"
git apply "$MEDICAL_CODEX_PATCH_ROOT/workspace-versions.patch"
```

Use an isolated Rust toolchain and dependency cache, with the prescribed compiler
and a dedicated build-output directory. Pass their paths through `RUSTUP_HOME`,
`CARGO_HOME` and `CARGO_TARGET_DIR`; leave global installation and shell profiles
unchanged. From the source's `codex-rs` directory:

```bash
"$MEDICAL_CODEX_CARGO" fetch --locked --target aarch64-apple-darwin
"$MEDICAL_CODEX_CARGO" build --offline --locked --release -p codex-cli --bin codex
```

Retain the original failed fetch, normalization checks, build logs and actual
executable hashes. Label this control build as a **normalized source baseline**,
not an unchanged official distribution. Normalizing local package metadata does
not establish that the source builds or that its runtime passes qualification.

## Intended native-tool restriction

The proposed candidate control is `tools.enabled=false`, resolved before tool
registration into the existing startup `ToolPolicy` with an empty allowlist.
Its default must preserve ordinary behavior. Generated Code Mode handlers,
extensions and hosted tools must obey the same ceiling; unsolicited tool calls
must fail without executing a handler or issuing a continuation request.

Preserve the original Astra catalogue and compare the normalized baseline,
patched default behavior and patched tools-disabled behavior. Actual outgoing
requests, dispatch probes and every existing isolation/limit/recovery check are
required. A declaration filter or an instruction not to call tools is insufficient.

The normalized baseline has built and its preserved synthetic request reproduces
native tool exposure. The patched candidate built with Rust 1.95.0, passed the
native regressions and all 20 mandatory actual CLI assessment checks, and passed
raw-evidence reauditing. Baseline and patched omitted-setting controls expose
identical declarations. The candidate executable SHA-256 is
`8229baba8ad7387cbf2636b0116c8abd6d94cf87f503b327c78abc47b44c619a`.
Source checkouts, toolchains, binaries, logs and raw evidence stay in ignored private
locations. The passing receipt is assessment-only: no operational runtime adoption,
installation or source-transmission authorization follows from this result.


## Build the candidate and retain provenance

Preserve the baseline executable and logs separately before modifying the build
checkout. Apply `native-tools.patch` after the version-only normalization. It adds
an experimental `tools.enabled` configuration field and preserves omitted/true
behavior. False publishes the startup ceiling before extensions initialize,
prevents Code Mode worker startup, rejects calls before argument parsing and
checks the ceiling again before dispatch. The session owns that immutable policy
for subsequent tool refreshes; a new/resumed session must reapply the setting.
No model-catalogue capability is changed.

From the isolated source's `codex-rs` directory, with the same environment as the
baseline, run:

```bash
"$MEDICAL_CODEX_CARGO" test --offline --locked --release -p codex-config model_tools -- --nocapture
"$MEDICAL_CODEX_CARGO" test --offline --locked --release -p codex-core --lib model_tools -- --nocapture
"$MEDICAL_CODEX_CARGO" test --offline --locked --release -p codex-core --lib allowed_tools_filter_sources_before_code_mode_and_discovery -- --nocapture
"$MEDICAL_CODEX_CARGO" run --offline --locked --release -p codex-config-schema --bin codex-write-config-schema
"$MEDICAL_CODEX_CARGO" build --offline --locked --release -p codex-cli --bin codex
```

Preserve the candidate separately. From this repository root, record the actual
completed build with explicit paths to the isolated compiler and Cargo binaries:

```bash
PYTHONPATH=src uv run --offline --locked python tools/codex-no-tools/record_build.py \
  --source "$MEDICAL_CODEX_BUILD_SOURCE" --original "$MEDICAL_CODEX_ORIGINAL_SOURCE" \
  --executable "$MEDICAL_CODEX_CANDIDATE" --build-log "$MEDICAL_CODEX_BUILD_LOG" \
  --output "$MEDICAL_CODEX_PROVENANCE" \
  --rustc "$MEDICAL_CODEX_RUSTC" --cargo "$MEDICAL_CODEX_CARGO_BINARY"
```

The output must be a fresh directory inside the ignored runtime-candidate boundary.
The recorder verifies clean original source, pinned commits, absence of untracked
source inputs and exact equality between the build checkout's native diff and the
reviewed patch. It retains original/normalized locks, both patches, toolchain,
source ledger and build log; manifest validation binds them to the executable.
Compiler/build provenance is local evidence, not a signed publisher attestation.

Compare the preserved baseline, patched omitted/default behavior and patched
explicitly disabled behavior against identical catalogue bytes. Candidate
qualification uses `--probe-build-manifest` together with `--probe-executable`;
all existing checks plus fatal unsolicited-call rejection remain mandatory.
A passing v3 receipt is still assessment-only, cannot prepare a source packet and
cannot authorize live execution. The official installed CLI is never replaced.

## Local upstream reproducer materials

The patch includes configuration, empty-registry/worker and pre-handler rejection
regressions. The configuration regression was exercised against the normalized
baseline first: false was discarded and serialized as null; it passes with the
candidate field. Preserved raw baseline and candidate requests/streams stay private.
To reproduce the original blocker, run the synthetic qualifier against the official
or normalized baseline with the immutable Astra catalogue and no build-manifest
argument. The outgoing request exposes `functions` despite the adapter's explicit
feature controls. To assess the remedy, use the exact candidate manifest. The
loopback provider issues unsolicited function/custom, namespaced/nested, malformed
search and hosted tool calls; every one must cause a fatal error without another
request. Source text mentioning tools remains source data.

These are prepared submission materials only. No upstream issue, message or pull
request is sent by this workflow. Redact private filesystem paths and retain
unmodified evidence locally if a later authorized submission is prepared.
