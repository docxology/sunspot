# r_ssn/

Report artifacts for the **R (OMNI2 sunspot-number series)** measure of the docxology correlation run
(source: OMNI2 hourly, daily mean (NASA SPDF); may differ slightly from SILSO ssn). Files were produced by `sunspot.correlate.run_correlation_report`
from the docxology commit history vs. this metric (see
[`docs/api/correlate.md`](../../../docs/api/correlate.md)).

| file | content |
|------|---------|
| `dual_axis.png` | daily commits (left axis) vs. this metric (right axis), shared time axis |
| `scatter.png` | daily commits vs. metric value; correlation stats in title |
| `lag.png` | lag-correlation profile (commits shifted vs. metric) |
| `rolling.csv` | `roll_pearson_90d` rolling 90-day Pearson series; dates before the first usable window are empty |

This per-metric subset is a manual export — the full canonical layout
(`statistics/report.json`, `data/`, `analysis/`, overview plots) is described in
[`output/README.md`](../../../output/README.md). Per-metric PNGs are exploratory,
not causal evidence.

Local-only under `projects/ongoing/DataTools/` — never commit. Parent:
[`../README.md`](../README.md).
