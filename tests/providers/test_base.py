"""
Unit tests for the LightProvider base class defaults.
"""
from unittest.mock import MagicMock

from octoprint_octohue.providers.base import LightProvider


class _MinimalProvider(LightProvider):
    """Implements only the abstract methods, to exercise base-class defaults."""
    def setup(self, settings): pass
    @property
    def is_ready(self): return True
    def set_light(self, **kwargs): pass
    def get_state(self, deviceid=None): return None
    def get_lights(self): return []
    def get_groups(self): return []


class TestCheckConnectionDefault:

    def test_default_reports_reachable(self):
        """Providers that don't override check_connection must not be reported unreachable."""
        assert _MinimalProvider(MagicMock()).check_connection() is True

    def test_check_connection_is_not_abstract(self):
        assert "check_connection" not in LightProvider.__abstractmethods__
