from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from sunspot import __version__, config
from sunspot.cohort import (
    default_cohort_dir,
    expand_preset,
    read_logins_file,
    regenerate_cohort_visualizations,
    run_cohort_report,
)
from sunspot.correlate import default_correlate_dir, run_correlation_report
from sunspot.github.client import has_github_token
from sunspot.github.commits import first_commit_date
from sunspot.logutil import configure_sunspot_logging, parse_log_level

app = typer.Typer(
    help="Correlate GitHub commits with geophysical time series.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Entry point: use the ``correlate`` subcommand."""
    return None


def _dt(s: str) -> date:
    y, m, d = s.strip().split("-", 2)
    return date(int(y), int(m), int(d))


def _discover_latest_cohort_run_for_regenerate() -> Path | None:
    """
    Newest ``output/correlate/<dir>/`` that has cohort ``report.json`` and wide commits CSV.
    """
    root = Path("output") / "correlate"
    if not root.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        rep = d / "statistics" / "report.json"
        wide = d / "data" / "commits" / "daily_users_wide.csv"
        if not rep.is_file() or not wide.is_file():
            continue
        try:
            kind = json.loads(rep.read_text(encoding="utf-8")).get("report_kind")
            if kind != "cohort":
                continue
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        try:
            mtime = rep.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _resolve_log_level(log_level: str, *, verbose: bool, quiet: bool) -> int:
    """
    Precedence: ``-v`` / ``--quiet`` override ``SUNSPOT_LOG_LEVEL`` and ``--log-level``.

    * ``-v``  → DEBUG
    * ``--quiet`` → WARNING
    * else → ``--log-level`` (default INFO), with env ``SUNSPOT_LOG_LEVEL`` used
      when the option is the default and env is set
    """
    if verbose:
        return parse_log_level("DEBUG")
    if quiet:
        return parse_log_level("WARNING")
    env = config.sunspot_log_level_env_raw()
    if env and log_level == "INFO":
        return parse_log_level(env)
    return parse_log_level(log_level)


@app.command("correlate")
def cmd_correlate(
    user: str = typer.Argument(help="GitHub user login (public data only)"),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help=(
            "Start date (UTC day) YYYY-MM-DD. "
            "Default: the user's earliest GitHub commit date "
            "(or, on lookup failure, the account creation date)."
        ),
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="End date (UTC day) YYYY-MM-DD. Default: today (UTC).",
    ),
    metrics: str = typer.Option(
        "ssn,f107,dst,ap",
        "--metrics",
        help="Comma list: ssn, f107, dst, ap, r_ssn (OMNI2)",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Run root directory (default: output/correlate/{user}__{since}__{until}/)",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="DEBUG, INFO, WARNING, ERROR (stderr). Env SUNSPOT_LOG_LEVEL if not set with -v/-q",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Log at DEBUG (overrides --log-level and env)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Log at WARNING (overrides --log-level and env)",
    ),
    no_commit_cache: bool = typer.Option(
        False,
        "--no-commit-cache",
        help="Refetch from GitHub (ignore output/github_data/commit_series cache)",
    ),
    compare_users: str = typer.Option(
        "",
        "--compare-users",
        help=("Comma-separated GitHub logins: 30d MA overlay vs SSN in visualizations/dynamics/"),
    ),
    rolling_window: int = typer.Option(
        90,
        "--rolling-window",
        help="Window (days) for rolling Pearson/Spearman in per-metric outputs",
    ),
    lag_max: int = typer.Option(
        60,
        "--lag-max",
        help="Maximum |lag| (days) for the per-metric lag search",
    ),
    no_mosaic: bool = typer.Option(
        False,
        "--no-mosaic",
        help="Skip the visualizations/mosaic.png graphical abstract",
    ),
    bootstrap: int = typer.Option(
        0,
        "--bootstrap",
        help="Percentile bootstrap CI iterations (0 disables); adds bootstrap_ci95 block",
    ),
    no_prewhiten: bool = typer.Option(
        False,
        "--no-prewhiten",
        help="Disable AR(1) prewhitening on the cross-correlation function (CCF)",
    ),
    top_repos: int = typer.Option(
        8,
        "--top-repos",
        help="Number of repos in per_repo/top_repos_30d_ma.png",
    ),
    no_acf: bool = typer.Option(
        False,
        "--no-acf",
        help="Skip ACF/PACF panels for commits and per metric",
    ),
    no_spectral: bool = typer.Option(
        False,
        "--no-spectral",
        help="Skip Lomb-Scargle periodogram panels",
    ),
    font_scale: float = typer.Option(
        1.45,
        "--font-scale",
        help="Multiplier on plot font sizes (env: SUNSPOT_FONT_SCALE)",
    ),
    line_width: float = typer.Option(
        1.9,
        "--line-width",
        help="Default line width for plots (env: SUNSPOT_LINEWIDTH)",
    ),
    dpi: int = typer.Option(
        300,
        "--dpi",
        help="Output DPI for PNGs (env: SUNSPOT_DPI)",
    ),
    theme: str = typer.Option(
        "light",
        "--theme",
        help="light or dark plot theme (env: SUNSPOT_THEME)",
    ),
) -> None:
    level = _resolve_log_level(log_level, verbose=verbose, quiet=quiet)
    configure_sunspot_logging(level=level, force=True)

    mets = [x.strip() for x in metrics.split(",") if x.strip()]
    import logging

    log = logging.getLogger("sunspot.cli")
    log.info("sunspot %s | log level %s", __version__, logging.getLevelName(level))
    if not has_github_token():
        log.warning(
            "No GITHUB_TOKEN or GH_TOKEN: REST API is limited to ~60 requests/hour. "
            "For large commit histories, set a token: export GITHUB_TOKEN=$(gh auth token) "
            "or see https://github.com/settings/tokens (read-only is enough for public data).",
        )
    else:
        log.info("GitHub API credentials present (higher rate limit than unauthenticated).")

    u0 = _dt(until) if until else date.today()
    if since:
        s0 = _dt(since)
    else:
        log.info("--since not provided: looking up first commit date for %s ...", user)
        resolved = first_commit_date(user)
        if resolved is None:
            raise typer.BadParameter(
                f"could not determine the first commit date for {user!r}; "
                "pass --since YYYY-MM-DD explicitly",
                param_hint="--since",
            )
        s0 = resolved
        log.info("--since defaulted to %s (first commit date for %s)", s0, user)
    if s0 > u0:
        raise typer.BadParameter(
            f"--since ({s0}) must be on or before --until ({u0})",
            param_hint="--since/--until",
        )

    out_dir = out if out is not None else default_correlate_dir(user, s0, u0)
    log.info("user=%s since=%s until=%s | metrics=%s", user, s0, u0, ",".join(mets))
    log.info("output directory: %s", out_dir)

    extra = [x.strip() for x in compare_users.split(",") if x.strip()]
    run_correlation_report(
        user,
        since=s0,
        until=u0,
        metrics=mets,
        out_dir=out_dir,
        use_commit_cache=not no_commit_cache,
        compare_user_logins=extra or None,
        rolling_window=rolling_window,
        lag_max=lag_max,
        make_mosaic=not no_mosaic,
        bootstrap=bootstrap,
        prewhiten=not no_prewhiten,
        top_repos=top_repos,
        enable_acf=not no_acf,
        enable_spectral=not no_spectral,
        style_overrides={
            "font_scale": font_scale,
            "line_width": line_width,
            "dpi": dpi,
            "theme": theme,
        },
    )
    typer.echo(
        f"Wrote under {out_dir} (statistics/, data/, visualizations/, analysis/)",
    )


