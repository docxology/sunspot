# Datasets

Implements **fetch → cache → parse** for public solar/geomagnetic products:

- `silso.py` — daily total SSN V2.0 CSV (semicolon).
- `noaa_swpc.py` — recent `daily-solar-indices.txt` (space-separated rows).
- `omni.py` — SPDF `omni2_YYYY.dat` hourly lines; daily mean by resample.
- `cache.py` — `~/.cache/sunspot/url/` keyed by URL hash.

Tests use `tests/fixtures/` snippets with real line formats.
