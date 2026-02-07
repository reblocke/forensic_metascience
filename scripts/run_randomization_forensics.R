#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
})

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(
    in_dir = NULL,
    out_dir = NULL,
    m = 10000L,
    plot_flag = FALSE
  )
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--in", "--out", "--m", "--plot")) {
      if (i == length(args)) {
        stop("Missing value for ", key)
      }
      value <- args[[i + 1L]]
      if (key == "--in") {
        parsed$in_dir <- value
      } else if (key == "--out") {
        parsed$out_dir <- value
      } else if (key == "--m") {
        parsed$m <- as.integer(value)
      } else if (key == "--plot") {
        parsed$plot_flag <- as.logical(tolower(value) %in% c("true", "1", "yes"))
      }
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$in_dir) || is.null(parsed$out_dir)) {
    stop("Usage: run_randomization_forensics.R --in <input_dir> --out <output_dir> [--m 10000] [--plot false]")
  }
  parsed
}

clip_p <- function(x) {
  pmax(pmin(x, 1 - 1e-16), 1e-16)
}

stouffer_upper <- function(p_values) {
  p_values <- p_values[!is.na(p_values)]
  p_values <- clip_p(p_values)
  if (length(p_values) == 0L) {
    return(NA_real_)
  }
  z_values <- qnorm(1 - p_values)
  1 - pnorm(sum(z_values) / sqrt(length(z_values)))
}

fisher_combined <- function(p_values) {
  p_values <- p_values[!is.na(p_values)]
  p_values <- clip_p(p_values)
  if (length(p_values) == 0L) {
    return(NA_real_)
  }
  stat <- -2 * sum(log(p_values))
  pchisq(stat, df = 2 * length(p_values), lower.tail = FALSE)
}

ensure_simdistr <- function() {
  if (requireNamespace("simdistr", quietly = TRUE)) {
    return(invisible(TRUE))
  }
  r_major <- R.version$major
  r_minor <- strsplit(R.version$minor, "\\.")[[1]][1]
  user_lib <- file.path(Sys.getenv("HOME"), "Library", "R", paste0(r_major, ".", r_minor), "library")
  if (dir.exists(user_lib)) {
    .libPaths(c(user_lib, .libPaths()))
  }
  if (!requireNamespace("simdistr", quietly = TRUE)) {
    stop(
      "Package `simdistr` not available. Install with:\n",
      "Rscript -e \"install.packages('simdistr', repos='https://cloud.r-project.org', ",
      "lib=paste0(Sys.getenv('HOME'), '/Library/R/4.5/library'))\""
    )
  }
}

build_simdistr_runtime <- function(csf_input) {
  runtime_long <- csf_input %>%
    mutate(variable_id = row_number()) %>%
    select(trial_id, variable_id, n_arm1, n_arm2, prop_arm1, prop_arm2) %>%
    pivot_longer(
      cols = c(n_arm1, n_arm2, prop_arm1, prop_arm2),
      names_to = c(".value", "arm"),
      names_pattern = "(n|prop)_arm(1|2)"
    ) %>%
    mutate(
      trial = 1L,
      variable = as.integer(variable_id),
      group = as.integer(arm),
      participants = as.integer(n),
      mean = as.numeric(prop),
      sd = NA_real_,
      decimals = 3L,
      type = 2L,
      name = as.character(trial_id)
    ) %>%
    select(trial, variable, group, participants, mean, sd, decimals, type, name)

  as.data.frame(runtime_long)
}

