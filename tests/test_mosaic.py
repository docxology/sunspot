import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from sunspot.viz.mosaic import (
    PER_METRIC_TILES,
    assemble_mosaic,
    save_executive_summary,
)


def _stub_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(2, 1.2))
    ax.plot([0, 1], [0, 1])
    fig.savefig(path, dpi=80)
    plt.close(fig)


def test_assemble_mosaic_packs_existing_pngs(tmp_path: Path) -> None:
    vis = tmp_path / "visualizations"
    _stub_png(vis / "dynamics" / "commits_and_solar.png")
    for nm in ("metric_correlation_matrix", "lag_grid", "metrics_zscored_overview"):
        _stub_png(vis / "overview" / f"{nm}.png")
    metrics = ["ssn", "f107"]
    for m in metrics:
        for tile in PER_METRIC_TILES:
            _stub_png(vis / m / f"{tile}.png")
    for nm in ("repo_metric_spearman_heatmap", "top_repos_30d_ma"):
        _stub_png(vis / "per_repo" / f"{nm}.png")
    out = assemble_mosaic(tmp_path, metrics=metrics)
    assert out.is_file() and out.stat().st_size > 4000
    idx = json.loads((vis / "mosaic_index.json").read_text())
    assert idx["mosaic"].endswith("mosaic.png")
    # All four sections referenced
    assert idx["header"] and idx["overview"] and idx["per_metric"] and idx["per_repo"]
    # Per-metric should have 2 metrics x 5 tiles = 10 files
    assert len(idx["per_metric"]) == len(metrics) * len(PER_METRIC_TILES)


def test_save_executive_summary_renders_card(tmp_path: Path) -> None:
    stats = tmp_path / "statistics"
    stats.mkdir(parents=True)
    report = {
        "user": "demo",
        "since": "2020-01-01",
        "until": "2024-01-01",
        "commits_total": 1234,
        "commits_summary": {
            "days_with_commits": 200,
            "total_days": 1462,
            "active_days_fraction": 0.137,
            "longest_active_streak_days": 14,
            "longest_quiet_streak_days": 60,
            "weekday_share": 0.78,
            "weekend_share": 0.22,
            "max_day": 42,
            "max_day_date": "2022-06-15",
        },
        "metrics": {
            "ssn": {
                "n_aligned": 1000,
                "pearson_ci95":   {"r":   0.10, "p": 0.001},
                "spearman_ci95":  {"rho": 0.18, "p": 1.0e-9},
                "lag":            {"best_lag": -45, "best": 0.21},
                "ccf":            {"peak_value": 0.22, "peak_lag": -45},
                "ma_correlations": [
                    {"window": 1,   "pearson_r": 0.10, "pearson_p": 0.001},
                    {"window": 30,  "pearson_r": 0.32, "pearson_p": 1e-12},
                    {"window": 180, "pearson_r": 0.41, "pearson_p": 1e-20},
                ],
                "partial_correlation_ar1": {
                    "pearson":  {"r":   0.05, "p": 0.07, "n": 999},
                    "spearman": {"rho": 0.06, "p": 0.04, "n": 999},
                },
                "dominant_period_days": 365.0,
            },
            "f107": {"error": "skipped"},
        },
    }
    (stats / "report.json").write_text(json.dumps(report), encoding="utf-8")
    out = save_executive_summary(tmp_path, out=tmp_path / "exec.png")
    assert out.is_file() and out.stat().st_size > 4000
