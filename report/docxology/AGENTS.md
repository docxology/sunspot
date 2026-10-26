# AGENTS.md — `sunspot/report/docxology`

## What this is

docxology correlation-run report exports: one `report.json` with per-metric
association/lag statistics (metrics: `ssn`, `f107`, `dst`, `ap`, `r_ssn` over
2008-01-01 → 2026-04-23) and five per-metric folders of PNGs + rolling CSV.
Produced by `sunspot.correlate.run_correlation_report` — see
[`docs/api/correlate.md`](../../docs/api/correlate.md).

## Layout (verified by direct listing, 2026-08-29)

```
ap/, dst/, f107/, r_ssn/, ssn/, report.json
```

## Gotchas

- `report.json` here is a slimmer per-metric export than the canonical
  `statistics/report.json` described in `output/README.md` — fewer blocks.
- `rolling.csv` files in the metric folders have empty values before the first
  90-day window; that is expected, not corruption.
- Regenerate via the CLI (`uv run sunspot correlate …`); do not hand-edit artifacts.