parse_simdistr_output <- function(output_lines) {
  idx_var <- which(grepl("^P-values for each variable", output_lines))
  idx_combined <- which(grepl("^Combined \\(overall\\) p-values", output_lines))
  if (length(idx_var) == 0L || length(idx_combined) == 0L) {
    stop("Could not parse simdistr output tables.")
  }

  var_lines <- output_lines[(idx_var[1] + 1L):(idx_combined[1] - 2L)]
  var_lines <- var_lines[nzchar(trimws(var_lines))]
  if (length(var_lines) < 2L) {
    stop("Variable-level simdistr output table is empty.")
  }
  var_headers <- character()
  row_values <- list()
  for (line in var_lines) {
    clean <- trimws(line)
    if (!nzchar(clean)) {
      next
    }
    if (grepl("^V\\d+", clean)) {
      header_tokens <- unlist(regmatches(clean, gregexpr("V\\d+", clean)))
      var_headers <- c(var_headers, header_tokens)
      next
    }
    tokens <- strsplit(clean, "\\s+")[[1]]
    if (length(tokens) < 2L) {
      next
    }
    trial_name <- tokens[1]
    values <- suppressWarnings(as.numeric(tokens[-1]))
    if (!trial_name %in% names(row_values)) {
      row_values[[trial_name]] <- numeric()
    }
    row_values[[trial_name]] <- c(row_values[[trial_name]], values)
  }
  if (length(var_headers) == 0L || length(row_values) == 0L) {
    stop("Could not parse variable-level simdistr values.")
  }
  variable_table <- as.data.frame(
    do.call(rbind, lapply(row_values, function(x) {
      x[seq_len(length(var_headers))]
    }))
  )
  colnames(variable_table) <- var_headers
  rownames(variable_table) <- names(row_values)

  combined_lines <- output_lines[(idx_combined[1] + 1L):length(output_lines)]
  combined_lines <- combined_lines[nzchar(trimws(combined_lines))]
  if (length(combined_lines) < 2L) {
    stop("Combined simdistr output table is empty.")
  }
  combined_table <- read.table(
    text = paste(combined_lines, collapse = "\n"),
    header = TRUE,
    check.names = FALSE,
    row.names = 1
  )

  list(variable_table = variable_table, combined_table = combined_table)
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir
  m <- args$m
  plot_flag <- args$plot_flag

  csf_path <- file.path(in_dir, "csf_input.csv")
  if (!file.exists(csf_path)) {
    stop("Missing input file: ", csf_path)
  }

  csf_input <- read_csv(csf_path, show_col_types = FALSE) %>%
    mutate(
      reported_p = as.numeric(reported_p),
      row_chisq_p = as.numeric(row_chisq_p)
    )

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  row_results <- csf_input %>%
    mutate(
      abs_p_delta = abs(reported_p - row_chisq_p),
      flagged_p_delta_0_05 = abs_p_delta >= 0.05
    )
  write_csv(row_results, file.path(out_dir, "row_level_results.csv"))

  pooled <- tibble::tibble(
    trial_id = unique(csf_input$trial_id)[1],
    n_rows_reported = sum(!is.na(csf_input$reported_p)),
    n_rows_recalc = sum(!is.na(csf_input$row_chisq_p)),
    stouffer_reported = stouffer_upper(csf_input$reported_p),
    stouffer_recalc = stouffer_upper(csf_input$row_chisq_p),
    fisher_reported = fisher_combined(csf_input$reported_p),
    fisher_recalc = fisher_combined(csf_input$row_chisq_p)
  )
  write_csv(pooled, file.path(out_dir, "pooled_pvalues.csv"))

  ensure_simdistr()
  sim_runtime <- build_simdistr_runtime(csf_input)
  write_csv(sim_runtime, file.path(out_dir, "simdistr_runtime_input.csv"))

  sim_output <- capture.output(
    simdistr::sim_distr(m = m, dataframe = sim_runtime, plot_flag = plot_flag)
  )
  writeLines(sim_output, con = file.path(out_dir, "simdistr_stdout.txt"))

  parsed <- parse_simdistr_output(sim_output)

  variable_df <- as.data.frame(parsed$variable_table)
  variable_df$trial_name <- rownames(variable_df)
  variable_long <- variable_df %>%
    pivot_longer(
      cols = starts_with("V"),
      names_to = "variable_id",
      values_to = "simdistr_pvalue"
    ) %>%
    mutate(variable_id = as.integer(sub("^V", "", variable_id)))

  variable_map <- csf_input %>%
    mutate(variable_id = dplyr::row_number()) %>%
    select(variable_id, variable, level)

  variable_long <- variable_long %>%
    left_join(variable_map, by = "variable_id")
  write_csv(variable_long, file.path(out_dir, "simdistr_variable_pvalues.csv"))

  combined_df <- as.data.frame(parsed$combined_table)
  combined_df$trial_name <- rownames(combined_df)
  names(combined_df)[1] <- "simdistr_combined_pvalue"
  write_csv(combined_df, file.path(out_dir, "simdistr_combined_pvalues.csv"))

  cat("Wrote ", file.path(out_dir, "row_level_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "pooled_pvalues.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "simdistr_runtime_input.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "simdistr_stdout.txt"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "simdistr_variable_pvalues.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "simdistr_combined_pvalues.csv"), "\n", sep = "")
}

main()
