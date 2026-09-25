#!/usr/bin/env bash
set -euo pipefail

RUN_RANDOMIZATION_AUDIT=false
FORENSICS_RAW=""
DIGITIZE_PLOTS=false
STUDY_ID="lungtime"
DRY_RUN=false
OFFLINE_REQUESTED=false
ALLOW_NETWORK=false
RENDER_REPORTS=false
OUTPUT_ROOT=""
RUN_ID=""

usage() {
  cat <<'USAGE'
Usage: bash scripts/run_pipeline.sh --forensics <categories> [options]

Options:
  --study-id ID             Configured study ID.
  --output-root PATH        Repository-contained parent for a fresh run directory.
  --run-id ID               Explicit run ID; an existing destination is refused.
  --dry-run                 Print selected stages and required sources without writing.
  --offline                 Disable network regardless of study config or other flags.
  --allow-network           Explicitly allow configured registry fetches.
  --render-reports          Render reports after calculation stages complete.
  --digitize-plots true|false  Run the explicitly requested interactive digitizer.
  --randomization-audit     Alias for --forensics randomization.
  --help                    Show this help without loading study inputs.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --offline)
      OFFLINE_REQUESTED=true
      shift
      ;;
    --allow-network)
      ALLOW_NETWORK=true
      shift
      ;;
    --render-reports)
      RENDER_REPORTS=true
      shift
      ;;
    --output-root)
      if [[ $# -lt 2 ]]; then echo "Missing value for --output-root"; exit 1; fi
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --run-id)
      if [[ $# -lt 2 ]]; then echo "Missing value for --run-id"; exit 1; fi
      RUN_ID="$2"
      shift 2
      ;;
    --randomization-audit)
      RUN_RANDOMIZATION_AUDIT=true
      shift
      ;;
    --forensics)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --forensics"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,transparency,meta] [--digitize-plots true|false]"
        exit 1
      fi
      FORENSICS_RAW="$2"
      shift 2
      ;;
    --study-id)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --study-id"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,transparency,meta] [--digitize-plots true|false]"
        exit 1
      fi
      STUDY_ID="$2"
      shift 2
      ;;
    --digitize-plots)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --digitize-plots"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,transparency,meta] [--digitize-plots true|false]"
        exit 1
      fi
      DIGITIZE_PLOTS="$(echo "$2" | tr '[:upper:]' '[:lower:]')"
      if [[ "$DIGITIZE_PLOTS" != "true" && "$DIGITIZE_PLOTS" != "false" ]]; then
        echo "Invalid value for --digitize-plots: $2"
        echo "Use true or false"
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [ "$RUN_RANDOMIZATION_AUDIT" = true ] && [ -z "$FORENSICS_RAW" ]; then
  FORENSICS_RAW="randomization"
fi

FORENSICS_RAW="${FORENSICS_RAW// /}"
if [ "$FORENSICS_RAW" = "all" ]; then
  FORENSICS_RAW="randomization,numeric,registration,visual,transparency,meta"
fi

if [ -n "$FORENSICS_RAW" ]; then
  IFS=',' read -r -a REQUESTED_CATEGORIES <<< "$FORENSICS_RAW"
  for category in "${REQUESTED_CATEGORIES[@]}"; do
    case "$category" in
      randomization|numeric|registration|visual|transparency|meta)
        ;;
      *)
        echo "Unknown forensics category: $category"
        echo "Valid categories: randomization,numeric,registration,visual,transparency,meta"
        exit 1
        ;;
    esac
  done
fi

FORENSICS_CSV=",$FORENSICS_RAW,"
has_category() {
  local category="$1"
  [[ "$FORENSICS_CSV" == *",$category,"* ]]
}

join_unique_basenames() {
  local joined=""
  local seen="|"
  local path=""
  local base=""
  for path in "$@"; do
    base="$(basename "$path")"
    if [[ "$seen" != *"|$base|"* ]]; then
      if [[ -n "$joined" ]]; then
        joined+="|"
      fi
      joined+="$base"
      seen+="$base|"
    fi
  done
  printf "%s" "$joined"
}

