import logging

from sunspot.logutil import configure_sunspot_logging, parse_log_level


def test_parse_log_level() -> None:
    assert parse_log_level("debug") == logging.DEBUG
    assert parse_log_level("INFO") == logging.INFO
    assert parse_log_level("unknown") == logging.INFO


def test_configure_idempotent_level_change() -> None:
    configure_sunspot_logging(level=logging.INFO, force=True)
    log = logging.getLogger("sunspot.test_n")
    log.info("hello")
    configure_sunspot_logging(level=logging.WARNING, force=False)
    # should not raise; level updated on existing handler
    log.debug("hidden")
    log.warning("visible")
    configure_sunspot_logging(level=logging.INFO, force=True)
