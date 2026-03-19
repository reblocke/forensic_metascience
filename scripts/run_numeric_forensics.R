#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tibble)
})

parse_bool <- function(value) {
  tolower(value) %in% c("true", "1", "yes", "y")
}

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(in_dir = NULL, out_dir = NULL, scrutiny_seq = FALSE)
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--in", "--out", "--scrutiny-seq")) {
      if (i == length(args)) {
        stop("Missing value for ", key)
      }
      value <- args[[i + 1L]]
      if (key == "--in") {
        parsed$in_dir <- value
      } else if (key == "--out") {
        parsed$out_dir <- value
      } else if (key == "--scrutiny-seq") {
        parsed$scrutiny_seq <- parse_bool(value)
      }
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$in_dir) || is.null(parsed$out_dir)) {
    stop(
      "Usage: run_numeric_forensics.R --in <input_dir> --out <output_dir> ",
      "[--scrutiny-seq false|true]"
    )
  }
  parsed
}

ensure_user_lib <- function() {
  r_major <- R.version$major
  r_minor <- strsplit(R.version$minor, "\\.")[[1]][1]
  user_lib <- file.path(
    Sys.getenv("HOME"),
    "Library",
    "R",
    paste0(r_major, ".", r_minor),
    "library"
  )
  if (dir.exists(user_lib)) {
    .libPaths(c(user_lib, .libPaths()))
  }
}

safe_package_version <- function(package_name) {
  if (!requireNamespace(package_name, quietly = TRUE)) {
    return(NA_character_)
  }
  as.character(utils::packageVersion(package_name))
}

empty_scrutiny_grim_raw <- function() {
  tibble(
    x = character(),
    n = numeric(),
    consistency = logical(),
    probability = numeric(),
    case_id = character(),
    source_unit = character()
  )
}

empty_scrutiny_grim_audit <- function() {
  tibble(
    incons_cases = integer(),
    all_cases = integer(),
    incons_rate = numeric(),
    mean_grim_prob = numeric(),
    incons_to_prob = numeric(),
    testable_cases = integer(),
    testable_rate = numeric()
  )
}

empty_scrutiny_grimmer_raw <- function() {
  tibble(
    case_id = character(),
    source_unit = character(),
    trial_id = character(),
    variable = character(),
    level = character(),
    group = character(),
    x = character(),
    sd = character(),
    n = numeric(),
    consistency = logical(),
    reason = character()
  )
}

empty_scrutiny_grimmer_audit <- function() {
  tibble(
    incons_cases = integer(),
    all_cases = integer(),
    incons_rate = numeric(),
    fail_grim = integer(),
    fail_test1 = integer(),
    fail_test2 = integer(),
    fail_test3 = integer()
  )
}

empty_scrutiny_debit_raw <- function() {
  tibble(
    x = character(),
    sd = character(),
    n = numeric(),
    consistency = logical(),
    rounding = character(),
    sd_lower = numeric(),
    sd_incl_lower = logical(),
    sd_upper = numeric(),
    sd_incl_upper = logical(),
    x_lower = numeric(),
    x_upper = numeric(),
    case_id = character(),
    source_unit = character()
  )
}

empty_scrutiny_debit_audit <- function() {
  tibble(
    incons_cases = integer(),
    all_cases = integer(),
    incons_rate = numeric(),
    mean_x = numeric(),
    mean_sd = numeric(),
    distinct_n = integer()
  )
}

empty_statcheck_raw <- function() {
  tibble(
    source = character(),
    test_type = character(),
    df1 = numeric(),
    df2 = numeric(),
    test_comp = character(),
    test_value = numeric(),
    p_comp = character(),
    reported_p = numeric(),
    computed_p = numeric(),
    raw = character(),
    error = logical(),
    decision_error = logical(),
    one_tailed_in_txt = logical(),
    apa_factor = numeric()
  )
}

empty_duplicates <- function() {
  tibble(
    case_id = character(),
    trial_id = character(),
    source_unit = character(),
    variable = character(),
    level = character(),
    group = character(),
    x = character(),
    sd = character(),
    n = numeric(),
    x_dup = logical(),
    sd_dup = logical(),
    n_dup = logical(),
    x_n = integer(),
    sd_n = integer(),
    n_n = integer()
  )
}

empty_rounding_bias <- function() {
  tibble(
    trial_id = character(),
    digits_x = integer(),
    n_values = integer(),
    bias_up = numeric(),
    bias_down = numeric(),
    abs_bias_gap = numeric(),
    anomaly_flag = logical()
  )
}

