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
    stop("Usage: run_visual_forensics.R --in <input_dir> --out <output_dir>")
  }
  parsed
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir

  checks_path <- file.path(in_dir, "inputs", "visual_checks_input.csv")
  digitized_path <- file.path(in_dir, "inputs", "plot_digitized_values.csv")
  if (!file.exists(checks_path)) {
    stop("Missing input file: ", checks_path)
  }

  checks <- read_csv(checks_path, show_col_types = FALSE)
  digitized <- if (file.exists(digitized_path)) {
    read_csv(digitized_path, show_col_types = FALSE)
  } else {
    tibble::tibble(
      study_id = character(),
      figure_id = character(),
      panel_id = character(),
      series_id = character(),
      x_value = numeric(),
      y_value = numeric(),
      x_unit = character(),
      y_unit = character(),
      source_image = character(),
      digitizer = character(),
      digitized_at = character(),
      extract_confidence = character()
    )
  }
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(checks, file.path(out_dir, "visual_row_results.csv"))
  write_csv(digitized, file.path(out_dir, "visual_digitized_values.csv"))

  n_figures <- as.integer(checks$n_figure_mentions[[1]])
  n_dupes <- as.integer(checks$n_duplicate_pairs[[1]])
  n_gaps <- as.integer(checks$n_numbering_gaps[[1]])
  n_digitized_figures <- if ("n_digitized_figures" %in% names(checks)) {
    as.integer(checks$n_digitized_figures[[1]])
  } else {
    0L
  }
  n_digitized_series <- if ("n_digitized_series" %in% names(checks)) {
    as.integer(checks$n_digitized_series[[1]])
  } else {
    0L
  }
  n_digitized_points <- if ("n_digitized_points" %in% names(checks)) {
    as.integer(checks$n_digitized_points[[1]])
  } else {
    0L
  }
  digitization_ready <- if ("digitization_ready" %in% names(checks)) {
    as.logical(checks$digitization_ready[[1]])
  } else {
    FALSE
  }
  summary_tbl <- tibble::tibble(
    trial_id = checks$trial_id[[1]],
    n_figure_mentions = n_figures,
    n_duplicate_pairs = n_dupes,
    near_duplicate_rate = if (!is.na(n_figures) && n_figures > 0) n_dupes / n_figures else NA_real_,
    n_numbering_gaps = n_gaps,
    numbering_gap_flag = !is.na(n_gaps) && n_gaps > 0,
    n_digitized_figures = n_digitized_figures,
    n_digitized_series = n_digitized_series,
    n_digitized_points = n_digitized_points,
    digitization_ready = digitization_ready
  )
  write_csv(summary_tbl, file.path(out_dir, "visual_summary.csv"))

  cat("Wrote ", file.path(out_dir, "visual_row_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "visual_digitized_values.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "visual_summary.csv"), "\n", sep = "")
}

main()
