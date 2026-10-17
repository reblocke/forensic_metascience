# Conditional summary-statistic reconciliation. No INSPECT-SR qualification route.

integer_scalar <- function(x, name, minimum = 0) {
  if (length(x) != 1L || !is.numeric(x) || !is.finite(x) ||
      x != floor(x) || x < minimum) stop("Invalid integer ", name)
  as.numeric(x)
}

printed_interval <- function(text) {
  if (length(text) != 1L || !is.character(text) ||
      !grepl("^(<=|>=|<|>|=)?[+-]?[0-9]+(\\.[0-9]+)?$", text)) {
    stop("Printed value must preserve a decimal string and optional comparator")
  }
  comparator <- sub("^((<=|>=|<|>|=)?).*", "\\1", text)
  number <- sub("^(<=|>=|<|>|=)", "", text)
  value <- as.numeric(number)
  digits <- if (grepl("\\.", number)) nchar(sub(".*\\.", "", number)) else 0L
  if (digits > 12L) stop("Unsupported printed precision")
  half <- 0.5 * 10^(-digits)
  # Unknown nearest-rounding tie rule: retain both boundary possibilities.
  lower <- value - half
  upper <- value + half
  if (comparator %in% c("<", "<=")) { lower <- -Inf; upper <- value }
  if (comparator %in% c(">", ">=")) { lower <- value; upper <- Inf }
  list(value = value, lower = lower, upper = upper, digits = digits,
       lower_closed = comparator != ">", upper_closed = comparator != "<")
}

in_printed_interval <- function(value, text) {
  p <- printed_interval(text)
  if (!is.finite(value)) return(FALSE)
  # Numerical tolerance only for unspecified ties, never for strict inequalities.
  tol <- 1e-12 * max(1, abs(value))
  lo <- if (p$lower_closed) value >= p$lower - tol else value > p$lower
  hi <- if (p$upper_closed) value <= p$upper + tol else value < p$upper
  lo && hi
}

intervals_overlap <- function(lower, upper, printed) {
  p <- printed_interval(printed)
  if (upper < p$lower || lower > p$upper) return(FALSE)
  if (!p$lower_closed && upper <= p$lower) return(FALSE)
  if (!p$upper_closed && lower >= p$upper) return(FALSE)
  TRUE
}

enumerate_or <- function(N, D, m) {
  N <- integer_scalar(N, "N", 1)
  D <- integer_scalar(D, "D")
  m <- integer_scalar(m, "m")
  if (D > N || m > N) stop("Margins exceed N")
  lo <- max(0, m + D - N)
  hi <- min(m, D)
  if (hi - lo > 100000) stop("Enumeration exceeds bounded request size")
  lapply(seq(lo, hi), function(a) {
    b <- m - a; c <- D - a; d <- N - m - D + a
    numerator <- a * d; denominator <- b * c
    state <- if (numerator == 0 && denominator == 0) "undefined" else
      if (denominator == 0) "infinite" else if (numerator == 0) "zero" else "finite"
    value <- if (state == "undefined") NA_real_ else if (state == "infinite") Inf else
      numerator / denominator
    list(a = a, b = b, c = c, d = d, state = state, or = value,
         se = if (all(c(a, b, c, d) > 0)) sqrt(sum(1 / c(a, b, c, d))) else Inf)
  })
}

wald_information <- function(reported) {
  est <- printed_interval(reported$or)
  low <- printed_interval(reported$lower)
  high <- printed_interval(reported$upper)
  if (low$lower <= 0 || high$lower <= low$upper || est$lower <= 0 ||
      any(!is.finite(c(est$lower, est$upper, low$lower, low$upper, high$lower, high$upper)))) {
    stop("Wald reconstruction requires positive, ordered, finite rounded limits")
  }
  z <- stats::qnorm(.975)
  se <- (log(high$value) - log(low$value)) / (2 * z)
  se_min <- (log(high$lower) - log(low$upper)) / (2 * z)
  se_max <- (log(high$upper) - log(low$lower)) / (2 * z)
  logs <- log(c(est$lower, est$upper))
  abs_min <- if (min(logs) <= 0 && max(logs) >= 0) 0 else min(abs(logs))
  list(implied_se = se, se_min = se_min, se_max = se_max,
       implied_p = 2 * stats::pnorm(-abs(log(est$value)) / se),
       p_min = 2 * stats::pnorm(-max(abs(logs)) / se_min),
       p_max = 2 * stats::pnorm(-abs_min / se_max))
}

