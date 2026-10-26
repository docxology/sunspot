# AGENTS.md — `sunspot/report/docxology/dst`

## What this is

Per-metric report artifacts (Dst index (geomagnetic)) for the docxology correlation run,
exported from a `sunspot.correlate.run_correlation_report` output tree
(`output/correlate/docxology__…/`). Same four files exist in each sibling
metric folder (`ssn/`, `f107/`, `dst/`, `ap/`, `r_ssn/`).

## Layout (verified by direct listing, 2026-08-29)

```
dual_axis.png, lag.png, rolling.csv, scatter.png
```

## Gotchas

- `rolling.csv` has a full daily date index but empty `roll_pearson_90d`
  values before the first 90-day window — blank cells are expected, not corruption.
- These are a curated subset; regenerate full runs with
  `uv run sunspot correlate docxology …` rather than editing artifacts here.