empty_seq_raw <- function() {
  tibble(
    case_id = character(),
    x = character(),
    sd = character(),
    n = numeric(),
    consistency = logical(),
    diff_var = numeric(),
    case = integer(),
    var = character()
  )
}

empty_seq_audit <- function() {
  tibble(
    case_id = character(),
    x = character(),
    sd = character(),
    n = numeric(),
    consistency = logical(),
    hits_total = numeric()
  )
}

format_numeric_with_decimals <- function(x, decimals) {
  if (is.na(x) || is.na(decimals)) {
    return(NA_character_)
  }
  digits <- max(as.integer(decimals), 0L)
  formatC(as.numeric(x), format = "f", digits = digits)
}

as_logical_count <- function(x) {
  if (length(x) == 0) {
    return(0L)
  }
  sum(as.logical(x), na.rm = TRUE)
}

run_scrutiny_grim <- function(scrutiny_grim_input) {
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_scrutiny_grim_raw(),
      audit = empty_scrutiny_grim_audit(),
      message = "Package `scrutiny` not installed."
    ))
  }
  if (nrow(scrutiny_grim_input) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_grim_raw(),
      audit = empty_scrutiny_grim_audit(),
      message = "No GRIM-eligible rows."
    ))
  }

  prepared <- scrutiny_grim_input %>%
    mutate(
      x = if ("digits_x" %in% names(scrutiny_grim_input)) {
        mapply(
          format_numeric_with_decimals,
          x = x,
          decimals = digits_x,
          USE.NAMES = FALSE
        )
      } else {
        as.character(x)
      },
      x = ifelse(
        is.na(x) | x == "",
        NA_character_,
        x
      ),
      n = as.numeric(n)
    ) %>%
    filter(!is.na(x), !is.na(n), n > 0) %>%
    select(x, n, case_id, source_unit)

  if (nrow(prepared) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_grim_raw(),
      audit = empty_scrutiny_grim_audit(),
      message = "No GRIM rows after filtering."
    ))
  }

  tryCatch(
    {
      grim_out <- scrutiny::grim_map(
        data = as_tibble(prepared),
        x = "x",
        n = "n",
        percent = FALSE,
        extra = Inf
      )
      audit_out <- scrutiny::audit(grim_out)
      list(
        available = TRUE,
        raw = as_tibble(grim_out),
        audit = as_tibble(audit_out),
        message = "ok"
      )
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_scrutiny_grim_raw(),
        audit = empty_scrutiny_grim_audit(),
        message = paste("GRIM execution error:", conditionMessage(exc))
      )
    }
  )
}

run_scrutiny_grimmer <- function(scrutiny_grimmer_input) {
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_scrutiny_grimmer_raw(),
      audit = empty_scrutiny_grimmer_audit(),
      message = "Package `scrutiny` not installed."
    ))
  }
  if (nrow(scrutiny_grimmer_input) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_grimmer_raw(),
      audit = empty_scrutiny_grimmer_audit(),
      message = "No GRIMMER-eligible rows."
    ))
  }

  prepared <- scrutiny_grimmer_input %>%
    mutate(
      x = as.character(x),
      sd = as.character(sd),
      x = ifelse(is.na(x) | x == "", NA_character_, x),
      sd = ifelse(is.na(sd) | sd == "", NA_character_, sd),
      n = as.numeric(n)
    ) %>%
    filter(!is.na(x), !is.na(sd), !is.na(n), n > 0)

  if (nrow(prepared) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_grimmer_raw(),
      audit = empty_scrutiny_grimmer_audit(),
      message = "No GRIMMER rows after filtering."
    ))
  }

  tryCatch(
    {
      grimmer_out <- suppressWarnings(
        scrutiny::grimmer_map(prepared %>% select(x, sd, n))
      )
      audit_out <- suppressWarnings(scrutiny::audit(grimmer_out))
      mapped_out <- bind_cols(
        prepared %>% select(case_id, source_unit, trial_id, variable, level, group),
        as_tibble(grimmer_out)
      )
      list(
        available = TRUE,
        raw = mapped_out,
        audit = as_tibble(audit_out),
        message = paste(
          "ok; GRIMMER caveat: scrutiny reports known false-positive issue #80."
        )
      )
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_scrutiny_grimmer_raw(),
        audit = empty_scrutiny_grimmer_audit(),
        message = paste("GRIMMER execution error:", conditionMessage(exc))
      )
    }
  )
}

