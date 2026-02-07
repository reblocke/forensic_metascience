# Optional: Snakemake orchestration for the pipeline.
#
# Usage:
#   uv sync
#   uv run snakemake -c1

rule all:
    input:
        "data/processed/sample_processed.csv",
        "reports/diagnostics/hist_value.png",

rule process:
    input:
        "data/raw/sample.csv",
    output:
        "data/processed/sample_processed.csv",
    shell:
        "uv run python scripts/process.py"

rule diagnostics:
    input:
        "data/processed/sample_processed.csv",
    output:
        "reports/diagnostics/hist_value.png",
    shell:
        "uv run python scripts/plot_diagnostics.py --input {input} --outdir reports/diagnostics"