render_study_report() {
  local notebook_path="$1"
  local category="$2"
  local report_dir="$3"
  local output_name="$4"

  FORENSICS_STUDY_ID="$STUDY_ID" FORENSICS_STUDY_TITLE="$STUDY_TITLE" \
    FORENSICS_REPORTS_ROOT="$REPORTS_ROOT" FORENSICS_PROCESSED_ROOT="$PROCESSED_ROOT" \
    quarto render "$notebook_path" \
    --to pdf \
    --output "$output_name" \
    --output-dir "$report_dir"
  if [[ ! -f "$report_dir/$output_name" ]]; then
    echo "Expected rendered report was not created under the run directory: $report_dir/$output_name" >&2
    return 1
  fi
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! "$STUDY_ID" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]]; then
  echo "Invalid study ID: $STUDY_ID" >&2
  exit 1
fi

CONFIG_PATH="$REPO_ROOT/config/studies/${STUDY_ID}.sh"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Unknown study-id: $STUDY_ID"
  echo "Expected config at: $CONFIG_PATH"
  exit 1
fi
source "$CONFIG_PATH"

REGISTRY_ID="${REGISTRY_ID:-}"
REGISTRY_URL="${REGISTRY_URL:-}"
REGISTRY_CURRENT_REL_PATH="${REGISTRY_CURRENT_REL_PATH:-}"
REGISTRY_HISTORY_REL_PATH="${REGISTRY_HISTORY_REL_PATH:-}"
REGISTRY_ALLOW_NETWORK="false"
REGISTRY_AS_OF_DATE="${REGISTRY_AS_OF_DATE:-}"
PUBLICATION_URL="${PUBLICATION_URL:-}"
PUBLICATION_DOI="${PUBLICATION_DOI:-}"
PUBLICATION_PMID="${PUBLICATION_PMID:-}"

REPORT_PDF="$REPO_ROOT/$REPORT_REL_PATH"
PROTOCOL_PDF="$REPO_ROOT/$PROTOCOL_REL_PATH"
SUPPLEMENT_PDF="$REPO_ROOT/$SUPPLEMENT_REL_PATH"
BASELINE_PDF="$REPO_ROOT/$BASELINE_REL_PATH"
if [ "$ALLOW_NETWORK" = true ] && [ "$OFFLINE_REQUESTED" = false ]; then
  REGISTRY_ALLOW_NETWORK="true"
  export UV_OFFLINE=0
fi
if [ "$OFFLINE_REQUESTED" = true ]; then
  REGISTRY_ALLOW_NETWORK="false"
  export UV_OFFLINE=1
elif [ "$ALLOW_NETWORK" = false ]; then
  export UV_OFFLINE=1
fi

OUTPUT_ROOT="${OUTPUT_ROOT:-$REPO_ROOT/data/processed/forensics_runs}"
OUTPUT_ROOT="$(PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py validate-output \
  --repo-root "$REPO_ROOT" --output-root "$OUTPUT_ROOT")"
REQUIRED_SOURCES=()
if has_category randomization; then
  REQUIRED_SOURCES+=("$REPORT_PDF" "$PROTOCOL_PDF" "$BASELINE_PDF")
fi
if has_category numeric; then
  REQUIRED_SOURCES+=("$REPORT_PDF" "$BASELINE_PDF")
fi
if has_category registration; then
  REQUIRED_SOURCES+=("$REPORT_PDF" "$PROTOCOL_PDF")
fi
if has_category visual || has_category transparency; then
  REQUIRED_SOURCES+=("$REPORT_PDF")
fi
if [ "$DRY_RUN" = true ]; then
  echo "Study: $STUDY_ID"
  echo "Requested categories: ${FORENSICS_RAW:-none}"
  echo "Offline: $([ "$OFFLINE_REQUESTED" = true ] || [ "$ALLOW_NETWORK" = false ] && echo true || echo false)"
  echo "Registry network fetch: $REGISTRY_ALLOW_NETWORK"
  printf 'Output root: %s (not created)\n' "$OUTPUT_ROOT"
  printf 'Required source: %s\n' "${REQUIRED_SOURCES[@]:-none}"
  if has_category numeric && ! has_category randomization; then
    echo "Randomization table extraction: selected; simdistr inference: not selected"
  elif has_category randomization; then
    echo "Randomization table extraction: selected; simdistr inference: selected"
  else
    echo "Randomization table extraction: not selected; simdistr inference: not selected"
  fi
  if [ "$RENDER_REPORTS" = true ]; then echo "Quarto: selected"; else echo "Quarto: not selected"; fi
  exit 0
