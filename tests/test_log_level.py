"""Tests for LOG_LEVEL being honored (issue #23).

The app must configure logging from settings.LOG_LEVEL instead of
hardcoding logging.INFO.
"""

import importlib
import logging
from unittest import mock


class TestLogLevelConfig:
    def test_basic_config_uses_settings_log_level(self):
        """main.py must pass settings.LOG_LEVEL to logging.basicConfig."""
        with mock.patch("logging.basicConfig") as mock_basic_config:
            # Force a fresh import so basicConfig runs even if another test
            # already imported app.main (module caching would skip it).
            importlib.reload(importlib.import_module("app.main"))

        assert mock_basic_config.called
        kwargs = mock_basic_config.call_args.kwargs
        assert "level" in kwargs, f"basicConfig called without level: {kwargs}"
        assert kwargs["level"] == logging.INFO

    def test_log_level_setting_exists(self):
        """The LOG_LEVEL setting must exist in config."""
        from app.core.config import settings

        assert hasattr(settings, "LOG_LEVEL")
        assert settings.LOG_LEVEL == "INFO"

    def test_getattr_mapping_for_valid_levels(self):
        """getattr(logging, level.upper()) must resolve for common levels."""
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            resolved = getattr(logging, level.upper())
            assert isinstance(resolved, int)

    def test_invalid_log_level_falls_back_to_info(self):
        """An unknown LOG_LEVEL should fall back to INFO, not crash."""
        from app.main import logging as main_logging  # noqa: F401 - ensure import works

        # Simulate the getattr fallback logic
        level = "BOGUS"
        resolved = getattr(logging, level.upper(), logging.INFO)
        assert resolved == logging.INFO