#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tibble)
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
    stop("Usage: run_prediction_review_forensics.R --in <input_dir> --out <output_dir>")
  }
  parsed
}

welch_summary_p <- function(mean_a, sd_a, n_a, mean_b, sd_b, n_b) {
  se_sq <- (sd_a^2 / n_a) + (sd_b^2 / n_b)
  if (is.na(se_sq) || se_sq <= 0) {
    return(NA_real_)
  }
  statistic <- (mean_a - mean_b) / sqrt(se_sq)
  numerator <- se_sq^2
  denominator <- ((sd_a^2 / n_a)^2 / (n_a - 1)) + ((sd_b^2 / n_b)^2 / (n_b - 1))
  if (is.na(denominator) || denominator <= 0) {
    return(NA_real_)
  }
  df <- numerator / denominator
  2 * stats::pt(abs(statistic), df = df, lower.tail = FALSE)
}

categorical_p_value <- function(subset) {
  counts <- stats::xtabs(count ~ level + group_label, data = subset)
  if (any(dim(counts) < 2)) {
    return(list(p_value = NA_real_, method = "insufficient_levels"))
  }
  expected <- suppressWarnings(stats::chisq.test(counts, correct = FALSE)$expected)
  if (all(dim(counts) == c(2, 2)) && any(expected < 5)) {
    out <- stats::fisher.test(counts)
    return(list(p_value = as.numeric(out$p.value), method = "fisher_test"))
  }
  out <- suppressWarnings(stats::chisq.test(counts, correct = FALSE))
  list(p_value = as.numeric(out$p.value), method = "chisq_test")
}

run_table2_checks <- function(table2) {
  if (nrow(table2) == 0) {
    return(tibble())
  }

  variables <- unique(table2$variable)
  rows <- vector("list", length(variables))
  for (index in seq_along(variables)) {
    variable_name <- variables[[index]]
    subset <- table2 %>% filter(variable == variable_name)
    measure_type <- subset$measure_type[[1]]
    reported_p <- suppressWarnings(as.numeric(subset$p_reported[[1]]))

    if (measure_type == "categorical_count_percent") {
      calc <- categorical_p_value(subset)
      recomputed_p <- calc$p_value
      method_used <- calc$method
      reproducible <- TRUE
      note <- paste("Based on", method_used)
    } else if (measure_type == "continuous_mean_sd") {
      if (nrow(subset) != 2) {
        recomputed_p <- NA_real_
        method_used <- "invalid_mean_sd_rows"
        reproducible <- FALSE
        note <- "Expected exactly two group rows for mean/SD comparison."
      } else {
        first <- subset[1, ]
        second <- subset[2, ]
        recomputed_p <- welch_summary_p(
          mean_a = first$mean,
          sd_a = first$sd,
          n_a = first$n_group,
          mean_b = second$mean,
          sd_b = second$sd,
          n_b = second$n_group
        )
        method_used <- "welch_t_from_summary"
        reproducible <- TRUE
        note <- "Approximate reproduction from summary statistics only."
      }
    } else {
      recomputed_p <- NA_real_
      method_used <- "not_reproducible_from_summary"
      reproducible <- FALSE
      note <- "Median/IQR rows do not support exact nonparametric p-value reproduction."
    }

    abs_delta <- if (!is.na(reported_p) && !is.na(recomputed_p)) {
      abs(reported_p - recomputed_p)
    } else {
      NA_real_
    }
    rows[[index]] <- tibble(
      variable = variable_name,
      measure_type = measure_type,
      reported_p = reported_p,
      recomputed_p = recomputed_p,
      abs_delta = abs_delta,
      reproducible = reproducible,
      method_used = method_used,
      anomaly_flag = reproducible && !is.na(abs_delta) && abs_delta >= 0.05,
      note = note
    )
  }
  bind_rows(rows)
}

