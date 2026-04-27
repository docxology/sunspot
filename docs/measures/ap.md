# Ap — planetary geomagnetic Ap index

## Physical meaning

Ap is the linear-equivalent average amplitude of geomagnetic disturbance
across a global network of mid-latitude observatories during a UTC day. It
is derived from the **Kp** index (a quasi-logarithmic 0–9 scale) by mapping
each three-hour Kp value to a linear "ap" amplitude (0–400 nT) and averaging
the eight three-hour values per day.

| Ap (nT) | qualitative interpretation                |
|---------|-------------------------------------------|
| 0…7     | quiet                                     |
| 8…15    | unsettled                                 |
| 16…29   | active                                    |
| 30…49   | minor storm (G1)                          |
| 50…99   | moderate storm (G2)                       |
| 100…199 | strong storm (G3)                         |
| 200…399 | severe storm (G4)                         |
| ≥400    | extreme storm (G5; saturated upper bound) |

## Source

- **Primary provider:** GFZ Helmholtz Centre Potsdam (Kp/ap derivation;
  formerly IAGA / Niemegk).
- **Aggregator used by `sunspot`:** NASA GSFC / SPDF **OMNI2**, column
  `ap_nT` (one record per UTC hour, with the daily Ap repeated across hours).

## Loader

[`sunspot.datasets.omni.load_omni2_daily()`](../../src/sunspot/datasets/omni.py)
exposes the column `ap_nT`. The daily aggregation step takes the
arithmetic mean (which equals the underlying daily Ap because the value is
held constant across the eight three-hour subintervals of each UTC day).

## Cadence and resampling

- **Native cadence:** Daily Ap, broadcast hourly inside OMNI2.
- **Sunspot resampling:** daily arithmetic mean (a no-op for Ap by
  construction).

## Range, sentinels, gaps

- **Typical range:** 0 – ~400 nT; values above ~200 are rare.
- **Missing-value sentinel:** OMNI2 uses `999` (int) → mapped to `NaN`.
- **Gaps:** Continuous since 1932. Provisional last-month values are
  revised by GFZ.

## Pipeline use

- Fourth default metric in `--metrics ssn,f107,dst,ap`.
- Pairs naturally with **Dst** as the "geomagnetic response" branch. Both
  rise during storms (Ap goes up, Dst goes down) so they are
  *anti-correlated* by construction.
- Strong solar wind / coronal-hole streams show as Ap elevation without
  large Dst deflection — these are visible as off-diagonal cells in the
  cross-metric correlation matrix.

## Pitfalls

- **Quasi-log nature of Kp leaks through.** Ap is the linearised ap-equivalent
  of Kp, but its distribution remains heavy-tailed. Spearman / rank-based
  statistics are usually more informative than Pearson for Ap; sunspot
  reports both side by side.
- **Saturation.** Both Kp and ap saturate at the top of the scale during
  great storms; rare extreme events are clipped, slightly biasing
  correlations toward zero in extreme bins.

## References

- Matzka, J., Stolle, C., Yamazaki, Y., Bronkalla, O., Morschhauser, A.
  (2021). The geomagnetic Kp index and derived indices of geomagnetic
  activity. *Space Weather*, 19, e2020SW002641.
  <https://doi.org/10.1029/2020SW002641>
- GFZ Kp/ap home: <https://kp.gfz-potsdam.de/>
