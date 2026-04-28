from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dateutil import parser as dateparser

from sunspot.github.client import default_sqlite_path, github_token, http_client
from sunspot.github.commit_cache import (
    save_commit_series_cache,
    save_first_commit_date,
    try_load_commit_series,
    try_load_first_commit_date,
)

_LOG = logging.getLogger(__name__)
_COMMIT_PAGE_LOG_INTERVAL = 10
# INFO on every Nth page (plus page 1) so large-repo fetches do not look hung.
_COMMIT_PAGE_INFO_INTERVAL = 5
_LOW_RATE_LIMIT_WARNED = False


def _sqlite_db_path(path: Path) -> str:
    """Absolute path as str for reliable SQLite opens."""
    p = path.resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def _init_db(path: Path) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    _maybe_migrate_sqlite_from_legacy(path)
    with sqlite3.connect(_sqlite_db_path(path), timeout=30.0) as cx:
        cx.execute(
            """
            CREATE TABLE IF NOT EXISTS commit_seen(
                user_login TEXT NOT NULL,
                repo TEXT NOT NULL,
                sha TEXT NOT NULL,
                author_ts_utc TEXT NOT NULL,
                PRIMARY KEY(user_login, repo, sha)
            )
            """
        )
        cx.execute("CREATE INDEX IF NOT EXISTS idx_commit_user ON commit_seen(user_login)")
        cx.commit()


def _maybe_migrate_sqlite_from_legacy(target: Path) -> None:
    """If the new default path is missing, copy from ``~/.cache/sunspot/`` once."""
    if target.is_file():
        return
    legacy = Path.home() / ".cache" / "sunspot" / "github_cache.sqlite3"
    if not legacy.is_file() or not legacy.stat().st_size:
        return
    try:
        shutil.copy2(legacy, target)
        _LOG.info(
            "GitHub: copied commit dedup DB from %s to %s (one-time migration)",
            legacy,
            target,
        )
    except OSError as e:
        _LOG.debug("GitHub: sqlite copy from legacy failed: %s", e)


def _parse_gh_time(s: str | None) -> datetime | None:
    if not s:
        return None
    dtx = dateparser.isoparse(s)
    if dtx.tzinfo is None:
        dtx = dtx.replace(tzinfo=timezone.utc)
    return dtx.astimezone(timezone.utc).replace(tzinfo=None)


def _throttle(remaining: str | None) -> None:
    if remaining and remaining.isdigit() and int(remaining) < 5:
        time.sleep(1.0)


