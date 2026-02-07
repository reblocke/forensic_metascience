"""Entry point for deterministic preprocessing (no plotting).

Snakemake-friendly.
"""

from __future__ import annotations

from pathlib import Path

from research_project.pipeline import default_config, run_pipeline


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = default_config(repo_root)
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
