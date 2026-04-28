"""Geophysical series loading shared with cohort."""

from __future__ import annotations

from datetime import date

import pandas as pd

from sunspot.align.join import clip_to_window
from sunspot.datasets import load_omni2_daily, load_silso_daily_tot_v2


def _years_between(s0: date, s1: date) -> list[int]:
    return list(range(s0.year, s1.year + 1))


def _series_for_metric(m: str, *, since: date, until: date) -> pd.Series:
    m = m.strip().lower()
    if m == "ssn":
        sil = load_silso_daily_tot_v2()
        s = clip_to_window(sil["ssn"], since, until)
        s.name = "ssn"
        return s
    if m in {"f107", "dst", "ap", "r_ssn"}:
        years = _years_between(since, until)
        d = load_omni2_daily(years, cache=True)
        dcol = {"f107": "f107", "dst": "dst", "ap": "ap_nT", "r_ssn": "r_ssn"}[m]
        s = clip_to_window(d[dcol], since, until)
        s.name = m
        return s
    raise ValueError(f"unknown metric: {m!r}")
