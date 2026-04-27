"""Stdlib logging setup for the ``sunspot`` package (stderr, consistent format)."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


_LEVEL_ALIASES: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def parse_log_level(name: str) -> int:
    return _LEVEL_ALIASES.get(name.strip().upper(), logging.INFO)


def configure_sunspot_logging(
    *,
    level: int | str = logging.INFO,
    stream: TextIO | None = None,
    force: bool = True,
) -> None:
    """
    Attach a single :class:`StreamHandler` to the ``sunspot`` logger.

    Child loggers (e.g. ``sunspot.github.commits``) propagate to it. If a
    handler already exists and ``force`` is false, only the level is updated.
    """
    global _CONFIGURED
    root = logging.getLogger("sunspot")
    if isinstance(level, str):
        level = parse_log_level(level)
    root.setLevel(level)

    if root.handlers and not force:
        for h in root.handlers:
            h.setLevel(level)
        return

    if force:
        for h in root.handlers[:]:
            root.removeHandler(h)
        root.handlers.clear()

    ch = logging.StreamHandler(stream or sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATEFMT))
    root.addHandler(ch)
    root.propagate = False
    _CONFIGURED = True
