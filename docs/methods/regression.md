# Regression diagnostics

## What it answers

> *Holding everything else equal, how many extra commits per day do we
> expect when the metric moves by one standard deviation, and is the linear
> model an adequate description of the residuals?*

## How it is computed

Implemented in [`save_regression()`](../api/viz.md#plots) — the writer is
both the plot and the statistical record (it returns the diagnostics dict
that ends up in `report.json["metrics"][m]["regression_ols"]`).

1. Drop NaN-pairs; z-score the metric: \(z = (m - \bar m)/\hat\sigma_m\).
2. Fit ordinary least squares
   \[
       \widehat{\text{commits}}_t = \beta_0 + \beta_1 \, z_t.
   \]
3. Report:
   - \(\beta_0, \beta_1\) — intercept and slope (slope = "extra commits per
     +1σ in metric").
   - \(R^2 = 1 - \mathrm{SSR}/\mathrm{SST}\) — coefficient of determination.
   - \(\hat\sigma^2 = \mathrm{SSR}/(n-2)\) — residual variance.
   - **Pearson r** of `(commits, metric)` with Fisher-z 95 % CI and p
     (so the table reports both r and r² for direct comparison with the
     `pearson_ci95` block).
   - **Durbin–Watson** \(d = \sum (\hat\varepsilon_t - \hat\varepsilon_{t-1})^2 / \sum \hat\varepsilon_t^2\).
     A value near 2 means residuals are uncorrelated; values < 1.5 indicate
     positive AR(1) residuals (very common for daily commit data).
   - **D'Agostino-Pearson omnibus normality** on the residuals (combines
     skewness + kurtosis tests; requires \(n \ge 20\)). Small p means the
     residuals are clearly non-normal — heavy commit-count tails will
     usually fail this.

## Defaults & assumptions

- Single regressor, no intercept-only fallback. With < 4 overlapping
  points or zero metric variance the writer raises and the pipeline skips
  the file silently.
- DW assumes equal-spaced observations. The pipeline reindexes everything
  to a strict daily grid before regression, so this holds.

## Failure modes

- **Heavy tails in commits.** OLS treats both axes as continuous Gaussian.
  Commit counts are non-negative integers with weekly seasonality; the
  regression line is correct in expectation but residuals will be
  non-normal (low normality p) and serially correlated (low DW). Treat the
  fit as a *summary*, not a generative model.
- **Outlier weeks.** A single intense weekend can shift β₁; cross-check
  with Spearman ρ in `report.json["metrics"][m]["spearman_ci95"]` and the
  rank-based MA correlation curve.

## Where to read it in the report

- `report.json["metrics"][m]["regression_ols"]` — full diagnostics.
- `summary.txt` line `OLS:  R²=±x.xxx  DW=…  norm-p=…`.
- `visualizations/{m}/regression.png` — scatter + OLS line + 95 % band +
  diagnostic text box; residual histogram inset.
- Mosaic exec-summary card column **R²·DW**.
