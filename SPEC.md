# SPEC — GitHub commit activity vs. solar and geomagnetic series

## Purpose

- Ingest a GitHub user’s **public** commit timestamps on default branches, aggregated to **UTC calendar days**, per repository and as a single “all repos” series.
- Load **real** vetted time series: international sunspot number (SILSO), and OMNI2-based daily means for F10.7, Dst, ap, and R (OMNI2).
- Align series on a common day index, compute **Pearson / Spearman / Kendall** associations, **lag search** with multiple-comparison awareness (documented, not a substitute for preregistered research), and **rolling** correlation.
- Emit static plots, CSVs, a machine-readable **report JSON** under `statistics/`, and a plaintext `analysis/summary.txt`—all under a run directory inside **`output/`** (see [output/README.md](output/README.md)).

## Out of scope (v1)

- Private repositories, organizations without explicit support, or Gitea/self-hosted remotes.
- Causal inference (Granger, VAR) without extra validation.
- TEC, foF2, or other explicit ionosonde products (possible future module).

## Ethics and data use

- Only **public** GitHub data via the public API. Respect [GitHub Terms](https://docs.github.com/en/site-policy/github-terms) and rate limits; prefer caching and tokens for repeated runs.
- **SILSO** is **CC BY-NC**; commercial redistribution of derived SILSO-based products may be restricted—verify compliance.
- **Exploratory correlation** only: life phase, job changes, tooling, and the solar cycle can confound any apparent link.

## Acceptance criteria (implemented in this repo)

- `uv sync` and `uv run pytest` pass in CI.
- Parsers are covered by **real file snippets** (fixtures), not hand-waved numeric mocks for domain code.
- CLI `sunspot correlate` runs end-to-end for a date range, writing JSON and images.

## Future

- Optional network integration tests.
- Optional TEC/foF2 ingest behind the same `datasets/` API.
