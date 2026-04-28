"""Unit tests for ``sunspot.config`` (env names and defaults)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sunspot import config


def test_dataset_cache_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg")
    assert config.dataset_cache_dir() == Path("/tmp/xdg/sunspot")


def test_github_token_prefers_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert config.github_token_from_env() is None
    monkeypatch.setenv("GITHUB_TOKEN", "  tok1  ")
    assert config.github_token_from_env() == "tok1"
    monkeypatch.setenv("GH_TOKEN", "tok2")
    assert config.github_token_from_env() == "tok1"


def test_read_plot_style_env_invalid_float_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_FONT_SCALE, "not-a-float")
    monkeypatch.setenv(config.ENV_LINE_WIDTH, "not-a-float")
    monkeypatch.setenv(config.ENV_DPI, "not-int")
    fs, lw, dpi, theme = config.read_plot_style_env()
    assert fs == config.DEFAULT_FONT_SCALE
    assert lw == config.DEFAULT_LINE_WIDTH
    assert dpi == config.DEFAULT_DPI
    assert theme == config.DEFAULT_THEME
