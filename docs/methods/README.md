# `docs/methods/` — statistical method notes

Topical, narrative companions to the function-level
[`docs/api/`](../api) reference. Each note explains one family of
techniques `sunspot` uses, sketches the math, and points to the exact
function(s) that implement it.

| topic | file | one-line role |
|-------|------|---------------|
| Regression diagnostics              | [`regression.md`](regression.md)   | OLS, R², Durbin–Watson, residual normality |
| Correlation (linear & rank)         | [`correlation.md`](correlation.md) | Pearson / Spearman / Kendall, CIs, partial r |
| Time-lag analysis                   | [`time_lag.md`](time_lag.md)       | lag scan, CCF + Bartlett, AR(1) prewhitening |
| Mutual information                  | [`mutual_information.md`](mutual_information.md) | binned + KSG estimators, MI lag curve |

Cross-cutting references:

- The four daily geophysical inputs are described in
  [`docs/measures/`](../measures/README.md).
- All plot writers consuming these statistics are listed in
  [`docs/api/viz.md`](../api/viz.md).
- The single-user pipeline: [`docs/api/correlate.md`](../api/correlate.md).
- **Among GitHub logins** (no per-metric deep dive):
  [`docs/api/cohort.md`](../api/cohort.md) and [`docs/api/stats.md`](../api/stats.md#multi_user) `multi_user` helpers.
