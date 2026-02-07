#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tibble)
})

required_target_columns <- function() {
  c(
    "study_id",
    "figure_id",
    "panel_id",
    "image_path",
    "plot_type",
    "x_unit",
    "y_unit",
    "x_scale",
    "y_scale",
    "target_series",
    "include"
  )
}

output_columns <- function() {
  c(
    "study_id",
    "figure_id",
    "panel_id",
    "series_id",
    "x_value",
    "y_value",
    "x_unit",
    "y_unit",
    "source_image",
    "digitizer",
    "digitized_at",
    "extract_confidence"
  )
}

empty_digitized_output <- function() {
  tibble(
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

parse_bool <- function(value) {
  text <- tolower(trimws(as.character(value)))
  if (text %in% c("true", "1", "yes", "y")) {
    return(TRUE)
  }
  if (text %in% c("false", "0", "no", "n")) {
    return(FALSE)
  }
  NA
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

parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  parsed <- list(targets = NULL, project_dir = NULL, out = NULL)
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--targets", "--project-dir", "--out")) {
      if (i == length(args)) {
        stop("Missing value for ", key)
      }
      value <- args[[i + 1L]]
      if (key == "--targets") {
        parsed$targets <- value
      } else if (key == "--project-dir") {
        parsed$project_dir <- value
      } else {
        parsed$out <- value
      }
      i <- i + 2L
    } else {
      stop("Unknown argument: ", key)
    }
  }
  if (is.null(parsed$targets) || is.null(parsed$project_dir) || is.null(parsed$out)) {
    stop(
      "Usage: run_plot_digitization.R --targets <targets_csv> ",
      "--project-dir <project_dir> --out <out_csv>"
    )
  }
  parsed
}

validate_targets <- function(targets) {
  required <- required_target_columns()
  missing <- setdiff(required, names(targets))
  if (length(missing) > 0) {
    stop("Missing required target columns: ", paste(missing, collapse = ", "))
  }
  targets <- targets %>%
    select(all_of(required)) %>%
    mutate(
      include = vapply(include, parse_bool, logical(1)),
      x_scale = tolower(as.character(x_scale)),
      y_scale = tolower(as.character(y_scale))
    )
  if (any(is.na(targets$include))) {
    bad <- which(is.na(targets$include))[1]
    stop("Invalid boolean value in `include` at row ", bad)
  }
  allowed_scale <- c("linear", "log10", "log2", "ln")
  if (any(!targets$x_scale %in% allowed_scale)) {
    bad <- which(!targets$x_scale %in% allowed_scale)[1]
    stop("Invalid x_scale at row ", bad, ": ", targets$x_scale[[bad]])
  }
  if (any(!targets$y_scale %in% allowed_scale)) {
    bad <- which(!targets$y_scale %in% allowed_scale)[1]
    stop("Invalid y_scale at row ", bad, ": ", targets$y_scale[[bad]])
  }
  targets
}

stage_images <- function(targets, project_dir) {
  dir.create(project_dir, recursive = TRUE, showWarnings = FALSE)
  staged <- targets %>%
    mutate(
      source_image = as.character(image_path),
      source_exists = file.exists(source_image)
    )
  if (any(!staged$source_exists)) {
    missing <- staged$source_image[!staged$source_exists]
    stop(
      "Missing image files for digitization targets: ",
      paste(unique(missing), collapse = ", ")
    )
  }

  staged_paths <- character(nrow(staged))
  staged_names <- character(nrow(staged))
  for (index in seq_len(nrow(staged))) {
    row <- staged[index, ]
    staged_name <- paste(
      row$study_id[[1]],
      row$figure_id[[1]],
      row$panel_id[[1]],
      basename(row$source_image[[1]]),
      sep = "__"
    )
    staged_path <- file.path(project_dir, staged_name)
    copied <- file.copy(row$source_image[[1]], staged_path, overwrite = TRUE)
    if (!copied) {
      stop("Failed to stage image: ", row$source_image[[1]])
    }
    staged_paths[[index]] <- staged_path
    staged_names[[index]] <- staged_name
  }

  staged %>%
    mutate(
      staged_image = staged_paths,
      staged_name = staged_names
    )
}

match_column <- function(df, candidates) {
  names_lower <- tolower(names(df))
  candidate_lower <- tolower(candidates)
  idx <- match(candidate_lower, names_lower, nomatch = 0L)
  idx <- idx[idx > 0]
  if (length(idx) == 0) {
    return(NA_character_)
  }
  names(df)[idx[[1]]]
}

