# Methods (sunspot)

## Inputs

- **GitHub commits** — public, non-fork repositories of the user; per-repo time series
  retrieved via the REST `commits` endpoint, normalized to UTC dates, then aggregated
  to a daily count. Per-repo series are cached on disk under
  `/Users/4d/Documents/GitHub/sunspot/output/github_data/commit_series/` (portable; see `output/github_data/README.md`). Commit SHA dedup uses
  `/Users/4d/Documents/GitHub/sunspot/output/github_data/github_cache.sqlite3` unless `SUNSPOT_CACHE` is set. Legacy cache hits may
  still read `~/.cache/sunspot/commit_series/`.
- **SILSO daily total sunspot number V2.0** (`ssn`) — Brussels SIDC.
- **NASA SPDF OMNI2 daily** — F10.7 cm radio flux (`f107`), Dst index (`dst`),
  ap-index in nT (`ap`), and OMNI's daily R sunspot number (`r_ssn`); aggregated
  from hourly via arithmetic mean.

## Statistics

- Per metric: Pearson r (with 95% Fisher-z CI), Spearman rho (Bonett-Wright CI),
  Kendall tau, plus a lag search in ±max_lag days (Spearman). Best lag and
  minimum profile p are recorded.
- Optional percentile bootstrap CIs (paired resampling) when --bootstrap > 0.
- Rolling Pearson and Spearman over a configurable window (default 90 days).
- Lag x window grid (heatmap) over lag in [-60, 60] step 5 and windows of
  30, 90, 180, 365 days.
- Cross-correlation function (CCF) with Bartlett +/- 95% bands; AR(1)
  pre-whitening on by default to suppress autocorrelation-driven inflation.
- ACF and PACF (Durbin-Levinson) for commits and each metric.
- Lomb-Scargle periodogram for commits and each metric (peak periods reported).
- Cross-metric pairwise Spearman matrix.
- Per-repo Spearman with Benjamini-Hochberg FDR control across repos within
  each metric (q = 0.10).
- Multi-user mode: per-user x metric Spearman heatmap with FDR, user x user
  rank matrix on smoothed activity, cumulative-commits-vs-solar, and a
  solar-quantile phase plot.

## Caveats

- Public commits only; squashes and force-pushes can re-time history.
- Solar/geomagnetic indices have annual to decadal cycles; high autocorrelation
  inflates raw p-values. Treat all coefficients as exploratory.
- Detrending and seasonal models are not applied here.
