"""CLI default-resolution tests (no network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from sunspot import cli as cli_mod
from sunspot import correlate as cor
from sunspot.cli import app


def _fake_commits(_user, *, since, until, use_commit_cache=True, **_):
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    s = pd.Series(0.0, index=idx, name="commits")
    return {"__all__": s, "a/r": s}


def test_since_defaults_to_first_commit_date(tmp_path: Path, monkeypatch) -> None:
    """--since omitted → resolved via github.first_commit_date."""
    seen: dict[str, date] = {}

    def fake_first(login: str, *, client=None) -> date:
        seen["user"] = login
        return date(2015, 6, 1)

    monkeypatch.setattr(cli_mod, "first_commit_date", fake_first)
    monkeypatch.setattr(cor, "public_commit_time_series", _fake_commits)

    runner = CliRunner()
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "correlate", "alice",
            "--until", "2015-06-30",
            "--metrics", "f107",
            "--out", str(out),
            "--no-mosaic", "--no-spectral", "--no-acf",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen == {"user": "alice"}
    assert (out / "statistics" / "report.json").is_file()


def test_until_defaults_to_today(tmp_path: Path, monkeypatch) -> None:
    """--until omitted → today (UTC); --since stays explicit."""
    monkeypatch.setattr(cor, "public_commit_time_series", _fake_commits)
    runner = CliRunner()
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "correlate", "alice",
            "--since", (date.today().replace(day=1)).isoformat(),
            "--metrics", "f107",
            "--out", str(out),
            "--no-mosaic", "--no-spectral", "--no-acf",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "statistics" / "report.json").is_file()


def test_since_resolution_failure_is_reported(tmp_path: Path, monkeypatch) -> None:
    """If first_commit_date returns None we fail loudly with a useful hint."""
    monkeypatch.setattr(cli_mod, "first_commit_date", lambda *_a, **_kw: None)
    runner = CliRunner()
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "correlate", "ghost",
            "--until", "2020-01-01",
            "--metrics", "f107",
            "--out", str(out),
        ],
    )
    assert result.exit_code != 0
    assert "first commit date" in (result.output + str(result.exception))


def test_swapped_dates_are_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cor, "public_commit_time_series", _fake_commits)
    runner = CliRunner()
    out = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "correlate", "alice",
            "--since", "2020-01-10",
            "--until", "2020-01-01",
            "--metrics", "f107",
            "--out", str(out),
        ],
    )
    assert result.exit_code != 0
    assert "must be on or before" in (result.output + str(result.exception))


def test_cohort_accepts_logging_flags(tmp_path: Path, monkeypatch) -> None:
    """Cohort has the same logging controls as correlate."""
    seen: dict[str, object] = {}

    def fake_run(logins, **kwargs):
        seen["logins"] = list(logins)
        seen["kwargs"] = kwargs
        out_dir = Path(kwargs["out_dir"])
        (out_dir / "statistics").mkdir(parents=True, exist_ok=True)
        (out_dir / "statistics" / "report.json").write_text("{}", encoding="utf-8")
        return {}

    monkeypatch.setattr(cli_mod, "run_cohort_report", fake_run)
    runner = CliRunner()
    out = tmp_path / "cohort"
    result = runner.invoke(
        app,
        [
            "cohort", "alice,bob",
            "--since", "2020-01-01",
            "--until", "2020-01-31",
            "--out", str(out),
            "--quiet",
            "--dpi", "300",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen["logins"] == ["alice", "bob"]
    assert seen["kwargs"]["out_dir"] == out
