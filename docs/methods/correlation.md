# Correlation: linear, rank, partial, rolling, moving-average

## What it answers

> *Do commits and the geophysical metric move together at the same time?
> If so, is the dependence linear, monotone, or only conditional on
> autocorrelation?*

`sunspot` reports **three** raw associations side by side and several
*derived* correlations that adjust for known confounds.

## Pearson r — linear association

\[
    r = \frac{\sum (x - \bar x)(y - \bar y)}
             {\sqrt{\sum (x - \bar x)^2}\sqrt{\sum (y - \bar y)^2}}
\]

- 95 % CI from the Fisher z-transform — see
  [`pearson_with_ci`](../api/stats.md).
- Heavy commit-tail outliers can dominate r; sunspot always pairs r with
  Spearman ρ.

## Spearman ρ and Kendall τ — monotone / rank association

- ρ replaces the values with their ranks before computing r → robust to
  outliers and to monotonic transforms.
- τ counts concordant minus discordant pairs → robust *and* easy to
  interpret as a probability.
- 95 % CI for ρ uses the **Bonett–Wright** Fisher-z extension; see
  [`spearman_with_ci`](../api/stats.md).

## Partial correlation (AR1-controlled)

For each metric `sunspot` also reports the partial Pearson r and partial
Spearman ρ between commits and the metric, **conditioning on one-day
lags of both series**:

\[
    r_{c,m \mid c_{-1}, m_{-1}}
\]

This removes most of the spurious correlation that arises because both
series are autocorrelated. See
[`partial_correlation`](../api/stats.md). When the partial r is much
smaller than the raw r, the joint movement is mostly inertia in each
series, not a same-day coupling.

## Rolling correlation

`save_rolling_corr` plots a 90-day rolling Pearson **and** Spearman with
significance bands. It is descriptive (no test), useful for spotting
regime changes (e.g. a particular solar cycle in which the dependence
flips sign).

## Moving-average correlation curve

`save_ma_correlation_curve` runs Pearson and Spearman with their 95 %
CIs at smoothing windows
\(w \in \{1, 3, 7, 14, 30, 60, 90, 180, 365\}\) days and reports an
*effective* sample size \(n_\text{eff}\) per window (deflated for
within-window dependence). It is the cleanest way to ask "at what
timescale is there *any* coupling?".

The peak |r| / lag is summarised in the executive-summary card.

## Cross-metric matrix

`save_metric_correlation_matrix` plots the symmetric Spearman matrix
between SSN, F10.7, Dst, Ap (and r_ssn). Used as a sanity check that the
solar / geomagnetic block-structure is recovered (SSN ↔ F10.7 highly
positive; Dst anti-correlated with Ap; etc.).

## Where to read it in the report

- `report.json["metrics"][m]["pearson_ci95"]`, `spearman_ci95`,
  `kendall`.
- `report.json["metrics"][m]["partial_correlation_ar1"]`.
- `report.json["metrics"][m]["ma_correlations"]` — full curve.
- `summary.txt` per-metric block (lines `Pearson`, `Spearman`, `MA-r`,
  `partial`).
- Mosaic exec-summary card columns **Pearson r**, **Spearman ρ**,
  **MA peak |r|**, **partial r (AR1)**.

## Among GitHub logins (cohort)

For multiple **user** time series and no per-metric figure grid, the package
uses Spearman (and similar) in [`multi_user_associations`](../api/stats.md#multi_user)
and pairwise user×user structure in `multi_user_rank_matrix`, not the
commit-vs-metric blocks above. See [cohort.md](../api/cohort.md).