fi

RUN_INIT_ARGS=(
  init --repo-root "$REPO_ROOT" --output-root "$OUTPUT_ROOT"
  --study-id "$STUDY_ID" --categories "$FORENSICS_RAW" --config "$CONFIG_PATH"
)
for required_source in "${REQUIRED_SOURCES[@]}"; do
  RUN_INIT_ARGS+=(--required-input "$required_source")
done
if [ -n "$REGISTRY_CURRENT_REL_PATH" ]; then
  RUN_INIT_ARGS+=(--input "$REPO_ROOT/$REGISTRY_CURRENT_REL_PATH")
fi
if [ -n "$REGISTRY_HISTORY_REL_PATH" ]; then
  RUN_INIT_ARGS+=(--input "$REPO_ROOT/$REGISTRY_HISTORY_REL_PATH")
fi
RUN_INPUTS=()
if has_category randomization; then
  RUN_INPUTS+=("$REPORT_PDF" "$PROTOCOL_PDF" "$BASELINE_PDF")
elif has_category numeric; then
  RUN_INPUTS+=("$REPORT_PDF" "$BASELINE_PDF")
fi
if has_category registration; then RUN_INPUTS+=("$REPORT_PDF" "$PROTOCOL_PDF"); fi
if has_category visual; then RUN_INPUTS+=("$REPORT_PDF"); fi
if has_category transparency; then
  RUN_INPUTS+=("$REPORT_PDF" "$PROTOCOL_PDF" "$SUPPLEMENT_PDF" "$BASELINE_PDF")
fi
if has_category registration; then
  if [ -n "$REGISTRY_CURRENT_REL_PATH" ]; then RUN_INPUTS+=("$REPO_ROOT/$REGISTRY_CURRENT_REL_PATH"); fi
  if [ -n "$REGISTRY_HISTORY_REL_PATH" ]; then RUN_INPUTS+=("$REPO_ROOT/$REGISTRY_HISTORY_REL_PATH"); fi
fi
if has_category visual && [ "$DIGITIZE_PLOTS" = true ] && \
  [ -f "$REPO_ROOT/data/raw/figures/$STUDY_ID/plot_digitization_targets.csv" ]; then
  RUN_INPUTS+=("$REPO_ROOT/data/raw/figures/$STUDY_ID/plot_digitization_targets.csv")
fi
for run_input in "${RUN_INPUTS[@]}"; do RUN_INIT_ARGS+=(--input "$run_input"); done
if [ -n "$RUN_ID" ]; then RUN_INIT_ARGS+=(--run-id "$RUN_ID"); fi
RUN_ROOT="$(PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py "${RUN_INIT_ARGS[@]}")"
RUN_MANIFEST="$RUN_ROOT/run_manifest.json"
PROCESSED_ROOT="$RUN_ROOT/processed"
REPORTS_ROOT="$RUN_ROOT/reports"
export FORENSICS_DISABLE_SHARED_MANIFEST=true
CURRENT_STAGE="initializing"
finish_run_on_exit() {
  local exit_code=$?
  if [ -n "${RUN_MANIFEST:-}" ] && [ -f "$RUN_MANIFEST" ]; then
    if [ "$exit_code" -eq 0 ]; then
      PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
        --manifest "$RUN_MANIFEST" --status completed >/dev/null
    else
      PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
        --manifest "$RUN_MANIFEST" --stage "$CURRENT_STAGE" --status failed \
        --error "Pipeline stopped during $CURRENT_STAGE (exit $exit_code)" >/dev/null || true
      PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
        --manifest "$RUN_MANIFEST" --status failed \
        --error "Pipeline stopped during $CURRENT_STAGE (exit $exit_code)" >/dev/null || true
    fi
  fi
  return "$exit_code"
}
trap finish_run_on_exit EXIT

