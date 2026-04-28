from __future__ import annotations

from pathlib import Path

import httpx

from sunspot import config


def github_token() -> str | None:
    return config.github_token_from_env()


def has_github_token() -> bool:
    return github_token() is not None


def github_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sunspot-corr/0.1",
    }
    tok = github_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def default_sqlite_path() -> Path:
    """
    Deduplication DB for (user, repo, sha) seen while walking ``/commits``.

    Default: ``output/github_data/github_cache.sqlite3`` (same tree as
    :func:`sunspot.github.commit_cache.github_data_dir`) so GitHub state is
    archivable with run outputs. Override with ``SUNSPOT_CACHE`` (directory
    containing ``github_cache.sqlite3``). The parent directory is created if
    missing; ``~`` in ``SUNSPOT_CACHE`` is expanded.
    """
    base = config.sqlite_parent_dir_from_env()
    if base is None:
        from sunspot.github.commit_cache import github_data_dir

        base = github_data_dir()
    p = (base / "github_cache.sqlite3").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def http_client() -> httpx.Client:
    return httpx.Client(
        base_url="https://api.github.com",
        # connect=20: flaky networks can exceed 10s; _get() also retries httpx.RequestError
        timeout=httpx.Timeout(60.0, connect=20.0),
        headers=github_headers(),
        follow_redirects=True,
    )
