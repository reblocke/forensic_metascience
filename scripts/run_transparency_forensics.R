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
    stop("Usage: run_transparency_forensics.R --in <input_dir> --out <output_dir>")
  }
  parsed
}

read_optional <- function(path) {
  if (file.exists(path)) {
    read_csv(path, show_col_types = FALSE)
  } else {
    tibble::tibble()
  }
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir

  checks_path <- file.path(in_dir, "inputs", "transparency_checks_input.csv")
  if (!file.exists(checks_path)) {
    stop("Missing input file: ", checks_path)
  }

  checks <- read_csv(checks_path, show_col_types = FALSE)
  if (nrow(checks) != 1) {
    stop("Expected one transparency checks row in ", checks_path)
  }

  open_practices <- read_optional(file.path(in_dir, "inputs", "transparency_open_practices.csv"))
  repository_links <- read_optional(file.path(in_dir, "inputs", "transparency_repository_links.csv"))
  preregistration_links <- read_optional(file.path(in_dir, "inputs", "transparency_preregistration_links.csv"))
  urls <- read_optional(file.path(in_dir, "inputs", "transparency_urls.csv"))
  sources <- read_optional(file.path(in_dir, "inputs", "research_object_sources.csv"))

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  write_csv(checks, file.path(out_dir, "transparency_row_results.csv"))
  write_csv(open_practices, file.path(out_dir, "transparency_open_practices.csv"))
  write_csv(repository_links, file.path(out_dir, "transparency_repository_links.csv"))
  write_csv(preregistration_links, file.path(out_dir, "transparency_preregistration_links.csv"))
  write_csv(urls, file.path(out_dir, "transparency_urls.csv"))
  write_csv(sources, file.path(out_dir, "research_object_sources.csv"))

  summary_tbl <- checks %>%
    transmute(
      study_id = study_id,
      n_source_files = n_source_files,
      n_pages = n_pages,
      n_urls = n_urls,
      n_repository_links = n_repository_links,
      n_preregistration_links = n_preregistration_links,
      n_availability_statements = n_availability_statements,
      data_statement_detected = data_statement_detected,
      code_statement_detected = code_statement_detected,
      materials_statement_detected = materials_statement_detected,
      registration_statement_detected = registration_statement_detected,
      on_request_statement_detected = on_request_statement_detected,
      transparency_evidence_burden = transparency_evidence_burden,
      external_network_used = external_network_used,
      llm_used = llm_used,
      metacheck_dependency_used = metacheck_dependency_used
    )
  write_csv(summary_tbl, file.path(out_dir, "transparency_summary.csv"))

  cat("Wrote ", file.path(out_dir, "transparency_row_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "transparency_summary.csv"), "\n", sep = "")
}

main()
