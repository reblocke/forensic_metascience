#!/usr/bin/env bash
set -euo pipefail

STUDY_ID=""
REPORT_PATH=""
REVIEW_TYPE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --study-id)
      STUDY_ID="$2"
      shift 2
      ;;
    --report)
      REPORT_PATH="$2"
      shift 2
      ;;
    --review-type)
      REVIEW_TYPE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: bash scripts/run_manuscript_review.sh --study-id <study_id> --report <pdf> --review-type prediction_validation"
      exit 1
      ;;
  esac
done

if [[ -z "$STUDY_ID" || -z "$REPORT_PATH" || -z "$REVIEW_TYPE" ]]; then
  echo "Usage: bash scripts/run_manuscript_review.sh --study-id <study_id> --report <pdf> --review-type prediction_validation"
  exit 1
fi

if [[ "$REVIEW_TYPE" != "prediction_validation" ]]; then
  echo "Unsupported review type: $REVIEW_TYPE"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT/src"

REVIEW_DATA_DIR="$REPO_ROOT/data/processed/reviews/$STUDY_ID"
REVIEW_REPORT_DIR="$REPO_ROOT/reports/reviews/$STUDY_ID"

mkdir -p "$REVIEW_DATA_DIR" "$REVIEW_REPORT_DIR"

PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_prediction_review.py \
  --report "$REPORT_PATH" \
  --study-id "$STUDY_ID" \
  --review-type "$REVIEW_TYPE" \
  --out "$REVIEW_DATA_DIR"

PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_prediction_review_inputs.py \
  --in "$REVIEW_DATA_DIR" \
  --out "$REVIEW_DATA_DIR"

Rscript scripts/run_numeric_forensics.R \
  --in "$REVIEW_DATA_DIR" \
  --out "$REVIEW_REPORT_DIR" \
  --scrutiny-seq false

PYTHONPATH="$REPO_ROOT/src" python3 scripts/extract_visual.py \
  --report "$REPORT_PATH" \
  --study-id "$STUDY_ID" \
  --out "$REVIEW_DATA_DIR"

PYTHONPATH="$REPO_ROOT/src" python3 scripts/build_visual_inputs.py \
  --in "$REVIEW_DATA_DIR" \
  --out "$REVIEW_DATA_DIR"

Rscript scripts/run_visual_forensics.R \
  --in "$REVIEW_DATA_DIR" \
  --out "$REVIEW_REPORT_DIR"

Rscript scripts/run_prediction_review_forensics.R \
  --in "$REVIEW_DATA_DIR" \
  --out "$REVIEW_REPORT_DIR"

REVIEW_STUDY_ID="$STUDY_ID" quarto render notebooks/prediction_validation_review.qmd \
  --to pdf \
  --output "${STUDY_ID}_prediction_validation_review.pdf" \
  --output-dir "$REVIEW_REPORT_DIR"

PYTHONPATH="$REPO_ROOT/src" python3 scripts/mark_forensics_ready.py \
  --study-id "$STUDY_ID" \
  --category "review_prediction_validation" \
  --source-pdf "$(basename "$REPORT_PATH")" \
  --extract-confidence "medium" \
  --page-ref "table2|table3|tablee2|figure1" \
  --table-ref "prediction_validation_review" \
  --ready
