# AI sharp edges log

Track recurring failure modes you observe when using coding agents.

## Common categories
- **Data assumptions** (wrong column units, missing values, timezones)
- **Silent numerical issues** (off-by-one, wrong axis reduction, dtype cast)
- **I/O and paths** (hard-coded paths, Windows vs POSIX)
- **Performance** (quadratic loops, unnecessary copies)
- **Reproducibility** (non-pinned deps, non-deterministic RNG)
- **Inference assumptions** (wrong test direction, mismatched effect-size family, invalid priors)
- **Package interface drift** (argument names/defaults changed across versions)
- **Overconfident explanations** (describes code it didn't read)

## Template
- **Date:** YYYY-MM-DD
- **Model/tool:**
- **What happened:**
- **Root cause:**
- **How we detected it (test/plot/etc):**
- **Prevent recurrence:**