run_scrutiny_debit <- function(scrutiny_debit_input) {
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_scrutiny_debit_raw(),
      audit = empty_scrutiny_debit_audit(),
      message = "Package `scrutiny` not installed."
    ))
  }
  if (nrow(scrutiny_debit_input) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_debit_raw(),
      audit = empty_scrutiny_debit_audit(),
      message = "No DEBIT-eligible rows."
    ))
  }

  prepared <- scrutiny_debit_input %>%
    mutate(
      x = as.character(x),
      sd = as.character(sd),
      x = ifelse(is.na(x) | x == "", NA_character_, x),
      sd = ifelse(is.na(sd) | sd == "", NA_character_, sd),
      n = as.numeric(n)
    ) %>%
    filter(!is.na(x), !is.na(sd), !is.na(n), n > 0) %>%
    select(x, sd, n, case_id, source_unit)

  if (nrow(prepared) == 0) {
    return(list(
      available = TRUE,
      raw = empty_scrutiny_debit_raw(),
      audit = empty_scrutiny_debit_audit(),
      message = "No DEBIT rows after filtering."
    ))
  }

  tryCatch(
    {
      debit_out <- scrutiny::debit_map(prepared)
      audit_out <- scrutiny::audit(debit_out)
      list(
        available = TRUE,
        raw = as_tibble(debit_out),
        audit = as_tibble(audit_out),
        message = "ok"
      )
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_scrutiny_debit_raw(),
        audit = empty_scrutiny_debit_audit(),
        message = paste("DEBIT execution error:", conditionMessage(exc))
      )
    }
  )
}

run_scrutiny_duplicates <- function(scrutiny_duplicates_input) {
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_duplicates(),
      message = "Package `scrutiny` not installed."
    ))
  }
  if (nrow(scrutiny_duplicates_input) == 0) {
    return(list(
      available = TRUE,
      raw = empty_duplicates(),
      message = "No rows for duplication checks."
    ))
  }

  prepared <- scrutiny_duplicates_input %>%
    mutate(
      x = ifelse(is.na(x), "", x),
      sd = ifelse(is.na(sd), "", sd),
      n = as.character(n)
    )

  tryCatch(
    {
      duplicate_detect <- suppressWarnings(
        as_tibble(scrutiny::duplicate_detect(prepared %>% select(x, sd, n)))
      )
      duplicate_tally <- suppressWarnings(
        as_tibble(scrutiny::duplicate_tally(prepared %>% select(x, sd, n)))
      )
      for (column_name in c("x_dup", "sd_dup", "n_dup")) {
        if (!column_name %in% names(duplicate_detect)) {
          duplicate_detect[[column_name]] <- FALSE
        }
      }
      for (column_name in c("x_n", "sd_n", "n_n")) {
        if (!column_name %in% names(duplicate_tally)) {
          duplicate_tally[[column_name]] <- 0L
        }
      }
      duplicate_out <- bind_cols(
        prepared %>% select(case_id, trial_id, source_unit, variable, level, group, x, sd, n),
        duplicate_detect %>% select(x_dup, sd_dup, n_dup),
        duplicate_tally %>% select(x_n, sd_n, n_n)
      )
      list(
        available = TRUE,
        raw = duplicate_out,
        message = "ok"
      )
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_duplicates(),
        message = paste("Duplicate execution error:", conditionMessage(exc))
      )
    }
  )
}

run_scrutiny_rounding_bias <- function(scrutiny_rounding_bias_input) {
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_rounding_bias(),
      message = "Package `scrutiny` not installed."
    ))
  }
  if (nrow(scrutiny_rounding_bias_input) == 0) {
    return(list(
      available = TRUE,
      raw = empty_rounding_bias(),
      message = "No rows for rounding-bias checks."
    ))
  }

  prepared <- scrutiny_rounding_bias_input %>%
    mutate(
      x = as.numeric(x),
      digits_x = as.integer(digits_x)
    ) %>%
    filter(!is.na(x), !is.na(digits_x), digits_x >= 0)

  if (nrow(prepared) == 0) {
    return(list(
      available = TRUE,
      raw = empty_rounding_bias(),
      message = "No rows after rounding-bias filtering."
    ))
  }

  tryCatch(
    {
      bias <- prepared %>%
        group_by(trial_id, digits_x) %>%
        summarise(
          n_values = n(),
          bias_up = scrutiny::rounding_bias(
            x = x,
            digits = first(digits_x),
            rounding = "up",
            mean = TRUE
          ),
          bias_down = scrutiny::rounding_bias(
            x = x,
            digits = first(digits_x),
            rounding = "down",
            mean = TRUE
          ),
          .groups = "drop"
        ) %>%
        mutate(
          abs_bias_gap = abs(as.numeric(bias_up) - as.numeric(bias_down)),
          anomaly_flag = abs_bias_gap >= 0.05
        )
      list(
        available = TRUE,
        raw = bias,
        message = "ok"
      )
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_rounding_bias(),
        message = paste("Rounding-bias execution error:", conditionMessage(exc))
      )
    }
  )
}