run_table3_checks <- function(table3, confusion_candidates) {
  prospective <- table3 %>% filter(tolower(cohort) == "prospective validation")
  if (nrow(prospective) == 0) {
    return(tibble())
  }
  prospective <- prospective[1, ]
  exact_count <- sum(as.logical(confusion_candidates$exact_rounded_match), na.rm = TRUE)
  best <- if (nrow(confusion_candidates) > 0) confusion_candidates[1, ] else tibble()

  bind_rows(
    tibble(
      metric = "confusion_matrix_reconciliation",
      reported_value = paste(
        "sens=", prospective$sensitivity,
        "; spec=", prospective$specificity,
        "; ppv=", prospective$ppv,
        "; npv=", prospective$npv,
        sep = ""
      ),
      exact_match_count = exact_count,
      best_tp = if (nrow(best) > 0) as.integer(best$tp) else NA_integer_,
      best_fp = if (nrow(best) > 0) as.integer(best$fp) else NA_integer_,
      best_tn = if (nrow(best) > 0) as.integer(best$tn) else NA_integer_,
      best_fn = if (nrow(best) > 0) as.integer(best$fn) else NA_integer_,
      best_total_abs_delta = if (nrow(best) > 0) as.numeric(best$total_abs_delta) else NA_real_,
      anomaly_flag = exact_count == 0,
      note = if (exact_count == 0) {
        "No integer confusion matrix exactly reproduces all rounded summary metrics."
      } else {
        "At least one integer confusion matrix matches the rounded summary metrics."
      }
    ),
    tibble(
      metric = "c_statistic",
      reported_value = paste0(
        prospective$c_statistic,
        " (",
        prospective$c_stat_low,
        "-",
        prospective$c_stat_high,
        ")"
      ),
      exact_match_count = NA_integer_,
      best_tp = NA_integer_,
      best_fp = NA_integer_,
      best_tn = NA_integer_,
      best_fn = NA_integer_,
      best_total_abs_delta = NA_real_,
      anomaly_flag = FALSE,
      note = "c-statistic is not reproducible from summary tables without individual-level predictions."
    )
  )
}

run_calibration_checks <- function(tablee2, calibration_totals) {
  n_groups <- nrow(tablee2)
  hl_stat <- sum(
    (tablee2$observed_outcomes - tablee2$expected_outcomes)^2 /
      (tablee2$expected_outcomes * (1 - tablee2$expected_outcomes / tablee2$total_individuals)),
    na.rm = TRUE
  )
  df <- max(n_groups - 2, 1)
  hl_p_value <- stats::pchisq(hl_stat, df = df, lower.tail = FALSE)
  totals <- calibration_totals[1, ]

  tibble(
    n_groups = n_groups,
    total_individuals_sum = as.integer(totals$total_individuals_sum),
    observed_outcomes_sum = as.integer(totals$observed_outcomes_sum),
    displayed_expected_outcomes_sum = as.numeric(totals$displayed_expected_outcomes_sum),
    displayed_expected_minus_observed = as.numeric(totals$displayed_expected_minus_observed),
    hl_statistic_from_displayed_rows = hl_stat,
    hl_df = df,
    hl_p_value_from_displayed_rows = hl_p_value,
    anomaly_flag = abs(as.numeric(totals$displayed_expected_minus_observed)) >= 2,
    note = "Hosmer-Lemeshow statistic uses displayed rounded expected counts and is approximate."
  )
}

standardize_table2 <- function(table2_checks, study_id) {
  if (nrow(table2_checks) == 0) {
    return(tibble())
  }
  table2_checks %>%
    transmute(
      trial_id = study_id,
      method = "table2_reproducibility",
      source_unit = variable,
      metric = "p_value_delta",
      value_numeric = abs_delta,
      p_value = recomputed_p,
      anomaly_flag = anomaly_flag,
      severity = ifelse(anomaly_flag, "medium", "low"),
      details = note
    )
}

standardize_table3 <- function(table3_checks, study_id) {
  if (nrow(table3_checks) == 0) {
    return(tibble())
  }
  table3_checks %>%
    transmute(
      trial_id = study_id,
      method = "prediction_metric_consistency",
      source_unit = metric,
      metric = "best_total_abs_delta",
      value_numeric = best_total_abs_delta,
      p_value = NA_real_,
      anomaly_flag = anomaly_flag,
      severity = ifelse(anomaly_flag, "medium", "low"),
      details = note
    )
}

