"""
Spectral analysis for daily-cadence sunspot/commit series.

Lomb–Scargle is robust to gaps in the index (commits often have empty days), so
it is preferred over FFT for the per-user activity series; FFT remains useful
for evenly-sampled solar metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import signal as scipy_signal

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Periodogram:
    periods_days: np.ndarray
    power: np.ndarray
    method: str
    n: int
    dominant_period_days: float

    def top_k(self, k: int = 5) -> list[tuple[float, float]]:
        """Top-k (period_days, power) tuples sorted by power desc."""
        if self.power.size == 0:
            return []
        idx = np.argsort(self.power)[::-1][:k]
        return [(float(self.periods_days[i]), float(self.power[i])) for i in idx]


def _period_grid(
    n_samples: int,
    *,
    min_period_days: float = 4.0,
    max_period_days: float | None = None,
    n_freqs: int = 1500,
) -> np.ndarray:
    """Log-spaced periods between ``min_period_days`` and ``min(max, n/2)``."""
    cap = float(min(max_period_days or n_samples, n_samples)) / 2.0
    cap = max(cap, min_period_days * 2.0)
    return np.geomspace(min_period_days, cap, n_freqs)


def lomb_scargle_periodogram(
    x: pd.Series,
    *,
    min_period_days: float = 4.0,
    max_period_days: float | None = None,
    n_freqs: int = 1500,
    standardize: bool = True,
) -> Periodogram:
    """
    Lomb–Scargle periodogram on a daily-indexed series. Days with NaN are
    dropped (the LS algorithm tolerates uneven sampling). The series is
    mean-centred and (optionally) variance-standardised so that ``power``
    is in [0, 1] (normalised LS).
    """
    s = x.dropna().astype(float)
    n = int(s.size)
    if n < 16 or float(s.std()) == 0.0:
        return Periodogram(
            periods_days=np.array([]),
            power=np.array([]),
            method="lomb-scargle",
            n=n,
            dominant_period_days=float("nan"),
        )
    t = (s.index - s.index.min()).days.to_numpy(dtype=float)
    y = s.to_numpy(dtype=float)
    y = y - y.mean()
    if standardize and float(y.std()) > 0.0:
        y = y / y.std()
    periods = _period_grid(
        n_samples=n, min_period_days=min_period_days, max_period_days=max_period_days,
        n_freqs=n_freqs,
    )
    ang = 2.0 * np.pi / periods
    pwr = scipy_signal.lombscargle(t, y, ang, normalize=True)
    if not np.isfinite(pwr).any():
        dom = float("nan")
    else:
        dom = float(periods[int(np.nanargmax(pwr))])
    _LOG.debug("LS periodogram: n=%s, dominant=%.2fd", n, dom)
    return Periodogram(
        periods_days=periods,
        power=pwr,
        method="lomb-scargle",
        n=n,
        dominant_period_days=dom,
    )


def dominant_period(p: Periodogram) -> float:
    """Convenience: returns the period (days) with the largest power."""
    return float(p.dominant_period_days)


def band_power(
    p: Periodogram,
    *,
    min_period_days: float,
    max_period_days: float,
) -> float:
    """
    Fraction of total power concentrated in the period band
    ``[min_period_days, max_period_days]`` (inclusive) of a normalized
    Lomb–Scargle periodogram.

    Returns ``0.0`` when the periodogram is empty; ``NaN`` if the band has no
    grid points or total power is non-positive. Bounds are in *days*, matching
    ``Periodogram.periods_days``; the larger number is treated as the upper
    bound regardless of argument order.
    """
    if p.periods_days.size == 0 or p.power.size == 0:
        return 0.0
    lo = float(min(min_period_days, max_period_days))
    hi = float(max(min_period_days, max_period_days))
    mask = (p.periods_days >= lo) & (p.periods_days <= hi)
    if not np.any(mask):
        return float("nan")
    total = float(np.nansum(p.power))
    if not np.isfinite(total) or total <= 0.0:
        return float("nan")
    return float(np.nansum(p.power[mask]) / total)
