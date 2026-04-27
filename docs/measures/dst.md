# Dst — disturbance storm time index

## Physical meaning

Dst measures the **mean horizontal magnetic field deviation** at four
low-latitude geomagnetic observatories (Hermanus, Kakioka, Honolulu, San
Juan), referenced to a quiet baseline. It is the canonical scalar
descriptor of the **ring current** that develops during geomagnetic storms:
when the ring current intensifies, magnetic field at low latitudes is
suppressed, so Dst becomes **more negative**.

| Dst (nT) | qualitative interpretation |
|----------|----------------------------|
| > -20    | quiet                      |
| -20…-50  | minor disturbance          |
| -50…-100 | moderate storm             |
| -100…-200| intense storm              |
| < -200   | severe / great storm       |

## Source

- **Primary provider:** WDC for Geomagnetism, Kyoto University.
- **Aggregator used by `sunspot`:** NASA GSFC / SPDF **OMNI2**, column
  `dst` (one record per UTC hour).

## Loader

[`sunspot.datasets.omni.load_omni2_daily()`](../../src/sunspot/datasets/omni.py)
returns the column `dst` as a daily mean of the 24 hourly values per UTC
day.

## Cadence and resampling

- **Native cadence:** hourly nT.
- **Sunspot resampling:** daily arithmetic mean. Pairs of (commit-day, Dst)
  are then aligned in `sunspot.align.join`.

## Range, sentinels, gaps

- **Typical range:** ~ +50 nT (positive sudden impulses) to < -400 nT during
  great storms (e.g. March 1989, October 2003, May 2024).
- **Missing-value sentinel:** OMNI2 uses `99999` (int) → mapped to `NaN`.
- **Gaps:** Continuous since 1957. Provisional values for the latest few
  months are revised by Kyoto.

## Pipeline use

- Third default metric in `--metrics ssn,f107,dst,ap`.
- Lag analyses against commits typically show **negative** correlations at
  short lags during active solar periods (storms suppress field → negative
  Dst → if there is any developer effect, fewer commits would yield a
  *positive* commits×Dst correlation, i.e. commits go down when Dst dips).
  In practice the |effect| is small and dominated by weekly seasonality.
- Annotated in `save_seasonal_calendar` only as the optional context strip
  if explicitly selected (default uses SSN).

## Pitfalls

- **Sign flip.** Dst is the *only* metric in the default set that runs
  *opposite* sign to "more activity → larger value". Read every Dst
  correlation with the inverted convention in mind.
- **Daily-mean dilution.** Storm signatures unfold over hours; daily means
  smooth out fast main-phase deepening. For high-cadence storm work,
  consider sub-daily Dst directly.
- **Pre-2007 epoch:** Dst values before 2007 use a slightly different
  baseline procedure (so-called "old" vs "new" Dst); for cross-decade trend
  work this matters.

## References

- Sugiura, M., Kamei, T. (1991). *Equatorial Dst index 1957–1986*. IAGA
  Bulletin No. 40.
- WDC Kyoto Dst home: <https://wdc.kugi.kyoto-u.ac.jp/dstdir/>