run_statcheck <- function(statcheck_text) {
  if (!requireNamespace("statcheck", quietly = TRUE)) {
    return(list(
      available = FALSE,
      raw = empty_statcheck_raw(),
      message = "Package `statcheck` not installed."
    ))
  }
  if (!nzchar(trimws(statcheck_text))) {
    return(list(
      available = TRUE,
      raw = empty_statcheck_raw(),
      message = "No report text available for statcheck."
    ))
  }

  tryCatch(
    {
      output <- suppressWarnings(
        statcheck::statcheck(
          texts = statcheck_text,
          messages = FALSE,
          AllPValues = FALSE
        )
      )
      raw_tbl <- if (
        is.null(output) ||
          (is.data.frame(output) && ncol(output) == 0)
      ) {
        empty_statcheck_raw()
      } else {
        as_tibble(output)
      }
      list(available = TRUE, raw = raw_tbl, message = "ok")
    },
    error = function(exc) {
      list(
        available = TRUE,
        raw = empty_statcheck_raw(),
        message = paste("statcheck execution error:", conditionMessage(exc))
      )
    }
  )
}

run_scrutiny_seq <- function(scrutiny_input, method = c("grim", "grimmer", "debit")) {
  method <- match.arg(method)
  if (!requireNamespace("scrutiny", quietly = TRUE)) {
    return(list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "scrutiny missing"))
  }
  if (nrow(scrutiny_input) == 0) {
    return(list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "no eligible rows"))
  }

  tryCatch(
    {
      seq_raw <- if (method == "grim") {
        scrutiny::grim_map_seq(
          scrutiny_input %>% select(x, n),
          include_reported = TRUE,
          include_consistent = TRUE
        )
      } else if (method == "grimmer") {
        suppressWarnings(
          scrutiny::grimmer_map_seq(
            scrutiny_input %>% select(x, sd, n),
            include_reported = TRUE,
            include_consistent = TRUE
          )
        )
      } else {
        scrutiny::debit_map_seq(
          scrutiny_input %>% select(x, sd, n),
          include_reported = TRUE,
          include_consistent = TRUE
        )
      }
      if (nrow(seq_raw) == 0) {
        return(list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "empty seq output"))
      }
      seq_raw <- as_tibble(seq_raw)
      if ("case" %in% names(seq_raw)) {
        valid_case <- seq_raw$case >= 1 & seq_raw$case <= nrow(scrutiny_input)
        seq_raw$case_id <- NA_character_
        seq_raw$case_id[valid_case] <- scrutiny_input$case_id[seq_raw$case[valid_case]]
      } else {
        seq_raw$case_id <- NA_character_
      }
      seq_audit <- scrutiny::audit_seq(seq_raw)
      seq_audit <- as_tibble(seq_audit)
      if (nrow(seq_audit) > 0) {
        seq_audit$case_id <- scrutiny_input$case_id[seq_len(nrow(seq_audit))]
      } else {
        seq_audit <- empty_seq_audit()
      }
      list(raw = seq_raw, audit = seq_audit, message = "ok")
    },
    error = function(exc) {
      list(
        raw = empty_seq_raw(),
        audit = empty_seq_audit(),
        message = paste("seq error:", conditionMessage(exc))
      )
    }
  )
}

severity_from_delta <- function(delta_value) {
  if (is.na(delta_value)) {
    return("unknown")
  }
  if (delta_value >= 1.0) {
    return("high")
  }
  if (delta_value >= 0.2) {
    return("medium")
  }
  "low"
}

standardize_rounding <- function(row_results) {
  if (nrow(row_results) == 0) {
    return(tibble())
  }
  row_results %>%
    transmute(
      trial_id = as.character(trial_id),
      method = "rounding_consistency",
      source_unit = paste(variable, level, group, sep = " / "),
      metric = "abs_percent_delta",
      value_numeric = as.numeric(abs_percent_delta),
      p_value = NA_real_,
      anomaly_flag = as.logical(flag_percent_delta_0_2),
      severity = vapply(as.numeric(abs_percent_delta), severity_from_delta, character(1)),
      details = paste0(
        "reported_percent=", round(as.numeric(reported_percent), 4),
        "; computed_percent=", round(as.numeric(computed_percent), 4)
      )
    )
}

