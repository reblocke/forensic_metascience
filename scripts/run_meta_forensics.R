#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
})

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(in_dir = NULL, out_dir = NULL)
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--in", "--out")) {
      if (i == length(args)) {
        stop("Missing value for ", key)
      }
      value <- args[[i + 1L]]
      if (key == "--in") {
        parsed$in_dir <- value
      } else {
        parsed$out_dir <- value
      }
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$in_dir) || is.null(parsed$out_dir)) {
    stop("Usage: run_meta_forensics.R --in <input_dir> --out <output_dir>")
  }
  parsed
}

risk_tier <- function(score) {
  if (is.na(score)) {
    return("insufficient_data")
  }
  if (score < 0.20) {
    return("low")
  }
  if (score < 0.45) {
    return("moderate")
  }
  "high"
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir

  scores_path <- file.path(in_dir, "inputs", "meta_category_scores.csv")
  if (!file.exists(scores_path)) {
    stop("Missing input file: ", scores_path)
  }

  scores <- read_csv(scores_path, show_col_types = FALSE)
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  if (!"anomaly_score" %in% colnames(scores)) {
    stop("Expected `anomaly_score` column in ", scores_path)
  }

  weights <- c(randomization = 1.0, numeric = 1.0, registration = 0.8, visual = 0.8)
  scores <- scores %>%
    mutate(weight = dplyr::coalesce(weights[category], 1.0))
  valid <- scores %>% filter(!is.na(anomaly_score))

  if (nrow(valid) == 0) {
    overall_score <- NA_real_
  } else {
    overall_score <- sum(valid$anomaly_score * valid$weight) / sum(valid$weight)
  }
  overall <- tibble::tibble(
    overall_score = overall_score,
    risk_tier = risk_tier(overall_score),
    n_categories = nrow(valid)
  )

  write_csv(scores, file.path(out_dir, "meta_category_scores_out.csv"))
  write_csv(overall, file.path(out_dir, "meta_overall_summary.csv"))

  cat("Wrote ", file.path(out_dir, "meta_category_scores_out.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "meta_overall_summary.csv"), "\n", sep = "")
}

main()
