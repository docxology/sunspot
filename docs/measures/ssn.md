# SSN — daily total sunspot number (SILSO V2.0)

## Physical meaning

The sunspot number summarises the count of dark photospheric features
weighted by their grouping. It is the longest continuous direct measurement
of solar activity in existence (Wolf, 1849; reanalysed and recalibrated as
the V2.0 series in 2015). Higher SSN means stronger photospheric magnetic
activity and (by lagged proxy) more flares, more coronal mass ejections, and
elevated ionospheric / geomagnetic disturbance.

## Source

- **Provider:** SIDC / Royal Observatory of Belgium — World Data Center
  *Sunspot Index and Long-term Solar Observations* (WDC-SILSO).
- **Pinned URL:** `https://www.sidc.be/silso/DATA/SN_d_tot_V2.0.csv`
- **License:** CC BY-NC 4.0 (non-commercial; cite SILSO/ROB).

## Loader

[`sunspot.datasets.silso.load_silso_daily_tot_v2()`](../../src/sunspot/datasets/silso.py)

```python
from sunspot.datasets import load_silso_daily_tot_v2
df = load_silso_daily_tot_v2()       # DataFrame indexed by date, column 'ssn'
```

The loader caches the CSV to disk and parses semicolon-separated daily
records. The wire format includes redundant year/month/day columns plus a
fractional-year column; sunspot retains only the `date → ssn` mapping.

## Cadence and resampling

- **Native cadence:** 1 record per UTC day.
- **`sunspot` resampling:** none — already daily. Aligned via
  `to_daily_dataframe` in `sunspot.align.join`.

## Range, sentinels, gaps

- **Typical range:** 0 – ~400 (cycle-25 daily peaks reach the low 300s).
- **Missing-value sentinel:** `-1` in the upstream CSV, mapped to `NaN` by
  the loader.
- **Gaps:** Daily SSN is essentially complete from 1818-01-01 to present. A
  handful of provisional days at the file's tail can be revised when SILSO
  finalises the month.

## Pipeline use

- Default first metric in `--metrics ssn,f107,dst,ap`.
- Drives the `dynamics/commits_and_solar.png` overlay (commits MA vs
  z-scored SSN and F10.7).
- `save_seasonal_calendar` uses SSN as the optional annual context strip.
- `save_compare_users_*` and the multi-user phase plot quantise commits by
  z(SSN) terciles.

## Pitfalls

- **V1 vs V2:** Historic literature often cites V1 SSN, which is ~0.6×
  smaller than V2.0 in absolute terms. Do not mix them in regression
  studies.
- **Smoothed sunspot number** (13-month Gaussian smoothed; SSN-S) is a
  *different* product and is **not** what `sunspot` ingests.
- For very long windows (multi-cycle), prefer Pearson on log-transformed or
  z-scored SSN; raw SSN is heavy-tailed.

## References

- Clette, F., Lefèvre, L. (2016). The new Sunspot Number: assembling all
  corrections. *Solar Physics* 291, 2629–2651.
- WDC-SILSO data documentation:
  <https://www.sidc.be/silso/datafiles>
