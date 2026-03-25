#!/usr/bin/env bash
set -euo pipefail

RUN_RANDOMIZATION_AUDIT=false
FORENSICS_RAW=""
DIGITIZE_PLOTS=false
STUDY_ID="lungtime"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --randomization-audit)
      RUN_RANDOMIZATION_AUDIT=true
      shift
      ;;
    --forensics)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --forensics"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
        exit 1
      fi
      FORENSICS_RAW="$2"
      shift 2
      ;;
    --study-id)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --study-id"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
        exit 1
      fi
      STUDY_ID="$2"
      shift 2
      ;;
    --digitize-plots)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --digitize-plots"
        echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
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
      echo "Usage: bash scripts/run_pipeline.sh [--study-id <study_id>] [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
      exit 1
      ;;
  esac
done

if [ "$RUN_RANDOMIZATION_AUDIT" = true ] && [ -z "$FORENSICS_RAW" ]; then
  FORENSICS_RAW="randomization"
fi

FORENSICS_RAW="${FORENSICS_RAW// /}"
if [ "$FORENSICS_RAW" = "all" ]; then
  FORENSICS_RAW="randomization,numeric,registration,visual,meta"
fi

if [ -n "$FORENSICS_RAW" ]; then
  IFS=',' read -r -a REQUESTED_CATEGORIES <<< "$FORENSICS_RAW"
  for category in "${REQUESTED_CATEGORIES[@]}"; do
    case "$category" in
      randomization|numeric|registration|visual|meta)
        ;;
      *)
        echo "Unknown forensics category: $category"
        echo "Valid categories: randomization,numeric,registration,visual,meta"
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

