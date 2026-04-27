# Align

Joins `pandas` series on the **union** of dates (`join_on_dates`); `zscore` for
visualization and lagged correlation (population, zeros for constant series);
`clip_to_window(series, since, until)` for inclusive date-range slicing used
throughout `correlate._series_for_metric`. Used by `correlate`, `cohort`, and
`stats.rolling_pearson`.
