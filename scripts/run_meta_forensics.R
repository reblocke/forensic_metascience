#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
})

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(in_dir = NULL, out_dir = NULL, legacy_reproduction = FALSE)
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--in", "--out")) {
      if (i == length(args)) stop("Missing value for ", key)
      value <- args[[i + 1L]]
      if (key == "--in") parsed$in_dir <- value else parsed$out_dir <- value
      i <- i + 2L
    } else if (key == "--legacy-reproduction") {
      parsed$legacy_reproduction <- TRUE
      i <- i + 1L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$in_dir) || is.null(parsed$out_dir)) {
    stop("Usage: run_meta_forensics.R --in <input_dir> --out <output_dir> [--legacy-reproduction]")
  }
  parsed
}

legacy_review_priority <- function(score) {
  if (is.na(score)) return("insufficient_data")
  if (score < 0.20) return("low")
  if (score < 0.45) return("moderate")
  "high"
}

run_legacy <- function(args) {
  scores_path <- file.path(args$in_dir, "inputs", "legacy", "meta_category_scores.csv")
  provenance_path <- file.path(args$in_dir, "inputs", "legacy", "meta_legacy_provenance.csv")
  if (!file.exists(scores_path)) stop("Missing isolated legacy input: ", scores_path)
  if (!file.exists(provenance_path)) stop("Missing legacy provenance label: ", provenance_path)
  provenance <- read_csv(provenance_path, show_col_types = FALSE)
  if (nrow(provenance) != 1 || provenance$schema_version[[1]] != "legacy_composite_v1" ||
      provenance$label[[1]] != "NOT_INSPECT" || !isTRUE(provenance$legacy_only[[1]])) {
    stop("Legacy inputs lack the required legacy_composite_v1 / NOT_INSPECT label.")
  }
  scores <- read_csv(scores_path, show_col_types = FALSE)
  if (!"anomaly_score" %in% colnames(scores)) {
    stop("Expected legacy `anomaly_score` column in ", scores_path)
  }
  weights <- c(randomization = 1.0, numeric = 1.0, registration = 0.8, visual = 0.8, transparency = 0.6)
  scores <- scores %>% mutate(weight = dplyr::coalesce(weights[category], 1.0))
  valid <- scores %>% filter(!is.na(anomaly_score))
  overall_score <- if (nrow(valid) == 0) NA_real_ else {
    sum(valid$anomaly_score * valid$weight) / sum(valid$weight)
  }
  tier <- legacy_review_priority(overall_score)
  overall <- tibble::tibble(
    overall_score = overall_score,
    risk_tier = tier,
    evidence_burden_score = overall_score,
    review_priority = tier,
    n_categories = nrow(valid)
  )
  out_dir <- file.path(args$out_dir, "legacy")
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(scores, file.path(out_dir, "meta_category_scores_out.csv"))
  write_csv(overall, file.path(out_dir, "meta_overall_summary.csv"))
  write_csv(
    tibble::tibble(schema_version = "legacy_composite_v1", label = "NOT_INSPECT", legacy_only = TRUE),
    file.path(out_dir, "meta_legacy_provenance.csv")
  )
  cat("Wrote explicitly labeled legacy reproduction under ", out_dir, "\n", sep = "")
}

main <- function() {
  args <- parse_args()
  if (args$legacy_reproduction) {
    run_legacy(args)
    return(invisible(NULL))
  }

  coverage_path <- file.path(args$in_dir, "inputs", "meta_evidence_coverage_v2.csv")
  concerns_path <- file.path(args$in_dir, "inputs", "meta_candidate_concerns_v1.csv")
  if (!file.exists(coverage_path)) stop("Missing input file: ", coverage_path)
  if (!file.exists(concerns_path)) stop("Missing input file: ", concerns_path)
  coverage <- read_csv(coverage_path, show_col_types = FALSE)
  concerns <- read_csv(concerns_path, show_col_types = FALSE)
  required_coverage <- c(
    "category", "requested", "assessed", "unavailable", "failed", "unsupported",
    "n_metrics_assessed", "n_metrics_missing", "source_file"
  )
  missing <- setdiff(required_coverage, names(coverage))
  if (length(missing) > 0) stop("Coverage input missing fields: ", paste(missing, collapse = ", "))

  count_known_true <- function(column) {
    values <- coverage[[column]]
    if (anyNA(values)) NA_integer_ else sum(as.logical(values))
  }
  summary <- tibble::tibble(
    schema_version = "evidence_coverage_v2",
    n_requested = count_known_true("requested"),
    n_assessed = count_known_true("assessed"),
    n_unavailable = count_known_true("unavailable"),
    n_failed = count_known_true("failed"),
    n_unsupported = count_known_true("unsupported")
  )

  dir.create(args$out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(coverage, file.path(args$out_dir, "meta_evidence_coverage_v2_out.csv"))
  write_csv(concerns, file.path(args$out_dir, "meta_candidate_concerns_v1_out.csv"))
  write_csv(summary, file.path(args$out_dir, "meta_coverage_summary_v1.csv"))
  cat("Wrote ", file.path(args$out_dir, "meta_evidence_coverage_v2_out.csv"), "\n", sep = "")
  cat("Wrote ", file.path(args$out_dir, "meta_candidate_concerns_v1_out.csv"), "\n", sep = "")
  cat("Wrote ", file.path(args$out_dir, "meta_coverage_summary_v1.csv"), "\n", sep = "")
}

if (sys.nframe() == 0) main()