extract_points <- function(df, source_key) {
  if (!is.data.frame(df) || nrow(df) == 0) {
    return(tibble())
  }
  x_col <- match_column(df, c("x", "time", "month", "months", "x_value"))
  y_col <- match_column(df, c("y", "survival", "estimate", "mean", "value", "y_value"))
  if (is.na(x_col) || is.na(y_col)) {
    return(tibble())
  }
  series_col <- match_column(df, c("series_id", "group", "group_id", "id", "label", "treatment"))

  out <- tibble(
    source_key = source_key,
    series_id = if (is.na(series_col)) {
      rep("series_1", nrow(df))
    } else {
      as.character(df[[series_col]])
    },
    x_value = suppressWarnings(as.numeric(df[[x_col]])),
    y_value = suppressWarnings(as.numeric(df[[y_col]]))
  ) %>%
    filter(is.finite(x_value), is.finite(y_value)) %>%
    mutate(series_id = ifelse(is.na(series_id) | series_id == "", "series_1", series_id))
  out
}

to_source_key <- function(value) {
  key <- tools::file_path_sans_ext(basename(as.character(value)))
  tolower(key)
}

metadata_for_key <- function(source_key, staged) {
  if (nrow(staged) == 1) {
    return(staged[1, ])
  }

  staged_keys <- tolower(tools::file_path_sans_ext(staged$staged_name))
  original_keys <- tolower(tools::file_path_sans_ext(basename(staged$source_image)))
  key <- tolower(source_key)
  idx <- which(staged_keys == key)
  if (length(idx) == 0) {
    idx <- which(original_keys == key)
  }
  if (length(idx) == 0) {
    return(staged[1, ])
  }
  staged[idx[[1]], ]
}

standardize_digitized <- function(raw_data, staged) {
  extracted <- list()

  if (is.data.frame(raw_data)) {
    extracted[[1]] <- extract_points(raw_data, "metaDigitise_output")
  } else if (is.list(raw_data)) {
    names_or_default <- names(raw_data)
    if (is.null(names_or_default)) {
      names_or_default <- rep("metaDigitise_output", length(raw_data))
    }
    for (index in seq_along(raw_data)) {
      extracted[[index]] <- extract_points(raw_data[[index]], names_or_default[[index]])
    }
  }

  combined <- bind_rows(extracted)
  if (nrow(combined) == 0) {
    return(empty_digitized_output())
  }

  who <- Sys.info()[["user"]]
  if (is.null(who) || !nzchar(who)) {
    who <- "unknown"
  }
  stamp <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z")

  rows <- vector("list", nrow(combined))
  for (index in seq_len(nrow(combined))) {
    point <- combined[index, ]
    meta_row <- metadata_for_key(point$source_key[[1]], staged)
    rows[[index]] <- tibble(
      study_id = as.character(meta_row$study_id[[1]]),
      figure_id = as.character(meta_row$figure_id[[1]]),
      panel_id = as.character(meta_row$panel_id[[1]]),
      series_id = as.character(point$series_id[[1]]),
      x_value = as.numeric(point$x_value[[1]]),
      y_value = as.numeric(point$y_value[[1]]),
      x_unit = as.character(meta_row$x_unit[[1]]),
      y_unit = as.character(meta_row$y_unit[[1]]),
      source_image = as.character(meta_row$source_image[[1]]),
      digitizer = who,
      digitized_at = stamp,
      extract_confidence = "medium"
    )
  }

  bind_rows(rows) %>% select(all_of(output_columns()))
}

main <- function() {
  ensure_user_lib()
  args <- parse_args()

  if (!requireNamespace("metaDigitise", quietly = TRUE)) {
    stop(
      "Package `metaDigitise` is not installed. Install with: ",
      "Rscript -e \"install.packages('metaDigitise', repos='https://cloud.r-project.org')\""
    )
  }

  targets_path <- args$targets
  project_dir <- args$project_dir
  out_path <- args$out

  if (!file.exists(targets_path)) {
    stop("Missing targets file: ", targets_path)
  }

  targets <- read_csv(targets_path, show_col_types = FALSE)
  targets <- validate_targets(targets)
  selected <- targets %>% filter(include)

  dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
  if (nrow(selected) == 0) {
    write_csv(empty_digitized_output(), out_path)
    cat("No included targets. Wrote ", out_path, "\n", sep = "")
    return()
  }

  staged <- stage_images(selected, project_dir)
  raw <- metaDigitise::metaDigitise(project_dir, summary = FALSE)
  standardized <- standardize_digitized(raw, staged)
  write_csv(standardized, out_path)
  cat("Wrote ", out_path, "\n", sep = "")
}

main()
