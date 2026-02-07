#!/usr/bin/env bash
set -euo pipefail

RUN_RANDOMIZATION_AUDIT=false
FORENSICS_RAW=""
DIGITIZE_PLOTS=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --randomization-audit)
      RUN_RANDOMIZATION_AUDIT=true
      shift
      ;;
    --forensics)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --forensics"
        echo "Usage: bash scripts/run_pipeline.sh [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
        exit 1
      fi
      FORENSICS_RAW="$2"
      shift 2
      ;;
    --digitize-plots)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --digitize-plots"
        echo "Usage: bash scripts/run_pipeline.sh [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
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
      echo "Usage: bash scripts/run_pipeline.sh [--randomization-audit] [--forensics randomization,numeric,registration,visual,meta] [--digitize-plots true|false]"
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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Ensure src/ is importable without packaging.
export PYTHONPATH="$REPO_ROOT/src"

# Run deterministic preprocessing
uv run python scripts/process.py

# Make cheap diagnostics/plots (safe to skip for headless environments)
uv run python scripts/plot_diagnostics.py --input "$REPO_ROOT/data/processed/sample_processed.csv" --outdir "$REPO_ROOT/reports/diagnostics" ||   echo "Diagnostics generation failed (non-fatal)."

run_randomization_category() {
  RANDOMIZATION_SOURCE_DIR="$REPO_ROOT/Checkpoint Inhib Time of Day"
  RANDOMIZATION_DATA_DIR="$REPO_ROOT/data/processed/randomization/lungtime"
  RANDOMIZATION_REPORT_DIR="$REPO_ROOT/reports/randomization/lungtime"

  mkdir -p "$RANDOMIZATION_DATA_DIR" "$RANDOMIZATION_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_randomization_table1.py \
    --report "$RANDOMIZATION_SOURCE_DIR/s41591-025-04181-w.pdf" \
    --protocol "$RANDOMIZATION_SOURCE_DIR/41591_2025_4181_MOESM1_ESM.pdf" \
    --out "$RANDOMIZATION_DATA_DIR" \
    --trial-id "lungtime_c01_s41591_025_04181"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_randomization_inputs.py \
    --in "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --out "$RANDOMIZATION_DATA_DIR"

  Rscript scripts/run_randomization_forensics.R \
    --in "$RANDOMIZATION_DATA_DIR" \
    --out "$RANDOMIZATION_REPORT_DIR" \
    --m 10000 \
    --plot false

  quarto render notebooks/lungtime_randomization_audit.qmd \
    --to pdf \
    --output-dir "$RANDOMIZATION_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "lungtime" \
    --category "randomization" \
    --source-pdf "s41591-025-04181-w.pdf|41591_2025_4181_MOESM1_ESM.pdf" \
    --extract-confidence "high" \
    --page-ref "table1_source_page" \
    --table-ref "baseline_characteristics" \
    --ready
}

run_numeric_category() {
  NUMERIC_DATA_DIR="$REPO_ROOT/data/processed/numeric/lungtime"
  NUMERIC_REPORT_DIR="$REPO_ROOT/reports/numeric/lungtime"
  RANDOMIZATION_DATA_DIR="$REPO_ROOT/data/processed/randomization/lungtime"

  mkdir -p "$NUMERIC_DATA_DIR" "$NUMERIC_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_numeric.py \
    --table1 "$RANDOMIZATION_DATA_DIR/table1_long.csv" \
    --report-pdf "$REPO_ROOT/Checkpoint Inhib Time of Day/s41591-025-04181-w.pdf" \
    --study-id "lungtime" \
    --source-pdf "s41591-025-04181-w.pdf" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_numeric_summary_tables.py \
    --report "$REPO_ROOT/Checkpoint Inhib Time of Day/s41591-025-04181-w.pdf" \
    --trial-id "lungtime_c01_s41591_025_04181" \
    --source-pdf "s41591-025-04181-w.pdf" \
    --out "$NUMERIC_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_numeric_inputs.py \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_DATA_DIR"

  Rscript scripts/run_numeric_forensics.R \
    --in "$NUMERIC_DATA_DIR" \
    --out "$NUMERIC_REPORT_DIR" \
    --scrutiny-seq false

  quarto render notebooks/lungtime_numeric_audit.qmd \
    --to pdf \
    --output-dir "$NUMERIC_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "lungtime" \
    --category "numeric" \
    --source-pdf "s41591-025-04181-w.pdf" \
    --extract-confidence "high" \
    --page-ref "table1_source_page" \
    --table-ref "baseline_characteristics" \
    --ready
}

