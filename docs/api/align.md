# `sunspot.align` (`align.join`)

Source: [`src/sunspot/align/join.py`](../../src/sunspot/align/join.py).

| name | description |
|------|-------------|
| `to_daily_dataframe(*series: pd.Series, names=None) -> pd.DataFrame` | Horizontally concatenates series; default column names from `s.name` or `s0`, `s1`, … |
| `join_on_dates(left: pd.Series, *others) -> pd.DataFrame` | Outer join on the **union** of the datetime indices, sorted. First column name from `left.name` or `x`. |
| `zscore(s: pd.Series) -> pd.Series` | Population std (`ddof=0`); zero std → all zeros. |
| `clip_to_window(s: pd.Series, since: date \| None, until: date \| None) -> pd.Series` | Inclusive restriction to `[since, until]`; either side may be `None` to leave that edge unbounded. Preserves `s.name` and dtype. Used by `correlate._series_for_metric`. |

The [`correlate`](correlate.md) and [cohort](cohort.md) pipelines both build a daily `DatetimeIndex` for each series before alignment with metrics.

Direct tests: `tests/test_align.py`. Broader coverage flows through `stats` (e.g. `rolling_pearson`) and the correlate pipeline.
