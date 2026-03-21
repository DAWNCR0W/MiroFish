import logging

from app.utils.logger import resolve_log_level


def test_resolve_log_level_defaults_when_value_is_missing():
    assert resolve_log_level(None, logging.WARNING) == logging.WARNING


def test_resolve_log_level_accepts_standard_level_names():
    assert resolve_log_level("debug") == logging.DEBUG
    assert resolve_log_level("INFO") == logging.INFO


def test_resolve_log_level_accepts_numeric_strings():
    assert resolve_log_level("25") == 25


def test_resolve_log_level_falls_back_on_unknown_values():
    assert resolve_log_level("not-a-level", logging.ERROR) == logging.ERROR