stage_begin() {
  CURRENT_STAGE="$1"
  PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
    --manifest "$RUN_MANIFEST" --stage "$CURRENT_STAGE" --status running
}
stage_complete() {
  local stage="$1"
  shift
  PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
    --manifest "$RUN_MANIFEST" --stage "$stage" --status completed
  for artifact in "$@"; do
    PYTHONPATH="$REPO_ROOT/src" python3 scripts/forensics_run.py update \
      --manifest "$RUN_MANIFEST" --artifact "$artifact"
  done
}

require_file() {
  local path="$1"
  local stage="$2"
  if [[ ! -f "$path" ]]; then
    echo "Missing required source for $stage: $path" >&2
    return 1
  fi
}

for required_source in "${REQUIRED_SOURCES[@]}"; do
  if [[ ! -f "$required_source" ]]; then
    CURRENT_STAGE="source_validation"
    echo "Missing required source for selected stages: $required_source" >&2
    exit 1
  fi
done

# Ensure src/ is importable without packaging.
export PYTHONPATH="$REPO_ROOT/src"

run_randomization_category() {
  RANDOMIZATION_DATA_DIR="$PROCESSED_ROOT/randomization"
  RANDOMIZATION_REPORT_DIR="$REPORTS_ROOT/randomization"

  if [ "$BASELINE_READY" = false ]; then run_baseline_extraction false; fi
  mkdir -p "$RANDOMIZATION_DATA_DIR" "$RANDOMIZATION_REPORT_DIR"
  stage_begin randomization_methods

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_randomization_inputs.py \
    --in "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --out "$RANDOMIZATION_DATA_DIR"

  Rscript scripts/run_randomization_forensics.R \
    --in "$RANDOMIZATION_DATA_DIR" \
    --out "$RANDOMIZATION_REPORT_DIR" \
    --m 10000 \
    --plot false

  stage_complete randomization_methods "$RANDOMIZATION_REPORT_DIR/row_level_results_v2.csv" \
    "$RANDOMIZATION_REPORT_DIR/reported_test_records_v1.csv" \
    "$RANDOMIZATION_REPORT_DIR/pooled_descriptive_v2.csv" \
    "$RANDOMIZATION_REPORT_DIR/allocation_arithmetic_v1.csv" \
    "$RANDOMIZATION_REPORT_DIR/randomization_run_receipt_v1.csv" \
    "$RANDOMIZATION_REPORT_DIR/simdistr_variable_pvalues_v1.csv" \
    "$RANDOMIZATION_REPORT_DIR/simdistr_combined_descriptive_v1.csv"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin randomization_report
    render_study_report "notebooks/lungtime_randomization_audit.qmd" "randomization" \
      "$RANDOMIZATION_REPORT_DIR" "${STUDY_ID}_randomization_audit_v1.pdf"
    stage_complete randomization_report "$RANDOMIZATION_REPORT_DIR/${STUDY_ID}_randomization_audit_v1.pdf"
  fi
}

BASELINE_READY=false
run_baseline_extraction() {
  local baseline_only="$1"
  RANDOMIZATION_DATA_DIR="$PROCESSED_ROOT/randomization"
  mkdir -p "$RANDOMIZATION_DATA_DIR"
  stage_begin baseline_extraction
  BASELINE_ARGS=(
    --report "$REPORT_PDF" --baseline-pdf "$BASELINE_PDF"
    --baseline-table-label "$BASELINE_TABLE_LABEL" --out "$RANDOMIZATION_DATA_DIR"
    --trial-id "$TRIAL_ID"
  )
  if [ "$baseline_only" = true ]; then
    BASELINE_ARGS+=(--baseline-only)
  else
    require_file "$PROTOCOL_PDF" "randomization extraction"
    BASELINE_ARGS+=(--protocol "$PROTOCOL_PDF")
  fi
  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_randomization_table1.py "${BASELINE_ARGS[@]}"
  BASELINE_READY=true
  stage_complete baseline_extraction "$RANDOMIZATION_DATA_DIR/table1_long.csv"
}

