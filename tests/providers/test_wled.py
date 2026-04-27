"""
Unit tests for WledProvider.

Tests the provider in isolation — no OctoPrint plugin involved.
All network calls are intercepted via a mock session.
"""
from unittest.mock import MagicMock
import pytest

from octoprint_octohue.providers.wled import (
    WledProvider,
    _mirek_to_wled_cct,
    _pct_to_wled_bri,
    _hex_to_rgb,
)


# ===========================================================================
# Helper function unit tests
# ===========================================================================

class TestMirekToWledCct:

    def test_cool_white_min_mirek(self):
        assert _mirek_to_wled_cct(153) == 0

    def test_warm_white_max_mirek(self):
        assert _mirek_to_wled_cct(500) == 255

    def test_midpoint(self):
        mid = (153 + 500) // 2  # 326
        result = _mirek_to_wled_cct(mid)
        assert 120 <= result <= 135  # roughly 127

    def test_clamps_below_min(self):
        assert _mirek_to_wled_cct(100) == 0

    def test_clamps_above_max(self):
        assert _mirek_to_wled_cct(600) == 255


class TestPctToWledBri:

    def test_zero_percent(self):
        assert _pct_to_wled_bri(0) == 0

    def test_full_brightness(self):
        assert _pct_to_wled_bri(100) == 255

    def test_fifty_percent(self):
        assert _pct_to_wled_bri(50) == 128

    def test_clamps_above_100(self):
        assert _pct_to_wled_bri(110) == 255

    def test_clamps_below_0(self):
        assert _pct_to_wled_bri(-10) == 0


class TestHexToRgb:

    def test_white(self):
        assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_black(self):
        assert _hex_to_rgb("#000000") == (0, 0, 0)

    def test_red(self):
        assert _hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_green(self):
        assert _hex_to_rgb("#00FF00") == (0, 255, 0)

    def test_blue(self):
        assert _hex_to_rgb("#0000FF") == (0, 0, 255)

    def test_mixed(self):
        assert _hex_to_rgb("#1A2B3C") == (0x1A, 0x2B, 0x3C)


# ===========================================================================
# setup / is_ready
# ===========================================================================

class TestSetup:

    def test_is_ready_when_address_set(self, wled_provider):
        assert wled_provider.is_ready is True

    def test_not_ready_when_address_missing(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": ""})
        assert p.is_ready is False

    def test_not_ready_when_address_none(self):
        p = WledProvider(MagicMock())
        p.setup({})
        assert p.is_ready is False

    def test_address_whitespace_treated_as_missing(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": "   "})
        assert p.is_ready is False

    def test_address_stored(self, wled_provider):
        assert wled_provider._address == "192.168.1.200"

    def test_session_created_when_ready(self, wled_provider):
        assert wled_provider._session is not None

    def test_setup_clears_state_when_reconfigured_empty(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": "192.168.1.1"})
        assert p.is_ready is True
        p.setup({"bridgeaddr": ""})
        assert p.is_ready is False
        assert p._address is None
        assert p._session is None


# ===========================================================================
# set_light
# ===========================================================================

class TestSetLight:

    def test_sends_on_true(self, wled_provider):
        wled_provider.set_light(on=True)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["on"] is True

    def test_sends_on_false(self, wled_provider):
        wled_provider.set_light(on=False)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["on"] is False

    def test_brightness_converted_to_255_scale(self, wled_provider):
        wled_provider.set_light(on=True, brightness_pct=100)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["bri"] == 255

    def test_brightness_50pct(self, wled_provider):
        wled_provider.set_light(on=True, brightness_pct=50)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["bri"] == 128

    def test_colour_hex_sent_as_rgb(self, wled_provider):
        wled_provider.set_light(on=True, colour_hex="#FF0000")
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["seg"][0]["col"] == [[255, 0, 0]]

    def test_ct_mirek_converted_to_cct(self, wled_provider):
        wled_provider.set_light(on=True, ct_mirek=153)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["seg"][0]["cct"] == 0

    def test_ct_takes_precedence_over_colour(self, wled_provider):
        wled_provider.set_light(on=True, ct_mirek=500, colour_hex="#FF0000")
        payload = wled_provider._session.post.call_args[1]["json"]
        assert "cct" in payload["seg"][0]
        assert "col" not in payload["seg"][0]

    def test_transition_converted_to_100ms_units(self, wled_provider):
        wled_provider.set_light(on=True, transition_ms=500)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["transition"] == 5

    def test_transition_rounds(self, wled_provider):
        wled_provider.set_light(on=True, transition_ms=150)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert payload["transition"] == 2

    def test_no_seg_when_off(self, wled_provider):
        wled_provider.set_light(on=False, colour_hex="#FF0000", brightness_pct=50)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert "seg" not in payload
        assert "bri" not in payload

    def test_no_seg_when_no_colour_or_ct(self, wled_provider):
        wled_provider.set_light(on=True, brightness_pct=50)
        payload = wled_provider._session.post.call_args[1]["json"]
        assert "seg" not in payload

    def test_posts_to_json_state(self, wled_provider):
        wled_provider.set_light(on=True)
        url = wled_provider._session.post.call_args[0][0]
        assert url == "http://192.168.1.200/json/state"

    def test_does_nothing_when_not_ready(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": ""})
        p.set_light(on=True)  # should not raise

    def test_deviceid_is_ignored(self, wled_provider):
        wled_provider.set_light(on=True, deviceid="anything")
        url = wled_provider._session.post.call_args[0][0]
        assert "anything" not in url


# ===========================================================================
# get_state
# ===========================================================================

class TestGetState:

    def test_returns_true_when_on(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {"on": True}
        assert wled_provider.get_state() is True

    def test_returns_false_when_off(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {"on": False}
        assert wled_provider.get_state() is False

    def test_returns_none_on_missing_key(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {"brightness": 100}
        assert wled_provider.get_state() is None

    def test_returns_none_on_empty_response(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {}
        assert wled_provider.get_state() is None

    def test_returns_none_when_not_ready(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": ""})
        assert p.get_state() is None

    def test_returns_none_on_network_error(self, wled_provider):
        wled_provider._session.get.side_effect = Exception("timeout")
        assert wled_provider.get_state() is None


# ===========================================================================
# get_lights
# ===========================================================================

class TestGetLights:

    def test_returns_single_entry(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {"name": "My WLED"}
        lights = wled_provider.get_lights()
        assert len(lights) == 1
        assert lights[0]["id"] == "wled"
        assert lights[0]["name"] == "My WLED"

    def test_falls_back_to_address_when_name_missing(self, wled_provider):
        wled_provider._session.get.return_value.json.return_value = {}
        lights = wled_provider.get_lights()
        assert lights[0]["name"] == "192.168.1.200"

    def test_falls_back_to_wled_when_info_fails(self, wled_provider):
        wled_provider._session.get.side_effect = Exception("timeout")
        lights = wled_provider.get_lights()
        assert lights[0]["name"] in ("192.168.1.200", "WLED")


# ===========================================================================
# get_groups
# ===========================================================================

class TestGetGroups:

    def test_always_returns_empty_list(self, wled_provider):
        assert wled_provider.get_groups() == []


# ===========================================================================
# pair
# ===========================================================================

class TestPair:

    def test_returns_success_immediately(self, wled_provider):
        result = wled_provider.pair()
        assert result == {"response": "success"}

    def test_returns_success_when_not_ready(self):
        p = WledProvider(MagicMock())
        p.setup({"bridgeaddr": ""})
        assert p.pair() == {"response": "success"}
