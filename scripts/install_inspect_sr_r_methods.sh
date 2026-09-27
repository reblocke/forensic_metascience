#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock_file="$repo_root/config/inspect_sr/r_method_packages.lock.json"
target_lib="${R_LIBS_USER:-${TMPDIR:-/tmp}/inspect-sr-r-library}"
download_dir="$(mktemp -d "${TMPDIR:-/tmp}/inspect-sr-r-pins.XXXXXX")"
trap 'rm -rf "$download_dir"' EXIT
mkdir -p "$target_lib"
export R_LIBS_USER="$target_lib"
export USE_BUNDLED_LIBUV=1

python3 - "$lock_file" "$download_dir" <<'PY'
import hashlib
import json
import pathlib
import sys
import urllib.request

lock_path = pathlib.Path(sys.argv[1])
download_dir = pathlib.Path(sys.argv[2])
lock = json.loads(lock_path.read_text(encoding="utf-8"))
for package in lock["packages"]:
    name = package["name"]
    archive = download_dir / f"{name}.tar.gz"
    with urllib.request.urlopen(package["source_url"]) as response:
        archive.write_bytes(response.read())
    observed = hashlib.sha256(archive.read_bytes()).hexdigest()
    if observed != package["sha256"]:
        raise SystemExit(f"SHA-256 mismatch for {name}: {observed}")
    print(f"verified {name} {package['version']} sha256={observed}")
PY

runtime_imports="$(python3 -c 'import json,sys; print(",".join(json.load(open(sys.argv[1], encoding="utf-8"))["runtime_imports_preparation_only"]))' "$lock_file")"
Rscript -e '
packages <- strsplit(commandArgs(trailingOnly = TRUE)[[1]], ",", fixed = TRUE)[[1]]
utils::install.packages(
  packages,
  lib = Sys.getenv("R_LIBS_USER"),
  repos = "https://cran.rstudio.com",
  dependencies = c("Depends", "Imports", "LinkingTo")
)
' "$runtime_imports"

Rscript - "$lock_file" <<'RS'
args <- commandArgs(trailingOnly = TRUE)
lock <- jsonlite::fromJSON(args[[1]], simplifyVector = FALSE)
packages <- unlist(lock$runtime_imports_preparation_only, use.names = FALSE)
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("Required isolated R imports unavailable: ", paste(missing, collapse = ", "))
RS

for package in scrutiny statcheck simdistr; do
  R CMD INSTALL -l "$target_lib" "$download_dir/$package.tar.gz"
done

Rscript - "$lock_file" <<'RS'
args <- commandArgs(trailingOnly = TRUE)
lock <- jsonlite::fromJSON(args[[1]], simplifyVector = TRUE)
runtime_imports <- jsonlite::fromJSON(args[[1]], simplifyVector = FALSE)$runtime_imports_preparation_only
missing <- unlist(runtime_imports, use.names = FALSE)[
  !vapply(unlist(runtime_imports, use.names = FALSE), requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing)) stop("Required isolated R imports unavailable: ", paste(missing, collapse = ", "))
for (i in seq_len(nrow(lock$packages))) {
  package <- lock$packages$name[[i]]
  expected <- lock$packages$version[[i]]
  if (!requireNamespace(package, quietly = TRUE)) stop(package, " namespace cannot be loaded")
  actual <- as.character(utils::packageVersion(package))
  if (!identical(actual, expected)) stop(package, " version mismatch: ", actual)
  cat(package, actual, "\n")
}
cat(paste(capture.output(utils::sessionInfo()), collapse = "\n"), "\n")
RS