run_numeric_category() {
  NUMERIC_DATA_DIR="$PROCESSED_ROOT/numeric"
  NUMERIC_REPORT_DIR="$REPORTS_ROOT/numeric"
  RANDOMIZATION_DATA_DIR="$PROCESSED_ROOT/randomization"

  mkdir -p "$NUMERIC_DATA_DIR" "$NUMERIC_REPORT_DIR"
  stage_begin numeric_methods

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_numeric.py \
    --table1 "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --report-pdf "$REPORT_PDF" \
    --study-id "$STUDY_ID" \
    --source-pdf "$(basename "$BASELINE_PDF")" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_numeric_summary_tables.py \
    --report "$REPORT_PDF" \
    --trial-id "$TRIAL_ID" \
    --source-pdf "$(basename "$REPORT_PDF")" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_numeric_inputs.py \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_DATA_DIR"

  Rscript scripts/run_numeric_forensics.R \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_REPORT_DIR" \
    --scrutiny-seq false

  stage_complete numeric_methods "$NUMERIC_REPORT_DIR/numeric_method_receipts.csv" \
    "$NUMERIC_REPORT_DIR/numeric_standardized_results.csv" "$NUMERIC_REPORT_DIR/numeric_summary.csv"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin numeric_report
    render_study_report "notebooks/lungtime_numeric_audit.qmd" "numeric" \
      "$NUMERIC_REPORT_DIR" "${STUDY_ID}_numeric_audit_v1.pdf"
    stage_complete numeric_report "$NUMERIC_REPORT_DIR/${STUDY_ID}_numeric_audit_v1.pdf"
  fi
}

run_registration_category() {
  REG_DATA_DIR="$PROCESSED_ROOT/registration"
  REG_REPORT_DIR="$REPORTS_ROOT/registration"

  mkdir -p "$REG_DATA_DIR" "$REG_REPORT_DIR"
  stage_begin registration_methods

  REGISTRY_ARGS=(
    --allow-network "$REGISTRY_ALLOW_NETWORK"
  )
  if [[ -n "$REGISTRY_ID" ]]; then
    REGISTRY_ARGS+=(--registry-id "$REGISTRY_ID")
  fi
  if [[ -n "$REGISTRY_URL" ]]; then
    REGISTRY_ARGS+=(--registry-url "$REGISTRY_URL")
  fi
  if [[ -n "$REGISTRY_CURRENT_REL_PATH" ]]; then
    REGISTRY_ARGS+=(--registry-current-json "$REPO_ROOT/$REGISTRY_CURRENT_REL_PATH")
  fi
  if [[ -n "$REGISTRY_HISTORY_REL_PATH" ]]; then
    REGISTRY_ARGS+=(--registry-history "$REPO_ROOT/$REGISTRY_HISTORY_REL_PATH")
  fi
  if [[ -n "$REGISTRY_AS_OF_DATE" ]]; then
    REGISTRY_ARGS+=(--as-of-date "$REGISTRY_AS_OF_DATE")
  fi
  if [[ -n "$PUBLICATION_URL" ]]; then
    REGISTRY_ARGS+=(--publication-url "$PUBLICATION_URL")
  fi
  if [[ -n "$PUBLICATION_DOI" ]]; then
    REGISTRY_ARGS+=(--publication-doi "$PUBLICATION_DOI")
  fi
  if [[ -n "$PUBLICATION_PMID" ]]; then
    REGISTRY_ARGS+=(--publication-pmid "$PUBLICATION_PMID")
  fi

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_registration.py \
    --report "$REPORT_PDF" \
    --protocol "$PROTOCOL_PDF" \
    --study-id "$STUDY_ID" \
    --out "$REG_DATA_DIR" \
    "${REGISTRY_ARGS[@]}"

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_registration_inputs.py \
    --in "$REG_DATA_DIR" \
    --out "$REG_DATA_DIR"

  Rscript scripts/run_registration_forensics.R \
    --in "$REG_DATA_DIR" \
    --out "$REG_REPORT_DIR"

  stage_complete registration_methods "$REG_REPORT_DIR/registration_summary.csv" \
    "$REG_REPORT_DIR/registration_row_results.csv"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin registration_report
    render_study_report "notebooks/lungtime_registration_audit.qmd" "registration" \
      "$REG_REPORT_DIR" "${STUDY_ID}_registration_audit_v1.pdf"
    stage_complete registration_report "$REG_REPORT_DIR/${STUDY_ID}_registration_audit_v1.pdf"
  fi
}

