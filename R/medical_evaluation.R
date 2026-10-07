# Descriptive counts of operator-attested evaluation records, never qualification.
# Inputs are versioned tables exported from explicitly validated private records.

medical_evaluation_outcomes <- function(views, findings, references, matches,
                                       synthesis, timings, attempts) {
  require_columns <- function(x, columns, label) {
    if (!is.data.frame(x) || !all(columns %in% names(x))) {
      stop(paste("Missing evaluation table columns:", label))
    }
  }
  flag <- function(x) {
    if (is.logical(x)) return(x)
    text <- as.character(x)
    text[!is.na(text) & text == ""] <- NA_character_
    if (any(!is.na(text) & !text %in% c("TRUE", "FALSE"))) {
      stop("Evaluation flags require TRUE, FALSE or unknown.")
    }
    as.logical(text)
  }
  number <- function(x) {
    if (is.character(x)) x[!is.na(x) & x == ""] <- NA_character_
    result <- suppressWarnings(as.numeric(x))
    if (any(!is.na(x) & is.na(result)) ||
        any(!is.na(result) & (!is.finite(result) | result < 0))) {
      stop("Observed evaluation quantities require finite nonnegative numbers or unknown.")
    }
    result
  }
  totals <- function(x) {
    x <- number(x)
    known <- sum(x, na.rm = TRUE)
    if (!is.finite(known)) stop("Evaluation sum is not representable; no clipping.")
    list(total = if (!length(x) || anyNA(x)) NA_real_ else known,
         known_sum = known, unknown_count = sum(is.na(x)), known_count = sum(!is.na(x)))
  }
  frames <- function(rows) {
    if (!length(rows)) return(data.frame())
    do.call(rbind, lapply(rows, function(row) as.data.frame(row, stringsAsFactors = FALSE)))
  }
  metadata <- c("view_id", "packet_id", "case_id", "analysis_unit_id", "partition",
                "profile_ids", "track", "condition_id", "repetition", "source_set_id",
                "input_equivalence")
  require_columns(views, c(metadata, "reviewer_supplied", "synthesis_supplied"), "views")
  require_columns(findings, c("item_id", "view_id", "case_id", "attempt_id", "stage", "disposition",
                             "serious_false_allegation", "source_attribution"), "findings")
  require_columns(references, c("case_id", "reference_id", "disposition", "important"), "references")
  require_columns(matches, c("item_id", "case_id", "reference_id"), "matches")
  require_columns(synthesis, c("item_id", "view_id", "attempt_id", "stage", "disposition", "distorted",
                              "error_stage", "caveats_lost", "caveats_distorted",
                              "caveats_unresolved"), "synthesis")
  require_columns(timings, c("view_id", "phase", "verification_seconds", "revision_seconds"), "timings")
  require_columns(attempts, c("packet_id", "attempt_id", "status", "elapsed_seconds",
                             "input_tokens", "output_tokens", "total_tokens",
                             "cost_amount", "cost_currency", "reviewer_supplied", "synthesis_supplied"), "attempts")
  if (!nrow(views) || anyDuplicated(views$view_id) || anyDuplicated(views$packet_id) ||
      anyDuplicated(findings$item_id) || anyDuplicated(attempts$attempt_id) ||
      anyDuplicated(references[c("case_id", "reference_id")]) ||
      !all(findings$view_id %in% views$view_id) ||
      !all(synthesis$item_id %in% findings$item_id) ||
      !all(timings$view_id %in% views$view_id) ||
      !all(attempts$packet_id %in% views$packet_id)) stop("Evaluation table identity/scope mismatch.")
  views$reviewer_supplied <- flag(views$reviewer_supplied)
  views$synthesis_supplied <- flag(views$synthesis_supplied)
  attempts$reviewer_supplied <- flag(attempts$reviewer_supplied)
  attempts$synthesis_supplied <- flag(attempts$synthesis_supplied)
  references$important <- flag(references$important)
  findings$serious_false_allegation <- flag(findings$serious_false_allegation)
  synthesis$distorted <- flag(synthesis$distorted)
  attempts$cost_currency <- as.character(attempts$cost_currency)
  attempts$cost_currency[!is.na(attempts$cost_currency) & attempts$cost_currency == ""] <- NA_character_
  if (anyNA(views$reviewer_supplied) || anyNA(views$synthesis_supplied) ||
      anyNA(attempts$reviewer_supplied) || anyNA(attempts$synthesis_supplied) ||
      !all(findings$stage %in% c("reviewer", "synthesis")) ||
      !all(findings$disposition %in% c("confirmed_concern", "unsupported_criticism", "unresolved", "optional_improvement")) ||
      !all(attempts$status %in% c("completed", "partial", "failed", "blocked", "not_started"))) {
    stop("Unsupported evaluation disposition/status or absent stage declaration.")
  }
  for (i in seq_len(nrow(findings))) {
    view <- views[views$view_id == findings$view_id[i], , drop = FALSE]
    attempt <- attempts[attempts$attempt_id == findings$attempt_id[i], , drop = FALSE]
    if (nrow(attempt) != 1 || findings$case_id[i] != view$case_id ||
        attempt$packet_id != view$packet_id ||
        !attempt[[paste0(findings$stage[i], "_supplied")]]) {
      stop("Finding is outside its supplied case/attempt/stage.")
    }
  }
  for (i in seq_len(nrow(matches))) {
    item <- findings[findings$item_id == matches$item_id[i], , drop = FALSE]
    if (nrow(item) != 1 || item$case_id != matches$case_id[i] ||
        !any(references$case_id == matches$case_id[i] &
             references$reference_id == matches$reference_id[i])) stop("Cross-case or unknown reference membership.")
  }
  for (i in seq_len(nrow(synthesis))) {
    item <- findings[findings$item_id == synthesis$item_id[i], , drop = FALSE]
    if (item$view_id != synthesis$view_id[i] || item$attempt_id != synthesis$attempt_id[i] ||
        item$stage != synthesis$stage[i]) stop("Synthesis item/attempt/stage mismatch.")
  }
  finding_summary <- function(view, items, supplied, stage) {
    ref <- references[references$case_id == view$case_id, , drop = FALSE]
    important <- ref$reference_id[ref$disposition == "reference_issue" & !is.na(ref$important) & ref$important]
    detected <- unique(matches$reference_id[matches$case_id == view$case_id &
      matches$item_id %in% items$item_id[items$disposition == "confirmed_concern"]])
    count <- function(condition) if (supplied) sum(condition, na.rm = TRUE) else NA_integer_
    c(as.list(view[metadata]), list(
      stage = stage, output_supplied = supplied, important_reference_count = length(important),
      important_reference_unknown = sum(ref$disposition == "reference_issue" & is.na(ref$important)),
      important_reference_detected = if (supplied) length(intersect(important, detected)) else NA_integer_,
      confirmed_records = count(items$disposition == "confirmed_concern"),
      unsupported_records = count(items$disposition == "unsupported_criticism"),
      unresolved_records = count(items$disposition == "unresolved"),
      optional_records = count(items$disposition == "optional_improvement"),
      serious_false_records = count(items$serious_false_allegation),
      serious_false_unknown = count(is.na(items$serious_false_allegation)),
      source_correct_records = count(items$source_attribution == "correct"),
      source_incorrect_records = count(items$source_attribution == "incorrect"),
      source_unresolved_records = count(items$source_attribution == "unresolved"),
      source_not_provided_records = count(items$source_attribution == "not_provided"),
      case_reference_scope = if ("case_reference_scope" %in% names(view))
        view$case_reference_scope else "unavailable_source_reference",
      review_coverage_available = FALSE))
  }
  finding_rows <- list()
  attempt_rows <- list()
  synthesis_rows <- list()
  effort_rows <- list()
  resource_rows <- list()
  error_rows <- list()
  for (i in seq_len(nrow(views))) {
    view <- views[i, , drop = FALSE]
    scoped_attempts <- attempts[attempts$packet_id == view$packet_id, , drop = FALSE]
    for (stage in c("reviewer", "synthesis")) {
      supplied_column <- paste0(stage, "_supplied")
      if (view[[supplied_column]] != any(scoped_attempts[[supplied_column]])) {
        stop("View stage declarations must reconcile with its supplied attempts.")
      }
      items <- findings[findings$view_id == view$view_id & findings$stage == stage, , drop = FALSE]
      finding_rows[[length(finding_rows) + 1L]] <- c(
        finding_summary(view, items, view[[supplied_column]], stage),
        list(aggregation_scope = "supplied_artifact_union_not_single_run"))
      for (j in seq_len(max(1L, nrow(scoped_attempts)))) {
        reported <- nrow(scoped_attempts) > 0
        attempt_id <- if (reported) scoped_attempts$attempt_id[j] else NA_character_
        selected <- items[!is.na(items$attempt_id) & items$attempt_id == attempt_id, , drop = FALSE]
        if (!reported) selected <- items[FALSE, , drop = FALSE]
        supplied <- reported && scoped_attempts[[supplied_column]][j]
        attempt_rows[[length(attempt_rows) + 1L]] <- c(
          finding_summary(view, selected, supplied, stage),
          list(attempt_id = attempt_id, attempt_status = if (reported) scoped_attempts$status[j] else "unreported",
               aggregation_scope = "one_declared_attempt_not_verified_execution"))
      }
    }
    rows <- synthesis[synthesis$view_id == view$view_id, , drop = FALSE]
    synthesis_rows[[length(synthesis_rows) + 1L]] <- c(as.list(view[metadata]), list(
      lost_records = sum(rows$disposition == "lost"),
      new_in_synthesis_records = sum(rows$disposition == "new_in_synthesis"),
      distorted_records = sum(rows$distorted, na.rm = TRUE),
      distortion_unknown = sum(is.na(rows$distorted)),
      unavailable_records = sum(rows$disposition == "unavailable"),
      unresolved_records = sum(rows$disposition == "unresolved"),
      caveats_lost = sum(number(rows$caveats_lost)),
      caveats_distorted = sum(number(rows$caveats_distorted)),
      caveats_unresolved = sum(number(rows$caveats_unresolved))))
    for (error_stage in c("source_extraction", "study_reconstruction", "reasoning", "retrieval",
                          "numerical_execution", "report_synthesis", "unknown", "not_applicable")) {
      error_rows[[length(error_rows) + 1L]] <- c(as.list(view[metadata]), list(
        error_stage = error_stage, annotated_records = sum(rows$error_stage == error_stage)))
    }
    for (phase in c("candidate_assessment", "synthesis_assessment")) {
      rows <- timings[timings$view_id == view$view_id & timings$phase == phase, , drop = FALSE]
      verification <- totals(rows$verification_seconds)
      revision <- totals(rows$revision_seconds)
      effort_rows[[length(effort_rows) + 1L]] <- c(as.list(view[metadata]), list(
        phase = phase, reported_time_records = nrow(rows),
        verification_seconds = verification$total, verification_known_sum = verification$known_sum,
        verification_unknown_count = verification$unknown_count,
        revision_seconds = revision$total, revision_known_sum = revision$known_sum,
        revision_unknown_count = revision$unknown_count))
    }
    rows <- attempts[attempts$packet_id == view$packet_id, , drop = FALSE]
    currencies <- unique(as.character(rows$cost_currency))
    if (!length(currencies)) currencies <- NA_character_
    for (currency in currencies) {
      selected <- if (is.na(currency)) rows[is.na(rows$cost_currency), , drop = FALSE] else
        rows[!is.na(rows$cost_currency) & rows$cost_currency == currency, , drop = FALSE]
      row <- c(as.list(view[metadata]), list(cost_currency = currency,
        reported_attempts = nrow(selected), completed_attempts = sum(selected$status == "completed"),
        partial_attempts = sum(selected$status == "partial"), failed_attempts = sum(selected$status == "failed"),
        blocked_attempts = sum(selected$status == "blocked"),
        not_started_attempts = sum(selected$status == "not_started")))
      for (field in c("elapsed_seconds", "input_tokens", "output_tokens", "total_tokens", "cost_amount")) {
        value <- totals(selected[[field]])
        prefix <- if (field == "cost_amount") "cost" else field
        row[[field]] <- value$total
        row[[paste0(prefix, "_known_sum")]] <- value$known_sum
        row[[paste0(prefix, "_unknown_count")]] <- value$unknown_count
      }
      resource_rows[[length(resource_rows) + 1L]] <- row
    }
  }
  outcomes <- frames(attempt_rows)
  paired <- list()
  for (i in seq_len(nrow(outcomes))) {
    left <- outcomes[i, , drop = FALSE]
    for (j in seq_len(nrow(outcomes))) {
      right <- outcomes[j, , drop = FALSE]
      if (j <= i || left$case_id != right$case_id || left$track != right$track ||
          left$repetition != right$repetition || left$stage != right$stage ||
          left$condition_id == right$condition_id) next
      matched <- left$source_set_id == right$source_set_id &&
        left$input_equivalence != "unmatched" && right$input_equivalence != "unmatched"
      status <- if (!matched) "unmatched_source_access" else if
        (!left$output_supplied || !right$output_supplied) "output_unavailable" else "descriptive_matched_sources"
      paired[[length(paired) + 1L]] <- list(case_id = left$case_id,
        analysis_unit_id = left$analysis_unit_id, partition = left$partition,
        profile_ids = left$profile_ids, track = left$track, repetition = left$repetition,
        stage = left$stage, left_condition = left$condition_id, right_condition = right$condition_id,
        left_attempt_id = left$attempt_id, right_attempt_id = right$attempt_id,
        left_attempt_status = left$attempt_status, right_attempt_status = right$attempt_status,
        pairing_scope = "same_case_track_planned_repetition_all_declared_attempt_pairs",
        independent_experimental_units = FALSE,
        comparison_status = status, important_detection_difference = if (status == "descriptive_matched_sources")
          right$important_reference_detected - left$important_reference_detected else NA_real_)
    }
  }
  list(findings_by_view_stage = frames(finding_rows), findings_by_attempt_stage = outcomes,
       synthesis_by_view = frames(synthesis_rows),
       effort_by_view_phase = frames(effort_rows), resources_by_packet_currency = frames(resource_rows),
       error_stage_by_view = frames(error_rows), paired_case_comparisons = frames(paired))
}
