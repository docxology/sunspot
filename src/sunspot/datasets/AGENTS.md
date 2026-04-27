# AGENTS — `datasets`

## Functions

| name | description |
|------|-------------|
| `cache.default_cache_dir()` | `XDG_CACHE_HOME` / `~/.cache/sunspot` |
| `cache.ensure_cached_url(url, suffix=, timeout_s=, client=)` | HTTP GET to cache; returns path; INFO for hit/miss and byte size |
| `silso.SILSO_DAILY_TOT_V2_URL` | Pinned public CSV |
| `silso.load_silso_daily_tot_v2(path_or_url=None, cache=True)` | DataFrame, index `date`, col `ssn` |
| `noaa_swpc.DAILY_SOLAR_INDICES_URL` | SWPC product URL |
| `noaa_swpc.load_noaa_daily_solar_indices(text=, url=, cache=True)` | cols `f107`, `solar_spot_number_swpc` |
| `omni.OMNI2_YEAR_URL` | `…/omni2_{year}.dat` |
| `omni.load_omni2_hourly_year(year, cache=True)` | hourly DataFrame, columns `f107`, `dst`, `r_ssn`, `ap_nT` |
| `omni.load_omni2_daily(years, cache=True)` | concatenated hourly, `resample("1D").mean()`; INFO for first-load year span and daily row count, DEBUG for in-memory hits |

## Parser internals

- `_parse_silso_csv`, `_parse_daily_solar_indices` — tested via fixtures.
- `_parse_omni2_hourly_line`, `_parse_omni2_hourly_lines` — whitespace token indices 40/41/49/50 for R, Dst, ap, F10.7 (see NASA `omni2.text`).
