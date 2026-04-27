"""On-disk cache for per-repository daily commit counts (avoids re-fetching GitHub API)."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd

from sunspot.datasets.cache import default_cache_dir

_LOG = logging.getLogger(__name__)


def github_data_dir() -> Path:
    """
    Project-local base for GitHub client data under ``output/github_data/``
    (portable: archive or rsync this tree to reuse fetches on another machine).

    Override individual pieces with ``SUNSPOT_COMMIT_SERIES`` (per-repo CSV tree)
    or ``SUNSPOT_CACHE`` (SQLite, see :func:`sunspot.github.client.default_sqlite_path`).
    """
    return (Path.cwd() / "output" / "github_data").resolve()


def commit_series_dir() -> Path:
    """
    Directory root for per-user subfolders of per-repo daily CSVs. Default:
    ``output/github_data/commit_series/`` (see :func:`github_data_dir`).

    Set ``SUNSPOT_COMMIT_SERIES`` to an absolute path to use a different root
    (replaces the default, not merged with ``github_data_dir()``).
    """
    env = os.environ.get("SUNSPOT_COMMIT_SERIES")
    if env and str(env).strip():
        return Path(env).expanduser().resolve()
    return (github_data_dir() / "commit_series").resolve()


def _legacy_commit_series_dir() -> Path:
    return (default_cache_dir() / "commit_series").resolve()


def _safe_segment(s: str) -> str:
    return s.replace("\\", "_").replace("/", "__").replace(":", "-")


def commit_series_cache_path(
    user: str,
    full_name: str,
    since: date,
    until: date,
    *,
    root: Path | None = None,
) -> Path:
    base = root if root is not None else commit_series_dir()
    base = base / _safe_segment(user)
    base.mkdir(parents=True, exist_ok=True)
    fn = f"{_safe_segment(full_name)}__{since.isoformat()}__{until.isoformat()}.csv"
    return base / fn


def commit_series_meta_path(path: Path) -> Path:
    return path.with_name(path.stem + ".meta.json")


def _read_commit_series_path(p: Path) -> pd.Series | None:
    if not p.is_file() or p.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if df.empty:
            s = pd.Series(dtype="float64", name="commits")
        else:
            s = df.squeeze("columns")
            if not isinstance(s, pd.Series):
                s = pd.Series(s.iloc[:, 0], name="commits")
            s = s.sort_index()
            s.index = pd.to_datetime(s.index).normalize()
            s.name = s.name or "commits"
    except (OSError, ValueError) as e:
        _LOG.debug("commit cache read failed %s: %s", p, e)
        return None
    nz = int((s > 0).sum()) if len(s) else 0
    _LOG.debug("commit cache hit: %s (%s non-zero days)", p.name, nz)
    return s


def try_load_commit_series(
    user: str,
    full_name: str,
    since: date,
    until: date,
    *,
    root: Path | None = None,
) -> pd.Series | None:
    p = commit_series_cache_path(user, full_name, since, until, root=root)
    s = _read_commit_series_path(p)
    if s is not None:
        return s
    if root is not None:
        return None
    p2 = commit_series_cache_path(
        user, full_name, since, until, root=_legacy_commit_series_dir(),
    )
    return _read_commit_series_path(p2)


def save_commit_series_cache(
    series: pd.Series,
    user: str,
    full_name: str,
    since: date,
    until: date,
    *,
    root: Path | None = None,
) -> Path:
    p = commit_series_cache_path(user, full_name, since, until, root=root)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = series.sort_index()
    if out.name is None:
        out.name = "commits"
    out.to_csv(p, index_label="date")
    meta = {
        "user": user,
        "full_name": full_name,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "rows": int(len(out)),
    }
    commit_series_meta_path(p).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _LOG.debug("wrote commit cache %s", p)
    return p


def first_commit_date_cache_path(user_login: str) -> Path:
    """``default_cache_dir()/first_commit_date/{sanitized_login}.json``."""
    base = default_cache_dir() / "first_commit_date"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{_safe_segment(user_login)}.json"


def try_load_first_commit_date(user_login: str) -> date | None:
    p = first_commit_date_cache_path(user_login)
    if not p.is_file() or p.stat().st_size == 0:
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as e:
        _LOG.debug("first_commit_date cache read failed %s: %s", p, e)
        return None
    ds = data.get("first_commit_date") or data.get("date")
    if not ds or not isinstance(ds, str):
        return None
    try:
        y, m, d = ds.strip().split("-", 2)
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError) as e:
        _LOG.debug("first_commit_date cache bad date in %s: %s", p, e)
        return None


def save_first_commit_date(user_login: str, d: date) -> Path:
    p = first_commit_date_cache_path(user_login)
    payload = {
        "user_login": user_login,
        "first_commit_date": d.isoformat(),
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _LOG.debug("wrote first_commit_date cache %s", p)
    return p