@app.command("cohort")
def cmd_cohort(
    logins: Optional[str] = typer.Argument(
        default=None,
        help="Comma-separated logins, when not using --preset",
    ),
    preset: str = typer.Option(
        "", "--preset",
        help="Named bundle: panel, ai, famous, wide, or full (see cohort_presets).",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="UTC start (YYYY-MM-DD). If omitted, see --since-policy.",
    ),
    since_policy: str = typer.Option(
        "union",
        "--since-policy",
        help="If --since omitted: union=earliest first-commit (longest window; "
        "suits solar/geomag series), intersection=latest first-commit (shortest "
        "common span for every account).",
    ),
    until: Optional[str] = typer.Option(
        None, "--until", help="UTC end, default: today (UTC).",
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", help="Run root; default: output/correlate/cohort_n{N}__{since}__{until}/",
    ),
    metrics: str = typer.Option(
        "ssn,f107,dst,ap", "--metrics", help="Geophysical series (for user×metric table)",
    ),
    no_commit_cache: bool = typer.Option(
        False,
        "--no-commit-cache",
        help="Ignore on-disk per-repo series (refetch; see output/github_data/)",
    ),
    no_mosaic: bool = typer.Option(False, "--no-mosaic", help="Skip mosaic.png"),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="DEBUG, INFO, WARNING, ERROR (stderr). Env SUNSPOT_LOG_LEVEL if not set with -v/-q",
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Log at DEBUG"),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Log at WARNING (overrides --log-level and env)",
    ),
    font_scale: float = typer.Option(1.45, "--font-scale", help="Plot font size multiplier"),
    line_width: float = typer.Option(1.9, "--line-width", help="Line width for plot elements"),
    dpi: int = typer.Option(300, "--dpi", help="Raster DPI for PNG output"),
    theme: str = typer.Option("light", "--theme", help="light or dark"),
    logins_file: Optional[Path] = typer.Option(
        None,
        "--logins-file",
        help=(
            "File: one login per line, # comments; merged with comma logins "
            "(file first, then positional)"
        ),
    ),
    min_active_days: int = typer.Option(
        30,
        "--min-active-days",
        help="Minimum active days in-window to include a user in user×metric Spearman table",
    ),
    large_cohort: bool = typer.Option(
        False,
        "--large-cohort",
        help=(
            "Skip O(n²) pairwise stats and heavy cohort plots; "
            "keep associations + distribution histograms"
        ),
    ),
    large_cohort_threshold: int = typer.Option(
        200,
        "--large-cohort-threshold",
        help="Enable large-cohort when login count >= this (or use --large-cohort)",
    ),
    regenerate_viz: bool = typer.Option(
        False,
        "--regenerate-viz",
        help="Redraw analysis + PNGs from existing data/commits/daily_users_wide.csv and "
        "statistics/report.json (no GitHub). If --out is omitted, uses the newest cohort "
        "run under output/correlate/ that has those files.",
    ),
) -> None:
    """Cohort run only: among-user PCA, clustering, and heatmaps (no per-metric deep dive)."""
    import logging

    level = _resolve_log_level(log_level, verbose=verbose, quiet=quiet)
    configure_sunspot_logging(level=level, force=True)
    if regenerate_viz:
        if out is not None:
            p = Path(out).expanduser()
        else:
            found = _discover_latest_cohort_run_for_regenerate()
            if found is None:
                raise typer.BadParameter(
                    "no cohort run found under output/correlate/ with "
                    "statistics/report.json and data/commits/daily_users_wide.csv "
                    "(report_kind=cohort), or pass --out explicitly",
                    param_hint="--out",
                )
            p = found
        if not p.is_dir():
            raise typer.BadParameter(
                f"cohort out directory not found: {p}", param_hint="--out",
            )
        log = logging.getLogger("sunspot.cli")
        log.info("cohort: --regenerate-viz on %s", p.resolve())
        regenerate_cohort_visualizations(p, make_mosaic=not no_mosaic)
        typer.echo(
            f"Regenerated analysis + visualizations under {p} "
            "(data/commits/ and statistics/ refreshed; no GitHub fetch).",
        )
        return
    if (logins and logins.strip() or logins_file) and preset and preset.strip():
        raise typer.BadParameter(
            "use only --preset, or use --logins-file / logins, not --preset with file/arg",
        )
    if preset and preset.strip():
        try:
            ulist = list(expand_preset(preset))
        except KeyError as e:
            raise typer.BadParameter(str(e), param_hint="--preset")
    else:
        ulist = []
        if logins_file is not None:
            p = Path(logins_file).expanduser()
            if not p.is_file():
                raise typer.BadParameter(f"logins file not found: {p}", param_hint="--logins-file")
            ulist.extend(read_logins_file(p))
        if logins and logins.strip():
            ulist.extend(x.strip() for x in logins.split(",") if x.strip())
        if not ulist:
            raise typer.BadParameter(
                "pass comma logins, --logins-file, or e.g. --preset full",
            )
        ulist = list(dict.fromkeys(ulist))

    if len(ulist) < 2:
        raise typer.BadParameter("at least two logins required for cohort")

    log = logging.getLogger("sunspot.cli")
    large_effective = bool(large_cohort) or len(ulist) >= int(large_cohort_threshold)
    if large_effective:
        log.info(
            "cohort: large-cohort mode (n=%s, threshold=%s, --large-cohort=%s)",
            len(ulist), large_cohort_threshold, large_cohort,
        )
    mets = [x.strip() for x in metrics.split(",") if x.strip()]
    u0 = _dt(until) if until else date.today()
    if since:
        s0 = _dt(since)
    else:
        if large_effective and len(ulist) >= 10:
            log.warning(
                "cohort: --since omitted: resolving first commit date per login (%s users). "
                "For large runs, pass --since YYYY-MM-DD to avoid many API calls.",
                len(ulist),
            )
        dlist: list[date] = []
        for u in ulist:
            d = first_commit_date(u)
            if d is not None:
                dlist.append(d)
        if not dlist:
            raise typer.BadParameter(
                f"could not determine first commit date for any of {ulist!r}; "
                "pass --since YYYY-MM-DD",
                param_hint="--since",
            )
        if since_policy.strip().lower() in ("intersection", "i", "max", "tight"):
            s0 = max(dlist)
            log.info(
                "cohort: --since defaulted to max first-commit (intersection): %s",
                s0,
            )
        else:
            s0 = min(dlist)
            log.info("cohort: --since defaulted to min first-commit (union): %s", s0)
    if s0 > u0:
        raise typer.BadParameter(
            f"--since ({s0}) must be on or before --until ({u0})",
            param_hint="--since/--until",
        )

    out_dir = out if out is not None else default_cohort_dir(len(ulist), s0, u0)
    log.info("cohort: users=%s | since=%s until=%s", ",".join(ulist), s0, u0)
    log.info("cohort: output: %s", out_dir)
    run_cohort_report(
        ulist,
        since=s0,
        until=u0,
        metrics=mets,
        out_dir=out_dir,
        use_commit_cache=not no_commit_cache,
        make_mosaic=not no_mosaic,
        style_overrides={
            "font_scale": font_scale,
            "line_width": line_width,
            "dpi": dpi,
            "theme": theme,
        },
        since_policy="explicit" if since else since_policy,
        min_active_days=int(min_active_days),
        large_cohort=bool(large_effective),
    )
    typer.echo(f"Wrote cohort under {out_dir} (data/commits/, analysis/, visualizations/)")


def main() -> None:
    app()
