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
| MED-01 | Existing private/public commands with the feature unused | Same offline defaults, current output contracts, and no backend requirement | baseline | Existing regression lanes; compatibility evidence pending |
| MED-02 | Help and dry-run/plan-only | No model calls, searches, output files, or installs; planning with absent sources is explicitly incomplete | WP1/WP2 | WP1 real CLI help/absent-source plan tested; full plan pending |
| MED-03 | Valid upstream result imported twice | Exact raw bytes retained; stable identity; no duplicate proposal or false evidence multiplication | WP1 | Lossless byte retention and identical real CLI replay tested |
| MED-04 | Unknown upstream schema or duplicate ID with changed payload | Explicit rejection/conflict; no silent field loss or overwrite | WP1 | Pinned schema and changed duplicate payload rejection tested |
| MED-05 | Wrong source hash, fuzzy-only quote, wrong page, ambiguous study map | Evidence unresolved or rejected; no exact-source claim | WP1/WP2 | Wrong quote/page/path, hashes and unreviewed mapping tested; full extraction pending |
| MED-06 | Source/SAP/registry corrected after review | New version and invalidated dependent reuse; old review remains historical | WP2/WP3 | Pending chronology and dependent-reuse tests |
| MED-07 | Supplement missing or table unreadable | Relevant check is unverifiable; report states the missing evidence | WP2/WP4 | Pending full missing-source and report tests |
| MED-08 | Upstream `ok` with empty findings and no coverage records | Import succeeds; substantive coverage remains unavailable | WP1 | Empty ok import retains unavailable coverage tested |
| MED-09 | Mixed trial and prediction aims; unsupported meta-analysis component | Relevant union selected; unsupported scope explicit; no full-coverage claim | WP2 | Pending mixed-profile and unsupported-scope tests |
| MED-10 | MRN-parity assignment described as randomization | Design discrepancy proposed with evidence; no assertion of concealed random allocation | WP2/pilot | Pending orchestration fixture; live capability requires pilot |
| MED-11 | Post-baseline exposure creates guaranteed survival time | Specific time-zero concern; properly aligned repaired control does not trigger it | WP2/pilot | Pending paired semantic fixture; live capability requires pilot |
| MED-12 | Apparent endpoint switch explained by a dated amendment | Both versions and chronology retained; no unsupported allegation of selective reporting | WP2/WP4/pilot | Pending chronology/counterevidence fixture |
| MED-13 | Crude/adjusted effects, differing denominators, or different time horizons | No false arithmetic contradiction across incompatible estimands | WP4 | Pending incompatible-estimand negative controls |
| MED-14 | Verified 2×2 discrepancy versus case-control PPV and zero-cell controls | Correct bounded calculation; invalid prevalence use and undefined quantities not silently repaired | WP4 | Pending verified diagnostic arithmetic and controls |
| MED-15 | Partial method failure, zero evaluated units, blocked rounding-bias | Never a no-finding result; no new INSPECT-SR candidate route | WP4/native R | Existing blocked-method regressions; connected medical handoff pending |
| MED-16 | Subgroup CIs differ in null crossing, without interaction evidence | No unsupported subgroup-effect conclusion | WP2/pilot | Pending subgroup safeguard fixture |
| MED-17 | Precise nonsignificant result, exploratory development model, known missing harms ascertainment | No boilerplate underpowered claim, no compulsory deployment-trial criticism, and no unsupported safety reassurance | WP2/pilot | Pending interpretation and harms safeguards |
| MED-18 | LLM supplies `human_verified`, fake receipt, or official assessment fields | Rejected or quarantined; existing human and method records unchanged | WP1/WP4 | Official-field rejection tested; human/receipt integration pending |
| MED-19 | Two agents make the same observation; two distinct issues share a quote | True duplicate grouped with all provenance; distinct issues retained; no independence claim | WP4 | Pending conservative grouping/provenance tests |
| MED-20 | Major concern with a critical caveat enters editor synthesis | Finding and caveat remain accounted for in Markdown/HTML/PDF | WP4/report integration | Pending caveat survival in Markdown/HTML/PDF |
| MED-21 | Malicious document/import requests secrets, extra files, commands, or search | Instructions treated as data; no unauthorized read, execution, or transmission | WP3 | Importer traversal/unknown fields tested; runner sentinel isolation pending |
| MED-22 | Allow flags conflict with application offline mode; model CLI cannot enforce restrictions | Offline wins; unsupported live mode fails closed | WP3/operational | Pending application-offline and restriction enforcement |
| MED-23 | Timeout, quota failure, resume after changed prompt/model/source | Partial status retained; no paid fallback; mismatched reuse refused | WP3 | WP1 input/code-change and tampered-artifact/origin refusal tested; live attempt recovery pending |
| MED-24 | Unsafe output override, symlink escape, public export attempt | Rejected; private logs, excerpts and identities remain inside protected roots | WP1/WP3 | Unsafe output, symlink/manifest escape and tracked-private input rejection tested; live/report boundaries pending |
| MED-25 | Human confirms/dismisses then revises a proposal | Write-once history, supersession link, evidence and original model provenance retained | WP4 | Pending write-once human supersession/history |
| MED-26 | New medical report exists without finalized INSPECT-SR review | No official judgment or synthesis disposition appears or becomes exportable | WP4/report integration | WP1 official assessment remains null; final reports/adoption pending |
| MED-27 | Real R/Quarto dependencies absent in required acceptance lane | Blocked/failed acceptance, never a passing mock substitute | baseline/native/report | Local native R (13) and report (5) lanes passed after environment preparation; hosted receipts pending |

WP1 reproductions:

```bash
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' tests/medical_review/test_importer.py
UV_OFFLINE=1 PYTHONPATH=src uv run --offline --locked pytest -q -o addopts='' -m 'not native_r and not report_integration'
UV_OFFLINE=1 uv run --offline --locked ruff check .
UV_OFFLINE=1 uv run --offline --locked ruff format . --check
```

`test_importer.py` exercises real storage and the thin CLI using only synthetic
local sources. Registered artifacts bind exact original bytes. Baseline native
and Quarto lanes use the existing required integration markers and pinned R
methods; new medical HTML/PDF coverage arrives with WP4. Hosted receipts for
the delivered revision remain a separate check from local passes.
