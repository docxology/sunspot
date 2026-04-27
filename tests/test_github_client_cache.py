"""Tests for :mod:`sunspot.github.client` header / token handling and
:mod:`sunspot.github.commit_cache` round-trip behaviour. Both modules ship
without direct coverage otherwise."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from sunspot.github import client as gc
from sunspot.github import commit_cache as cc


def test_github_token_prefers_github_token_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "  abc123  ")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert gc.github_token() == "abc123"
    assert gc.has_github_token() is True


def test_github_token_falls_back_to_gh_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "xyz789")
    assert gc.github_token() == "xyz789"


def test_github_token_empty_treated_as_missing(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "   ")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert gc.github_token() is None
    assert gc.has_github_token() is False


def test_github_headers_injects_authorization_when_token_present(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    h = gc.github_headers()
    assert h["Accept"] == "application/vnd.github+json"
    assert h["User-Agent"].startswith("sunspot")
    assert h["Authorization"] == "Bearer tok"


def test_github_headers_omits_authorization_without_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    h = gc.github_headers()
    assert "Authorization" not in h


def test_default_sqlite_path_respects_sunspot_cache_env(
    monkeypatch, tmp_path: Path,
) -> None:
    base = tmp_path / "custom_cache"
    monkeypatch.setenv("SUNSPOT_CACHE", str(base))
    p = gc.default_sqlite_path()
    assert p.parent.exists()
    assert p.name == "github_cache.sqlite3"
    assert str(p).startswith(str(base.resolve()))


def test_commit_series_dir_respects_env(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "series_root"
    monkeypatch.setenv("SUNSPOT_COMMIT_SERIES", str(root))
    assert cc.commit_series_dir() == root.resolve()


def test_commit_series_roundtrip_preserves_data(tmp_path: Path) -> None:
    s0, u0 = date(2020, 1, 1), date(2020, 1, 10)
    idx = pd.date_range(pd.Timestamp(s0), pd.Timestamp(u0), freq="D")
    series = pd.Series([0, 1, 0, 3, 2, 0, 0, 5, 1, 0], index=idx, name="commits")

    p = cc.save_commit_series_cache(
        series, "alice", "alice/demo", s0, u0, root=tmp_path,
    )
    assert p.is_file()
    meta = cc.commit_series_meta_path(p)
    assert meta.is_file()

    back = cc.try_load_commit_series(
        "alice", "alice/demo", s0, u0, root=tmp_path,
    )
    assert back is not None
    assert back.index.equals(series.index)
    assert back.to_numpy().tolist() == series.to_numpy().tolist()


def test_try_load_commit_series_returns_none_on_cache_miss(tmp_path: Path) -> None:
    out = cc.try_load_commit_series(
        "bob", "bob/ghost", date(2020, 1, 1), date(2020, 1, 2), root=tmp_path,
    )
    assert out is None


def test_safe_segment_sanitizes_special_chars(tmp_path: Path) -> None:
    # Indirect: path construction must not contain raw slashes.
    p = cc.commit_series_cache_path(
        "al/ice", "al/ice/demo",
        date(2020, 1, 1), date(2020, 1, 2),
        root=tmp_path,
    )
    # User segment sanitized (the "/" in the login becomes "__")
    assert "al__ice" in p.parent.name
    # Repo segment sanitized to use "__" between owner and repo.
    assert "al__ice__demo" in p.name


def test_first_commit_date_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = date(2012, 4, 21)
    p = cc.save_first_commit_date("alice", d)
    assert p.is_file()
    assert cc.try_load_first_commit_date("alice") == d
    assert (
        cc.first_commit_date_cache_path("a/b")
        == tmp_path / "sunspot" / "first_commit_date" / "a__b.json"
    )
