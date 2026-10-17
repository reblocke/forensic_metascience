# Source tables and conditional summary reconciliation

These opt-in inputs extend existing study layouts. They do not create verified
human responses, qualified INSPECT-SR candidates, or medical-performance claims.
All case inputs, findings and execution logs belong in ignored private storage.

## Table input

Set TABLE_INPUT_REL_PATH in a study configuration, or pass --table-input to
extract_randomization_table1.py, extract_numeric.py and
extract_numeric_summary_tables.py. The JSON schema_version is
source_table_input_v1 and includes:

- trial_id, baseline_table_id;
- sources: source_id, repository-relative path, sha256 and format (html or docx);
- tables: unique table_id, source_id, locator and raw_rows, re-extracted and
  compared against the hashed source before use;
- for mapped tables: header_rows, column_map (label, arm_a, arm_b, optional
  total and p_value), and row_kinds keyed by zero-based expanded row index.

Column indexes are zero-based. Evidence locators are one-based. HTML locators
use aria-labelledby, id, or a stable positional fallback. DOCX locators use
docx:table=N. HTML row/column spans and DOCX merged cells are expanded; hidden
aria-hidden tables are excluded. Repeated visible identities are rejected.
Different tables remain distinct even when their printed numbers coincide.

Supported row kinds are section, count_percent, mean_sd (printed plus/minus),
median_iqr, median_range and unknown. Raw cells, missing cells, labels and
precision are retained. Optional units and analysis_denominators are keyed by
row; the latter maps arm_a/arm_b to available-case denominators. A printed cell
denominator must agree with an explicit supplied denominator. Unknown measurement
scale, weighting, adjustment and transformation remain unknown. No integer-scale
qualification is inferred from an integer-looking mean or the variable name.
Total is retained in the sidecar for reconciliation and cannot be an analyzed arm.
Source-table locators do not acquire fabricated publisher page numbers.

The legacy standard parser now rejects Total/Overall in an assumed arm position.
Otherwise existing supported layouts retain their route. The planned allocation
ratio is extracted from concordant report/protocol claims; absent or conflicting
claims remain unknown. allocation_ratio is a compatibility alias for
planned_allocation_ratio, not a ratio computed from observed counts.
observed_randomized_n_a/b and row-specific analysis denominators are separate.
This metadata change does not enable unrestricted randomization simulation or
fixed-block inference.

## Reconciliation input

Set SUMMARY_RECONCILIATION_REL_PATH to add the stage to the numeric category.
The CLI is:

    PYTHONPATH=src uv run --offline --locked python scripts/run_summary_reconciliation.py --input INPUT.json --out data/processed/PRIVATE_RUN/reconciliation

The destination must be new and repository-contained. schema_version is
summary_reconciliation_v1. sources contain source_id, path, sha256 and format
(html, docx or text). Each request requires a unique request_id, check,
assumption_status (declared, conditional or unknown), evidence, population,
timepoint, orientation, predictor_coding, adjustment, weighting, estimator,
se_method, ci_method and test_method. Use unknown explicitly when unsupported.
Evidence binds source_version_id, exact locator and raw_value, evidence_id and
input_verification=proposed_transcription. Use bind_evidence to construct identities.
Validation compares quotations to original source cells or one-based text lines.
This is structural validation, not independent verification of the proposed
statistical interpretation or the mapping from quotations to numeric arguments.

Checks and calculation-specific inputs:

| Check | Inputs and restrictions |
|---|---|
| or_margins | N, event margin D, exposed margin m, reported.or; crude unweighted binary cross-product or ordinary logistic MLE |
| wald_bound | N, m, optional D, reported OR/lower/upper; conventional crude 2x2 Wald variance |
| wald_consistency | reported OR/lower/upper/P; explicitly conditional or declared Wald CI/test |
| binary_contrast | two events and denominators; unweighted RR, log-Wald CI, RD with unpooled Wald CI and Pearson P without continuity correction |
| exact_contingency | ordered 2x3 cells, three categories, two denominators, optional reported.p; exact Fisher without simulation |
| sum | finite values, reported.total |
| percentage | count, denominator, reported.percent |

All reported values are decimal strings preserving precision and optional
comparators. Nearest-rounding intervals conservatively retain ties; strict
inequalities remain strict. Binary optional comparisons are rr, rr_lower,
rr_upper, rd_percent, rd_lower_percent, rd_upper_percent and p. Different
CI/test methods are not disproved by a conditional Wald incompatibility.
The CI/P check uses a conservative rounding envelope; compatibility does not
prove a unique joint reconstruction. OR enumeration preserves zero, finite,
infinite and undefined states. JSON null is accompanied by a state; native RDS
retains native nonfinite values and htest objects. Collapsed 2x2 comparisons are
separate from the full 2x3 test, and conditional and cross-product ORs differ.

Outputs include native_results.rds, reconciliation_results.json/.csv,
requests.json, r_session.txt, stdout/stderr and run_provenance.json. Source,
request and implementation hashes are recorded; source/request drift fails the
run. These are candidate-only calculations and never method-receipt promotion.
Unknown assumptions produce zero evaluated units, not reassurance. No new package
dependency is introduced: calculations use stats and the existing jsonlite.

## Verification

Focused tests: tests/test_source_tables.py, tests/test_summary_reconciliation.py
and existing randomization/numeric tests. The native marker requires Rscript and
the configured existing R library. The pipeline dry-run remains output-free.
Run all required Python, native-R and report lanes before release.

Native report metadata substitutes control characters for display only; original
extracted CSV bytes remain available for source review.
