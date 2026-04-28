"""Commit artifact writers and methods.md for correlate runs."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from sunspot.github.commit_cache import commit_series_dir, github_data_dir

from ._constants import DIR_ANALYSIS, OUTPUT_ROOT


def default_correlate_dir(user: str, since: date, until: date) -> Path:
    """Default run directory: ``output/correlate/{user}__{since}__{until}/``."""
    safe_user = user.replace("\\", "_").replace("/", "_")
    slug = f"{safe_user}__{since.isoformat()}__{until.isoformat()}"
    return OUTPUT_ROOT / "correlate" / slug


def _safe_login(name: str) -> str:
    """Sanitize a GitHub login or repo full-name segment for use as a filename."""
    return name.replace("\\", "_").replace("/", "_")


def _safe_repo_filename(full_name: str) -> str:
    return full_name.replace("/", "__")


def _write_per_repo_commits(
    commits_dir: Path,
    commits_map: dict[str, pd.Series],
    *,
    since: date,
    until: date,
) -> list[dict[str, Any]]:
    """Write ``data/commits/by_repo/*.csv`` and return a small manifest list."""
    base = commits_dir / "by_repo"
    base.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for k, s in commits_map.items():
        if not k or k == "__all__":
            continue
        s2 = s.sort_index()
        tot = float(s2.sum()) if len(s2) else 0.0
        fn = f"{_safe_repo_filename(k)}.csv"
        (base / fn).write_text(s2.to_csv(), encoding="utf-8")
        manifest.append({"repo": k, "file": f"by_repo/{fn}", "commits_in_window": tot})
    (commits_dir / "manifest.json").write_text(
        json.dumps(
            {"since": since.isoformat(), "until": until.isoformat(), "repos": manifest},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_commit_rollups(
    commits_dir: Path,
    commits: pd.Series,
    summary: dict[str, Any],
) -> list[Path]:
    """
    Write weekly / monthly / day-of-week roll-ups and a one-row daily summary
    CSV next to ``commits/daily.csv``. Returns the paths written.
    """
    commits_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    weekly = commits.resample("W-MON", label="left", closed="left").sum().rename("commits")
    weekly.index = weekly.index.rename("week_starting")
    p = commits_dir / "weekly.csv"
    weekly.to_csv(p)
    paths.append(p)

    monthly = commits.resample("MS").sum().rename("commits")
    monthly.index = monthly.index.rename("month_starting")
    p = commits_dir / "monthly.csv"
    monthly.to_csv(p)
    paths.append(p)

    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    s = commits.sort_index().astype(float).fillna(0.0)
    dow = pd.to_datetime(s.index).dayofweek
    rows = []
    for k, lab in enumerate(labels):
        sel = s[dow == k]
        n_days = int(sel.size)
        rows.append({
            "dow": lab,
            "n_days": n_days,
            "mean": float(sel.mean()) if n_days else float("nan"),
            "median": float(sel.median()) if n_days else float("nan"),
            "total": float(sel.sum()) if n_days else 0.0,
        })
    p = commits_dir / "dow_means.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    paths.append(p)

    serialisable = {
        k: v for k, v in summary.items()
        if not isinstance(v, list | dict)
    }
    p = commits_dir / "summary.csv"
    pd.DataFrame([serialisable]).to_csv(p, index=False)
    paths.append(p)

    return paths


def _write_per_user_commits(
    commits_dir: Path,
    user_series: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    """Write ``data/commits/by_user/{login}.csv`` for compare-users runs."""
    base = commits_dir / "by_user"
    base.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for login, s in user_series.items():
        if not login:
            continue
        s2 = s.sort_index().astype(float).rename("commits")
        fn = f"{_safe_login(login)}.csv"
        s2.to_csv(base / fn)
        manifest.append({
            "user": login,
            "file": f"by_user/{fn}",
            "commits_in_window": float(s2.sum()),
            "active_days": int((s2 > 0).sum()),
        })
    (base / "manifest.json").write_text(
        json.dumps({"users": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest

def _write_methods(out_root: Path, report: dict[str, Any] | None = None) -> None:
    cdir = commit_series_dir()
    gdb = github_data_dir()
    report = report or {}
    metric_names = list((report.get("metrics") or {}).keys()) or list(
        report.get("requested_metrics") or [],
    )
    metrics = ", ".join(metric_names) or "run metrics"
    lag_max = report.get("lag_max", "max_lag")
    rolling_window = report.get("rolling_window", 90)
    bootstrap = report.get("bootstrap", 0)
    prewhiten = report.get("prewhiten", True)
    enable_acf = not report.get("acf_disabled", False)
    enable_spectral = not report.get("spectral_disabled", False)
    methods = f"""\
# Methods (sunspot)

## Run settings

- Window: `{report.get("since", "?")}` to `{report.get("until", "?")}`.
- Metrics: `{metrics}`.
- Rolling window: `{rolling_window}` days.
- Lag search: `±{lag_max}` days; lag-profile BH-FDR uses `q=0.10`.
- Bootstrap iterations: `{bootstrap}`.
- CCF AR(1) pre-whitening: `{prewhiten}`.
- ACF/PACF panels: `{enable_acf}`. Lomb-Scargle panels: `{enable_spectral}`.

## Inputs

- **GitHub commits** — public, non-fork repositories of the user; per-repo time series
  retrieved via the REST `commits` endpoint, normalized to UTC dates, then aggregated
  to a daily count. Per-repo series are cached on disk under
  `{cdir}/` (portable; see `output/github_data/README.md`). Commit SHA dedup uses
  `{gdb / "github_cache.sqlite3"}` unless `SUNSPOT_CACHE` is set. Legacy cache hits may
  still read `~/.cache/sunspot/commit_series/`.
- **SILSO daily total sunspot number V2.0** (`ssn`) — Brussels SIDC.
- **NASA SPDF OMNI2 daily** — F10.7 cm radio flux (`f107`), Dst index (`dst`),
  ap-index in nT (`ap`), and OMNI's daily R sunspot number (`r_ssn`); aggregated
  from hourly via arithmetic mean.

## Statistics

- Per metric: Pearson r (with 95% Fisher-z CI), Spearman rho (Bonett-Wright CI),
  Kendall tau, plus a lag search in `±{lag_max}` days (Spearman). Best lag,
  minimum profile p, and per-lag FDR flags are recorded.
- Optional percentile bootstrap CIs (paired resampling) when --bootstrap > 0.
- Rolling Pearson and Spearman over the configured `{rolling_window}` day window.
- Lag x window grid (heatmap) over lag in [-60, 60] step 5 and windows of
  30, 90, 180, 365 days.
- Cross-correlation function (CCF) with Bartlett +/- 95% bands; AR(1)
  pre-whitening follows this run's `prewhiten={prewhiten}` setting.
- ACF and PACF (Durbin-Levinson) for commits and each metric.
- Lomb-Scargle periodogram for commits and each metric (peak periods and named
  band-power fractions reported when spectral output is enabled).
- Cross-metric pairwise Spearman matrix.
- Per-repo Spearman with Benjamini-Hochberg FDR control across repos within
  each metric (q = 0.10).
- Multi-user mode: per-user x metric Spearman heatmap with FDR, user x user
  rank matrix on smoothed activity, cumulative-commits-vs-solar, and a
  solar-quantile phase plot.

## Caveats

- Public commits only; squashes and force-pushes can re-time history.
- Solar/geomagnetic indices have annual to decadal cycles; high autocorrelation
  inflates raw p-values. Treat all coefficients as exploratory.
- Detrending and seasonal models are not applied here.
"""
    (out_root / DIR_ANALYSIS).mkdir(parents=True, exist_ok=True)
    (out_root / DIR_ANALYSIS / "methods.md").write_text(methods, encoding="utf-8")

