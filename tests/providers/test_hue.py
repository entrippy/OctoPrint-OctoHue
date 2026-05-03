"""
Unit tests for HueProvider.

Tests the provider in isolation — no OctoPrint plugin involved.
All network calls are intercepted via a mock session.
"""
import sys
from unittest.mock import MagicMock, patch
import pytest

from octoprint_octohue.providers.hue import HueProvider


# ===========================================================================
# setup / is_ready
# ===========================================================================

class TestSetup:

    def test_is_ready_when_addr_and_key_present(self, hue_provider):
        assert hue_provider.is_ready is True

    def test_not_ready_when_addr_missing(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "", "husername": "key", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.is_ready is False

    def test_not_ready_when_key_missing(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "192.168.1.1", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.is_ready is False

    def test_not_ready_when_both_missing(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.is_ready is False

    def test_pbridge_set_correctly(self, hue_provider):
        assert hue_provider._pbridge == {"addr": "192.168.1.100", "key": "test-api-key"}

    def test_session_created_when_ready(self, hue_provider):
        assert hue_provider._session is not None

    def test_lampisgroup_stored(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "1.2.3.4", "husername": "k", "lampid": "x", "lampisgroup": True, "plugid": ""})
        assert p._lampisgroup is True

    def test_plugid_stored(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "1.2.3.4", "husername": "k", "lampid": "x", "lampisgroup": False, "plugid": "plug-1"})
        assert p._plugid == "plug-1"

    def test_setup_clears_bridge_when_reconfigured_empty(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "1.2.3.4", "husername": "k", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.is_ready is True
        p.setup({"bridgeaddr": "", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.is_ready is False


# ===========================================================================
# rgb_to_xy
# ===========================================================================

class TestRgbToXy:

    def test_pure_red_integers(self):
        xy = HueProvider.rgb_to_xy(255, 0, 0)
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_pure_green_integers(self):
        xy = HueProvider.rgb_to_xy(0, 255, 0)
        assert abs(xy[0] - 0.3000) < 0.001
        assert abs(xy[1] - 0.6000) < 0.001

    def test_pure_blue_integers(self):
        xy = HueProvider.rgb_to_xy(0, 0, 255)
        assert abs(xy[0] - 0.1500) < 0.001
        assert abs(xy[1] - 0.0601) < 0.001

    def test_white_integers(self):
        xy = HueProvider.rgb_to_xy(255, 255, 255)
        assert abs(xy[0] - 0.3127) < 0.001
        assert abs(xy[1] - 0.3290) < 0.001

    def test_red_hex_string(self):
        xy = HueProvider.rgb_to_xy("#FF0000")
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_lowercase_hex_string(self):
        xy_upper = HueProvider.rgb_to_xy("#FF0000")
        xy_lower = HueProvider.rgb_to_xy("#ff0000")
        assert abs(xy_upper[0] - xy_lower[0]) < 0.0001
        assert abs(xy_upper[1] - xy_lower[1]) < 0.0001

    def test_black_returns_none(self):
        assert HueProvider.rgb_to_xy(0, 0, 0) is None

    def test_black_hex_returns_none(self):
        assert HueProvider.rgb_to_xy("#000000") is None

    def test_invalid_hex_raises_value_error(self):
        with pytest.raises(ValueError):
            HueProvider.rgb_to_xy("invalid")

    def test_missing_green_blue_raises_value_error(self):
        with pytest.raises(ValueError):
            HueProvider.rgb_to_xy(255)

    def test_coordinates_in_unit_range(self):
        for r, g, b in [(255, 128, 0), (0, 128, 255), (128, 0, 255)]:
            xy = HueProvider.rgb_to_xy(r, g, b)
            assert 0.0 <= xy[0] <= 1.0
            assert 0.0 <= xy[1] <= 1.0


# ===========================================================================
# set_light
# ===========================================================================

class TestSetLight:

    def test_on_builds_on_payload(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid")
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["on"] == {"on": True}

    def test_off_builds_off_payload(self, hue_provider):
        hue_provider.set_light(on=False, deviceid="lamp-uuid")
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["on"] == {"on": False}

    def test_brightness_sent_as_percentage(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", brightness_pct=75)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["dimming"]["brightness"] == 75.0

    def test_brightness_clamped_to_100(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", brightness_pct=255)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["dimming"]["brightness"] == 100.0

    def test_ct_sent_as_mirek(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", ct_mirek=370)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["color_temperature"] == {"mirek": 370}

    def test_colour_hex_converted_to_xy(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", colour_hex="#FF0000")
        payload = hue_provider._session.request.call_args[1]["json"]
        assert "color" in payload
        assert "xy" in payload["color"]

    def test_ct_takes_precedence_over_colour(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", colour_hex="#FF0000", ct_mirek=370)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert "color_temperature" in payload
        assert "color" not in payload

    def test_black_colour_does_not_add_xy(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", colour_hex="#000000")
        payload = hue_provider._session.request.call_args[1]["json"]
        assert "color" not in payload

    def test_flash_adds_breathe_alert(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", flash=True)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["alert"] == {"action": "breathe"}

    def test_no_flash_no_alert(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", flash=False)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert "alert" not in payload

    def test_transition_ms_sent_as_dynamics_duration(self, hue_provider):
        hue_provider.set_light(on=True, deviceid="lamp-uuid", transition_ms=400)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert payload["dynamics"] == {"duration": 400}

    def test_on_false_omits_brightness_colour_ct(self, hue_provider):
        hue_provider.set_light(on=False, deviceid="lamp-uuid",
                               brightness_pct=80, colour_hex="#FF0000", ct_mirek=370)
        payload = hue_provider._session.request.call_args[1]["json"]
        assert "dimming" not in payload
        assert "color" not in payload
        assert "color_temperature" not in payload

    def test_light_uses_light_endpoint(self, hue_provider):
        hue_provider._lampisgroup = False
        hue_provider.set_light(on=True, deviceid="lamp-uuid")
        url = hue_provider._session.request.call_args[0][1]
        assert "light/lamp-uuid" in url
        assert "grouped_light" not in url

    def test_group_uses_grouped_light_endpoint(self, hue_provider):
        hue_provider._lampisgroup = True
        hue_provider._plugid = "other-plug"
        hue_provider.set_light(on=True, deviceid="lamp-uuid")
        url = hue_provider._session.request.call_args[0][1]
        assert "grouped_light/lamp-uuid" in url

    def test_plug_always_uses_light_endpoint(self, hue_provider):
        hue_provider._lampisgroup = True
        hue_provider._plugid = "plug-uuid"
        hue_provider.set_light(on=True, deviceid="plug-uuid")
        url = hue_provider._session.request.call_args[0][1]
        assert "light/plug-uuid" in url
        assert "grouped_light" not in url

    def test_does_nothing_when_not_ready(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        p.set_light(on=True)  # must not raise


# ===========================================================================
# get_state
# ===========================================================================

class TestGetState:

    def test_returns_true_when_light_on(self, hue_provider):
        hue_provider._session.request.return_value.json.return_value = {
            "data": [{"on": {"on": True}}]
        }
        assert hue_provider.get_state("lamp-uuid") is True

    def test_returns_false_when_light_off(self, hue_provider):
        hue_provider._session.request.return_value.json.return_value = {
            "data": [{"on": {"on": False}}]
        }
        assert hue_provider.get_state("lamp-uuid") is False

    def test_returns_none_when_data_empty(self, hue_provider):
        hue_provider._session.request.return_value.json.return_value = {"data": []}
        assert hue_provider.get_state("lamp-uuid") is None

    def test_returns_none_when_not_ready(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.get_state() is None

    def test_group_queries_grouped_light_endpoint(self, hue_provider):
        hue_provider._lampisgroup = True
        hue_provider._session.request.return_value.json.return_value = {"data": [{"on": {"on": True}}]}
        hue_provider.get_state("lamp-uuid")
        url = hue_provider._session.request.call_args[0][1]
        assert "grouped_light/lamp-uuid" in url

    def test_light_queries_light_endpoint(self, hue_provider):
        hue_provider._lampisgroup = False
        hue_provider._session.request.return_value.json.return_value = {"data": [{"on": {"on": True}}]}
        hue_provider.get_state("lamp-uuid")
        url = hue_provider._session.request.call_args[0][1]
        assert "light/lamp-uuid" in url

    def test_defaults_to_configured_lampid(self, hue_provider):
        hue_provider._lampisgroup = False
        hue_provider._lampid = "default-lamp"
        hue_provider._session.request.return_value.json.return_value = {"data": [{"on": {"on": True}}]}
        hue_provider.get_state()
        url = hue_provider._session.request.call_args[0][1]
        assert "default-lamp" in url

    def test_returns_none_on_malformed_response(self, hue_provider):
        """Non-empty data with missing 'on' key must return None, not raise KeyError."""
        hue_provider._session.request.return_value.json.return_value = {"data": [{"unexpected": "key"}]}
        assert hue_provider.get_state("lamp-uuid") is None


# ===========================================================================
# get_lights / get_groups / get_plugs
# ===========================================================================

class TestGetLights:

    _V2_LIGHTS = [
        {"id": "uuid-1", "metadata": {"name": "Desk Lamp", "archetype": "tableShade"}},
        {"id": "uuid-2", "metadata": {"name": "Smart Plug", "archetype": "plug"}},
    ]

    def test_returns_id_name_archetype(self, hue_provider):
        hue_provider._session.request.return_value.json.return_value = {"data": self._V2_LIGHTS}
        lights = hue_provider.get_lights()
        assert len(lights) == 2
        assert lights[0] == {"id": "uuid-1", "name": "Desk Lamp", "archetype": "tableShade"}

    def test_empty_when_not_ready(self):
        p = HueProvider(MagicMock())
        p.setup({"bridgeaddr": "", "husername": "", "lampid": "", "lampisgroup": False, "plugid": ""})
        assert p.get_lights() == []


class TestGetGroups:

    def test_returns_rooms_and_zones(self, hue_provider):
        room = [{"metadata": {"name": "Living Room"}, "services": [{"rid": "gl-1", "rtype": "grouped_light"}]}]
        zone = [{"metadata": {"name": "Upstairs"}, "services": [{"rid": "gl-2", "rtype": "grouped_light"}]}]

        call_count = 0
        def fake_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {"data": room if "room" in url else zone}
            return mock

        hue_provider._session.request.side_effect = fake_request
        groups = hue_provider.get_groups()
        assert len(groups) == 2
        names = [g["name"] for g in groups]
        assert "Living Room" in names
        assert "Upstairs" in names

    def test_skips_items_without_grouped_light_service(self, hue_provider):
        data = [
            {"metadata": {"name": "Room A"}, "services": [{"rid": "x", "rtype": "device"}]},
            {"metadata": {"name": "Room B"}, "services": [{"rid": "gl-2", "rtype": "grouped_light"}]},
        ]

        def fake_request(method, url, **kwargs):
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {"data": data if "room" in url else []}
            return mock

        hue_provider._session.request.side_effect = fake_request
        groups = hue_provider.get_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "Room B"


class TestGetPlugs:

    def test_returns_only_plug_archetype(self, hue_provider):
        lights = [
            {"id": "uuid-1", "metadata": {"name": "Desk Lamp", "archetype": "tableShade"}},
            {"id": "uuid-2", "metadata": {"name": "Smart Plug", "archetype": "plug"}},
        ]
        hue_provider._session.request.return_value.json.return_value = {"data": lights}
        plugs = hue_provider.get_plugs()
        assert len(plugs) == 1
        assert plugs[0]["id"] == "uuid-2"
        assert plugs[0]["name"] == "Smart Plug"


# ===========================================================================
# discover / pair
# ===========================================================================

class TestDiscover:

    def test_returns_discovered_bridges(self, hue_provider):
        bridges = [{"internalipaddress": "192.168.1.100", "id": "abc123"}]
        sys.modules["requests"].get.return_value.json.return_value = bridges
        result = hue_provider.discover()
        assert result == bridges

    def test_returns_empty_on_exception(self, hue_provider):
        sys.modules["requests"].get.side_effect = Exception("network error")
        result = hue_provider.discover()
        assert result == []
        sys.modules["requests"].get.side_effect = None


class TestPair:

    def test_success_returns_success_response(self, hue_provider):
        session_mock = sys.modules["requests"].Session.return_value
        session_mock.post.return_value.json.return_value = [
            {"success": {"username": "new-api-key"}}
        ]
        result = hue_provider.pair(bridgeaddr="192.168.1.100")
        assert result["response"] == "success"
        assert result["husername"] == "new-api-key"
        assert result["bridgeaddr"] == "192.168.1.100"

    def test_error_returns_error_response(self, hue_provider):
        session_mock = sys.modules["requests"].Session.return_value
        session_mock.post.return_value.json.return_value = [
            {"error": {"description": "link button not pressed"}}
        ]
        result = hue_provider.pair(bridgeaddr="192.168.1.100")
        assert result["response"] == "error"

    def test_network_exception_returns_error(self, hue_provider):
        session_mock = sys.modules["requests"].Session.return_value
        session_mock.post.side_effect = Exception("connection refused")
        result = hue_provider.pair(bridgeaddr="192.168.1.100")
        assert result["response"] == "error"
        session_mock.post.side_effect = None