standardize_scrutiny_map <- function(raw_df, trial_id, method_name, metric_name) {
  if (nrow(raw_df) == 0) {
    return(tibble())
  }
  p_col <- if ("probability" %in% names(raw_df)) "probability" else NA_character_
  raw_df %>%
    transmute(
      trial_id = if ("trial_id" %in% names(raw_df)) {
        as.character(.data[["trial_id"]])
      } else {
        rep(as.character(trial_id), n())
      },
      method = method_name,
      source_unit = if ("source_unit" %in% names(raw_df)) as.character(source_unit) else case_id,
      metric = metric_name,
      value_numeric = ifelse(as.logical(consistency), 0, 1),
      p_value = if (!is.na(p_col)) as.numeric(.data[[p_col]]) else NA_real_,
      anomaly_flag = !as.logical(consistency),
      severity = ifelse(!as.logical(consistency), "medium", "low"),
      details = if ("reason" %in% names(raw_df)) as.character(reason) else as.character(case_id)
    )
}

standardize_duplicates <- function(duplicates_df) {
  if (nrow(duplicates_df) == 0) {
    return(tibble())
  }
  duplicates_df %>%
    mutate(
      dup_count = as.integer(x_dup) + as.integer(sd_dup) + as.integer(n_dup)
    ) %>%
    transmute(
      trial_id = as.character(trial_id),
      method = "scrutiny_duplicates",
      source_unit = as.character(source_unit),
      metric = "duplicate_fields_count",
      value_numeric = as.numeric(dup_count),
      p_value = NA_real_,
      anomaly_flag = dup_count >= 2,
      severity = ifelse(dup_count >= 2, "medium", "low"),
      details = paste0("x_dup=", x_dup, "; sd_dup=", sd_dup, "; n_dup=", n_dup)
    )
}

standardize_rounding_bias <- function(rounding_bias_df) {
  if (nrow(rounding_bias_df) == 0) {
    return(tibble())
  }
  rounding_bias_df %>%
    transmute(
      trial_id = as.character(trial_id),
      method = "scrutiny_rounding_bias",
      source_unit = paste0("digits_", as.integer(digits_x)),
      metric = "abs_bias_gap",
      value_numeric = as.numeric(abs_bias_gap),
      p_value = NA_real_,
      anomaly_flag = as.logical(anomaly_flag),
      severity = ifelse(as.logical(anomaly_flag), "medium", "low"),
      details = paste0(
        "n_values=", n_values,
        "; bias_up=", round(as.numeric(bias_up), 5),
        "; bias_down=", round(as.numeric(bias_down), 5)
      )
    )
}

standardize_statcheck <- function(statcheck_raw, trial_id) {
  if (nrow(statcheck_raw) == 0) {
    return(tibble())
  }
  statcheck_raw %>%
    mutate(
      unit_id = if ("raw" %in% names(statcheck_raw)) as.character(raw) else as.character(row_number()),
      abs_p_delta = if (
        "reported_p" %in% names(statcheck_raw) &&
          "computed_p" %in% names(statcheck_raw)
      ) {
        abs(as.numeric(reported_p) - as.numeric(computed_p))
      } else {
        NA_real_
      },
      anomaly = if ("error" %in% names(statcheck_raw)) as.logical(error) else FALSE,
      decision_anomaly = if ("decision_error" %in% names(statcheck_raw)) {
        as.logical(decision_error)
      } else {
        FALSE
      },
      severity = ifelse(decision_anomaly, "high", ifelse(anomaly, "medium", "low"))
    ) %>%
    transmute(
      trial_id = trial_id,
      method = "statcheck",
      source_unit = unit_id,
      metric = "reported_vs_computed_p_delta",
      value_numeric = as.numeric(abs_p_delta),
      p_value = if ("computed_p" %in% names(statcheck_raw)) as.numeric(computed_p) else NA_real_,
      anomaly_flag = as.logical(anomaly),
      severity = severity,
      details = if ("raw" %in% names(statcheck_raw)) as.character(raw) else source_unit
    )
}

standardize_rsprite_stub <- function(rsprite2_input, trial_id) {
  if (nrow(rsprite2_input) == 0) {
    return(tibble())
  }
  rsprite2_input %>%
    transmute(
      trial_id = trial_id,
      method = "rsprite2_stub",
      source_unit = paste(variable, level, sep = " / "),
      metric = "abs_percent_between_arms",
      value_numeric = as.numeric(abs_percent_between_arms),
      p_value = NA_real_,
      anomaly_flag = as.numeric(abs_percent_between_arms) >= 5,
      severity = ifelse(as.numeric(abs_percent_between_arms) >= 10, "high", "low"),
      details = paste0(
        "group_a=", group_a, "; group_b=", group_b,
        "; percent_a=", round(as.numeric(percent_a), 4),
        "; percent_b=", round(as.numeric(percent_b), 4)
      )
    )
}