run_visual_category() {
  VISUAL_DATA_DIR="$PROCESSED_ROOT/visual"
  VISUAL_REPORT_DIR="$REPORTS_ROOT/visual"
  FIGURE_RAW_ROOT="$REPO_ROOT/data/raw/figures"
  SOURCE_DIGITIZE_TARGETS="$FIGURE_RAW_ROOT/$STUDY_ID/plot_digitization_targets.csv"
  DIGITIZE_TARGET_ROOT="$VISUAL_DATA_DIR/inputs/plot_digitization_targets"
  DIGITIZE_TARGETS="$DIGITIZE_TARGET_ROOT/$STUDY_ID/plot_digitization_targets.csv"
  DIGITIZE_PROJECT_DIR="$RUN_ROOT/generated/plot_digitization/$STUDY_ID/metaDigitise"
  DIGITIZE_OUTPUT="$VISUAL_DATA_DIR/inputs/plot_digitized_values.csv"

  mkdir -p "$VISUAL_DATA_DIR" "$VISUAL_REPORT_DIR"
  stage_begin visual_methods

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_visual.py \
    --report "$REPORT_PDF" \
    --study-id "$STUDY_ID" \
    --out "$VISUAL_DATA_DIR"

  if [ "$DIGITIZE_PLOTS" = "true" ]; then
    if [ -f "$SOURCE_DIGITIZE_TARGETS" ]; then
      mkdir -p "$DIGITIZE_TARGET_ROOT/$STUDY_ID"
      cp "$SOURCE_DIGITIZE_TARGETS" "$DIGITIZE_TARGETS"
    fi
    PYTHONPATH="$REPO_ROOT/src" uv run python scripts/init_plot_digitization_targets.py \
      --study-id "$STUDY_ID" \
      --out-root "$DIGITIZE_TARGET_ROOT"

    Rscript scripts/run_plot_digitization.R \
      --targets "$DIGITIZE_TARGETS" \
      --project-dir "$DIGITIZE_PROJECT_DIR" \
      --out "$DIGITIZE_OUTPUT"
  fi

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_visual_inputs.py \
    --in "$VISUAL_DATA_DIR" \
    --out "$VISUAL_DATA_DIR"

  Rscript scripts/run_visual_forensics.R \
    --in "$VISUAL_DATA_DIR" \
    --out "$VISUAL_REPORT_DIR"

  VISUAL_ARTIFACTS=("$VISUAL_REPORT_DIR/visual_summary.csv" "$VISUAL_REPORT_DIR/visual_row_results.csv")
  if [ "$DIGITIZE_PLOTS" = true ]; then
    VISUAL_ARTIFACTS+=("$DIGITIZE_TARGETS" "$DIGITIZE_OUTPUT")
  fi
  stage_complete visual_methods "${VISUAL_ARTIFACTS[@]}"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin visual_report
    render_study_report "notebooks/lungtime_visual_audit.qmd" "visual" \
      "$VISUAL_REPORT_DIR" "${STUDY_ID}_visual_audit_v1.pdf"
    stage_complete visual_report "$VISUAL_REPORT_DIR/${STUDY_ID}_visual_audit_v1.pdf"
  fi
}