def _wait_for_github_rate_limit(response: httpx.Response) -> None:
    """
    Block until GitHub's ``X-RateLimit-Reset`` (UTC epoch seconds) if present,
    else sleep one minute. Adds a 2s buffer.
    """
    reset = response.headers.get("X-RateLimit-Reset")
    if reset and str(reset).isdigit():
        reset_i = int(reset)
        target = reset_i - time.time() + 2.0
        sleep_s = max(1.0, min(7200.0, target))
        reset_utc = datetime.fromtimestamp(reset_i, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        lim = response.headers.get("X-RateLimit-Limit", "?")
        _LOG.warning(
            "GitHub rate limit: sleeping %.0fs until reset (%s); remaining=%s; limit/hour=%s",
            sleep_s,
            reset_utc,
            response.headers.get("X-RateLimit-Remaining", "?"),
            lim,
        )
        if not github_token() or (str(lim).isdigit() and int(lim) <= 60):
            _LOG.warning(
                "To raise the cap: create a read-only personal access token and "
                "export GITHUB_TOKEN=... (thousands of requests/hour vs ~60 unauthenticated). "
                "If you use GitHub CLI: export GITHUB_TOKEN=$(gh auth token) "
                "https://github.com/settings/tokens",
            )
        time.sleep(sleep_s)
    else:
        _LOG.warning("GitHub rate limit: no X-RateLimit-Reset; sleeping 60s")
        time.sleep(60.0)


def _get(client: httpx.Client, path: str, params: dict[str, Any]) -> httpx.Response:
    """GET with handling for primary rate limit (403/429) and transient network errors."""
    rate_attempt = 0
    max_net_retries = 5
    while True:
        net_i = 0
        while True:
            try:
                r = client.get(path, params=params)
                break
            except httpx.RequestError as e:
                if net_i >= max_net_retries:
                    _LOG.error(
                        "GET %s: network error after %s retries: %s",
                        path,
                        max_net_retries,
                        e,
                    )
                    raise
                net_i += 1
                wait = min(60.0, 2.0**net_i)
                _LOG.warning(
                    "GET %s: %s (network retry %s/%s, sleeping %.1fs)",
                    path,
                    e,
                    net_i,
                    max_net_retries,
                    wait,
                )
                time.sleep(wait)
        rem = r.headers.get("X-RateLimit-Remaining", "")
        _LOG.debug(
            "GET %s status=%s remaining=%s",
            path,
            r.status_code,
            rem,
        )
        if r.status_code == 403 and rem == "0":
            rate_attempt += 1
            _LOG.info("rate limit response (attempt %s), waiting", rate_attempt)
            _wait_for_github_rate_limit(r)
            continue
        if r.status_code in (403, 429) and "rate" in (r.text or "").lower():
            rate_attempt += 1
            _LOG.info("rate limit text in body (attempt %s), waiting", rate_attempt)
            _wait_for_github_rate_limit(r)
            continue
        return r


def first_commit_date(
    user_login: str,
    *,
    client: httpx.Client | None = None,
    use_cache: bool = True,
) -> date | None:
    """
    Best-effort earliest authored-commit date for ``user_login`` on GitHub.

    When ``use_cache`` is True and no ``client`` is passed, a prior result under
    ``~/.cache/sunspot/first_commit_date/`` (or ``$XDG_CACHE_HOME/sunspot/…``) is
    returned without calling the API.

    Strategy (after cache, cheap → durable):

    1. ``GET /search/commits?q=author:{user}&sort=author-date&order=asc&per_page=1``
       — one round-trip returns the oldest commit GitHub knows about.
    2. If search returns nothing or fails, fall back to the account
       ``created_at`` from ``/users/{user}``.
    3. Returns ``None`` if both fail; callers should then require an explicit
       ``--since``.

    Successful resolutions are written to the on-disk cache when ``use_cache``
    is True and ``client`` is None (normal CLI / library use).
    """
    if use_cache and client is None:
        cached = try_load_first_commit_date(user_login)
        if cached is not None:
            _LOG.info(
                "first_commit_date(%s): cache → %s",
                user_login,
                cached,
            )
            return cached

    own = client or http_client()
    try:
        out: date | None = None
        try:
            r = _get(
                own,
                "/search/commits",
                params={
                    "q": f"author:{user_login}",
                    "sort": "author-date",
                    "order": "asc",
                    "per_page": 1,
                },
            )
            if r.status_code < 300:
                items = r.json().get("items", [])
                if items:
                    dta = _commit_dt(items[0])
                    if dta is not None:
                        _LOG.info(
                            "first_commit_date(%s): search-commits → %s",
                            user_login, dta.date(),
                        )
                        out = dta.date()
            else:
                _LOG.debug(
                    "first_commit_date(%s): search-commits HTTP %s",
                    user_login, r.status_code,
                )
        except (httpx.HTTPError, ValueError, KeyError) as e:
            _LOG.debug("first_commit_date(%s): search-commits failed: %s", user_login, e)
        if out is None:
            try:
                r2 = _get(own, f"/users/{user_login}", params={})
                if r2.status_code < 300:
                    ca = r2.json().get("created_at")
                    if ca:
                        dta = _parse_gh_time(ca)
                        if dta is not None:
                            _LOG.info(
                                "first_commit_date(%s): account created_at → %s (fallback)",
                                user_login, dta.date(),
                            )
                            out = dta.date()
            except (httpx.HTTPError, ValueError, KeyError) as e:
                _LOG.debug("first_commit_date(%s): /users lookup failed: %s", user_login, e)
        if out is not None and use_cache and client is None:
            save_first_commit_date(user_login, out)
        return out
    finally:
        if client is None:
            own.close()


def list_public_repos(
    user_login: str,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    global _LOW_RATE_LIMIT_WARNED
    own = client or http_client()
    try:
        page = 1
        out: list[dict[str, Any]] = []
        while True:
            r = _get(
                own,
                f"/users/{user_login}/repos",
                params={"per_page": 100, "page": page, "type": "owner", "sort": "pushed"},
            )
            if r.status_code == 404:
                _LOG.warning(
                    "skipping %s: /users/.../repos → HTTP 404 (gone or renamed?)", user_login
                )
                return []
            r.raise_for_status()
            if not _LOW_RATE_LIMIT_WARNED:
                lim = r.headers.get("X-RateLimit-Limit", "")
                if not github_token() or (lim.isdigit() and int(lim) <= 60):
                    _LOW_RATE_LIMIT_WARNED = True
                    _LOG.warning(
                        "GitHub API using unauthenticated or low cap (limit/hour=%s). "
                        "Set GITHUB_TOKEN for ~5000/hour — export GITHUB_TOKEN=$(gh auth token)",
                        lim or "?",
                    )
            data = r.json()
            if not data:
                break
            for item in data:
                if not item.get("fork"):
                    out.append(
                        {
                            "full_name": item["full_name"],
                            "default_branch": item.get("default_branch") or "main",
                            "pushed_at": item.get("pushed_at"),
                        }
                    )
            _LOG.debug("listed repos page %s (+%s rows)", page, len(data))
            if len(data) < 100:
                break
            page += 1
        _LOG.info("found %s public non-fork repos for %s", len(out), user_login)
        return out
    finally:
        if client is None:
            own.close()


def _commit_dt(item: dict[str, Any]) -> datetime | None:
    commit = item.get("commit") or {}
    a = (commit.get("author") or {}) if isinstance(commit, dict) else {}
    t = a.get("date")
    dta = _parse_gh_time(t) if t else None
    if dta is None and isinstance(commit, dict):
        c = commit.get("committer") or {}
        t2 = c.get("date") if isinstance(c, dict) else None
        dta = _parse_gh_time(t2) if t2 else None
    return dta


def _record_cache(path: Path, user_login: str, repo: str, sha: str, dta: datetime) -> None:
    _record_cache_many(path, user_login, repo, [(sha, dta)])


def _record_cache_many(
    path: Path,
    user_login: str,
    repo: str,
    rows: list[tuple[str, datetime]],
) -> None:
    if not rows:
        return
    _init_db(path)
    with sqlite3.connect(_sqlite_db_path(path), timeout=30.0) as cx:
        cx.executemany(
            "INSERT OR REPLACE INTO commit_seen VALUES(?,?,?,?)",
            [(user_login, repo, sha, dta.isoformat()) for sha, dta in rows],
        )
        cx.commit()


def _commit_list_utc_params(
    user_login: str,
    default_branch: str,
    page: int,
    since: date,
    until: date,
) -> dict[str, Any]:
    """Query params for ``GET /repos/.../commits`` scoped to the analysis window."""
    since_utc = datetime(since.year, since.month, since.day, 0, 0, 0, tzinfo=timezone.utc)
    until_utc = datetime(until.year, until.month, until.day, 23, 59, 59, tzinfo=timezone.utc)
    return {
        "author": user_login,
        "sha": default_branch,
        "per_page": 100,
        "page": page,
        "since": since_utc.isoformat().replace("+00:00", "Z"),
        "until": until_utc.isoformat().replace("+00:00", "Z"),
    }


def iter_commits(
    user_login: str,
    full_name: str,
    default_branch: str,
    *,
    since: date | None = None,
    until: date | None = None,
    client: httpx.Client | None = None,
) -> Iterator[tuple[str, datetime]]:
    """
    Walk ``/commits`` in reverse chronological order. Returns no rows if the
    API responds with HTTP 409 (empty or conflict) or 404 (repo missing,
    e.g. renamed or deleted but still listed). Commits are limited to
    ``since``/``until`` (passed to the API) so we do not page backward from
    HEAD through years of history when only a window is needed — pathological
    for large repos (e.g. the Linux kernel). Stop when a page is short or
    the oldest commit on a page is entirely before ``since`` (safety for
    pre-filtered responses).
    """
    c = client or http_client()
    path = default_sqlite_path()
    if since is None:
        since = date(1990, 1, 1)
    if until is None:
        until = date.today()
    try:
        page = 1
        n_yield = 0
        rows_for_cache: list[tuple[str, datetime]] = []
        while True:
            r = _get(
                c,
                f"/repos/{full_name}/commits",
                params=_commit_list_utc_params(user_login, default_branch, page, since, until),
            )
            if r.status_code == 409:
                _LOG.warning("skipping %s: empty or conflict (HTTP 409)", full_name)
                break
            if r.status_code == 404:
                _LOG.warning("skipping %s: not found (HTTP 404)", full_name)
                break
            r.raise_for_status()
            _throttle(r.headers.get("X-RateLimit-Remaining"))
            time.sleep(0.1)
            batch: list[dict[str, Any]] = r.json()
            if page == 1 or page % _COMMIT_PAGE_INFO_INTERVAL == 0:
                _LOG.info(
                    "commits %s: page %s, batch=%s, yielded=%s (big repos need many pages)",
                    full_name,
                    page,
                    len(batch),
                    n_yield,
                )
            if page == 1 or page % _COMMIT_PAGE_LOG_INTERVAL == 0:
                _LOG.debug(
                    "commits %s page %s batch_size=%s yielded_so_far=%s",
                    full_name,
                    page,
                    len(batch),
                    n_yield,
                )
            if not batch:
                break
            oldest: date | None = None
            for item in batch:
                sha = item.get("sha") or ""
                dta = _commit_dt(item)
                if dta is None or not sha:
                    continue
                d = dta.date()
                if oldest is None or d < oldest:
                    oldest = d
                if d < since:
                    continue
                if d > until:
                    continue
                rows_for_cache.append((sha, dta))
                n_yield += 1
                yield sha, dta
            if len(batch) < 100:
                break
            if oldest is not None and oldest < since:
                break
            page += 1
        _record_cache_many(path, user_login, full_name, rows_for_cache)
        _LOG.debug("commits %s: %s commits in window, pages=%s", full_name, n_yield, page)
    finally:
        if client is None:
            c.close()


def _collect_repo_times(
    user_login: str,
    repo: dict[str, Any],
    since: date,
    until: date,
    c: httpx.Client,
) -> list[datetime]:
    times: list[datetime] = []
    for _sha, dta in iter_commits(
        user_login,
        repo["full_name"],
        repo["default_branch"],
        since=since,
        until=until,
        client=c,
    ):
        times.append(dta)
    return times


def to_daily_commit_counts(times: list[datetime]) -> pd.Series:
    if not times:
        s = pd.Series(dtype="float64", name="commits")
        return s
    idx = pd.DatetimeIndex([pd.Timestamp(t).normalize() for t in times])
    s = pd.Series(1, index=idx, name="commits").groupby(level=0).sum().sort_index()
    s.name = "commits"
    return s


def _reindex_commits(
    s: pd.Series,
    since: date,
    until: date,
) -> pd.Series:
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    out = s.reindex(idx, fill_value=0.0)
    out.name = "commits"
    return out


def _sum_daily_by_repo(
    by_repo: dict[str, pd.Series],
    since: date,
    until: date,
) -> pd.Series:
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    acc = pd.Series(0.0, index=idx, name="commits")
    for k, s in by_repo.items():
        if not k or k == "__all__":
            continue
        s2 = s.reindex(idx, fill_value=0.0)
        acc = acc.add(s2, fill_value=0.0)
    return acc


def public_commit_time_series(
    user_login: str,
    *,
    since: date | None = None,
    until: date | None = None,
    use_commit_cache: bool = True,
) -> dict[str, pd.Series]:
    """
    One daily commit-count series per public non-fork repo, plus ``__all__`` (sum over repos).
    When ``use_commit_cache`` is True, reuses on-disk series for (user, repo, since, until)
    under ``output/github_data/commit_series/`` (or ``SUNSPOT_COMMIT_SERIES``) to avoid
    re-fetching from GitHub. Legacy path ``~/.cache/sunspot/commit_series/`` is still
    read for cache hits; new writes go to the project-local tree.
    """
    repos = list_public_repos(user_login)
    s0 = since or date(2000, 1, 1)
    u0 = until or date.today()
    nrepos = len(repos)
    _LOG.info(
        "commits: %s repos, window %s..%s (disk cache %s)",
        nrepos,
        s0,
        u0,
        "on" if use_commit_cache else "off",
    )
    c = http_client()
    out: dict[str, pd.Series] = {}
    all_times: list[datetime] = []
    n_cache = 0
    n_api = 0
    try:
        for i, r in enumerate(repos, start=1):
            fn = r["full_name"]
            daily: pd.Series | None = None
            n_in_window: int
            if use_commit_cache:
                cached = try_load_commit_series(user_login, fn, s0, u0, root=None)
                if cached is not None:
                    daily = _reindex_commits(cached, s0, u0)
                    n_in_window = int(daily.sum())
                    n_cache += 1
                    _LOG.debug(
                        "(%s/%s) %s: cache, %s commits, %s active days",
                        i,
                        nrepos,
                        fn,
                        n_in_window,
                        int((daily > 0).sum()),
                    )
                    out[fn] = daily
                    if i == 1 or i == nrepos or i % 25 == 0:
                        _LOG.info(
                            "commits progress %s: %s/%s repos processed (cache=%s api=%s)",
                            user_login, i, nrepos, n_cache, n_api,
                        )
                    continue
            tms = _collect_repo_times(user_login, r, s0, u0, c)
            all_times.extend(tms)
            daily = to_daily_commit_counts(tms)
            daily_ri = _reindex_commits(daily, s0, u0)
            n_in_window = len(tms)
            n_api += 1
            if use_commit_cache:
                try:
                    save_commit_series_cache(daily, user_login, fn, s0, u0, root=None)
                except OSError as e:
                    _LOG.debug("commit cache write failed %s: %s", fn, e)
            out[fn] = daily_ri
            _LOG.debug(
                "(%s/%s) %s: api, %s commits, %s active days",
                i,
                nrepos,
                fn,
                n_in_window,
                int((daily_ri > 0).sum()),
            )
            if i == 1 or i == nrepos or i % 25 == 0:
                _LOG.info(
                    "commits progress %s: %s/%s repos processed (cache=%s api=%s)",
                    user_login, i, nrepos, n_cache, n_api,
                )
    finally:
        c.close()
    out["__all__"] = _sum_daily_by_repo(out, s0, u0)
    total_ts = int(out["__all__"].sum()) if len(out["__all__"]) else 0
    _LOG.info(
        "commits done: %s total commits in window, __all__ max day=%s, cache hits=%s api repos=%s",
        total_ts,
        float(out["__all__"].max()) if len(out["__all__"]) else 0.0,
        n_cache,
        n_api,
    )
    return out
