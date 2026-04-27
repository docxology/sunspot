# AGENTS — `docs/methods/`

| path | content |
|------|---------|
| [`README.md`](README.md)             | Index of method notes |
| [`regression.md`](regression.md)     | OLS + R² + Durbin–Watson + D'Agostino normality |
| [`correlation.md`](correlation.md)   | Pearson / Spearman / Kendall / partial / rolling |
| [`time_lag.md`](time_lag.md)         | Lag scan, CCF, AR(1) pre-whitening, Bartlett bands |
| [`mutual_information.md`](mutual_information.md) | Binned (Miller–Madow) + KSG-1, MI lag curve |

**Multi-login runs:** [cohort.md](../api/cohort.md) and [stats#multi_user](../api/stats.md#multi_user) — not the same report blocks as single-user `correlate`.

**Source of truth:** Every formula or default parameter cited here must
match the implementation in `src/sunspot/stats/*.py`. When a default
changes (e.g. bin rule, max_lag, normality test cut-off), update the
corresponding method note in the same change.

**Style:** Each page follows the same outline — *What it answers · How
it's computed · Defaults & assumptions · Failure modes · Where to read
it in the report · Related plots*. Keep equations short (LaTeX inline);
direct readers to canonical textbooks for proofs.
