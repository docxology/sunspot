# Mutual information

## What it answers

> *Beyond linear or rank dependence, how much do commits and the metric
> share in information-theoretic terms — and at what lag?*

Pearson and Spearman pick up only monotone structure. **Mutual
information**

\[
    I(X; Y) = \int p(x, y) \log \frac{p(x, y)}{p(x)p(y)} \, dx \, dy
\]

picks up *any* statistical dependence (nonlinear, non-monotone,
multimodal). It is zero iff `X ⟂ Y`. `sunspot` implements two
estimators and a lag scan; both are exposed by
[`sunspot.stats.information`](../api/stats.md#information).

## 1. Binned (histogram) estimator with Miller–Madow correction

[`mutual_information_binned`](../api/stats.md#information):

1. Drop NaN-pairs.
2. Choose a 2-D bin grid. Default uses the **Freedman–Diaconis** rule on
   each axis (clamped to `[8, 64]`), then takes the larger of the two so
   the joint grid is square.
3. Compute the plug-in MI on the joint histogram.
4. Apply the **Miller–Madow** finite-sample correction:

\[
    \Delta I = \frac{m_X + m_Y - \hat R - 1}{2 n}
\]

   where \(m_X, m_Y\) are the number of *occupied* marginal bins and
   \(\hat R\) the number of jointly-occupied joint cells. This typically
   subtracts the well-known positive bias of the plug-in estimator for
   sparse joints.

The estimate is clipped at zero. Returns `(mi_nats, n, bins_used)`.

A normalisation `normalised_mi(mi, n, bins)` divides by
`log(min(bins, n))` so MI lands in `[0, 1]` regardless of the bin grid —
useful for cross-metric comparison inside the executive summary.

## 2. KSG (Kraskov-Stögbauer-Grassberger) k-NN estimator

[`mutual_information_ksg`](../api/stats.md#information): the standard
distribution-free MI estimator (KSG-1):

\[
    \hat I_\text{KSG-1}(X;Y) = \psi(k) + \psi(N) - \langle \psi(n_X + 1) + \psi(n_Y + 1) \rangle
\]

where \(\psi\) is the digamma, \(N\) the sample size, and \(n_X, n_Y\)
count marginal points within the joint Chebyshev k-NN distance. Default
\(k=5\). Lower bias than histograms when the joint isn't axis-aligned;
slower (\(O(N \log N)\)).

A tiny iid jitter is added to handle ties (e.g. days with identical Ap
values); the seed is fixed so re-runs are reproducible.

## 3. MI lag curve

[`mutual_information_lag_curve`](../api/stats.md#information) mirrors
the lag-correlation scan: at each \(\ell \in [-L, +L]\) it computes
\(I(\text{commits}.\text{shift}(\ell); \text{metric})\) using the
estimator of choice (default `binned`).

The matching plot writer is
[`save_mi_lag_curve`](../api/viz.md#plots) — it draws the chosen
estimator solid and the alternate estimator faintly dashed as a
sanity check.

## Defaults & assumptions

- Both inputs are coerced to `float`; pairs with NaN in either series are
  dropped pairwise.
- For `binned`, the Freedman–Diaconis rule is the default; pass an
  explicit integer to fix the grid (useful for cross-day-of-week MI).
- For `ksg`, `k=5` is the standard reference; raising k smooths the
  estimate at the cost of more bias toward zero for short series.

## Failure modes

- **Constant input.** Returns `0.0` (no information possible).
- **Very small n.** Both estimators are noisy below `n ≈ 100`; the binned
  estimator returns `nan` for `n<4`, KSG for `n ≤ k+1`.
- **Heavy ties.** KSG handles ties via random jitter; binned MI is robust
  by design.

## Where to read it in the report

- `report.json["metrics"][m]["mutual_information"]`:
  `binned_nats`, `binned_normalised`, `binned_bins`, `ksg_nats`, `n`.
- `report.json["metrics"][m]["mi_lag"]`:
  `lags`, `values_nats`, `n_per_lag`, `best_lag`, `best_value_nats`,
  `method`, `bins_or_k`.
- `summary.txt` line `MI:    binned=… nat (norm=…, bins=…)  KSG=… nat  peak=… @ lag=…d`.
- Mosaic exec-summary card column **MI [nats] / lag**.
- Per-metric mosaic tile `mi_lag.png`.
