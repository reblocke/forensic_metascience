METHOD_RECEIPT_SCHEMA_VERSION <- "method_receipt_v1"
METHOD_APPLICABILITY_STATES <- c("eligible", "ineligible", "unknown", "mixed")
METHOD_EXECUTION_STATES <- c(
  "not_requested", "not_implemented", "dependency_missing", "blocked",
  "failed", "partial", "completed"
)

new_method_receipt <- function(
  run_id,
  method_id,
  method_version,
  package_name,
  package_version,
  unit_of_evaluation,
  input_evidence_ids,
  parameters,
  applicability,
  execution,
  n_input,
  n_eligible,
  n_evaluated,
  n_failed,
  n_flagged,
  output_reference,
  diagnostic
) {
  stopifnot(length(applicability) == 1L, applicability %in% METHOD_APPLICABILITY_STATES)
  stopifnot(length(execution) == 1L, execution %in% METHOD_EXECUTION_STATES)
  counts <- c(n_input, n_eligible, n_evaluated, n_failed)
  if (anyNA(counts) || any(counts < 0) || n_eligible > n_input ||
      n_evaluated > n_eligible || n_evaluated + n_failed > n_eligible) {
    stop("Method receipt counts violate input/evaluation bounds.")
  }
  if (!is.na(n_flagged) && (n_flagged < 0 || n_flagged > n_evaluated)) {
    stop("Method receipt flagged count must be bounded by evaluated units.")
  }
  if (execution == "completed" && (n_evaluated < 1L || n_failed > 0L || is.na(n_flagged))) {
    stop("A completed method requires positive evaluated coverage and no failed units.")
  }
  if (execution == "partial" && (n_evaluated < 1L || n_failed < 1L)) {
    stop("A partial method requires both evaluated and failed units.")
  }
  if (execution %in% c("not_requested", "not_implemented", "dependency_missing", "blocked") &&
      (n_evaluated > 0L || !is.na(n_flagged))) {
    stop("An unexecuted method cannot carry evaluated findings.")
  }

  result_status <- if (execution == "completed") {
    if (n_flagged > 0L) "findings_present" else "no_finding"
  } else if (execution == "not_requested") {
    "not_evaluated"
  } else {
    "indeterminate"
  }

  tibble::tibble(
    schema_version = METHOD_RECEIPT_SCHEMA_VERSION,
    run_id = as.character(run_id),
    method_id = as.character(method_id),
    method_version = as.character(method_version),
    package_name = as.character(package_name),
    package_version = as.character(package_version),
    unit_of_evaluation = as.character(unit_of_evaluation),
    input_evidence_ids = as.character(input_evidence_ids),
    parameters = as.character(parameters),
    applicability = as.character(applicability),
    execution = as.character(execution),
    result_status = result_status,
    n_input = as.integer(n_input),
    n_eligible = as.integer(n_eligible),
    n_evaluated = as.integer(n_evaluated),
    n_failed = as.integer(n_failed),
    n_flagged = as.integer(n_flagged),
    output_reference = as.character(output_reference),
    diagnostic = as.character(diagnostic)
  )
}

receipt_from_method_run <- function(
  run_id,
  method_id,
  method_version,
  package_name,
  package_version,
  unit_of_evaluation,
  input_evidence_ids,
  parameters,
  input_count,
  eligible_count,
  method_run,
  output_reference,
  requested = TRUE,
  implemented = TRUE,
  applicability_override = NULL,
  report_text_evaluated = FALSE,
  evaluated_count_override = NULL,
  failed_count_override = NULL,
  flagged_count_override = NULL
) {
  raw <- method_run$raw
  message <- as.character(method_run$message %||% "")
  raw_count <- if (is.null(raw)) 0L else nrow(raw)
  consistency <- if (!is.null(raw) && "consistency" %in% names(raw)) {
    as.logical(raw$consistency)
  } else {
    logical()
  }
  failed_count <- if (!is.null(failed_count_override)) {
    as.integer(failed_count_override)
  } else if (length(consistency)) {
    sum(is.na(consistency))
  } else {
    0L
  }
  evaluated_count <- if (!is.null(evaluated_count_override)) {
    as.integer(evaluated_count_override)
  } else if (length(consistency)) {
    sum(!is.na(consistency))
  } else if (report_text_evaluated && !grepl("error", message, ignore.case = TRUE)) {
    1L
  } else {
    raw_count
  }
  flagged_count <- if (!is.null(flagged_count_override)) {
    as.integer(flagged_count_override)
  } else if (length(consistency)) {
    sum(!consistency, na.rm = TRUE)
  } else if (!is.null(raw) && "error" %in% names(raw)) {
    sum(as.logical(raw$error), na.rm = TRUE)
  } else if (evaluated_count > 0L) {
    0L
  } else {
    NA_integer_
  }

  applicability <- if (!is.null(applicability_override)) {
    applicability_override
  } else if (eligible_count == 0L) {
    if (input_count == 0L) "unknown" else "ineligible"
  } else if (eligible_count < input_count) {
    "mixed"
  } else {
    "eligible"
  }
  if (!requested) {
    execution <- "not_requested"
  } else if (!implemented) {
    execution <- "not_implemented"
    flagged_count <- NA_integer_
  } else if (grepl("not installed|dependency missing", message, ignore.case = TRUE)) {
    execution <- "dependency_missing"
    flagged_count <- NA_integer_
  } else if (eligible_count == 0L) {
    execution <- "blocked"
    flagged_count <- NA_integer_
  } else if (grepl("execution error|execution failed|error:", message, ignore.case = TRUE)) {
    execution <- if (evaluated_count > 0L && failed_count > 0L) "partial" else "failed"
    if (execution == "failed") {
      evaluated_count <- 0L
      flagged_count <- NA_integer_
    }
  } else if (evaluated_count == 0L && failed_count == 0L) {
    execution <- "failed"
    message <- paste(message, "No evaluation units were returned.")
    flagged_count <- NA_integer_
  } else if (failed_count > 0L) {
    execution <- if (evaluated_count > 0L) "partial" else "failed"
    if (execution == "failed") flagged_count <- NA_integer_
  } else {
    execution <- "completed"
  }

  if (execution %in% c("not_requested", "not_implemented", "dependency_missing", "blocked")) {
    evaluated_count <- 0L
    failed_count <- 0L
    flagged_count <- NA_integer_
  }
  if (execution == "failed" && evaluated_count == 0L) {
    failed_count <- max(failed_count, eligible_count)
  }
  if (execution == "partial") {
    failed_count <- max(failed_count, eligible_count - evaluated_count)
  }

  new_method_receipt(
    run_id = run_id,
    method_id = method_id,
    method_version = method_version,
    package_name = package_name,
    package_version = package_version,
    unit_of_evaluation = unit_of_evaluation,
    input_evidence_ids = input_evidence_ids,
    parameters = parameters,
    applicability = applicability,
    execution = execution,
    n_input = input_count,
    n_eligible = eligible_count,
    n_evaluated = evaluated_count,
    n_failed = failed_count,
    n_flagged = flagged_count,
    output_reference = output_reference,
    diagnostic = message
  )
}

`%||%` <- function(value, fallback) {
  if (is.null(value) || length(value) == 0L || is.na(value[[1]])) fallback else value
}
