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

logical_or_na <- function(x) {
  text <- tolower(trimws(as.character(x)))
  dplyr::case_when(
    text %in% c("true", "t", "1", "yes") ~ TRUE,
    text %in% c("false", "f", "0", "no") ~ FALSE,
    TRUE ~ NA
  )
}

first_claim_status <- function(checks, target_claim_id) {
  rows <- checks %>% filter(.data$claim_id == .env$target_claim_id)
  if (nrow(rows) == 0) {
    return(NA_character_)
  }
  rows$assessment_status[[1]]
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir

  checks_path <- file.path(in_dir, "inputs", "registration_checks_input.csv")
  if (!file.exists(checks_path)) {
    stop("Missing input file: ", checks_path)
  }

  checks <- read_csv(checks_path, show_col_types = FALSE)
  if (!("claim_id" %in% names(checks)) && "claim" %in% names(checks)) {
    checks$claim_id <- checks$claim
  }
  if (!("assessment_status" %in% names(checks))) {
    checks$assessment_status <- ifelse(logical_or_na(checks$match_status), "match", "mismatch")
  }
  if (!("assessed_flag" %in% names(checks))) {
    checks$assessed_flag <- checks$assessment_status %in% c("match", "mismatch")
  }
  checks <- checks %>%
    mutate(
      match_status = logical_or_na(.data$match_status),
      mismatch_flag = .data$assessment_status == "mismatch",
      assessed_flag = .data$assessment_status %in% c("match", "mismatch"),
      is_missing_report = as.logical(.data$is_missing_report),
      is_missing_protocol = as.logical(.data$is_missing_protocol)
    )

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(checks, file.path(out_dir, "registration_row_results.csv"))

  history_path <- file.path(in_dir, "inputs", "registration_history_events.csv")
  if (file.exists(history_path)) {
    history_events <- read_csv(history_path, show_col_types = FALSE)
  } else {
    history_events <- tibble::tibble(
      study_id = character(),
      registry_id = character(),
      event_id = character(),
      event_date = character(),
      registry_field = character(),
      old_value = character(),
      new_value = character(),
      change_type = character(),
      severity = character(),
      notes = character()
    )
  }
  write_csv(history_events, file.path(out_dir, "registration_history_events.csv"))

  n_claims <- nrow(checks)
  n_assessed <- sum(checks$assessed_flag, na.rm = TRUE)
  n_mismatch <- sum(checks$mismatch_flag, na.rm = TRUE)
  n_missing <- sum(checks$is_missing_report | checks$is_missing_protocol, na.rm = TRUE)
  n_indeterminate <- sum(checks$assessment_status == "indeterminate", na.rm = TRUE)
  n_not_assessed <- sum(checks$assessment_status == "not_assessed", na.rm = TRUE)

  prospective_rows <- checks %>% filter(.data$claim_id == "clinicaltrials_prospective_registration")
  prospective_status <- if (nrow(prospective_rows) == 0) {
    NA_character_
  } else if (isTRUE(prospective_rows$match_status[[1]])) {
    "prospective"
  } else if (identical(prospective_rows$match_status[[1]], FALSE)) {
    "retrospective"
  } else {
    prospective_rows$assessment_status[[1]]
  }

  summary_tbl <- tibble::tibble(
    trial_id = if (n_claims > 0) checks$trial_id[[1]] else NA_character_,
    n_claims = n_claims,
    n_claims_total = n_claims,
    n_claims_assessed = n_assessed,
    n_not_assessed = n_not_assessed,
    n_indeterminate = n_indeterminate,
    n_mismatch = n_mismatch,
    mismatch_rate = if (n_assessed > 0) n_mismatch / n_assessed else NA_real_,
    n_missing = n_missing,
    missing_rate = if (n_claims > 0) n_missing / n_claims else NA_real_,
    prospective_registration_status = prospective_status,
    n_major_registry_history_changes = sum(
      history_events$change_type == "value_changed" &
        history_events$severity %in% c("medium", "high"),
      na.rm = TRUE
    ),
    results_overdue_flag = identical(
      first_claim_status(checks, "clinicaltrials_results_overdue"),
      "mismatch"
    ),
    publication_link_missing_flag = identical(
      first_claim_status(checks, "clinicaltrials_publication_linkage"),
      "mismatch"
    )
  )
  write_csv(summary_tbl, file.path(out_dir, "registration_summary.csv"))

  cat("Wrote ", file.path(out_dir, "registration_row_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "registration_summary.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "registration_history_events.csv"), "\n", sep = "")
}

main()
