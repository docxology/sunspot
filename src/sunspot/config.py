"""
Authoritative environment variable names and defaults for sunspot.

Call sites should use the helpers here so behaviour and documentation stay
aligned. The Typer CLI remains the source of truth for command-line flags;
many flags mirror the ``SUNSPOT_*`` variables listed in ``docs/configuration.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Environment variable names (public for introspection and docs) ---

ENV_XDG_CACHE_HOME = "XDG_CACHE_HOME"
ENV_SUNSPOT_CACHE = "SUNSPOT_CACHE"
ENV_SUNSPOT_COMMIT_SERIES = "SUNSPOT_COMMIT_SERIES"
ENV_GITHUB_TOKEN = "GITHUB_TOKEN"
ENV_GH_TOKEN = "GH_TOKEN"
ENV_SUNSPOT_LOG_LEVEL = "SUNSPOT_LOG_LEVEL"
ENV_FONT_SCALE = "SUNSPOT_FONT_SCALE"
ENV_LINE_WIDTH = "SUNSPOT_LINEWIDTH"
ENV_DPI = "SUNSPOT_DPI"
ENV_THEME = "SUNSPOT_THEME"

# --- Defaults (match viz.style.PlotStyle and CLI) ---

DEFAULT_FONT_SCALE = 1.45
DEFAULT_LINE_WIDTH = 1.9
DEFAULT_DPI = 300
DEFAULT_THEME = "light"


def dataset_cache_dir() -> Path:
    """Root for URL-backed dataset files: ``XDG_CACHE_HOME/sunspot`` or ``~/.cache/sunspot``."""
    base = os.environ.get(ENV_XDG_CACHE_HOME)
    if base:
        return Path(base) / "sunspot"
    return Path.home() / ".cache" / "sunspot"


def github_token_from_env() -> str | None:
    t = os.environ.get(ENV_GITHUB_TOKEN) or os.environ.get(ENV_GH_TOKEN)
    if t and t.strip():
        return t.strip()
    return None


def sunspot_log_level_env_raw() -> str:
    """Raw ``SUNSPOT_LOG_LEVEL`` value (may be empty). Used with CLI default INFO."""
    return os.environ.get(ENV_SUNSPOT_LOG_LEVEL, "").strip()


def commit_series_root_from_env() -> Path | None:
    """``SUNSPOT_COMMIT_SERIES`` if set, else ``None`` (use project default under output)."""
    env = os.environ.get(ENV_SUNSPOT_COMMIT_SERIES)
    if env and str(env).strip():
        return Path(env).expanduser().resolve()
    return None


def sqlite_parent_dir_from_env() -> Path | None:
    """
    If ``SUNSPOT_CACHE`` is set, the directory that should contain
    ``github_cache.sqlite3``. If unset, callers use
    :func:`sunspot.github.commit_cache.github_data_dir`.
    """
    d = os.environ.get(ENV_SUNSPOT_CACHE)
    if d and str(d).strip():
        return Path(d).expanduser().resolve()
    return None


def read_plot_style_env() -> tuple[float, float, int, str]:
    """Env (font_scale, line_width, dpi, theme); bad floats use module defaults."""
    try:
        fs = float(os.environ.get(ENV_FONT_SCALE, str(DEFAULT_FONT_SCALE)))
    except ValueError:
        fs = DEFAULT_FONT_SCALE
    try:
        lw = float(os.environ.get(ENV_LINE_WIDTH, str(DEFAULT_LINE_WIDTH)))
    except ValueError:
        lw = DEFAULT_LINE_WIDTH
    try:
        dpi = int(os.environ.get(ENV_DPI, str(DEFAULT_DPI)))
    except ValueError:
        dpi = DEFAULT_DPI
    theme = os.environ.get(ENV_THEME, DEFAULT_THEME).strip().lower() or DEFAULT_THEME
    return (fs, lw, dpi, theme)
