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
    stop("Usage: run_registration_forensics.R --in <input_dir> --out <output_dir>")
  }
  parsed
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir

  checks_path <- file.path(in_dir, "inputs", "registration_checks_input.csv")
  if (!file.exists(checks_path)) {
    stop("Missing input file: ", checks_path)
  }

  checks <- read_csv(checks_path, show_col_types = FALSE) %>%
    mutate(
      match_status = as.logical(match_status),
      mismatch_flag = as.logical(mismatch_flag)
    )

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(checks, file.path(out_dir, "registration_row_results.csv"))

  n_claims <- nrow(checks)
  n_mismatch <- sum(checks$mismatch_flag, na.rm = TRUE)
  n_missing <- sum(checks$is_missing_report | checks$is_missing_protocol, na.rm = TRUE)

  summary_tbl <- tibble::tibble(
    trial_id = if (n_claims > 0) checks$trial_id[[1]] else NA_character_,
    n_claims = n_claims,
    n_mismatch = n_mismatch,
    mismatch_rate = if (n_claims > 0) n_mismatch / n_claims else NA_real_,
    n_missing = n_missing,
    missing_rate = if (n_claims > 0) n_missing / n_claims else NA_real_
  )
  write_csv(summary_tbl, file.path(out_dir, "registration_summary.csv"))

  cat("Wrote ", file.path(out_dir, "registration_row_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "registration_summary.csv"), "\n", sep = "")
}

main()
