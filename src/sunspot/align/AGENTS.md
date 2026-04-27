# AGENTS — `align`

| function | description |
|----------|-------------|
| `join.to_daily_dataframe(*series, names=)` | `concat` to DataFrame (optional helper) |
| `join.join_on_dates(left, *others)` | outer join on the *union* of dates; sorted index; preserves series names (autonames missing ones `x`, `x1`, `x2`, …) |
| `join.zscore(s)` | population z-score (ddof=0); constant series → zeros |
| `join.clip_to_window(s, since, until)` | inclusive restriction to `[since, until]` on a daily `DatetimeIndex`; `None` on either side is unbounded; preserves name and dtype |

`stats.rolling_pearson` imports `join_on_dates`. `correlate._series_for_metric`
uses `clip_to_window` when slicing SILSO/OMNI2 series to the run window.
