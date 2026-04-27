# `sunspot.datasets`

Public re-exports: [`__init__.py`](../../src/sunspot/datasets/__init__.py) — `SILSO_DAILY_TOT_V2_URL`, `load_silso_daily_tot_v2`, `load_omni2_daily`, `load_noaa_daily_solar_indices`.

**Note:** the GitHub client has a separate cache root override
(`SUNSPOT_CACHE`); see [github.md](github.md). Dataset URL files live under
`default_cache_dir()` / `url/`.

## `cache` ([`cache.py`](../../src/sunspot/datasets/cache.py))

| name | description |
|------|-------------|
| `default_cache_dir() -> Path` | `XDG_CACHE_HOME/sunspot` or `~/.cache/sunspot`. |
| `cache_path_for_url(url, suffix) -> Path` | SHA-256–based filename under `url/`. |
| `ensure_cached_url(url, *, suffix=".txt", timeout_s=60, client=None) -> Path` | GET if missing; returns path. |
| `read_text_cached(url, **kwargs) -> str` | `ensure_cached_url` + UTF-8 text read. |

## `silso` ([`silso.py`](../../src/sunspot/datasets/silso.py))

| name | description |
|------|-------------|
| `SILSO_DAILY_TOT_V2_URL` | Pinned WDC-SILSO CSV URL. |
| `load_silso_daily_tot_v2(path_or_url=None, *, cache=True) -> pd.DataFrame` | Index `date`, column `ssn`. CC BY-NC — see root README. |

## `omni` ([`omni.py`](../../src/sunspot/datasets/omni.py))

| name | description |
|------|-------------|
| `OMNI2_YEAR_URL` | Template `…/omni2_{year}.dat`. |
| `load_omni2_hourly_year(year, *, cache=True) -> pd.DataFrame` | Columns `f107`, `dst`, `r_ssn`, `ap_nT`; index hourly UTC. |
| `load_omni2_daily(years, *, cache=True) -> pd.DataFrame` | Concatenated years, `resample("1D").mean()`; in-memory dedup by year set. |

## `noaa_swpc` ([`noaa_swpc.py`](../../src/sunspot/datasets/noaa_swpc.py))

| name | description |
|------|-------------|
| `DAILY_SOLAR_INDICES_URL` | SWPC text product (recent window). |
| `load_noaa_daily_solar_indices(text=None, *, url=, cache=True) -> pd.DataFrame` | Columns `f107`, `solar_spot_number_swpc`. |

**Internals:** `_parse_silso_csv`, `_parse_daily_solar_indices`, `_parse_omni2_*` — covered by fixture-based tests in `tests/`.
