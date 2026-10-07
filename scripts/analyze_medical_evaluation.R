#!/usr/bin/env Rscript
# Explicit local CSV boundary; base R only. No source discovery or qualification.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L || args[1] != "--in" || args[3] != "--out") {
  stop("Usage: analyze_medical_evaluation.R --in INPUT_ROOT --out OUTPUT_ROOT")
}
input_root <- normalizePath(args[2], mustWork = TRUE)
output_root <- normalizePath(args[4], mustWork = TRUE)
script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1L) stop("Cannot resolve the analysis script identity.")
script_path <- normalizePath(sub("^--file=", "", script_arg), mustWork = TRUE)
source(file.path(dirname(dirname(script_path)), "R", "medical_evaluation.R"))
table_names <- c("views", "findings", "references", "matches", "synthesis", "timings", "attempts")
tables <- lapply(table_names, function(name) read.csv(file.path(input_root, paste0(name, ".csv")),
  colClasses = "character", na.strings = character(), check.names = FALSE,
  stringsAsFactors = FALSE, fileEncoding = "UTF-8"))
names(tables) <- table_names
result <- do.call(medical_evaluation_outcomes, tables)
result$runtime <- data.frame(name = c("schema_version", "r_version", "platform", "base_version",
                                     "inferential_analysis", "medical_performance_validated"),
  value = c("medical_evaluation_descriptive_tables_v2", R.version.string,
    R.version$platform, as.character(packageVersion("base")), "not_performed", "false"))
targets <- file.path(output_root, paste0(names(result), ".csv"))
if (any(file.exists(targets))) stop("Analysis output exists; choose a fresh run instead of overwriting.")
for (i in seq_along(result)) {
  write.table(result[[i]], targets[i], sep = ",", row.names = FALSE, col.names = TRUE,
              quote = TRUE, na = "", fileEncoding = "UTF-8")
}
