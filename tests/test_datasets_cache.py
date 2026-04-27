"""Unit tests for :mod:`sunspot.datasets.cache` (URL cache) and for the
``default_correlate_dir`` / ``default_cohort_dir`` path helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from sunspot.cohort import default_cohort_dir
from sunspot.correlate import default_correlate_dir
from sunspot.datasets import cache as cache_mod


def test_default_cache_dir_respects_xdg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = cache_mod.default_cache_dir()
    assert p == tmp_path / "sunspot"


def test_default_cache_dir_falls_back_to_home(monkeypatch) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    p = cache_mod.default_cache_dir()
    # Must contain the canonical suffix regardless of HOME.
    assert p.name == "sunspot"
    assert ".cache" in str(p)


def test_cache_path_for_url_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p1 = cache_mod.cache_path_for_url("https://example.com/foo", ".csv")
    p2 = cache_mod.cache_path_for_url("https://example.com/foo", ".csv")
    p3 = cache_mod.cache_path_for_url("https://example.com/bar", ".csv")
    assert p1 == p2
    assert p1 != p3
    assert p1.parent.name == "url"


def test_ensure_cached_url_writes_then_serves_from_disk(
    monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    call_count = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, content=b"CONTENT-v1", headers={"Content-Type": "text/plain"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        p1 = cache_mod.ensure_cached_url(
            "https://example.com/data.txt", suffix=".txt", client=client,
        )
        assert p1.read_bytes() == b"CONTENT-v1"
        assert call_count["n"] == 1
        # Second call must hit the on-disk cache (no extra HTTP).
        p2 = cache_mod.ensure_cached_url(
            "https://example.com/data.txt", suffix=".txt", client=client,
        )
        assert p1 == p2
        assert call_count["n"] == 1
    finally:
        client.close()


def test_read_text_cached_reads_bytes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(200, content=b"hello world"),
        ),
    )
    try:
        text = cache_mod.read_text_cached(
            "https://example.com/page", suffix=".txt", client=client,
        )
        assert text == "hello world"
    finally:
        client.close()


def test_ensure_cached_url_raises_on_http_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(404)),
    )
    try:
        with pytest.raises(httpx.HTTPStatusError):
            cache_mod.ensure_cached_url(
                "https://example.com/nope", suffix=".txt", client=client,
            )
    finally:
        client.close()


def test_default_correlate_dir_builds_expected_slug() -> None:
    d = default_correlate_dir("alice", date(2020, 1, 1), date(2024, 12, 31))
    # Path is relative to cwd; check the slug under output/correlate/.
    parts = d.parts
    assert "output" in parts
    assert "correlate" in parts
    assert parts[-1] == "alice__2020-01-01__2024-12-31"


def test_default_correlate_dir_sanitizes_slashes() -> None:
    d = default_correlate_dir("al/ice", date(2020, 1, 1), date(2020, 1, 2))
    assert "al_ice__" in d.parts[-1]
    # No raw slashes leaked into the leaf directory name.
    assert "/" not in d.parts[-1]


def test_default_cohort_dir_expected_shape() -> None:
    d = default_cohort_dir(5, date(2020, 1, 1), date(2023, 1, 1))
    assert d.parts[-1] == "cohort_n5__2020-01-01__2023-01-01"


def test_default_cohort_dir_rejects_non_date() -> None:
    with pytest.raises(TypeError):
        default_cohort_dir(3, "2020-01-01", date(2021, 1, 1))
