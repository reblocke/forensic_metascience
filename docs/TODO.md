# Deferred work and decisions

This ledger separates work outside the passed FM-12 gate from current defects.
None of these items authorizes source-paper analysis, new scientific assumptions,
new dependencies, automatic adjudication, or a rewrite of historical records.
The [INSPECT-SR acceptance map](INSPECT_SR_ACCEPTANCE.md) records the qualified
current methods; [HANDOFF](HANDOFF.md) records the release receipts.

| Item | Evidence and present state | Decision needed before work | Acceptance condition |
|---|---|---|---|
| FM-13 / R33–R34: RIPE-KG reference import | Optional supplied ticket; no importer or local normalization contract is implemented. | Select and license-check an immutable upstream snapshot; approve intended agreement analysis. | Offline checksum-verified import preserves reviewer/agent roles, disagreement, unknown fields, and unresolved publication links; reports observed check coverage without treating labels as truth. |
| Rounding-bias qualification | `rounding_bias_blocked_v1` preserves inputs but evaluates zero units because printed values lack independent higher-precision observations. | Approve a scientifically valid input and package-argument contract, including eligible source measurements. | Independent valid/adversarial numerical expectations, source-linked receipts, and native/report acceptance pass before enabling candidates. |
| Optional sequence diagnostics | Direct R entrypoint and receipts currently block these methods. | Approve design, ordered-input, and inferential applicability rules. | Independent synthetic qualification plus fail-closed missing/partial/error cases and a new method revision. |
| SPRITE | Stub/descriptive arm differences do not emit anomalies. | Approve method assumptions, input requirements, and any new R dependency. | Implemented method has independent numerical tests and native provenance; stubs remain non-anomalous until then. |
| Transitive R dependency reproducibility | Pinned method-package source archives are verified, but transitive R packages are inventoried rather than independently locked. | Decide whether a separate transitive lock is worth its maintenance and platform cost. | A documented, reproducible isolated install verifies the full closure across supported CI runtimes without production-time installation. |
| Human-reviewed real-study pilot | Synthetic FM-12 acceptance does not adjudicate a source paper; reviewer identities, ambiguous trial/report mappings, and review-specific synthesis policy remain human inputs. | Authorize the source material and rights, name reviewers, resolve mappings, and approve a versioned policy for that review. | Private, source-linked independent submissions and adjudication pass current snapshot/export validation; no automatic exclusion or public allegations. |
| Python package metadata | `pyproject.toml` still names the template-era project `codex_research_template`; changing it affects the lock and installation identity. | Choose a package name and migration/release policy; a whole-package rename was outside the INSPECT-SR ticket. | Lock, imports, entrypoints, install guidance, and hosted lanes agree after an explicitly versioned migration. |

Recheck upstream versions, licenses, and source hashes when an item is selected;
the references above describe the current local contracts, not future approval.
