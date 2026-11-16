"""
Shared fixtures for provider tests.

Provider tests import the provider classes directly (not via the plugin), so
they need their own minimal mocking of requests and requests.adapters.
The top-level conftest.py already registers these mocks in sys.modules before
the plugin is imported; here we just expose convenient fixtures.
"""
import sys
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def wled_provider():
    """A WledProvider instance wired to a mock session, ready for use."""
    from octoprint_octohue.providers.wled import WledProvider

    provider = WledProvider(MagicMock(name="logger"))
    provider.setup({"bridgeaddr": "192.168.1.200"})
    # Replace the real session with a mock so no network calls are made
    provider._session = MagicMock(name="session")
    provider._session.get.return_value.status_code = 200
    provider._session.get.return_value.json.return_value = {}
    provider._session.post.return_value.status_code = 200
    provider._session.post.return_value.json.return_value = {}
    return provider


@pytest.fixture
def hue_provider():
    """A HueProvider instance wired to a mock session, ready for use."""
    # Import after sys.modules mocks are in place (done by top-level conftest)
    from octoprint_octohue.providers.hue import HueProvider

    provider = HueProvider(MagicMock(name="logger"))
    provider.setup({
        "bridgeaddr": "192.168.1.100",
        "husername": "test-api-key",
        "lampid": "lamp-uuid",
        "lampisgroup": False,
        "plugid": "plug-uuid",
    })
    # Replace the real session with a mock so no network calls are made
    provider._session = MagicMock(name="session")
    provider._session.request.return_value.status_code = 200
    provider._session.request.return_value.json.return_value = {}
    return provider
