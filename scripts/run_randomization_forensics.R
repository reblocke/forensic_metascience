#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
})

parse_integer_arg <- function(value, key) {
  if (!grepl("^[+-]?[0-9]+$", value)) stop(key, " must be an integer")
  parsed <- suppressWarnings(as.integer(value))
  if (is.na(parsed)) stop(key, " is outside the supported integer range")
  parsed
}

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(
    in_dir = NULL,
    out_dir = NULL,
    m = 10000L,
    plot_flag = FALSE,
    allocation_design = "unknown",
    expert_opt_in = FALSE,
    seed = NA_integer_,
    allocation_counts_basis = "unknown",
    allocation_n_arm1 = NA_integer_,
    allocation_n_arm2 = NA_integer_,
    strata_count = NA_integer_,
    list_count = NA_integer_
  )
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c(
      "--in", "--out", "--m", "--plot", "--allocation-design", "--expert-opt-in",
      "--seed", "--allocation-counts-basis", "--allocation-n-arm1", "--allocation-n-arm2",
      "--strata-count", "--list-count"
    )) {
      if (i == length(args)) {
        stop("Missing value for ", key)
      }
      value <- args[[i + 1L]]
      if (key == "--in") {
        parsed$in_dir <- value
      } else if (key == "--out") {
        parsed$out_dir <- value
      } else if (key == "--m") {
        parsed$m <- parse_integer_arg(value, key)
      } else if (key == "--plot") {
        parsed$plot_flag <- as.logical(tolower(value) %in% c("true", "1", "yes"))
      } else if (key == "--allocation-design") {
        parsed$allocation_design <- value
      } else if (key == "--expert-opt-in") {
        normalized <- tolower(value)
        if (!normalized %in% c("true", "false", "1", "0", "yes", "no")) {
          stop("--expert-opt-in must be true or false")
        }
        parsed$expert_opt_in <- normalized %in% c("true", "1", "yes")
      } else if (key == "--seed") {
        parsed$seed <- parse_integer_arg(value, key)
      } else if (key == "--allocation-counts-basis") {
        parsed$allocation_counts_basis <- value
      } else if (key == "--allocation-n-arm1") {
        parsed$allocation_n_arm1 <- parse_integer_arg(value, key)
      } else if (key == "--allocation-n-arm2") {
        parsed$allocation_n_arm2 <- parse_integer_arg(value, key)
      } else if (key == "--strata-count") {
        parsed$strata_count <- parse_integer_arg(value, key)
      } else if (key == "--list-count") {
        parsed$list_count <- parse_integer_arg(value, key)
      }
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$in_dir) || is.null(parsed$out_dir)) {
    stop("Usage: run_randomization_forensics.R --in <input_dir> --out <output_dir> [design and opt-in options]")
  }
  valid_designs <- c(
    "unknown", "mrn_parity", "unrestricted_individual_1to1",
    "fixed_block_4_single_list_1to1", "clustered", "stratified", "crossover",
    "multiple_arms", "quasi_randomized", "other"
  )
  if (!parsed$allocation_design %in% valid_designs) {
    stop("Unsupported allocation design label: ", parsed$allocation_design)
  }
  if (!parsed$allocation_counts_basis %in% c("unknown", "randomized", "post_exclusion")) {
    stop("--allocation-counts-basis must be unknown, randomized, or post_exclusion")
  }
  if (!is.finite(parsed$m) || parsed$m < 1L) stop("--m must be a positive integer")
  if (parsed$expert_opt_in && is.na(parsed$seed)) {
    stop("--seed is required with --expert-opt-in true")
  }
  parsed
}

pearson_2x2_pvalue <- function(a, b, c, d) {
  values <- c(a, b, c, d)
  if (any(!is.finite(values)) || any(values < 0)) return(NA_real_)
  total <- sum(values)
  denominator <- (a + b) * (c + d) * (a + c) * (b + d)
  if (total <= 0 || denominator == 0) return(NA_real_)
  statistic <- total * (a * d - b * c)^2 / denominator
  stats::pchisq(statistic, df = 1, lower.tail = FALSE)
}

ensure_simdistr <- function() {
  requireNamespace("simdistr", quietly = TRUE)
}

build_simdistr_runtime <- function(csf_input) {
  runtime_long <- csf_input %>%
    arrange(recalculated_test_id) %>%
    mutate(variable_id = row_number()) %>%
    select(
      trial_id, variable_id, recalculated_test_id, n_arm1, n_arm2, prop_arm1, prop_arm2,
      reported_percent_raw_arm1, reported_percent_raw_arm2,
      reported_percent_decimals_arm1, reported_percent_decimals_arm2
    ) %>%
    pivot_longer(
      cols = c(
        n_arm1, n_arm2, prop_arm1, prop_arm2,
        reported_percent_raw_arm1, reported_percent_raw_arm2,
        reported_percent_decimals_arm1, reported_percent_decimals_arm2
      ),
      names_to = c(".value", "arm"),
      names_pattern = "(n|prop|reported_percent_raw|reported_percent_decimals)_arm(1|2)"
    ) %>%
    mutate(
      trial = 1L,
      variable = as.integer(variable_id),
      group = as.integer(arm),
      participants = as.integer(n),
      mean = as.numeric(reported_percent_raw) / 100,
      sd = NA_real_,
      decimals = as.integer(reported_percent_decimals) + 2L,
      type = 2L,
      name = as.character(trial_id)
    ) %>%
    select(trial, variable, group, participants, mean, sd, decimals, type, name)

  as.data.frame(runtime_long)
}