reconcile_request <- function(q) {
  result <- list(request_id = q$request_id, check = q$check, status = "blocked",
                 classification = "unresolved_source_or_method_question",
                 n_evaluated = 0L, assumptions = q$assumption_status,
                 details = list(), qualified_method_result = FALSE)
  finish <- function(details, compatible = NULL, arithmetic = FALSE) {
    result$n_evaluated <- 1L
    result$details <- details
    result$status <- if (is.null(compatible)) "calculated" else
      if (compatible) "compatible" else "incompatible"
    result$classification <- if (is.null(compatible)) "supporting_calculation" else
      if (compatible) "successful_reproduction_under_stated_assumptions" else
      if (arithmetic) "confirmed_arithmetic_discrepancy" else "conditional_incompatibility"
    result
  }
  blocked <- function(reason) {
    result$details <- list(reason = reason)
    result
  }
  if (!q$assumption_status %in% c("declared", "conditional")) {
    return(blocked("Analytic assumptions are unknown"))
  }
  if (q$check %in% c("or_margins", "wald_bound")) {
    if (is.null(q$estimator) || !q$estimator %in% c("cross_product", "ordinary_logistic_mle") ||
        !identical(q$adjustment, "crude") || !identical(q$weighting, "unweighted") ||
        !identical(q$predictor_coding, "binary")) {
      return(blocked("Requires a matching unweighted crude binary cross-product/logistic-MLE analysis"))
    }
    if (is.null(q$N) || is.null(q$m) || (q$check == "or_margins" && is.null(q$D))) {
      return(blocked("Required margins unavailable"))
    }
    if (q$check == "or_margins") {
      tables <- enumerate_or(q$N, q$D, q$m)
      compatible <- any(vapply(tables, function(t) in_printed_interval(t$or, q$reported$or), logical(1)))
      return(finish(list(tables = tables, compatible = compatible), compatible))
    }
    if (!identical(q$ci_method, "wald") || !identical(q$se_method, "wald_2x2")) {
      return(blocked("Requires a conventional crude 2x2 Wald standard error and interval"))
    }
    N <- integer_scalar(q$N, "N", 2)
    m <- integer_scalar(q$m, "m", 1)
    if (m >= N) return(blocked("Both predictor groups must be nonempty"))
    bound <- sqrt(4 / m + 4 / (N - m))
    if (!is.null(q$D)) {
      tables <- enumerate_or(N, q$D, m)
      bound <- min(vapply(tables, function(t) t$se, numeric(1)))
    }
    info <- wald_information(q$reported)
    info$minimum_se <- bound
    info$bound_kind <- if (is.null(q$D)) "group_margin_bound" else "integer_table_minimum"
    return(finish(info, info$se_max >= bound))
  }
  if (q$check == "wald_consistency") {
    if (!identical(q$ci_method, "wald") || !identical(q$test_method, "wald")) {
      return(blocked("Unknown or different CI/test methods cannot be reconciled as Wald"))
    }
    info <- wald_information(q$reported)
    low <- printed_interval(q$reported$lower); high <- printed_interval(q$reported$upper)
    info$centered <- intervals_overlap(sqrt(low$lower * high$lower),
                                      sqrt(low$upper * high$upper), q$reported$or)
    info$p_compatible <- intervals_overlap(info$p_min, info$p_max, q$reported$p)
    info$rounding_interpretation <- "conservative outer envelope; compatibility is not proof of a unique reconstruction"
    return(finish(info, info$centered && info$p_compatible))
  }
  if (q$check == "binary_contrast") {
    if (!identical(q$weighting, "unweighted")) return(blocked("Requires unweighted counts"))
    e <- unlist(q$events); n <- unlist(q$denominators)
    if (length(e) != 2 || length(n) != 2) stop("Exactly two event counts and denominators required")
    for (i in 1:2) { integer_scalar(e[i], "events"); integer_scalar(n[i], "denominator", 1) }
    if (any(e > n)) stop("Events exceed denominators")
    risk <- e / n
    rr <- risk[1] / risk[2]
    z <- stats::qnorm(.975)
    rr_ci <- if (all(e > 0)) exp(log(rr) + c(-1, 1) * z * sqrt(sum(1 / e - 1 / n))) else c(NA, NA)
    rd <- risk[1] - risk[2]
    rd_ci <- rd + c(-1, 1) * z * sqrt(sum(risk * (1 - risk) / n))
    mat <- cbind(e, n - e)
    pearson <- suppressWarnings(stats::chisq.test(mat, correct = FALSE))
    values <- list(rr = rr, rr_lower = rr_ci[1], rr_upper = rr_ci[2],
                   rd_percent = 100 * rd, rd_lower_percent = 100 * rd_ci[1],
                   rd_upper_percent = 100 * rd_ci[2], p = unname(pearson$p.value))
    comparisons <- lapply(names(q$reported), function(key) {
      if (!key %in% names(values)) stop("Unknown binary comparison field")
      list(field = key, computed = values[[key]], printed = q$reported[[key]],
           compatible = in_printed_interval(values[[key]], q$reported[[key]]))
    })
    rr_state <- if (is.nan(rr)) "undefined" else if (is.infinite(rr)) "infinite" else
      if (rr == 0) "zero" else "finite"
    return(finish(list(rr = rr, rr_state = rr_state, rr_ci = rr_ci, rd = rd, rd_ci = rd_ci,
                       pearson_p = unname(pearson$p.value),
                       rounding_comparisons = comparisons,
                       rr_ci_method = "unadjusted log-Wald, no zero-cell correction",
                       rd_ci_method = "unpooled Wald", native_pearson = pearson),
                  if (!length(comparisons)) NULL else
                    all(vapply(comparisons, function(x) x$compatible, logical(1)))))
  }
  if (q$check == "exact_contingency") {
    if (!identical(q$weighting, "unweighted")) return(blocked("Requires unweighted counts"))
    mat <- do.call(rbind, lapply(q$cells, unlist))
    if (!identical(dim(mat), c(2L, 3L)) || length(unlist(q$categories)) != 3L ||
        any(!is.finite(mat)) || any(mat < 0) || any(mat != floor(mat))) stop("Requires ordered 2x3 counts")
    if (length(unlist(q$denominators)) != 2L || any(rowSums(mat) != unlist(q$denominators))) {
      stop("Contingency rows disagree with population denominators")
    }
    omnibus <- stats::fisher.test(mat, hybrid = FALSE, simulate.p.value = FALSE)
    collapsed <- stats::fisher.test(cbind(mat[, 1], rowSums(mat[, 2:3, drop = FALSE])))
    collapsed_cells <- cbind(mat[, 1], rowSums(mat[, 2:3, drop = FALSE]))
    cross_product <- prod(diag(collapsed_cells)) / (collapsed_cells[1,2] * collapsed_cells[2,1])
    return(finish(list(omnibus_p = omnibus$p.value, collapsed_p = collapsed$p.value,
                       categories = q$categories, collapsed_contrast = "first category versus remaining categories",
                       conditional_or = unname(collapsed$estimate),
                       cross_product_or = cross_product, native_omnibus = omnibus,
                       native_collapsed = collapsed),
                  if (is.null(q$reported$p)) NULL else in_printed_interval(omnibus$p.value, q$reported$p)))
  }
  if (q$check == "sum") {
    values <- unlist(q$values)
    if (!length(values) || any(!is.finite(values))) stop("Finite summands required")
    return(finish(list(computed_total = sum(values), printed_total = q$reported$total),
                  in_printed_interval(sum(values), q$reported$total), arithmetic = TRUE))
  }
  if (q$check == "percentage") {
    n <- integer_scalar(q$denominator, "denominator", 1)
    count <- integer_scalar(q$count, "count")
    if (count > n) stop("Count exceeds denominator")
    value <- count / n * 100
    return(finish(list(computed_percentage = value, printed_percentage = q$reported$percent),
                  in_printed_interval(value, q$reported$percent)))
  }
  stop("Unsupported reconciliation check")
}