standardize_calibration <- function(calibration_checks, study_id) {
  if (nrow(calibration_checks) == 0) {
    return(tibble())
  }
  calibration_checks %>%
    transmute(
      trial_id = study_id,
      method = "calibration_consistency",
      source_unit = "tablee2",
      metric = "displayed_expected_minus_observed",
      value_numeric = displayed_expected_minus_observed,
      p_value = hl_p_value_from_displayed_rows,
      anomaly_flag = anomaly_flag,
      severity = ifelse(anomaly_flag, "medium", "low"),
      details = note
    )
}

standardize_flow <- function(flow_checks, study_id) {
  if (nrow(flow_checks) == 0) {
    return(tibble())
  }
  flow_checks %>%
    transmute(
      trial_id = study_id,
      method = "flow_consistency",
      source_unit = check_name,
      metric = "delta",
      value_numeric = as.numeric(delta),
      p_value = NA_real_,
      anomaly_flag = !as.logical(pass_flag),
      severity = ifelse(!as.logical(pass_flag), "medium", "low"),
      details = note
    )
}

main <- function() {
  args <- parse_args()
  in_dir <- args$in_dir
  out_dir <- args$out_dir
  inputs_dir <- file.path(in_dir, "inputs")

  required_paths <- c(
    file.path(inputs_dir, "table2_baseline_by_outcome.csv"),
    file.path(inputs_dir, "table3_discrimination_metrics.csv"),
    file.path(inputs_dir, "tablee2_calibration_deciles.csv"),
    file.path(inputs_dir, "table3_confusion_matrix_matches.csv"),
    file.path(inputs_dir, "calibration_sum_checks.csv"),
    file.path(inputs_dir, "flow_reconciliation.csv")
  )
  missing_paths <- required_paths[!file.exists(required_paths)]
  if (length(missing_paths) > 0) {
    stop("Missing prediction-review inputs: ", paste(missing_paths, collapse = ", "))
  }

  table2 <- read_csv(file.path(inputs_dir, "table2_baseline_by_outcome.csv"), show_col_types = FALSE)
  table3 <- read_csv(file.path(inputs_dir, "table3_discrimination_metrics.csv"), show_col_types = FALSE)
  tablee2 <- read_csv(file.path(inputs_dir, "tablee2_calibration_deciles.csv"), show_col_types = FALSE)
  confusion_candidates <- read_csv(
    file.path(inputs_dir, "table3_confusion_matrix_matches.csv"),
    show_col_types = FALSE
  )
  calibration_totals <- read_csv(
    file.path(inputs_dir, "calibration_sum_checks.csv"),
    show_col_types = FALSE
  )
  flow_checks <- read_csv(file.path(inputs_dir, "flow_reconciliation.csv"), show_col_types = FALSE)

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  table2_checks <- run_table2_checks(table2)
  table3_checks <- run_table3_checks(table3, confusion_candidates)
  calibration_checks <- run_calibration_checks(tablee2, calibration_totals)

  study_id <- unique(table2$study_id)[1]

  standardized <- bind_rows(
    standardize_table2(table2_checks, study_id),
    standardize_table3(table3_checks, study_id),
    standardize_calibration(calibration_checks, study_id),
    standardize_flow(flow_checks, study_id)
  )

  numeric_statcheck <- if (file.exists(file.path(out_dir, "numeric_statcheck_raw.csv"))) {
    read_csv(file.path(out_dir, "numeric_statcheck_raw.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }
  grim_audit <- if (file.exists(file.path(out_dir, "numeric_scrutiny_grim_audit.csv"))) {
    read_csv(file.path(out_dir, "numeric_scrutiny_grim_audit.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }
  grimmer_audit <- if (file.exists(file.path(out_dir, "numeric_scrutiny_grimmer_audit.csv"))) {
    read_csv(file.path(out_dir, "numeric_scrutiny_grimmer_audit.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }
  duplicates_df <- if (file.exists(file.path(out_dir, "numeric_scrutiny_duplicates.csv"))) {
    read_csv(file.path(out_dir, "numeric_scrutiny_duplicates.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }
  rounding_bias_df <- if (file.exists(file.path(out_dir, "numeric_scrutiny_rounding_bias.csv"))) {
    read_csv(file.path(out_dir, "numeric_scrutiny_rounding_bias.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }
  visual_summary <- if (file.exists(file.path(out_dir, "visual_summary.csv"))) {
    read_csv(file.path(out_dir, "visual_summary.csv"), show_col_types = FALSE)
  } else {
    tibble()
  }

  review_summary <- tibble(
    study_id = study_id,
    statcheck_rows = nrow(numeric_statcheck),
    statcheck_errors = if ("error" %in% names(numeric_statcheck)) {
      sum(as.logical(numeric_statcheck$error), na.rm = TRUE)
    } else {
      0L
    },
    statcheck_decision_errors = if ("decision_error" %in% names(numeric_statcheck)) {
      sum(as.logical(numeric_statcheck$decision_error), na.rm = TRUE)
    } else {
      0L
    },
    grim_incons_cases = if (nrow(grim_audit) > 0) as.integer(grim_audit$incons_cases[[1]]) else 0L,
    grimmer_incons_cases = if (nrow(grimmer_audit) > 0) {
      as.integer(grimmer_audit$incons_cases[[1]])
    } else {
      0L
    },
    duplicate_flag_rows = if (nrow(duplicates_df) > 0) {
      sum(
        as.logical(duplicates_df$x_dup) |
          as.logical(duplicates_df$sd_dup) |
          as.logical(duplicates_df$n_dup),
        na.rm = TRUE
      )
    } else {
      0L
    },
    rounding_bias_flags = if (nrow(rounding_bias_df) > 0) {
      sum(as.logical(rounding_bias_df$anomaly_flag), na.rm = TRUE)
    } else {
      0L
    },
    table2_reproducible_rows = sum(as.logical(table2_checks$reproducible), na.rm = TRUE),
    table2_flagged_rows = sum(as.logical(table2_checks$anomaly_flag), na.rm = TRUE),
    exact_confusion_match_count = if (nrow(table3_checks) > 0) {
      as.integer(table3_checks$exact_match_count[[1]])
    } else {
      0L
    },
    best_confusion_total_abs_delta = if (nrow(table3_checks) > 0) {
      as.numeric(table3_checks$best_total_abs_delta[[1]])
    } else {
      NA_real_
    },
    calibration_total_n = as.integer(calibration_checks$total_individuals_sum[[1]]),
    calibration_observed_events = as.integer(calibration_checks$observed_outcomes_sum[[1]]),
    calibration_displayed_expected_events = as.numeric(
      calibration_checks$displayed_expected_outcomes_sum[[1]]
    ),
    flow_failed_checks = sum(!as.logical(flow_checks$pass_flag), na.rm = TRUE),
    visual_duplicate_pairs = if (nrow(visual_summary) > 0) {
      as.integer(visual_summary$n_duplicate_pairs[[1]])
    } else {
      0L
    },
    visual_numbering_gaps = if (nrow(visual_summary) > 0) {
      as.integer(visual_summary$n_numbering_gaps[[1]])
    } else {
      0L
    }
  )

  write_csv(table2_checks, file.path(out_dir, "review_table2_reproducibility.csv"))
  write_csv(table3_checks, file.path(out_dir, "review_table3_metric_checks.csv"))
  write_csv(calibration_checks, file.path(out_dir, "review_calibration_checks.csv"))
  write_csv(flow_checks, file.path(out_dir, "review_flow_checks.csv"))
  write_csv(review_summary, file.path(out_dir, "review_summary.csv"))
  write_csv(standardized, file.path(out_dir, "review_standardized_results.csv"))

  cat("Wrote ", file.path(out_dir, "review_table2_reproducibility.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "review_table3_metric_checks.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "review_calibration_checks.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "review_flow_checks.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "review_summary.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "review_standardized_results.csv"), "\n", sep = "")
}

main()