standardize_seq <- function(seq_audit, trial_id, method_name) {
  if (nrow(seq_audit) == 0) {
    return(tibble())
  }
  hits_col <- if ("hits_total" %in% names(seq_audit)) "hits_total" else NA_character_
  seq_audit %>%
    transmute(
      trial_id = trial_id,
      method = method_name,
      source_unit = if ("case_id" %in% names(seq_audit)) as.character(case_id) else as.character(row_number()),
      metric = "seq_hits_total",
      value_numeric = if (!is.na(hits_col)) as.numeric(.data[[hits_col]]) else NA_real_,
      p_value = NA_real_,
      anomaly_flag = if ("consistency" %in% names(seq_audit)) !as.logical(consistency) else FALSE,
      severity = ifelse(anomaly_flag, "medium", "low"),
      details = "Sequence check across dispersed alternatives."
    )
}

main <- function() {
  ensure_user_lib()
  args <- parse_args()

  in_dir <- args$in_dir
  out_dir <- args$out_dir
  scrutiny_seq <- args$scrutiny_seq

  required_inputs <- c(
    "numeric_checks_input.csv",
    "statcheck_input.csv",
    "statcheck_text.txt",
    "rsprite2_input.csv",
    "scrutiny_cases.csv",
    "scrutiny_grim_input.csv",
    "scrutiny_grimmer_input.csv",
    "scrutiny_debit_input.csv",
    "scrutiny_duplicates_input.csv",
    "scrutiny_rounding_bias_input.csv"
  )
  missing_inputs <- required_inputs[
    !file.exists(file.path(in_dir, "inputs", required_inputs))
  ]
  if (length(missing_inputs) > 0) {
    stop("Missing input files: ", paste(missing_inputs, collapse = ", "))
  }

  numeric <- read_csv(
    file.path(in_dir, "inputs", "numeric_checks_input.csv"),
    show_col_types = FALSE
  )
  statcheck_input <- read_csv(
    file.path(in_dir, "inputs", "statcheck_input.csv"),
    show_col_types = FALSE
  )
  statcheck_text <- read_file(file.path(in_dir, "inputs", "statcheck_text.txt"))
  rsprite2_input <- read_csv(
    file.path(in_dir, "inputs", "rsprite2_input.csv"),
    show_col_types = FALSE
  )
  scrutiny_cases <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_cases.csv"),
    show_col_types = FALSE
  )
  scrutiny_grim_input <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_grim_input.csv"),
    show_col_types = FALSE
  )
  scrutiny_grimmer_input <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_grimmer_input.csv"),
    show_col_types = FALSE
  )
  scrutiny_debit_input <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_debit_input.csv"),
    show_col_types = FALSE
  )
  scrutiny_duplicates_input <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_duplicates_input.csv"),
    show_col_types = FALSE
  )
  scrutiny_rounding_bias_input <- read_csv(
    file.path(in_dir, "inputs", "scrutiny_rounding_bias_input.csv"),
    show_col_types = FALSE
  )

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

  row_results <- numeric %>%
    mutate(
      abs_percent_delta = as.numeric(abs_percent_delta),
      flag_percent_delta_0_2 = abs_percent_delta >= 0.2
    )
  write_csv(row_results, file.path(out_dir, "numeric_row_results.csv"))

  n_rows <- nrow(row_results)
  n_rounding_flags <- sum(row_results$flag_percent_delta_0_2, na.rm = TRUE)
  n_reported_p <- sum(!is.na(row_results$reported_p))
  median_delta <- median(row_results$abs_percent_delta, na.rm = TRUE)
  if (!is.finite(median_delta)) {
    median_delta <- NA_real_
  }

  trial_id <- if (n_rows > 0) as.character(row_results$trial_id[[1]]) else NA_character_

  grim_run <- run_scrutiny_grim(scrutiny_grim_input)
  grimmer_run <- run_scrutiny_grimmer(scrutiny_grimmer_input)
  debit_run <- run_scrutiny_debit(scrutiny_debit_input)
  duplicates_run <- run_scrutiny_duplicates(scrutiny_duplicates_input)
  rounding_bias_run <- run_scrutiny_rounding_bias(scrutiny_rounding_bias_input)
  statcheck_run <- run_statcheck(statcheck_text)

  grim_raw_path <- file.path(out_dir, "numeric_scrutiny_grim_raw.csv")
  grim_audit_path <- file.path(out_dir, "numeric_scrutiny_grim_audit.csv")
  grimmer_raw_path <- file.path(out_dir, "numeric_scrutiny_grimmer_raw.csv")
  grimmer_audit_path <- file.path(out_dir, "numeric_scrutiny_grimmer_audit.csv")
  debit_raw_path <- file.path(out_dir, "numeric_scrutiny_debit_raw.csv")
  debit_audit_path <- file.path(out_dir, "numeric_scrutiny_debit_audit.csv")
  duplicates_path <- file.path(out_dir, "numeric_scrutiny_duplicates.csv")
  rounding_bias_path <- file.path(out_dir, "numeric_scrutiny_rounding_bias.csv")
  statcheck_raw_path <- file.path(out_dir, "numeric_statcheck_raw.csv")

  write_csv(grim_run$raw, grim_raw_path)
  write_csv(grim_run$audit, grim_audit_path)
  write_csv(grimmer_run$raw, grimmer_raw_path)
  write_csv(grimmer_run$audit, grimmer_audit_path)
  write_csv(debit_run$raw, debit_raw_path)
  write_csv(debit_run$audit, debit_audit_path)
  write_csv(duplicates_run$raw, duplicates_path)
  write_csv(rounding_bias_run$raw, rounding_bias_path)
  write_csv(statcheck_run$raw, statcheck_raw_path)

  # Backward-compatible aliases.
  write_csv(grim_run$raw, file.path(out_dir, "numeric_scrutiny_raw.csv"))
  write_csv(grim_run$audit, file.path(out_dir, "numeric_scrutiny_audit.csv"))

  grim_seq <- list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "disabled")
  grimmer_seq <- list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "disabled")
  debit_seq <- list(raw = empty_seq_raw(), audit = empty_seq_audit(), message = "disabled")
  if (scrutiny_seq) {
    grim_seq <- run_scrutiny_seq(scrutiny_grim_input, method = "grim")
    grimmer_seq <- run_scrutiny_seq(scrutiny_grimmer_input, method = "grimmer")
    debit_seq <- run_scrutiny_seq(scrutiny_debit_input, method = "debit")
  }
  write_csv(grim_seq$raw, file.path(out_dir, "numeric_scrutiny_grim_seq_raw.csv"))
  write_csv(grim_seq$audit, file.path(out_dir, "numeric_scrutiny_grim_seq_audit.csv"))
  write_csv(grimmer_seq$raw, file.path(out_dir, "numeric_scrutiny_grimmer_seq_raw.csv"))
  write_csv(grimmer_seq$audit, file.path(out_dir, "numeric_scrutiny_grimmer_seq_audit.csv"))
  write_csv(debit_seq$raw, file.path(out_dir, "numeric_scrutiny_debit_seq_raw.csv"))
  write_csv(debit_seq$audit, file.path(out_dir, "numeric_scrutiny_debit_seq_audit.csv"))

  standardized <- bind_rows(
    standardize_rounding(row_results),
    standardize_scrutiny_map(
      grim_run$raw,
      trial_id = trial_id,
      method_name = "scrutiny_grim_map",
      metric_name = "grim_inconsistency_flag"
    ),
    standardize_scrutiny_map(
      grimmer_run$raw,
      trial_id = trial_id,
      method_name = "scrutiny_grimmer_map",
      metric_name = "grimmer_inconsistency_flag"
    ),
    standardize_scrutiny_map(
      debit_run$raw,
      trial_id = trial_id,
      method_name = "scrutiny_debit_map",
      metric_name = "debit_inconsistency_flag"
    ),
    standardize_duplicates(duplicates_run$raw),
    standardize_rounding_bias(rounding_bias_run$raw),
    standardize_statcheck(statcheck_run$raw, trial_id = trial_id),
    standardize_rsprite_stub(rsprite2_input, trial_id = trial_id),
    standardize_seq(
      grim_seq$audit,
      trial_id = trial_id,
      method_name = "scrutiny_grim_map_seq"
    ),
    standardize_seq(
      grimmer_seq$audit,
      trial_id = trial_id,
      method_name = "scrutiny_grimmer_map_seq"
    ),
    standardize_seq(
      debit_seq$audit,
      trial_id = trial_id,
      method_name = "scrutiny_debit_map_seq"
    )
  )
  standardized_path <- file.path(out_dir, "numeric_standardized_results.csv")
  write_csv(standardized, standardized_path)

  summary_table <- tibble(
    trial_id = trial_id,
    n_rows = n_rows,
    n_rounding_flags = n_rounding_flags,
    rounding_flag_rate = if (n_rows > 0) n_rounding_flags / n_rows else NA_real_,
    n_reported_p = n_reported_p,
    median_abs_percent_delta = median_delta,
    max_abs_percent_delta = suppressWarnings(max(row_results$abs_percent_delta, na.rm = TRUE)),
    scrutiny_cases_n = nrow(scrutiny_cases),
    grim_available = grim_run$available,
    grim_cases = nrow(grim_run$raw),
    grim_incons_cases = if ("consistency" %in% names(grim_run$raw)) {
      sum(!as.logical(grim_run$raw$consistency), na.rm = TRUE)
    } else {
      0L
    },
    grimmer_available = grimmer_run$available,
    grimmer_cases = nrow(grimmer_run$raw),
    grimmer_incons_cases = if ("consistency" %in% names(grimmer_run$raw)) {
      sum(!as.logical(grimmer_run$raw$consistency), na.rm = TRUE)
    } else {
      0L
    },
    debit_available = debit_run$available,
    debit_cases = nrow(debit_run$raw),
    debit_incons_cases = if ("consistency" %in% names(debit_run$raw)) {
      sum(!as.logical(debit_run$raw$consistency), na.rm = TRUE)
    } else {
      0L
    },
    duplicates_available = duplicates_run$available,
    duplicate_flag_rows = if (nrow(duplicates_run$raw) > 0) {
      as_logical_count(
        duplicates_run$raw$x_dup | duplicates_run$raw$sd_dup | duplicates_run$raw$n_dup
      )
    } else {
      0L
    },
    rounding_bias_available = rounding_bias_run$available,
    rounding_bias_groups = nrow(rounding_bias_run$raw),
    statcheck_available = statcheck_run$available,
    statcheck_rows = nrow(statcheck_input),
    statcheck_cases = nrow(statcheck_run$raw),
    statcheck_errors = if ("error" %in% names(statcheck_run$raw)) {
      as_logical_count(statcheck_run$raw$error)
    } else {
      0L
    },
    statcheck_decision_errors = if ("decision_error" %in% names(statcheck_run$raw)) {
      as_logical_count(statcheck_run$raw$decision_error)
    } else {
      0L
    },
    rsprite2_rows = nrow(rsprite2_input),
    scrutiny_seq_enabled = scrutiny_seq
  )
  write_csv(summary_table, file.path(out_dir, "numeric_summary.csv"))

  package_status <- tibble(
    package = c("scrutiny", "rsprite2", "statcheck"),
    installed = c(
      requireNamespace("scrutiny", quietly = TRUE),
      requireNamespace("rsprite2", quietly = TRUE),
      requireNamespace("statcheck", quietly = TRUE)
    ),
    version = c(
      safe_package_version("scrutiny"),
      safe_package_version("rsprite2"),
      safe_package_version("statcheck")
    ),
    objective = c(
      "GRIM/GRIMMER/DEBIT/duplication/rounding-bias checks",
      "SPRITE-style proportion and distribution plausibility checks",
      "Recompute p-values from reported statistics and compare consistency"
    ),
    executed = c(
      grim_run$available || grimmer_run$available || debit_run$available,
      requireNamespace("rsprite2", quietly = TRUE),
      statcheck_run$available
    ),
    execution_note = c(
      paste(
        "grim=", grim_run$message,
        "; grimmer=", grimmer_run$message,
        "; debit=", debit_run$message,
        "; duplicates=", duplicates_run$message,
        "; rounding_bias=", rounding_bias_run$message,
        "; seq=", ifelse(scrutiny_seq, "enabled", "disabled")
      ),
      "Package execution not yet implemented in this runner.",
      statcheck_run$message
    )
  )
  write_csv(package_status, file.path(out_dir, "numeric_package_status.csv"))

  cat("Wrote ", file.path(out_dir, "numeric_row_results.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "numeric_summary.csv"), "\n", sep = "")
  cat("Wrote ", file.path(out_dir, "numeric_package_status.csv"), "\n", sep = "")
  cat("Wrote ", grim_raw_path, "\n", sep = "")
  cat("Wrote ", grim_audit_path, "\n", sep = "")
  cat("Wrote ", grimmer_raw_path, "\n", sep = "")
  cat("Wrote ", grimmer_audit_path, "\n", sep = "")
  cat("Wrote ", debit_raw_path, "\n", sep = "")
  cat("Wrote ", debit_audit_path, "\n", sep = "")
  cat("Wrote ", duplicates_path, "\n", sep = "")
  cat("Wrote ", rounding_bias_path, "\n", sep = "")
  cat("Wrote ", statcheck_raw_path, "\n", sep = "")
  cat("Wrote ", standardized_path, "\n", sep = "")
}

main()
