# Time-lag analysis

## What it answers

> *Does one series lead the other? If so, by how many days, and is the
> apparent lead/lag really there once we strip out the autocorrelation in
> each series?*

`sunspot` runs three complementary lag analyses for every metric.

## 1. Lag scan (rank-based)

[`lag_correlation_search`](../api/stats.md) shifts the **commits** series
by \(\ell \in [-L, +L]\) days (default \(L=60\), configurable via
`--lag-max`) and computes Spearman ρ at each lag. Positive ℓ ⇒ commits
lead the metric. Returns:

- the curve `(ℓ, ρ_ℓ, p_ℓ)`,
- the best lag and its ρ,
- a Benjamini–Hochberg-flagged set of lags with q < 0.05.

The plot is `visualizations/{m}/lag.png` and the data lives at
`report.json["metrics"][m]["lag"]`. The peak lag and its ρ are surfaced
in the **best lag** column of the executive-summary card.

## 2. Cross-correlation function (CCF)

[`cross_correlation_function`](../api/stats.md) computes the symmetric
Pearson cross-correlation up to ±max_lag. By default sunspot
**pre-whitens** both series with a joint AR(1) residualisation
(`ar1_prewhiten`) before the CCF — this strips the dominant lag-1
autocorrelation that would otherwise smear the CCF into a wide hump and
shift the peak.

The plot `visualizations/{m}/ccf.png` shows:

- the CCF curve,
- the **Bartlett ±95 % envelope** \(\pm 1.96 / \sqrt{n_\text{eff}}\),
- a count of lags whose magnitude exceeds the envelope.

## 3. Lag × window heatmap

[`lag_window_grid`](../api/stats.md) computes the median rolling
Spearman ρ over a lag × window grid. The plot `lag_heatmap.png` lets the
reader look for *time-scale-dependent* lag structure (e.g. a coupling
that exists at the 90 d window but vanishes at 30 d).

## AR(1) pre-whitening

For two series \(a, b\) with AR(1) residual structure
\(\hat\phi_a, \hat\phi_b\) the joint pre-whitening is:

\[
    \tilde a_t = a_t - \hat\phi_a a_{t-1}, \quad
    \tilde b_t = b_t - \hat\phi_b b_{t-1}.
\]

[`ar1_prewhiten`](../api/stats.md) returns the burned-in residuals.
Without pre-whitening, two strongly autocorrelated series can show a
spurious peak |r| of 0.5 or more at lag 0 even when independent.

## Where to read it in the report

- `report.json["metrics"][m]["lag"]` — full lag-correlation curve.
- `report.json["metrics"][m]["ccf"]` — peak, prewhiten flag, Bartlett CI,
  `n_eff`.
- `summary.txt` per-metric `Lag:` and `CCF (AR1-pw):` lines.
- Mosaic per-metric tiles: `lag.png`, `ccf.png`, `lag_heatmap.png`, plus
  the new `mi_lag.png` (see [`mutual_information.md`](mutual_information.md)).
