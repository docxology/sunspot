"""
Centralized matplotlib style for sunspot plots.

Plots read these defaults via :func:`get_style`. Override per-plot by passing
``style=PlotStyle(...)`` or globally via :func:`set_style` / env variables:

- ``SUNSPOT_FONT_SCALE`` (float, default 1.45)
- ``SUNSPOT_LINEWIDTH`` (float, default 1.9)
- ``SUNSPOT_DPI`` (int, default 300)
- ``SUNSPOT_THEME`` (``light`` | ``dark``, default ``light``)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Categorical palette (color-blind friendly, 8 hues + neutrals).
PALETTE_LIGHT: tuple[str, ...] = (
    "#0B5FA5",  # blue
    "#D1495B",  # red
    "#2E933C",  # green
    "#E08E45",  # orange
    "#7C5295",  # purple
    "#1FA39A",  # teal
    "#B23A48",  # crimson
    "#8C7A6B",  # taupe
)
PALETTE_DARK: tuple[str, ...] = (
    "#7AB7E5",
    "#F08FA3",
    "#7CD08A",
    "#F0B675",
    "#B89BC9",
    "#7AD7D0",
    "#E08A95",
    "#C9BAAB",
)


@dataclass(frozen=True)
class PlotStyle:
    """Configurable plotting defaults."""

    font_scale: float = 1.45
    line_width: float = 1.9
    dpi: int = 300
    theme: str = "light"  # "light" | "dark"
    palette: tuple[str, ...] = field(default_factory=lambda: PALETTE_LIGHT)
    title_size: float | None = None
    label_size: float | None = None
    tick_size: float | None = None
    legend_size: float | None = None
    grid: bool = True
    show_metadata_footer: bool = True

    @property
    def base_size(self) -> float:
        return 10.0 * self.font_scale

    @property
    def axis_fg(self) -> str:
        return "#0A0A0A" if self.theme == "light" else "#F2F2F2"

    @property
    def axis_bg(self) -> str:
        return "#FFFFFF" if self.theme == "light" else "#101418"

    @property
    def grid_color(self) -> str:
        return "#D9D9D9" if self.theme == "light" else "#2A2F36"


def _env_style() -> PlotStyle:
    fs = float(os.environ.get("SUNSPOT_FONT_SCALE", "1.45"))
    lw = float(os.environ.get("SUNSPOT_LINEWIDTH", "1.9"))
    dpi = int(os.environ.get("SUNSPOT_DPI", "300"))
    theme = os.environ.get("SUNSPOT_THEME", "light").strip().lower() or "light"
    palette = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
    return PlotStyle(font_scale=fs, line_width=lw, dpi=dpi, theme=theme, palette=palette)


_CURRENT: PlotStyle = _env_style()


def get_style() -> PlotStyle:
    """Return the active :class:`PlotStyle`."""
    return _CURRENT


def set_style(
    *,
    font_scale: float | None = None,
    line_width: float | None = None,
    dpi: int | None = None,
    theme: str | None = None,
    grid: bool | None = None,
    show_metadata_footer: bool | None = None,
) -> PlotStyle:
    """Replace the global style with overrides; returns the new style."""
    global _CURRENT
    upd: dict[str, object] = {}
    if font_scale is not None:
        upd["font_scale"] = float(font_scale)
    if line_width is not None:
        upd["line_width"] = float(line_width)
    if dpi is not None:
        upd["dpi"] = int(dpi)
    if theme is not None:
        upd["theme"] = theme
        upd["palette"] = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
    if grid is not None:
        upd["grid"] = bool(grid)
    if show_metadata_footer is not None:
        upd["show_metadata_footer"] = bool(show_metadata_footer)
    _CURRENT = replace(_CURRENT, **upd)
    apply_rcparams(_CURRENT)
    return _CURRENT


def apply_rcparams(style: PlotStyle | None = None) -> None:
    """Push ``style`` into matplotlib ``rcParams``."""
    s = style or _CURRENT
    base = s.base_size
    plt.rcParams.update({
        "figure.dpi": s.dpi,
        "savefig.dpi": s.dpi,
        "figure.facecolor": s.axis_bg,
        "axes.facecolor": s.axis_bg,
        "axes.edgecolor": s.axis_fg,
        "axes.labelcolor": s.axis_fg,
        "axes.titleweight": "semibold",
        "axes.titlesize": s.title_size or base * 1.18,
        "axes.labelsize": s.label_size or base * 1.02,
        "axes.labelweight": "regular",
        "axes.linewidth": max(0.8, s.line_width * 0.55),
        "axes.grid": s.grid,
        "axes.prop_cycle": plt.cycler(color=list(s.palette)),
        "xtick.labelsize": s.tick_size or base * 0.95,
        "ytick.labelsize": s.tick_size or base * 0.95,
        "xtick.color": s.axis_fg,
        "ytick.color": s.axis_fg,
        "grid.color": s.grid_color,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.55,
        "legend.fontsize": s.legend_size or base * 0.95,
        "legend.frameon": True,
        "legend.framealpha": 0.92,
        "legend.fancybox": False,
        "legend.edgecolor": s.grid_color,
        "lines.linewidth": s.line_width,
        "lines.markersize": 4.5 * s.font_scale,
        "font.size": base,
        "font.family": ["DejaVu Sans"],
        "text.color": s.axis_fg,
        "figure.titleweight": "semibold",
        "figure.titlesize": base * 1.25,
        "figure.constrained_layout.use": False,
    })


def period_label(since: date | None, until: date | None) -> str:
    """Return ``"YYYY-MM-DD .. YYYY-MM-DD (Nd)"`` or empty when missing."""
    if since is None or until is None:
        return ""
    days = (until - since).days + 1
    return f"{since.isoformat()} … {until.isoformat()} ({days}d)"


def metadata_footer(
    fig,  # noqa: ANN001
    *,
    parts: list[str] | None = None,
    style: PlotStyle | None = None,
) -> None:
    """Render a thin centered metadata strip at the bottom of ``fig``."""
    s = style or _CURRENT
    if not s.show_metadata_footer or not parts:
        return
    txt = "  •  ".join(p for p in parts if p)
    if not txt:
        return
    fig.text(
        0.5,
        0.005,
        txt,
        ha="center",
        va="bottom",
        fontsize=s.base_size * 0.82,
        color=s.axis_fg,
        alpha=0.78,
    )


# Apply env-driven defaults at import time.
apply_rcparams(_CURRENT)
