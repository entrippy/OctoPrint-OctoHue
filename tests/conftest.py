"""
Pytest configuration: mock all OctoPrint/external modules before the plugin
is imported so the test suite has no dependency on a live OctoPrint install.
"""
import sys
import types
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Lightweight stand-ins for the OctoPrint plugin base classes.
# Using real (empty) classes allows Python to build a valid MRO for
# OctohuePlugin without complaining about inheriting from MagicMock instances.
# ---------------------------------------------------------------------------
class _StartupPlugin:
    pass

class _ShutdownPlugin:
    pass

class _SettingsPlugin:
    """Minimal stand-in; on_settings_save must exist so the plugin can super()-call it."""
    def on_settings_save(self, data):
        pass

class _SimpleApiPlugin:
    pass

class _AssetPlugin:
    pass

class _TemplatePlugin:
    pass

class _EventHandlerPlugin:
    pass

class _PrinterInterface:
    pass


# ---------------------------------------------------------------------------
# Build the mock module objects
# ---------------------------------------------------------------------------

# octoprint.plugin – needs the mixin class attributes set to real types
mock_op_plugin = MagicMock()
mock_op_plugin.StartupPlugin = _StartupPlugin
mock_op_plugin.ShutdownPlugin = _ShutdownPlugin
mock_op_plugin.SettingsPlugin = _SettingsPlugin
mock_op_plugin.SimpleApiPlugin = _SimpleApiPlugin
mock_op_plugin.AssetPlugin = _AssetPlugin
mock_op_plugin.TemplatePlugin = _TemplatePlugin
mock_op_plugin.EventHandlerPlugin = _EventHandlerPlugin

# octoprint.printer
mock_op_printer = MagicMock()
mock_op_printer.PrinterInterface = _PrinterInterface

# octoprint.util – use a real module so `from octoprint.util import *` only
# imports the names we explicitly place there (no MagicMock noise).
mock_util = types.ModuleType("octoprint.util")
mock_util.ResettableTimer = MagicMock(name="ResettableTimer")

# octoprint (top-level)
mock_octoprint = MagicMock()
mock_octoprint.plugin = mock_op_plugin
mock_octoprint.printer = mock_op_printer
mock_octoprint.util = mock_util
mock_octoprint.events = MagicMock()

# flask – real module so `from flask import *` is clean
mock_flask = types.ModuleType("flask")
mock_flask.jsonify = MagicMock(name="flask.jsonify")
mock_flask.request = MagicMock(name="flask.request")

# Register everything before the plugin module is imported
sys.modules["octoprint"] = mock_octoprint
sys.modules["octoprint.plugin"] = mock_op_plugin
sys.modules["octoprint.printer"] = mock_op_printer
sys.modules["octoprint.util"] = mock_util
sys.modules["octoprint.events"] = mock_octoprint.events
sys.modules["qhue"] = MagicMock(name="qhue")
sys.modules["requests"] = MagicMock(name="requests")
sys.modules["urllib3"] = MagicMock(name="urllib3")
sys.modules["urllib3.exceptions"] = MagicMock(name="urllib3.exceptions")
sys.modules["flask"] = mock_flask


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
import pytest


@pytest.fixture(autouse=True)
def _reset_shared_mocks():
    """Reset the mocks that are shared across tests before each test runs."""
    sys.modules["flask"].jsonify.reset_mock()
    sys.modules["requests"].get.reset_mock()
    sys.modules["requests"].post.reset_mock()
    sys.modules["octoprint.util"].ResettableTimer.reset_mock()
    sys.modules["qhue"].Bridge.reset_mock()
    yield


@pytest.fixture
def plugin():
    """Bare OctohuePlugin instance with mocked OctoPrint internals."""
    from octoprint_octohue import OctohuePlugin

    p = OctohuePlugin.__new__(OctohuePlugin)
    p._logger = MagicMock(name="_logger")
    p._settings = MagicMock(name="_settings")
    p._printer = MagicMock(name="_printer")
    p._plugin_version = "0.7.0"
    p.pbridge = MagicMock(name="pbridge")
    p.discoveryurl = "https://discovery.meethue.com/"
    return p


def make_settings_getter(overrides=None):
    """
    Return a callable suitable for ``plugin._settings.get.side_effect``.
    Handles the ``['key']`` list-of-one calling convention used throughout
    the plugin.
    """
    defaults = {
        "bridgeaddr": "192.168.1.100",
        "husername": "test-api-key",
        "lampid": "1",
        "plugid": "2",
        "lampisgroup": False,
        "defaultbri": 200,
        "offonshutdown": True,
        "autopoweroff": False,
        "powerofftime": 0,
        "powerofftemp": 40,
        "ononstartup": False,
        "ononstartupevent": "",
        "offonshutdown": True,
        "showhuetoggle": True,
        "showpowertoggle": False,
        "statusDict": [],
    }
    if overrides:
        defaults.update(overrides)

    def getter(key):
        if isinstance(key, list) and len(key) == 1:
            return defaults.get(key[0])
        return None

    return getter


@pytest.fixture
def plugin_with_settings(plugin):
    """Plugin fixture with a fully populated settings mock."""
    plugin._settings.get.side_effect = make_settings_getter()
    return plugin
