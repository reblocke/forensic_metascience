# INSPECT-SR acceptance map

This map connects the supplied R01–R32 acceptance scenarios to executable
coverage and required CI lanes. `Python` is the Python-only lane, `Native R`
is the pinned package and R boundary lane, and `Report/review` is the Quarto
and connected CLI lane. A local pass is evidence for that checkout only; FM-12
closes only after all three hosted lanes pass on the final PR head and merged
`main`.

| ID | Acceptance scenario | Test evidence | Required lane |
|---|---|---|---|
| R01 | Medians/IQR are retained as evidence and excluded from mean-only checks | `tests/test_forensics_categories.py::test_scrutiny_case_eligibility_and_method_inputs`; `tests/test_prediction_review.py` | Python |
| R02 | Unknown summaries remain unresolved; bounded continuous values are not treated as binary | `tests/test_forensics_categories.py::test_scrutiny_eligibility_requires_documented_summary_semantics` | Python + Native R |
| R03 | Binary/proportion checks require explicit Bernoulli semantics | `tests/test_forensics_categories.py::test_scrutiny_eligibility_requires_documented_summary_semantics`; `test_numeric_r_boundary_revalidates_method_eligibility` | Python + Native R |
| R04 | Printed decimal precision survives Python/R I/O | `tests/test_forensics_categories.py::test_printed_numeric_strings_survive_python_readr_python_roundtrip`; `tests/test_inspect_sr_cli.py::test_csv_loader_preserves_identifiers_and_printed_precision` | Python + Native R |
| R05 | 33% and 33.3% retain their reported proportion precision | `tests/test_randomization.py::test_csf_preserves_reported_percent_for_proportion_precision`; `test_simdistr_runtime_converts_reported_percent_to_proportion_precision` | Python + Native R |
| R06 | Unsupported reported percentages remain incompatible/indeterminate under the declared rule | `tests/test_forensics_categories.py::test_numeric_precision_denominator_and_percentage_contract` | Python |
| R07 | Unknown, weighted, or outcome-mismatched denominators do not yield a negative | `tests/test_forensics_categories.py::test_numeric_precision_denominator_and_percentage_contract` | Python |
| R08 | Invalid counts, nonfinite values, P-value comparators, and printed text survive parsing | `tests/test_forensics_categories.py::test_numeric_precision_denominator_and_percentage_contract`; `test_p_value_inequality_and_out_of_range_value_are_preserved`; `tests/test_randomization.py::test_table1_preserves_source_numeric_strings_and_p_comparator`; `tests/test_inspect_sr_cli.py::test_csv_loader_decodes_only_method_receipt_numeric_fields` | Python + Native R |
| R09 | SPRITE remains unimplemented and cannot emit anomalies | `tests/test_forensics_categories.py::test_numeric_runner_receipts_keep_means_only_trial_and_exclude_sprite_stub` | Python + Native R |
| R10 | Missing packages, zero eligibility, malformed output, and exceptions are not clean negatives | `tests/test_forensics_categories.py::test_r_method_receipt_contract_has_truthful_outcomes`; `tests/test_r_integration.py::test_malformed_simdistr_output_raises_instead_of_becoming_no_finding` | Native R |
| R11 | Partial execution reconciles every eligible unit and stays indeterminate | `tests/test_forensics_categories.py::test_r_method_receipt_contract_has_truthful_outcomes`; `tests/test_r_integration.py::test_malformed_simdistr_output_raises_instead_of_becoming_no_finding` | Native R |
| R12 | Means-only inputs retain the correct trial identity and source-linked units | `tests/test_forensics_categories.py::test_numeric_runner_receipts_keep_means_only_trial_and_exclude_sprite_stub`; `tests/test_inspect_sr_cli_workflow.py::test_cli_complete_review_and_private_report` | Native R + Report/review |
| R13 | Empty/all-missing summaries cannot be marked assessed from populated cells alone | `tests/test_forensics_categories.py::test_meta_coverage_requires_evaluation_receipt_not_populated_summary_cells` | Python |
| R14 | Candidate leads remain visible without a score or INSPECT judgment | `tests/test_inspect_sr_reporting.py::test_report_draft_has_no_computed_judgment_or_legacy_category`; connected report workflow | Python + Report/review |
| R15 | Run A outputs cannot leak into run B | `tests/test_pipeline.py::test_run_manifest_is_fresh_hashes_inputs_and_refuses_collision`; `test_randomization_report_renders_only_current_run_inputs` | Python + Report/review |
| R16 | Network access remains opt-in and offline override wins | `tests/test_pipeline.py::test_forensics_pipeline_help_and_dry_run_are_output_free`; `tests/test_registration_forensics.py::test_registration_extractor_requires_explicit_network_opt_in`; network namespace wrapper in each hosted lane | Python + all hosted lanes |
| R17 | Numeric-only runs do not invoke unrelated engines | `tests/test_pipeline.py` run-mode coverage; `tests/test_forensics_categories.py::test_numeric_runner_receipts_keep_means_only_trial_and_exclude_sprite_stub` | Python + Native R |
| R18 | Collisions, interruption, changed source bytes, and terminal manifest mutation fail safely | `tests/test_pipeline.py::test_run_manifest_is_fresh_hashes_inputs_and_refuses_collision`; `test_terminal_run_manifest_rejects_later_mutations`; `test_meta_rejects_inputs_that_appear_after_run_initialization`; `tests/test_inspect_sr_snapshot.py::test_snapshot_binds_current_source_bytes_and_evidence` | Python + Report/review |
| R19 | Omnibus P-values remain distinct from row-level P-values | `tests/test_randomization.py::test_reported_omnibus_record_is_deduplicated_and_never_repeated_as_level_p`; `test_equal_p_values_at_distinct_source_rows_remain_distinct_tests` | Python |
| R20 | Seeded simdistr requires qualified allocation design and is reproducible | `tests/test_randomization.py::test_randomization_r_runner_gates_design_and_executes_seeded_simdistr`; `tests/test_r_integration.py::test_randomization_production_runner_executes_seeded_pinned_simdistr` | Native R |
| R21 | Blinding roles retain role-specific, source-linked claims | `tests/test_registration_forensics.py::test_negated_blinding_claim_does_not_match_positive_claim`; `tests/test_forensics_categories.py::test_registration_claims_and_registry_id_extraction` | Python |
| R22 | Numeric and manual evidence retain exact source locators | `tests/test_forensics_categories.py::test_numeric_evidence_identity_requires_source_hash_locator_and_raw_value`; connected report workflow | Python + Report/review |
| R23 | Malformed or undated history is not synthesized into ordered changes | `tests/test_clinicaltrials_registry.py::test_malformed_history_date_is_parse_failed_without_synthetic_events`; `test_history_orders_dates_chronologically_and_rejects_undated_rows` | Python |
| R24 | Report identities bind trial, guidance, source snapshot, and records | `tests/test_inspect_sr_records.py::test_guidance_hash_tampering_is_detected`; `tests/test_inspect_sr_review.py::test_reviewer_identity_binds_trial_and_guidance`; connected report workflow | Python + Report/review |
| R25 | Source/evidence identities are stable under ordering and require content plus locator | `tests/test_inspect_sr_records.py::test_trial_report_and_evidence_ids_are_stable_under_row_reordering`; `tests/test_inspect_sr_snapshot.py::test_snapshot_binds_current_source_bytes_and_evidence` | Python + Report/review |
| R26 | Captions alone cannot complete image-integrity review | `tests/test_inspect_sr_evidence.py::test_caption_signal_cannot_complete_image_integrity_route`; `tests/test_forensics_categories.py::test_visual_forensics_caption_checks` | Python |
| R27 | Independent reviewer submissions remain immutable; disagreement is adjudicated separately | `tests/test_inspect_sr_review.py::test_reviewer_submissions_are_separate_and_disagreement_does_not_edit_them`; connected report workflow | Python + Report/review |
| R28 | Early stopping requires a reason and serious-concerns judgment; remaining checks are marked unassessed | `tests/test_inspect_sr_review.py::test_pending_checks_block_finalization_but_early_stop_is_explicit`; connected CLI early-stop branch in `tests/test_inspect_sr_cli_workflow.py::test_cli_complete_review_and_private_report` | Python + Report/review |
| R29 | Pending checks block ordinary CLI finalization | `tests/test_inspect_sr_review.py::test_pending_checks_block_finalization_but_early_stop_is_explicit`; connected CLI rejection and justified early stop in `tests/test_inspect_sr_cli_workflow.py::test_cli_complete_review_and_private_report` | Python + Report/review |
| R30 | Multiple report/comparison rows preserve one disposition per trial and cardinality | `tests/test_inspect_sr_reporting.py::test_export_requires_adjudicated_final_review_and_propagates_policy_by_trial`; `test_unresolved_assessments_block_or_are_explicitly_listed` | Python + Report/review |
| R31 | Public exports exclude source excerpts, reviewer identities, and private canaries | `tests/test_inspect_sr_reporting.py::test_public_export_is_explicit_allowlisted_and_excludes_private_canaries`; connected report workflow | Python + Report/review |
| R32 | Zero selected, skipped, failed, or errored tests cannot pass a required lane | `tests/test_ci_acceptance.py`; `scripts/check_pytest_junit.py`; hosted lane artifact/upload gates | Python + all hosted lanes |

