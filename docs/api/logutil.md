# `sunspot.logutil`

Source: [`src/sunspot/logutil.py`](../../src/sunspot/logutil.py). Logger name: `sunspot` (hierarchy, e.g. `sunspot.github.commits`).

| name | description |
|------|-------------|
| `parse_log_level(name: str) -> int` | Maps `DEBUG`, `INFO`, `WARNING`/`WARN`, `ERROR`, `CRITICAL` to `logging` levels; unknown → `INFO`. |
| `configure_sunspot_logging(*, level=INFO, stream=None, force=True) -> None` | Attaches one `StreamHandler` on `stream` (default `sys.stderr`); with `force=True`, replaces existing handlers. Child loggers propagate to the `sunspot` logger. |

See the repository [README — Logging section](../../README.md#logging) for CLI/env precedence with `SUNSPOT_LOG_LEVEL`.