allocation_arithmetic_result <- function(args) {
  status <- "unsupported_design"
  reason <- "allocation design is not the supported fixed-block-4 single-list 1:1 case"
  total <- NA_integer_
  remainder <- NA_integer_
  difference <- NA_integer_
  allowed <- NA_character_
  if (args$allocation_design == "fixed_block_4_single_list_1to1") {
    if (args$allocation_counts_basis != "randomized") {
      status <- "unsupported_count_basis"
      reason <- "allocation arithmetic requires counts before post-randomization exclusions"
    } else if (is.na(args$strata_count) || is.na(args$list_count) ||
               args$strata_count != 1L || args$list_count != 1L) {
      status <- "unsupported_structure"
      reason <- "only one unstratified allocation list is supported"
    } else if (is.na(args$allocation_n_arm1) || is.na(args$allocation_n_arm2) ||
               args$allocation_n_arm1 < 1L || args$allocation_n_arm2 < 1L) {
      status <- "missing_allocation_counts"
      reason <- "explicit positive randomized counts for both arms are required"
    } else {
      total <- args$allocation_n_arm1 + args$allocation_n_arm2
      remainder <- total %% 4L
      difference <- abs(args$allocation_n_arm1 - args$allocation_n_arm2)
      allowed_values <- switch(
        as.character(remainder),
        "0" = 0L,
        "1" = 1L,
        "2" = c(0L, 2L),
        "3" = 1L
      )
      allowed <- paste(allowed_values, collapse = ",")
      if (difference %in% allowed_values) {
        status <- "consistent_with_design"
        reason <- "observed randomized counts satisfy the fixed-block-4 incomplete-block bound"
      } else {
        status <- "incompatible_with_design"
        reason <- "observed randomized count difference exceeds the fixed-block-4 bound"
      }
    }
  }
  tibble::tibble(
    allocation_design = args$allocation_design,
    counts_basis = args$allocation_counts_basis,
    n_arm1 = args$allocation_n_arm1,
    n_arm2 = args$allocation_n_arm2,
    total = total,
    terminal_block_size = remainder,
    absolute_difference = difference,
    allowed_absolute_differences = allowed,
    strata_count = args$strata_count,
    list_count = args$list_count,
    status = status,
    reason = reason
  )
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

  csf_path <- file.path(in_dir, "csf_input_v3.csv")
  if (!file.exists(csf_path)) {
    stop("Missing input file: ", csf_path)
  }

  csf_input <- read_csv(csf_path, show_col_types = FALSE) %>%
    arrange(recalculated_test_id)
  if (any(csf_input$schema_version != "baseline_csf_v3")) {
    stop("Unsupported CSF input schema; expected baseline_csf_v3.")
  }
  reported_path <- file.path(in_dir, "reported_tests_v1.csv")
  if (!file.exists(reported_path)) stop("Missing input file: ", reported_path)
  reported_tests <- read_csv(reported_path, show_col_types = FALSE)
  if (any(reported_tests$schema_version != "reported_test_v1")) {
    stop("Unsupported reported-test schema; expected reported_test_v1.")
  }

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  recalc_status <- if (args$allocation_design != "unrestricted_individual_1to1") {
    "unsupported_design"
  } else if (!args$expert_opt_in) {
    "not_requested"
  } else {
    "evaluated"
  }
  row_results <- csf_input %>%
    mutate(
      row_chisq_p = if (recalc_status == "evaluated") {
        mapply(
          pearson_2x2_pvalue,
          count_arm1,
          n_arm1 - count_arm1,
          count_arm2,
          n_arm2 - count_arm2
        )
      } else {
        NA_real_
      },
      recalculated_p_status = recalc_status,
      comparison_status = if_else(
        is.na(reported_test_id), "no_reported_test", "not_comparable"
      ),
      comparison_reason = if_else(
        is.na(reported_test_id),
        "no reported variable test was extracted",
        "reported test scope, method, tail, and population are unknown"
      ),
      flagged_p_delta_0_05 = NA
    )
  write_csv(row_results, file.path(out_dir, "row_level_results_v2.csv"))
  write_csv(reported_tests, file.path(out_dir, "reported_test_records_v1.csv"))

  pooled <- tibble::tibble(
    trial_id = if (nrow(csf_input) > 0) csf_input$trial_id[[1]] else NA_character_,
    n_reported_tests = nrow(reported_tests),
    n_rows_recalc = sum(!is.na(row_results$row_chisq_p)),
    status = "descriptive_only",
    interpretation = "not_calibrated_dependence_unknown"
  )
  write_csv(pooled, file.path(out_dir, "pooled_descriptive_v2.csv"))

  sim_status <- "not_requested"
  sim_reason <- "expert opt-in was not supplied"
  simdistr_version <- NA_character_
  sim_variable <- tibble::tibble(
    execution_status = sim_status,
    reason = sim_reason
  )
  sim_combined <- tibble::tibble(
    execution_status = sim_status,
    reason = sim_reason,
    interpretation = "uncalibrated_dependence_unknown"
  )
  if (args$expert_opt_in) {
    if (args$allocation_design != "unrestricted_individual_1to1") {
      sim_status <- "unsupported_design"
      sim_reason <- "simdistr runtime supports only explicitly declared unstratified individual 1:1 allocation"
    } else if (!all(is.finite(csf_input$reported_percent_decimals_arm1)) ||
               !all(is.finite(csf_input$reported_percent_decimals_arm2))) {
      sim_status <- "blocked_precision_unknown"
      sim_reason <- "source-reported percentage precision is required; precision is not inferred"
    } else {
      sim_runtime <- build_simdistr_runtime(csf_input)
      write_csv(sim_runtime, file.path(out_dir, "simdistr_runtime_input_v1.csv"))
      if (!ensure_simdistr()) {
        sim_status <- "dependency_missing"
        sim_reason <- "R package simdistr is unavailable"
      } else {
        sim_status <- "completed"
        sim_reason <- "expert opt-in with supported explicit allocation design"
        simdistr_version <- as.character(utils::packageVersion("simdistr"))
        RNGkind("Mersenne-Twister", "Inversion", "Rejection")
        set.seed(args$seed)
        sim_output <- capture.output(
          simdistr::sim_distr(m = m, dataframe = sim_runtime, plot_flag = plot_flag)
        )
        writeLines(sim_output, con = file.path(out_dir, "simdistr_stdout_v1.txt"))
        parsed <- parse_simdistr_output(sim_output)
        variable_df <- as.data.frame(parsed$variable_table)
        variable_df$trial_name <- rownames(variable_df)
        sim_variable <- variable_df %>%
          pivot_longer(
            cols = starts_with("V"),
            names_to = "variable_id",
            values_to = "simdistr_pvalue"
          ) %>%
          mutate(variable_id = as.integer(sub("^V", "", variable_id))) %>%
          left_join(
            csf_input %>% arrange(recalculated_test_id) %>%
              mutate(variable_id = dplyr::row_number()) %>%
              select(variable_id, recalculated_test_id, variable, level),
            by = "variable_id"
          ) %>%
          mutate(execution_status = "completed")
        combined_df <- as.data.frame(parsed$combined_table)
        combined_df$trial_name <- rownames(combined_df)
        names(combined_df)[1] <- "simdistr_combined_pvalue"
        sim_combined <- tibble::as_tibble(combined_df) %>%
          mutate(
            execution_status = "completed",
            interpretation = "uncalibrated_dependence_unknown"
          )
      }
    }
  }
  sim_variable$execution_status <- sim_status
  sim_variable$reason <- sim_reason
  sim_combined$execution_status <- sim_status
  sim_combined$reason <- sim_reason
  write_csv(sim_variable, file.path(out_dir, "simdistr_variable_pvalues_v1.csv"))
  write_csv(sim_combined, file.path(out_dir, "simdistr_combined_descriptive_v1.csv"))

  allocation <- allocation_arithmetic_result(args)
  write_csv(allocation, file.path(out_dir, "allocation_arithmetic_v1.csv"))

  receipt <- tibble::tibble(
    schema_version = "baseline_randomization_receipt_v1",
    method_revision = "baseline_design_gate_v2",
    allocation_design = args$allocation_design,
    expert_opt_in = args$expert_opt_in,
    seed = args$seed,
    rng_kind = paste(RNGkind(), collapse = "/"),
    R_version = as.character(getRversion()),
    simdistr_version = simdistr_version,
    simulation_size = m,
    inferential_diagnostic_status = sim_status,
    inferential_diagnostic_reason = sim_reason
  )
  write_csv(receipt, file.path(out_dir, "randomization_run_receipt_v1.csv"))

  cat("Wrote ", file.path(out_dir, "row_level_results_v2.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "pooled_descriptive_v2.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "reported_test_records_v1.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "allocation_arithmetic_v1.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "randomization_run_receipt_v1.csv"), "\n", sep = "")
  if (file.exists(file.path(out_dir, "simdistr_runtime_input_v1.csv"))) {
    cat("Wrote ", file.path(out_dir, "simdistr_runtime_input_v1.csv"), "\n", sep = "")
  }
  if (file.exists(file.path(out_dir, "simdistr_stdout_v1.txt"))) {
    cat("Wrote ", file.path(out_dir, "simdistr_stdout_v1.txt"), "\n", sep = "")
  }
  cat("Wrote ", file.path(out_dir, "simdistr_variable_pvalues_v1.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "simdistr_combined_descriptive_v1.csv"), "\n", sep = "")
}

if (sys.nframe() == 0L) main()