run_registration_category() {
  SOURCE_DIR="$REPO_ROOT/Checkpoint Inhib Time of Day"
  REG_DATA_DIR="$REPO_ROOT/data/processed/registration/lungtime"
  REG_REPORT_DIR="$REPO_ROOT/reports/registration/lungtime"

  mkdir -p "$REG_DATA_DIR" "$REG_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_registration.py \
    --report "$SOURCE_DIR/s41591-025-04181-w.pdf" \
    --protocol "$SOURCE_DIR/41591_2025_4181_MOESM1_ESM.pdf" \
    --study-id "lungtime" \
    --out "$REG_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_registration_inputs.py \
    --in "$REG_DATA_DIR" \
    --out "$REG_DATA_DIR"

  Rscript scripts/run_registration_forensics.R \
    --in "$REG_DATA_DIR" \
    --out "$REG_REPORT_DIR"

  quarto render notebooks/lungtime_registration_audit.qmd \
    --to pdf \
    --output-dir "$REG_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "lungtime" \
    --category "registration" \
    --source-pdf "s41591-025-04181-w.pdf|41591_2025_4181_MOESM1_ESM.pdf" \
    --extract-confidence "medium" \
    --page-ref "claim_level" \
    --table-ref "report_vs_protocol" \
    --ready
}

run_visual_category() {
  SOURCE_DIR="$REPO_ROOT/Checkpoint Inhib Time of Day"
  VISUAL_DATA_DIR="$REPO_ROOT/data/processed/visual/lungtime"
  VISUAL_REPORT_DIR="$REPO_ROOT/reports/visual/lungtime"
  FIGURE_RAW_ROOT="$REPO_ROOT/data/raw/figures"
  DIGITIZE_TARGETS="$FIGURE_RAW_ROOT/lungtime/plot_digitization_targets.csv"
  DIGITIZE_PROJECT_DIR="$REPO_ROOT/data/generated/plot_digitization/lungtime/metaDigitise"
  DIGITIZE_OUTPUT="$VISUAL_DATA_DIR/inputs/plot_digitized_values.csv"

  mkdir -p "$VISUAL_DATA_DIR" "$VISUAL_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_visual.py \
    --report "$SOURCE_DIR/s41591-025-04181-w.pdf" \
    --study-id "lungtime" \
    --out "$VISUAL_DATA_DIR"

  if [ "$DIGITIZE_PLOTS" = "true" ]; then
    PYTHONPATH="$REPO_ROOT/src" python3 scripts/init_plot_digitization_targets.py \
      --study-id "lungtime" \
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

  quarto render notebooks/lungtime_visual_audit.qmd \
    --to pdf \
    --output-dir "$VISUAL_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "lungtime" \
    --category "visual" \
    --source-pdf "s41591-025-04181-w.pdf" \
    --extract-confidence "low" \
    --page-ref "figure_mentions" \
    --table-ref "figure_caption_text" \
    --ready
}

run_meta_category() {
  META_DATA_DIR="$REPO_ROOT/data/processed/meta/lungtime"
  META_REPORT_DIR="$REPO_ROOT/reports/meta/lungtime"

  mkdir -p "$META_DATA_DIR" "$META_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_meta.py \
    --study-id "lungtime" \
    --repo-root "$REPO_ROOT" \
    --out "$META_DATA_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_meta_inputs.py \
    --in "$META_DATA_DIR" \
    --out "$META_DATA_DIR"

  Rscript scripts/run_meta_forensics.R \
    --in "$META_DATA_DIR" \
    --out "$META_REPORT_DIR"

  quarto render notebooks/lungtime_meta_audit.qmd \
    --to pdf \
    --output-dir "$META_REPORT_DIR"

  PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
    --study-id "lungtime" \
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
