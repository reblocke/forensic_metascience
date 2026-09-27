#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/run_manuscript_review.sh --study-id ID --report PDF \
  --review-type prediction_validation [options]

Options:
  --output-root PATH   Repository-contained parent for a fresh private-review run.
  --run-id ID          Explicit run ID; an existing destination is refused.
  --dry-run            Print requirements without checking PDFs or writing outputs.
  --offline            Prohibit network access (the default).
  --render-report      Render Quarto after calculation stages complete.
  --help               Show this help.
USAGE
}

STUDY_ID=""
REPORT_PATH=""
REVIEW_TYPE=""
OUTPUT_ROOT=""
RUN_ID=""
DRY_RUN=false
RENDER_REPORT=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --offline) shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --render-report) RENDER_REPORT=true; shift ;;
    --study-id) [[ $# -ge 2 ]] || { echo "Missing --study-id value" >&2; exit 1; }; STUDY_ID="$2"; shift 2 ;;
    --report) [[ $# -ge 2 ]] || { echo "Missing --report value" >&2; exit 1; }; REPORT_PATH="$2"; shift 2 ;;
    --review-type) [[ $# -ge 2 ]] || { echo "Missing --review-type value" >&2; exit 1; }; REVIEW_TYPE="$2"; shift 2 ;;
    --output-root) [[ $# -ge 2 ]] || { echo "Missing --output-root value" >&2; exit 1; }; OUTPUT_ROOT="$2"; shift 2 ;;
    --run-id) [[ $# -ge 2 ]] || { echo "Missing --run-id value" >&2; exit 1; }; RUN_ID="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$STUDY_ID" || -z "$REPORT_PATH" || "$REVIEW_TYPE" != "prediction_validation" ]]; then
  echo "Study ID, report path, and supported review type are required." >&2
  usage
  exit 1
fi
if [[ ! "$STUDY_ID" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]]; then
  echo "Invalid study ID: $STUDY_ID" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src"
export UV_OFFLINE=1
export FORENSICS_DISABLE_SHARED_MANIFEST=true
OUTPUT_ROOT="${OUTPUT_ROOT:-$REPO_ROOT/data/processed/forensics_runs/private_reviews}"
OUTPUT_ROOT="$(python3 scripts/forensics_run.py validate-output --repo-root "$REPO_ROOT" --output-root "$OUTPUT_ROOT")"
if [[ "$REPORT_PATH" != /* ]]; then REPORT_PATH="$REPO_ROOT/$REPORT_PATH"; fi

if [ "$DRY_RUN" = true ]; then
  echo "Study: $STUDY_ID"
  echo "Review type: $REVIEW_TYPE"
  echo "Required source: $REPORT_PATH"
  echo "Offline: true"
  echo "Output root: $OUTPUT_ROOT (not created)"
  if [ "$RENDER_REPORT" = true ]; then echo "Quarto: selected"; else echo "Quarto: not selected"; fi
  exit 0
fi
if [[ ! -f "$REPORT_PATH" ]]; then
  echo "Missing review report PDF: $REPORT_PATH" >&2
  exit 1
fi

RUN_ARGS=(
  init --repo-root "$REPO_ROOT" --output-root "$OUTPUT_ROOT"
  --study-id "$STUDY_ID" --categories prediction_validation --config "$0"
  --input "$REPORT_PATH" --required-input "$REPORT_PATH"
)
if [ -n "$RUN_ID" ]; then RUN_ARGS+=(--run-id "$RUN_ID"); fi
RUN_ROOT="$(python3 scripts/forensics_run.py "${RUN_ARGS[@]}")"
RUN_MANIFEST="$RUN_ROOT/run_manifest.json"
REVIEW_DATA_DIR="$RUN_ROOT/processed"
REVIEW_REPORT_DIR="$RUN_ROOT/reports"
CURRENT_STAGE="prediction_validation_review"
finish_run_on_exit() {
  local exit_code=$?
  if [ -f "$RUN_MANIFEST" ]; then
    if [ "$exit_code" -eq 0 ]; then
      python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" --status completed >/dev/null
    else
      python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" --stage "$CURRENT_STAGE" \
        --status failed --error "Private review stopped during $CURRENT_STAGE (exit $exit_code)" >/dev/null || true
      python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" --status failed \
        --error "Private review stopped during $CURRENT_STAGE (exit $exit_code)" >/dev/null || true
    fi
  fi
  return "$exit_code"
}
trap finish_run_on_exit EXIT
python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" \
  --stage "$CURRENT_STAGE" --status running

python3 scripts/extract_prediction_review.py \
  --report "$REPORT_PATH" --study-id "$STUDY_ID" \
  --review-type "$REVIEW_TYPE" --out "$REVIEW_DATA_DIR"
python3 scripts/build_prediction_review_inputs.py \
  --in "$REVIEW_DATA_DIR" --out "$REVIEW_DATA_DIR"
Rscript scripts/run_numeric_forensics.R \
  --in "$REVIEW_DATA_DIR" --out "$REVIEW_REPORT_DIR" --scrutiny-seq false
python3 scripts/extract_visual.py \
  --report "$REPORT_PATH" --study-id "$STUDY_ID" --out "$REVIEW_DATA_DIR"
python3 scripts/build_visual_inputs.py \
  --in "$REVIEW_DATA_DIR" --out "$REVIEW_DATA_DIR"
Rscript scripts/run_visual_forensics.R \
  --in "$REVIEW_DATA_DIR" --out "$REVIEW_REPORT_DIR"
Rscript scripts/run_prediction_review_forensics.R \
  --in "$REVIEW_DATA_DIR" --out "$REVIEW_REPORT_DIR"
for artifact in "$REVIEW_REPORT_DIR"/*; do
  if [ -f "$artifact" ]; then
    python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" --artifact "$artifact"
  fi
done
python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" \
  --stage "$CURRENT_STAGE" --status completed

if [ "$RENDER_REPORT" = true ]; then
  CURRENT_STAGE="prediction_validation_report"
  python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" \
    --stage "$CURRENT_STAGE" --status running
  (
    cd "$REVIEW_REPORT_DIR"
    REVIEW_STUDY_ID="$STUDY_ID" REVIEW_REPORTS_ROOT="$REVIEW_REPORT_DIR" \
      REVIEW_PROCESSED_ROOT="$REVIEW_DATA_DIR" \
      quarto render "$REPO_ROOT/notebooks/prediction_validation_review.qmd" \
      --to pdf --output "${STUDY_ID}_prediction_validation_review_v1.pdf"
  )
  python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" \
    --artifact "$REVIEW_REPORT_DIR/${STUDY_ID}_prediction_validation_review_v1.pdf"
  python3 scripts/forensics_run.py update --manifest "$RUN_MANIFEST" \
    --stage "$CURRENT_STAGE" --status completed
fi
printf 'Completed private review run: %s\n' "$RUN_ROOT"