run_transparency_category() {
  TRANSPARENCY_DATA_DIR="$PROCESSED_ROOT/transparency"
  TRANSPARENCY_REPORT_DIR="$REPORTS_ROOT/transparency"

  mkdir -p "$TRANSPARENCY_DATA_DIR" "$TRANSPARENCY_REPORT_DIR"
  stage_begin transparency_methods

  TRANSPARENCY_SOURCE_ARGS=(--report "$REPORT_PDF")
  if [ -f "$PROTOCOL_PDF" ]; then TRANSPARENCY_SOURCE_ARGS+=(--protocol "$PROTOCOL_PDF"); fi
  if [ -f "$SUPPLEMENT_PDF" ]; then TRANSPARENCY_SOURCE_ARGS+=(--supplement "$SUPPLEMENT_PDF"); fi
  if [ -f "$BASELINE_PDF" ]; then TRANSPARENCY_SOURCE_ARGS+=(--baseline "$BASELINE_PDF"); fi

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_transparency.py \
    "${TRANSPARENCY_SOURCE_ARGS[@]}" \
    --study-id "$STUDY_ID" \
    --study-title "$STUDY_TITLE" \
    --trial-id "$TRIAL_ID" \
    --registry-id "$REGISTRY_ID" \
    --registry-url "$REGISTRY_URL" \
    --publication-url "$PUBLICATION_URL" \
    --publication-doi "$PUBLICATION_DOI" \
    --publication-pmid "$PUBLICATION_PMID" \
    --out "$TRANSPARENCY_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_transparency_inputs.py \
    --in "$TRANSPARENCY_DATA_DIR" \
    --out "$TRANSPARENCY_DATA_DIR"

  Rscript scripts/run_transparency_forensics.R \
    --in "$TRANSPARENCY_DATA_DIR" \
    --out "$TRANSPARENCY_REPORT_DIR"

  stage_complete transparency_methods "$TRANSPARENCY_REPORT_DIR/transparency_summary.csv" \
    "$TRANSPARENCY_REPORT_DIR/transparency_row_results.csv"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin transparency_report
    render_study_report "notebooks/lungtime_transparency_audit.qmd" "transparency" \
      "$TRANSPARENCY_REPORT_DIR" "${STUDY_ID}_transparency_audit_v1.pdf"
    stage_complete transparency_report "$TRANSPARENCY_REPORT_DIR/${STUDY_ID}_transparency_audit_v1.pdf"
  fi
}

run_meta_category() {
  META_DATA_DIR="$PROCESSED_ROOT/meta"
  META_REPORT_DIR="$REPORTS_ROOT/meta"
  META_REQUESTED_CATEGORIES=""
  for category in randomization numeric registration visual transparency; do
    if has_category "$category"; then
      if [ -n "$META_REQUESTED_CATEGORIES" ]; then
        META_REQUESTED_CATEGORIES+=","
      fi
      META_REQUESTED_CATEGORIES+="$category"
    fi
  done
  mkdir -p "$META_DATA_DIR" "$META_REPORT_DIR"
  stage_begin meta_aggregation

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/extract_meta.py \
    --study-id "$STUDY_ID" \
    --repo-root "$REPO_ROOT" \
    --reports-root "$REPORTS_ROOT" \
    --run-manifest "$RUN_MANIFEST" \
    --requested-categories "$META_REQUESTED_CATEGORIES" \
    --out "$META_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" uv run python scripts/build_meta_inputs.py \
    --in "$META_DATA_DIR" \
    --out "$META_DATA_DIR"

  Rscript scripts/run_meta_forensics.R \
    --in "$META_DATA_DIR" \
    --out "$META_REPORT_DIR"

  stage_complete meta_aggregation "$META_REPORT_DIR/meta_coverage_summary_v1.csv" \
    "$META_REPORT_DIR/meta_candidate_concerns_v1_out.csv"
  if [ "$RENDER_REPORTS" = true ]; then
    stage_begin meta_report
    render_study_report "notebooks/lungtime_meta_audit.qmd" "meta" \
      "$META_REPORT_DIR" "${STUDY_ID}_meta_audit_v2.pdf"
    stage_complete meta_report "$META_REPORT_DIR/${STUDY_ID}_meta_audit_v2.pdf"
  fi
}

if [ -n "$FORENSICS_RAW" ]; then
  if has_category randomization; then
    run_randomization_category
  elif has_category numeric; then
    run_baseline_extraction true
  fi
  if has_category numeric; then
    run_numeric_category
  fi
  if has_category registration; then
    run_registration_category
  fi
  if has_category visual; then
    run_visual_category
  fi
  if has_category transparency; then
    run_transparency_category
  fi
  if has_category meta; then
    run_meta_category
  fi
fi
