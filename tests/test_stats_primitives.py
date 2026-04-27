"""Direct tests for small statistical primitives that previously had only
indirect coverage: ``acf_values`` / ``pacf_values`` / ``ar1_prewhiten``
edge cases, ``partial_correlation`` with no controls, and the two new
helpers ``durbin_watson`` and ``band_power``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sunspot.stats import (
    acf_values,
    ar1_prewhiten,
    band_power,
    durbin_watson,
    lomb_scargle_periodogram,
    pacf_values,
    partial_correlation,
)


def _ts(seed: int, n: int = 200, phi: float = 0.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    e = rng.normal(size=n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return pd.Series(x, index=idx)


def test_acf_values_lag0_is_one() -> None:
    acf, band = acf_values(_ts(0, 200), n_lags=10)
    assert acf[0] == 1.0
    assert acf.size == 11
    assert band > 0.0 and band < 1.0


def test_acf_values_recovers_strong_ar1_decay() -> None:
    acf, _ = acf_values(_ts(0, 800, phi=0.8), n_lags=10)
    # AR(1) with phi=0.8 → acf[1] ≈ 0.8, acf[2] ≈ 0.64
    assert acf[1] > 0.6
    assert acf[2] > 0.4
    # Monotone non-increasing magnitude for the first few lags
    assert abs(acf[2]) <= abs(acf[1]) + 0.05


def test_acf_values_handles_short_series() -> None:
    s = pd.Series([1.0, 2.0], index=pd.date_range("2020-01-01", periods=2, freq="D"))
    acf, band = acf_values(s, n_lags=3)
    assert acf.size == 0
    assert np.isnan(band)


def test_pacf_values_ar1_has_single_spike() -> None:
    pacf, _ = pacf_values(_ts(0, 800, phi=0.7), n_lags=10)
    assert pacf[0] == 1.0
    # PACF at lag 1 ≈ phi; all higher lags should be small for a pure AR(1)
    assert pacf[1] > 0.5
    assert all(abs(pacf[k]) < 0.25 for k in range(3, 11))


def test_ar1_prewhiten_short_series_degenerates_gracefully() -> None:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx, name="a")
    b = pd.Series([2.0, 3.0, 4.0, 5.0, 6.0], index=idx, name="b")
    ax, bx, phi_a, phi_b = ar1_prewhiten(a, b)
    # Fewer than 10 valid points → returns the input (minus first) with NaN phi.
    assert len(ax) == 4
    assert np.isnan(phi_a) and np.isnan(phi_b)


def test_ar1_prewhiten_constant_series_returns_nan_phi() -> None:
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    a = pd.Series(np.ones(50), index=idx, name="a")
    b = pd.Series(np.arange(50, dtype=float), index=idx, name="b")
    _ax, _bx, phi_a, phi_b = ar1_prewhiten(a, b)
    assert np.isnan(phi_a) and np.isnan(phi_b)


def test_partial_correlation_with_no_controls_returns_nan() -> None:
    a = _ts(0, 100)
    b = _ts(1, 100)
    r, p, n = partial_correlation(a, b, controls=[])
    assert np.isnan(r)
    assert p is None
    assert n >= 0


def test_durbin_watson_white_noise_near_two() -> None:
    rng = np.random.default_rng(0)
    dw = durbin_watson(rng.normal(size=5000))
    # Independent residuals → DW near 2.
    assert abs(dw - 2.0) < 0.1


def test_durbin_watson_positive_ar1_below_two() -> None:
    rng = np.random.default_rng(1)
    n = 5000
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = 0.8 * r[i - 1] + rng.normal()
    dw = durbin_watson(r)
    assert 0.0 <= dw < 1.0


def test_durbin_watson_negative_ar1_above_two() -> None:
    rng = np.random.default_rng(2)
    n = 5000
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = -0.8 * r[i - 1] + rng.normal()
    dw = durbin_watson(r)
    assert 3.0 < dw <= 4.0


def test_durbin_watson_constant_residuals_nan() -> None:
    assert np.isnan(durbin_watson(np.zeros(50)))
    assert np.isnan(durbin_watson(np.array([3.0])))


def test_durbin_watson_accepts_pandas_series() -> None:
    rng = np.random.default_rng(3)
    s = pd.Series(rng.normal(size=500))
    dw = durbin_watson(s)
    assert 1.6 < dw < 2.4


def test_band_power_concentrates_at_known_frequency() -> None:
    n = 800
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    t = np.arange(n)
    y = np.sin(2 * np.pi * t / 27.0) + 0.2 * rng.normal(size=n)
    p = lomb_scargle_periodogram(pd.Series(y, index=idx), min_period_days=4, n_freqs=800)
    in_band = band_power(p, min_period_days=20, max_period_days=35)
    out_band = band_power(p, min_period_days=100, max_period_days=200)
    # Overwhelming majority of power near the 27 d peak.
    assert in_band > 0.2
    assert in_band > out_band


def test_band_power_argument_order_insensitive() -> None:
    n = 300
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(1)
    y = rng.normal(size=n)
    p = lomb_scargle_periodogram(pd.Series(y, index=idx), n_freqs=300)
    assert abs(
        band_power(p, min_period_days=10, max_period_days=30)
        - band_power(p, min_period_days=30, max_period_days=10)
    ) < 1e-12


def test_band_power_empty_periodogram_is_zero() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    p = lomb_scargle_periodogram(pd.Series(np.ones(10), index=idx))
    # Constant series → empty periodogram
    assert p.power.size == 0
    assert band_power(p, min_period_days=5, max_period_days=15) == 0.0