## Subsequent review findings

| Finding | Regression / acceptance evidence |
|---|---|
| Invalid hosted environment declarations and missing R dependency closure | `.github/workflows/ci.yml`; `scripts/install_inspect_sr_r_methods.sh`; hosted R/report setup logs and runtime artifacts |
| Rounding-bias execution falsely implies a no-finding | `tests/test_r_integration.py::test_numeric_production_runner_executes_pinned_method_packages` asserts blocked/unknown/indeterminate, zero evaluation, preserved input count, null flags, new method revision, and empty anomaly output |
| Receipt CSV coerces identifiers/text or accepts malformed counts | `tests/test_inspect_sr_cli.py::test_csv_loader_preserves_identifiers_and_printed_precision`; `test_csv_loader_decodes_only_method_receipt_numeric_fields`; `test_csv_loader_rejects_invalid_method_receipt_counts`; connected R-CSV CLI workflow |
| Review/snapshot identities fail to bind current content and references | `tests/test_inspect_sr_review.py::test_reviewer_identity_binds_trial_and_guidance`; `test_finalization_identity_binds_references`; `tests/test_inspect_sr_snapshot.py`; `tests/test_inspect_sr_reporting.py::test_synthesis_leaves_tampered_finalization_unresolved` |
| Finalized reports accept missing records or stale evidence | `tests/test_inspect_sr_reporting.py::test_report_rejects_candidate_without_current_receipt_and_evidence`; `test_export_requires_adjudicated_final_review_and_propagates_policy_by_trial`; connected CLI workflow revalidates changed source bytes |
| Duplicate source filenames select an arbitrary source | `tests/test_forensics_categories.py::test_source_evidence_does_not_choose_last_duplicate_filename` |
| Private report paths escape or overwrite via symlink/collision | `tests/test_inspect_sr_cli.py::test_private_record_path_rejects_absolute_and_traversal_ids`; connected CLI workflow tests output leaf symlinks, collisions, traversal, and outside canaries |
| Mixed evidence/candidate shapes break rendered report tables | `tests/test_inspect_sr_cli_workflow.py::test_cli_complete_review_and_private_report` renders both record shapes and asserts candidate ID and locator appear in HTML |
| Private prediction-review report contains stale data or invalid fixture shape | `tests/test_inspect_sr_reporting.py::test_private_prediction_review_renders_current_synthetic_inputs` uses populated contract-shaped files, renders HTML/PDF, and checks current/stale canaries |
| Historical artifacts or human records could be overwritten | `tests/test_inspect_sr_records.py::test_record_writer_refuses_to_overwrite_human_authored_file`; synthetic artifact preservation uses exclusive creation |

## Required lane evidence and deferred cases

The workflow writes per-lane JUnit, runtime/package inventories, source hashes,
and explicitly allowlisted synthetic outputs to the CI artifact store. The
connected report lane must have zero skips and retain synthetic HTML/PDF; private
working stores are excluded. R33–R34 are not acceptance requirements for this
repair: they remain deferred with FM-13. Hosted receipts and their final verified
commit SHA are added to `docs/HANDOFF.md` before FM-12 can close.