render_study_report() {
  local notebook_path="$1"
  local category="$2"
  local report_dir="$3"
  local output_name="$4"

  FORENSICS_STUDY_ID="$STUDY_ID" FORENSICS_STUDY_TITLE="$STUDY_TITLE" quarto render "$notebook_path" \
    --to pdf \
    --output "$output_name" \
    --output-dir "$report_dir"

  local fallback_path="$REPO_ROOT/reports/$category/$output_name"
  local target_path="$report_dir/$output_name"
  if [[ -f "$fallback_path" && "$fallback_path" != "$target_path" ]]; then
    mv -f "$fallback_path" "$target_path"
  fi
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONFIG_PATH="$REPO_ROOT/config/studies/${STUDY_ID}.sh"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Unknown study-id: $STUDY_ID"
  echo "Expected config at: $CONFIG_PATH"
  exit 1
fi
source "$CONFIG_PATH"

REPORT_PDF="$REPO_ROOT/$REPORT_REL_PATH"
PROTOCOL_PDF="$REPO_ROOT/$PROTOCOL_REL_PATH"
SUPPLEMENT_PDF="$REPO_ROOT/$SUPPLEMENT_REL_PATH"
BASELINE_PDF="$REPO_ROOT/$BASELINE_REL_PATH"

if [[ ! -f "$REPORT_PDF" ]]; then
  echo "Missing report PDF: $REPORT_PDF"
  exit 1
fi
if [[ ! -f "$PROTOCOL_PDF" ]]; then
  echo "Missing protocol PDF: $PROTOCOL_PDF"
  exit 1
fi
if [[ ! -f "$SUPPLEMENT_PDF" ]]; then
  echo "Missing supplement PDF: $SUPPLEMENT_PDF"
  exit 1
fi
if [[ ! -f "$BASELINE_PDF" ]]; then
  echo "Missing baseline PDF: $BASELINE_PDF"
  exit 1
fi

# Ensure src/ is importable without packaging.
export PYTHONPATH="$REPO_ROOT/src"

# Run deterministic preprocessing
uv run python scripts/process.py

# Make cheap diagnostics/plots (safe to skip for headless environments)
uv run python scripts/plot_diagnostics.py --input "$REPO_ROOT/data/processed/sample_processed.csv" --outdir "$REPO_ROOT/reports/diagnostics" ||   echo "Diagnostics generation failed (non-fatal)."

run_randomization_category() {
  RANDOMIZATION_DATA_DIR="$REPO_ROOT/data/processed/randomization/$STUDY_ID"
  RANDOMIZATION_REPORT_DIR="$REPO_ROOT/reports/randomization/$STUDY_ID"

  mkdir -p "$RANDOMIZATION_DATA_DIR" "$RANDOMIZATION_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_randomization_table1.py \
    --report "$REPORT_PDF" \
    --protocol "$PROTOCOL_PDF" \
    --baseline-pdf "$BASELINE_PDF" \
    --baseline-table-label "$BASELINE_TABLE_LABEL" \
    --out "$RANDOMIZATION_DATA_DIR" \
    --trial-id "$TRIAL_ID"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_randomization_inputs.py \
    --in "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --out "$RANDOMIZATION_DATA_DIR"

  Rscript scripts/run_randomization_forensics.R \
    --in "$RANDOMIZATION_DATA_DIR" \
    --out "$RANDOMIZATION_REPORT_DIR" \
    --m 10000 \
    --plot false

  render_study_report \
    "notebooks/lungtime_randomization_audit.qmd" \
    "randomization" \
    "$RANDOMIZATION_REPORT_DIR" \
    "${STUDY_ID}_randomization_audit.pdf"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "$STUDY_ID" \
    --category "randomization" \
    --source-pdf "$(basename "$REPORT_PDF")|$(basename "$PROTOCOL_PDF")|$(basename "$SUPPLEMENT_PDF")" \
    --extract-confidence "high" \
    --page-ref "table1_source_page" \
    --table-ref "baseline_characteristics" \
    --ready
}

run_numeric_category() {
  NUMERIC_DATA_DIR="$REPO_ROOT/data/processed/numeric/$STUDY_ID"
  NUMERIC_REPORT_DIR="$REPO_ROOT/reports/numeric/$STUDY_ID"
  RANDOMIZATION_DATA_DIR="$REPO_ROOT/data/processed/randomization/$STUDY_ID"

  mkdir -p "$NUMERIC_DATA_DIR" "$NUMERIC_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_numeric.py \
    --table1 "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --report-pdf "$REPORT_PDF" \
    --study-id "$STUDY_ID" \
    --source-pdf "$(basename "$BASELINE_PDF")" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_numeric_summary_tables.py \
    --report "$REPORT_PDF" \
    --trial-id "$TRIAL_ID" \
    --source-pdf "$(basename "$REPORT_PDF")" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_numeric_inputs.py \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_DATA_DIR"

  Rscript scripts/run_numeric_forensics.R \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_REPORT_DIR" \
    --scrutiny-seq false

  render_study_report \
    "notebooks/lungtime_numeric_audit.qmd" \
    "numeric" \
    "$NUMERIC_REPORT_DIR" \
    "${STUDY_ID}_numeric_audit.pdf"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "$STUDY_ID" \
    --category "numeric" \
    --source-pdf "$(basename "$REPORT_PDF")|$(basename "$SUPPLEMENT_PDF")" \
    --extract-confidence "high" \
    --page-ref "table1_source_page" \
    --table-ref "baseline_characteristics" \
    --ready
}

run_registration_category() {
  REG_DATA_DIR="$REPO_ROOT/data/processed/registration/$STUDY_ID"
  REG_REPORT_DIR="$REPO_ROOT/reports/registration/$STUDY_ID"

  mkdir -p "$REG_DATA_DIR" "$REG_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_registration.py \
    --report "$REPORT_PDF" \
    --protocol "$PROTOCOL_PDF" \
    --study-id "$STUDY_ID" \
    --out "$REG_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_registration_inputs.py \
    --in "$REG_DATA_DIR" \
    --out "$REG_DATA_DIR"

  Rscript scripts/run_registration_forensics.R \
    --in "$REG_DATA_DIR" \
    --out "$REG_REPORT_DIR"

  render_study_report \
    "notebooks/lungtime_registration_audit.qmd" \
    "registration" \
    "$REG_REPORT_DIR" \
    "${STUDY_ID}_registration_audit.pdf"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "$STUDY_ID" \
    --category "registration" \
    --source-pdf "$(basename "$REPORT_PDF")|$(basename "$PROTOCOL_PDF")" \
    --extract-confidence "medium" \
    --page-ref "claim_level" \
    --table-ref "report_vs_protocol" \
    --ready
}

run_visual_category() {
  VISUAL_DATA_DIR="$REPO_ROOT/data/processed/visual/$STUDY_ID"
  VISUAL_REPORT_DIR="$REPO_ROOT/reports/visual/$STUDY_ID"
  FIGURE_RAW_ROOT="$REPO_ROOT/data/raw/figures"
  DIGITIZE_TARGETS="$FIGURE_RAW_ROOT/$STUDY_ID/plot_digitization_targets.csv"
  DIGITIZE_PROJECT_DIR="$REPO_ROOT/data/generated/plot_digitization/$STUDY_ID/metaDigitise"
  DIGITIZE_OUTPUT="$VISUAL_DATA_DIR/inputs/plot_digitized_values.csv"

  mkdir -p "$VISUAL_DATA_DIR" "$VISUAL_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_visual.py \
    --report "$REPORT_PDF" \
    --study-id "$STUDY_ID" \
    --out "$VISUAL_DATA_DIR"

  if [ "$DIGITIZE_PLOTS" = "true" ]; then
    PYTHONPATH="$REPO_ROOT/src" python3 scripts/init_plot_digitization_targets.py \
      --study-id "$STUDY_ID" \
      --out-root "$FIGURE_RAW_ROOT"

    Rscript scripts/run_plot_digitization.R \
      --targets "$DIGITIZE_TARGETS" \
      --project-dir "$DIGITIZE_PROJECT_DIR" \
      --out "$DIGITIZE_OUTPUT"
  fi

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_visual_inputs.py \
    --in "$VISUAL_DATA_DIR" \
    --out "$VISUAL_DATA_DIR"

  Rscript scripts/run_visual_forensics.R \
    --in "$VISUAL_DATA_DIR" \
    --out "$VISUAL_REPORT_DIR"

  render_study_report \
    "notebooks/lungtime_visual_audit.qmd" \
    "visual" \
    "$VISUAL_REPORT_DIR" \
    "${STUDY_ID}_visual_audit.pdf"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "$STUDY_ID" \
    --category "visual" \
    --source-pdf "$(basename "$REPORT_PDF")" \
    --extract-confidence "low" \
    --page-ref "figure_mentions" \
    --table-ref "figure_caption_text" \
    --ready
}

run_meta_category() {
  META_DATA_DIR="$REPO_ROOT/data/processed/meta/$STUDY_ID"
  META_REPORT_DIR="$REPO_ROOT/reports/meta/$STUDY_ID"

  mkdir -p "$META_DATA_DIR" "$META_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_meta.py \
    --study-id "$STUDY_ID" \
    --repo-root "$REPO_ROOT" \
    --out "$META_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_meta_inputs.py \
    --in "$META_DATA_DIR" \
    --out "$META_DATA_DIR"

  Rscript scripts/run_meta_forensics.R \
    --in "$META_DATA_DIR" \
    --out "$META_REPORT_DIR"

  render_study_report \
    "notebooks/lungtime_meta_audit.qmd" \
    "meta" \
    "$META_REPORT_DIR" \
    "${STUDY_ID}_meta_audit.pdf"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "$STUDY_ID" \
    --category "meta" \
    --source-pdf "derived_from_category_reports" \
    --extract-confidence "medium" \
    --page-ref "n/a" \
    --table-ref "category_summary_tables" \
    --ready
}

if [ -n "$FORENSICS_RAW" ]; then
  NEED_RANDOMIZATION=false
  if has_category randomization || has_category numeric || has_category meta; then
    NEED_RANDOMIZATION=true
  fi
  if [ "$NEED_RANDOMIZATION" = true ]; then
    run_randomization_category
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
  if has_category meta; then
    run_meta_category
  fi
fi
