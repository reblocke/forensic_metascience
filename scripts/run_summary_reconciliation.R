#!/usr/bin/env Rscript
source("R/summary_reconciliation.R")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L || args[1] != "--input" || args[3] != "--out") {
  stop("Usage: run_summary_reconciliation.R --input requests.json --out existing_output_dir")
}
spec <- jsonlite::fromJSON(args[2], simplifyVector = FALSE)
if (!identical(spec$schema_version, "summary_reconciliation_v1")) stop("Unsupported input")
results <- lapply(spec$requests, function(q) {
  tryCatch(reconcile_request(q), error = function(e) {
    list(request_id = q$request_id, check = q$check, status = "failed",
         classification = "execution_failure", n_evaluated = 0L,
         assumptions = q$assumption_status, details = list(error = conditionMessage(e)),
         qualified_method_result = FALSE)
  })
})
saveRDS(results, file.path(args[4], "native_results.rds"))
# Native htest classes remain intact in RDS; JSON contains their plain fields.
plain_fields <- function(x) {
  if (inherits(x, "htest")) x <- unclass(x)
  if (is.list(x)) lapply(x, plain_fields) else x
}
jsonlite::write_json(list(schema_version = "summary_reconciliation_results_v1", results = plain_fields(results)),
                    file.path(args[4], "reconciliation_results.json"), pretty = TRUE,
                    auto_unbox = TRUE, digits = 16, na = "null", null = "null")
rows <- do.call(rbind, lapply(results, function(x) {
  data.frame(request_id = x$request_id, check = x$check, status = x$status,
             classification = x$classification, n_evaluated = x$n_evaluated,
             assumptions = x$assumptions, qualified_method_result = FALSE)
}))
write.csv(rows, file.path(args[4], "reconciliation_results.csv"), row.names = FALSE)
writeLines(capture.output(sessionInfo()), file.path(args[4], "r_session.txt"))
if (any(rows$status == "failed")) stop("One or more reconciliation requests failed; partial results retained")
