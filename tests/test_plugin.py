"""
Unit tests for OctoHue OctoPrint plugin (octoprint_octohue/__init__.py).

Tests are grouped into classes by method under test.  Each class documents any
known bugs found during analysis with a BUG comment so they are easy to find
and fix.
"""
import sys
from datetime import datetime as real_datetime, time as real_time
from unittest.mock import MagicMock, call, patch
import pytest

# conftest.py has already registered all sys.modules mocks before this import.
from octoprint_octohue import OctohuePlugin
from tests.conftest import make_settings_getter


# ===========================================================================
# rgb_to_xy
# ===========================================================================

class TestRgbToXy:
    """
    rgb_to_xy converts an 8-bit RGB triplet (or a '#RRGGBB' hex string) to
    CIE 1931 xy chromaticity coordinates used by the Hue API.
    """

    def test_pure_red_integers(self, plugin):
        xy = plugin.rgb_to_xy(255, 0, 0)
        assert len(xy) == 2
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_pure_green_integers(self, plugin):
        xy = plugin.rgb_to_xy(0, 255, 0)
        assert abs(xy[0] - 0.3000) < 0.001
        assert abs(xy[1] - 0.6000) < 0.001

    def test_pure_blue_integers(self, plugin):
        xy = plugin.rgb_to_xy(0, 0, 255)
        assert abs(xy[0] - 0.1500) < 0.001
        assert abs(xy[1] - 0.0601) < 0.001

    def test_white_integers(self, plugin):
        xy = plugin.rgb_to_xy(255, 255, 255)
        assert abs(xy[0] - 0.3127) < 0.001
        assert abs(xy[1] - 0.3290) < 0.001

    def test_red_hex_string(self, plugin):
        xy = plugin.rgb_to_xy("#FF0000")
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_green_hex_string(self, plugin):
        xy = plugin.rgb_to_xy("#00FF00")
        assert abs(xy[0] - 0.3000) < 0.001
        assert abs(xy[1] - 0.6000) < 0.001

    def test_blue_hex_string(self, plugin):
        xy = plugin.rgb_to_xy("#0000FF")
        assert abs(xy[0] - 0.1500) < 0.001
        assert abs(xy[1] - 0.0601) < 0.001

    def test_lowercase_hex_string(self, plugin):
        """int(..., 16) accepts lowercase hex digits."""
        xy_upper = plugin.rgb_to_xy("#FF0000")
        xy_lower = plugin.rgb_to_xy("#ff0000")
        assert abs(xy_upper[0] - xy_lower[0]) < 0.0001
        assert abs(xy_upper[1] - xy_lower[1]) < 0.0001

    def test_invalid_hex_string_raises_value_error(self, plugin):
        with pytest.raises(ValueError):
            plugin.rgb_to_xy("invalid")

    def test_returns_list_of_two_floats(self, plugin):
        xy = plugin.rgb_to_xy(100, 150, 200)
        assert isinstance(xy, list)
        assert len(xy) == 2
        assert all(isinstance(v, float) for v in xy)

    def test_coordinates_in_unit_range(self, plugin):
        """All valid colours must produce xy values in [0, 1]."""
        for r, g, b in [(255, 128, 0), (0, 128, 255), (128, 0, 255)]:
            xy = plugin.rgb_to_xy(r, g, b)
            assert 0.0 <= xy[0] <= 1.0
            assert 0.0 <= xy[1] <= 1.0

    def test_low_gamma_linear_range(self, plugin):
        """Values ≤10 (ratio ≤0.04045) use the linear branch of gamma correction."""
        # All channels in the linear branch; result should still be valid coords.
        xy = plugin.rgb_to_xy(9, 9, 9)
        # A neutral grey must map to the same xy as white (D65 white point).
        xy_white = plugin.rgb_to_xy(255, 255, 255)
        assert abs(xy[0] - xy_white[0]) < 0.001
        assert abs(xy[1] - xy_white[1]) < 0.001

    def test_neutral_grey_same_xy_as_white(self, plugin):
        """Any neutral grey should share the white-point chromaticity."""
        xy_white = plugin.rgb_to_xy(255, 255, 255)
        xy_grey = plugin.rgb_to_xy(128, 128, 128)
        assert abs(xy_white[0] - xy_grey[0]) < 0.001
        assert abs(xy_white[1] - xy_grey[1]) < 0.001

    def test_black_returns_none(self, plugin):
        """Black (0,0,0) has no chromaticity — rgb_to_xy signals this with None."""
        assert plugin.rgb_to_xy(0, 0, 0) is None

    def test_black_hex_string_returns_none(self, plugin):
        assert plugin.rgb_to_xy("#000000") is None


# ===========================================================================
# build_state
# ===========================================================================

class TestBuildState:
    """
    build_state assembles the Hue API state dict and forwards it to set_state.
    """

    def _setup(self, plugin):
        plugin.set_state = MagicMock()
        plugin.rgb_to_xy = MagicMock(return_value=[0.64, 0.33])
        return plugin

    def test_on_true_with_colour_adds_xy(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, colour="#FF0000", bri=200, deviceid="1")
        state, deviceid = plugin.set_state.call_args[0]
        assert state["on"] is True
        assert state["bri"] == 200
        assert state["xy"] == [0.64, 0.33]
        plugin.rgb_to_xy.assert_called_once_with("#FF0000")

    def test_colour_key_excluded_from_state(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, colour="#FF0000", bri=100, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert "colour" not in state

    def test_deviceid_excluded_from_state(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, colour="#FF0000", bri=100, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert "deviceid" not in state

    def test_deviceid_forwarded_to_set_state(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=False, deviceid="42")
        _, deviceid = plugin.set_state.call_args[0]
        assert deviceid == "42"

    def test_on_false_does_not_add_xy(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=False, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert state["on"] is False
        assert "xy" not in state
        plugin.rgb_to_xy.assert_not_called()

    def test_on_true_without_colour_no_xy(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, bri=200, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert "xy" not in state
        plugin.rgb_to_xy.assert_not_called()

    def test_on_true_with_none_colour_no_xy(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, colour=None, bri=200, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert "xy" not in state
        plugin.rgb_to_xy.assert_not_called()

    def test_extra_kwargs_passed_through_to_state(self, plugin):
        self._setup(plugin)
        plugin.build_state(on=True, bri=150, transitiontime=4, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert state["transitiontime"] == 4

    def test_black_colour_does_not_add_xy(self, plugin):
        """#000000 → rgb_to_xy returns None → xy must not appear in state."""
        plugin.set_state = MagicMock()
        plugin.build_state(on=True, colour="#000000", bri=200, deviceid="1")
        state, _ = plugin.set_state.call_args[0]
        assert "xy" not in state


# ===========================================================================
# get_state
# ===========================================================================

class TestGetState:
    """get_state queries the bridge and returns a bool."""

    def test_returns_none_when_bridge_not_ready(self, plugin):
        plugin.pbridge = None
        assert plugin.get_state("1") is None

    def test_group_reads_action_key(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampisgroup": True})
        plugin.pbridge.groups.__getitem__.return_value.return_value = {
            "action": {"on": True}
        }
        assert plugin.get_state("1") is True

    def test_light_reads_state_key(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampisgroup": False})
        plugin.pbridge.lights.__getitem__.return_value.return_value = {
            "state": {"on": False}
        }
        assert plugin.get_state("1") is False

    def test_defaults_to_settings_lampid_when_none(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampisgroup": False, "lampid": "5"}
        )
        plugin.pbridge.lights.__getitem__.return_value.return_value = {
            "state": {"on": True}
        }
        plugin.get_state()
        plugin._settings.get.assert_any_call(["lampid"])


# ===========================================================================
# set_state
# ===========================================================================

class TestSetState:
    """set_state dispatches to pbridge groups or lights depending on config."""

    def test_does_nothing_when_bridge_not_ready(self, plugin):
        plugin.pbridge = None
        plugin.set_state({"on": False}, "1")  # must not raise
        plugin._logger.warning.assert_called()

    def test_group_calls_action(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampisgroup": True})
        state = {"on": True, "bri": 200}
        plugin.set_state(state, "1")
        plugin.pbridge.groups.__getitem__.return_value.action.assert_called_once_with(
            **state
        )

    def test_light_calls_state(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampisgroup": False})
        state = {"on": False}
        plugin.set_state(state, "1")
        plugin.pbridge.lights.__getitem__.return_value.state.assert_called_once_with(
            **state
        )

    def test_plug_always_uses_lights_not_groups(self, plugin):
        """Even when lampisgroup=True, the plug device must use lights not groups."""
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampisgroup": True, "plugid": "2"}
        )
        plugin.set_state({"on": True}, "2")  # deviceid == plugid
        plugin.pbridge.lights.__getitem__.return_value.state.assert_called_once_with(
            on=True
        )
        plugin.pbridge.groups.__getitem__.return_value.action.assert_not_called()

    def test_defaults_to_settings_lampid_when_none(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampisgroup": False, "lampid": "3"}
        )
        plugin.set_state({"on": False})
        plugin._settings.get.assert_any_call(["lampid"])


# ===========================================================================
# toggle_state
# ===========================================================================

class TestToggleState:
    """toggle_state reads current state then flips it."""

    def test_when_on_turns_off(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampid": "1"})
        plugin.get_state = MagicMock(return_value=True)
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")
        plugin.build_state.assert_called_once_with(on=False, deviceid="1")

    def test_when_off_lamp_turns_on_with_brightness(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": "2", "defaultbri": 200}
        )
        plugin.get_state = MagicMock(return_value=False)
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")  # deviceid "1" != plugid "2"
        plugin.build_state.assert_called_once_with(on=True, bri=200, deviceid="1")

    def test_when_off_plug_turns_on_without_brightness(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"plugid": "2"})
        plugin.get_state = MagicMock(return_value=False)
        plugin.build_state = MagicMock()
        plugin.toggle_state("2")  # deviceid "2" == plugid "2"
        plugin.build_state.assert_called_once_with(on=True, deviceid="2")

    def test_defaults_to_settings_lampid_when_none(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampid": "3", "plugid": "99"}
        )
        plugin.get_state = MagicMock(return_value=True)
        plugin.build_state = MagicMock()
        plugin.toggle_state()
        plugin._settings.get.assert_any_call(["lampid"])


# ===========================================================================
# get_configured_events
# ===========================================================================

class TestGetConfiguredEvents:

    def test_returns_event_names(self, plugin):
        plugin._settings.get.return_value = [
            {"event": "PrintStarted", "colour": "#FFF"},
            {"event": "PrintDone", "colour": "#0F0"},
        ]
        assert plugin.get_configured_events() == ["PrintStarted", "PrintDone"]

    def test_empty_status_dict_returns_empty_list(self, plugin):
        plugin._settings.get.return_value = []
        assert plugin.get_configured_events() == []


# ===========================================================================
# on_after_startup
# ===========================================================================

class TestOnAfterStartup:

    def test_calls_establish_bridge_with_settings(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.establishBridge = MagicMock()
        plugin.on_after_startup()
        plugin.establishBridge.assert_called_once_with(
            "192.168.1.100", "test-api-key"
        )


# ===========================================================================
# on_shutdown
# ===========================================================================

# ===========================================================================
# printer_start_power_down
# ===========================================================================

class TestPrinterStartPowerDown:

    @property
    def _timer(self):
        return sys.modules["octoprint.util"].ResettableTimer

    def test_passes_callback_not_return_value(self, plugin):
        """ResettableTimer must receive the function object, not the result of calling it."""
        plugin._settings.get.side_effect = make_settings_getter({"powerofftime": 0})
        plugin.printer_check_temp_power_down = MagicMock()
        plugin.printer_start_power_down()
        _, callback = self._timer.call_args[0]
        assert callback is plugin.printer_check_temp_power_down

    def test_timer_uses_configured_delay(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"powerofftime": 120})
        plugin.printer_check_temp_power_down = MagicMock()
        plugin.printer_start_power_down()
        delay, _ = self._timer.call_args[0]
        assert delay == 120

    def test_timer_is_started(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"powerofftime": 0})
        plugin.printer_check_temp_power_down = MagicMock()
        plugin.printer_start_power_down()
        self._timer.return_value.start.assert_called_once()

    def test_zero_delay_when_powerofftime_not_set(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"powerofftime": None})
        plugin.printer_check_temp_power_down = MagicMock()
        plugin.printer_start_power_down()
        delay, _ = self._timer.call_args[0]
        assert delay == 0


# ===========================================================================
# printer_check_temp_power_down
# ===========================================================================

class TestPrinterCheckTempPowerDown:
    """
    The method must check temperature once and either shut down or schedule
    a single retry — it must NOT block in a loop.
    """

    @property
    def _timer(self):
        return sys.modules["octoprint.util"].ResettableTimer

    def _setup(self, plugin, current_temp, target_temp=50, plugid="2"):
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": plugid, "powerofftemp": target_temp}
        )
        plugin._printer.get_current_temperatures.return_value = {
            "tool0": {"actual": current_temp}
        }
        plugin.build_state = MagicMock()

    def test_shuts_down_when_at_target_temp(self, plugin):
        self._setup(plugin, current_temp=50, target_temp=50)
        plugin.printer_check_temp_power_down()
        plugin.build_state.assert_called_once_with(on=False, deviceid="2")

    def test_shuts_down_when_below_target_temp(self, plugin):
        self._setup(plugin, current_temp=30, target_temp=50)
        plugin.printer_check_temp_power_down()
        plugin.build_state.assert_called_once_with(on=False, deviceid="2")

    def test_shuts_down_when_below_safety_floor_of_40(self, plugin):
        """Falls back to 40°C hard floor even if target_temp is 0."""
        self._setup(plugin, current_temp=39, target_temp=0)
        plugin.printer_check_temp_power_down()
        plugin.build_state.assert_called_once_with(on=False, deviceid="2")

    def test_reschedules_when_still_hot(self, plugin):
        self._setup(plugin, current_temp=150, target_temp=50)
        plugin.printer_check_temp_power_down()
        plugin.build_state.assert_not_called()
        self._timer.assert_called_once_with(30.0, plugin.printer_check_temp_power_down)
        self._timer.return_value.start.assert_called_once()

    def test_does_not_block_when_still_hot(self, plugin):
        """Function must return promptly — no loop, just one timer scheduled."""
        self._setup(plugin, current_temp=150, target_temp=50)
        # If the implementation loops, the mock timer's start() would be called
        # multiple times within a single call to the method.
        plugin.printer_check_temp_power_down()
        assert self._timer.call_count == 1

    def test_empty_string_powerofftemp_does_not_raise(self, plugin):
        """Legacy installs may have powerofftemp="" stored; int('' or 0) must not crash."""
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": "2", "powerofftemp": ""}
        )
        plugin._printer.get_current_temperatures.return_value = {
            "tool0": {"actual": 30}
        }
        plugin.build_state = MagicMock()
        plugin.printer_check_temp_power_down()  # must not raise ValueError
        plugin.build_state.assert_called_once_with(on=False, deviceid="2")


class TestOnShutdown:

    def test_turns_off_when_offonshutdown_true(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"offonshutdown": True}
        )
        plugin.set_state = MagicMock()
        plugin.on_shutdown()
        plugin.set_state.assert_called_once_with({"on": False})

    def test_no_action_when_offonshutdown_false(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"offonshutdown": False}
        )
        plugin.set_state = MagicMock()
        plugin.on_shutdown()
        plugin.set_state.assert_not_called()


# ===========================================================================
# on_event
# ===========================================================================

class TestOnEvent:
    """
    on_event looks up the incoming event in statusDict and schedules a delayed
    light-state change via ResettableTimer.
    """

    @property
    def _timer(self):
        return sys.modules["octoprint.util"].ResettableTimer

    def _status_dict_entry(self, event, turnoff=False, flash=False,
                           colour="#FFFFFF", brightness=200, delay=0):
        return {
            "event": event,
            "colour": colour,
            "brightness": brightness,
            "delay": delay,
            "turnoff": turnoff,
            "flash": flash,
        }

    def test_known_event_turnoff_false_schedules_on(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintStarted")],
                "autopoweroff": False,
            }
        )
        plugin.on_event("PrintStarted", {})
        self._timer.assert_called_once()
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["on"] is True
        assert kwargs["kwargs"]["colour"] == "#FFFFFF"
        assert kwargs["kwargs"]["bri"] == 200
        assert kwargs["kwargs"]["deviceid"] == "1"

    def test_known_event_turnoff_true_schedules_off(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [
                    self._status_dict_entry("Disconnected", turnoff=True)
                ],
                "autopoweroff": False,
            }
        )
        plugin.on_event("Disconnected", {})
        self._timer.assert_called_once()
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["on"] is False

    def test_unknown_event_no_timer_scheduled(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"statusDict": [], "autopoweroff": False}
        )
        plugin.on_event("UnknownEvent", {})
        self._timer.assert_not_called()

    def test_delayed_task_is_started(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintDone", delay=5)],
                "autopoweroff": False,
            }
        )
        plugin.on_event("PrintDone", {})
        timer_instance = self._timer.return_value
        timer_instance.start.assert_called_once()

    def test_print_done_with_autopoweroff_triggers_powerdown(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"statusDict": [], "autopoweroff": True}
        )
        plugin.printer_start_power_down = MagicMock()
        plugin.on_event("PrintDone", {})
        plugin.printer_start_power_down.assert_called_once()

    def test_print_done_without_autopoweroff_no_powerdown(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"statusDict": [], "autopoweroff": False}
        )
        plugin.printer_start_power_down = MagicMock()
        plugin.on_event("PrintDone", {})
        plugin.printer_start_power_down.assert_not_called()

    def test_non_print_done_event_does_not_trigger_powerdown(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintStarted")],
                "autopoweroff": True,  # enabled, but event is not PrintDone
            }
        )
        plugin.printer_start_power_down = MagicMock()
        plugin.on_event("PrintStarted", {})
        plugin.printer_start_power_down.assert_not_called()


# ===========================================================================
# on_api_command  –  bridge sub-commands
# ===========================================================================

class TestOnApiCommandBridge:

    def test_getstatus_unconfigured(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unconfigured")

    def test_getstatus_unauthed(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.100", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unauthed")

    def test_getstatus_configured(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.100", "husername": "key"}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="configured")

    def test_discover_calls_discovery_url(self, plugin):
        requests = sys.modules["requests"]
        requests.get.return_value.json.return_value = [
            {"internalipaddress": "192.168.1.100", "id": "abc"}
        ]
        plugin.on_api_command("bridge", {"discover": "true"})
        requests.get.assert_called_once_with(plugin.discoveryurl)

    def test_discover_passes_parsed_list_to_jsonify(self, plugin):
        flask = sys.modules["flask"]
        requests = sys.modules["requests"]
        bridges = [{"internalipaddress": "192.168.1.100", "id": "abc"}]
        requests.get.return_value.json.return_value = bridges
        plugin.on_api_command("bridge", {"discover": "true"})
        flask.jsonify.assert_called_once_with(bridges)

    def test_discover_parses_response_once(self, plugin):
        requests = sys.modules["requests"]
        requests.get.return_value.json.return_value = []
        plugin.on_api_command("bridge", {"discover": "true"})
        requests.get.return_value.json.assert_called_once()

    def test_pair_success_saves_credentials(self, plugin):
        requests = sys.modules["requests"]
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.establishBridge = MagicMock()
        requests.post.return_value.json.return_value = [
            {"success": {"username": "new-api-key"}}
        ]
        plugin.on_api_command(
            "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
        )
        plugin._settings.set.assert_any_call(["husername"], "new-api-key")
        plugin._settings.set.assert_any_call(["bridgeaddr"], "192.168.1.100")
        plugin._settings.save.assert_called()

    def test_pair_success_re_establishes_bridge(self, plugin):
        requests = sys.modules["requests"]
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.establishBridge = MagicMock()
        requests.post.return_value.json.return_value = [
            {"success": {"username": "new-api-key"}}
        ]
        plugin.on_api_command(
            "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
        )
        plugin.establishBridge.assert_called_once()

    def test_pair_error_returns_error_response(self, plugin):
        flask = sys.modules["flask"]
        requests = sys.modules["requests"]
        requests.post.return_value.json.return_value = [
            {"error": {"description": "link button not pressed"}}
        ]
        plugin.on_api_command(
            "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
        )
        flask.jsonify.assert_called()
        args = flask.jsonify.call_args[0][0]
        assert args[0]["response"] == "error"

    def test_pair_parses_response_once(self, plugin):
        requests = sys.modules["requests"]
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.establishBridge = MagicMock()
        requests.post.return_value.json.return_value = [
            {"success": {"username": "key"}}
        ]
        plugin.on_api_command(
            "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
        )
        requests.post.return_value.json.assert_called_once()


# ===========================================================================
# on_api_command  –  getdevices
# ===========================================================================

class TestOnApiCommandGetDevices:

    def test_returns_empty_devices_when_bridge_not_ready(self, plugin):
        flask = sys.modules["flask"]
        plugin.pbridge = None
        plugin.on_api_command("getdevices", {})
        flask.jsonify.assert_called_once_with(devices=[])

    _DEVICES = {
        "1": {"name": "Desk Lamp", "config": {"archetype": "tableShade"}},
        "2": {"name": "Smart Plug", "config": {"archetype": "plug"}},
        "3": {"name": "Floor Lamp", "config": {"archetype": "floorShade"}},
    }

    def test_returns_all_devices_when_no_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin.pbridge.lights.return_value = self._DEVICES
        plugin.on_api_command("getdevices", {})
        devices = flask.jsonify.call_args[1]["devices"]
        assert len(devices) == 3

    def test_filters_by_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin.pbridge.lights.return_value = self._DEVICES
        plugin.on_api_command("getdevices", {"archetype": "plug"})
        devices = flask.jsonify.call_args[1]["devices"]
        assert len(devices) == 1
        assert devices[0]["name"] == "Smart Plug"

    def test_device_dict_contains_id_name_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin.pbridge.lights.return_value = self._DEVICES
        plugin.on_api_command("getdevices", {})
        devices = flask.jsonify.call_args[1]["devices"]
        for d in devices:
            assert "id" in d
            assert "name" in d
            assert "archetype" in d

    def test_empty_archetype_filter_returns_nothing(self, plugin):
        flask = sys.modules["flask"]
        plugin.pbridge.lights.return_value = self._DEVICES
        plugin.on_api_command("getdevices", {"archetype": "nonexistent"})
        devices = flask.jsonify.call_args[1]["devices"]
        assert devices == []


# ===========================================================================
# on_api_command  –  togglehue / getstate / turnoff / cooldown
# ===========================================================================

class TestOnApiCommandMisc:

    def test_togglehue_with_explicit_deviceid(self, plugin):
        plugin.toggle_state = MagicMock()
        plugin.on_api_command("togglehue", {"deviceid": "3"})
        plugin.toggle_state.assert_called_once_with("3")

    def test_togglehue_without_deviceid_uses_lampid(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampid": "1"})
        plugin.toggle_state = MagicMock()
        plugin.on_api_command("togglehue", {})
        plugin.toggle_state.assert_called_once_with("1")

    def test_getstate_when_on_returns_true_string(self, plugin):
        flask = sys.modules["flask"]
        plugin.get_state = MagicMock(return_value=True)
        plugin.on_api_command("getstate", {})
        flask.jsonify.assert_called_once_with(on="true")

    def test_getstate_when_off_returns_false_string(self, plugin):
        flask = sys.modules["flask"]
        plugin.get_state = MagicMock(return_value=False)
        plugin.on_api_command("getstate", {})
        flask.jsonify.assert_called_once_with(on="false")

    def test_turnoff_uses_settings_lampid_by_default(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampid": "1"})
        plugin.build_state = MagicMock()
        plugin.on_api_command("turnoff", {})
        plugin.build_state.assert_called_once_with(on=False, deviceid="1")

    def test_turnoff_uses_deviceid_from_data(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.build_state = MagicMock()
        plugin.on_api_command("turnoff", {"deviceid": "5"})
        plugin.build_state.assert_called_once_with(on=False, deviceid="5")

    def test_cooldown_delegates_to_printer_check(self, plugin):
        plugin.printer_check_temp_power_down = MagicMock()
        plugin.on_api_command("cooldown", {})
        plugin.printer_check_temp_power_down.assert_called_once()

    def test_turnon_uses_settings_lampid_by_default(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampid": "1", "defaultbri": 200}
        )
        plugin.build_state = MagicMock()
        plugin.on_api_command("turnon", {})
        plugin.build_state.assert_called_once_with(on=True, bri=200, deviceid="1")

    def test_turnon_uses_deviceid_from_data(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"defaultbri": 200})
        plugin.build_state = MagicMock()
        plugin.on_api_command("turnon", {"deviceid": "7"})
        plugin.build_state.assert_called_once_with(on=True, bri=200, deviceid="7")

    def test_turnon_with_colour_passes_colour_and_deviceid(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampid": "1", "defaultbri": 200}
        )
        plugin.build_state = MagicMock()
        plugin.on_api_command("turnon", {"colour": "#FF0000"})
        plugin.build_state.assert_called_once_with(
            on=True, colour="#FF0000", bri=200, deviceid="1"
        )


# ===========================================================================
# get_settings_defaults
# ===========================================================================

class TestGetSettingsDefaults:

    def test_all_expected_keys_present(self, plugin):
        defaults = plugin.get_settings_defaults()
        required = [
            "enabled", "installed_version", "bridgeaddr", "husername",
            "lampid", "plugid", "lampisgroup", "defaultbri",
            "ononstartup", "ononstartupevent", "offonshutdown",
            "showhuetoggle", "showpowertoggle", "autopoweroff",
            "powerofftime", "powerofftemp", "statusDict",
        ]
        for key in required:
            assert key in defaults, f"Missing key in defaults: {key!r}"

    def test_default_values(self, plugin):
        d = plugin.get_settings_defaults()
        assert d["enabled"] is True
        assert d["bridgeaddr"] == ""
        assert d["husername"] == ""
        assert d["lampid"] == ""
        assert d["defaultbri"] == 255
        assert d["offonshutdown"] is True
        assert d["showhuetoggle"] is True
        assert d["autopoweroff"] is False
        assert d["statusDict"] == []
        assert d["lampisgroup"] is False
        assert d["powerofftime"] == 0
        assert d["powerofftemp"] == 0


# ===========================================================================
# on_settings_migrate
# ===========================================================================

class TestOnSettingsMigrate:

    def test_first_install_sets_example_status_dict(self, plugin):
        plugin.on_settings_migrate(target=1, current=None)
        set_calls = [
            c for c in plugin._settings.set.call_args_list
            if c[0][0] == ["statusDict"]
        ]
        assert len(set_calls) == 1
        events = [entry["event"] for entry in set_calls[0][0][1]]
        assert "Connected" in events
        assert "PrintStarted" in events
        assert "PrintDone" in events
        assert "PrintFailed" in events

    def test_first_install_saves_settings(self, plugin):
        plugin.on_settings_migrate(target=1, current=None)
        plugin._settings.save.assert_called()

    def test_up_to_date_does_not_modify_settings(self, plugin):
        """current == target → nothing should change."""
        plugin.on_settings_migrate(target=1, current=1)
        plugin._settings.set.assert_not_called()


# ===========================================================================
# on_settings_load
# ===========================================================================

class TestOnSettingsLoad:

    def test_all_expected_keys_in_returned_dict(self, plugin):
        sys.modules["octoprint.events"].all_events.return_value = []
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.get_configured_events = MagicMock(return_value=[])
        result = plugin.on_settings_load()
        for key in [
            "availableEvents", "statusDict", "bridgeaddr", "husername",
            "lampid", "plugid", "lampisgroup", "defaultbri", "ononstartup",
            "configuredEvents", "ononstartupevent", "offonshutdown",
            "showhuetoggle", "showpowertoggle", "autopoweroff",
            "powerofftime", "powerofftemp",
        ]:
            assert key in result, f"Missing key: {key!r}"

    def test_configured_events_populated(self, plugin):
        sys.modules["octoprint.events"].all_events.return_value = []
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.get_configured_events = MagicMock(
            return_value=["PrintStarted", "PrintDone"]
        )
        result = plugin.on_settings_load()
        assert result["configuredEvents"] == ["PrintStarted", "PrintDone"]

    def test_available_events_from_octoprint(self, plugin):
        all_events = ["PrintStarted", "PrintDone", "PrintFailed"]
        sys.modules["octoprint.events"].all_events.return_value = all_events
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.get_configured_events = MagicMock(return_value=[])
        result = plugin.on_settings_load()
        assert result["availableEvents"] == all_events


# ===========================================================================
# on_settings_save
# ===========================================================================

class TestOnSettingsSave:

    def test_removes_available_events_before_save(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        data = {"availableEvents": ["PrintStarted"], "lampid": "1"}
        plugin.on_settings_save(data)
        assert "availableEvents" not in data

    def test_re_establishes_bridge_after_save(self, plugin):
        Bridge = sys.modules["qhue"].Bridge
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.on_settings_save({"lampid": "1"})
        Bridge.assert_called_once()

    def test_bridge_created_with_saved_addr_and_key(self, plugin):
        Bridge = sys.modules["qhue"].Bridge
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "10.0.0.1", "husername": "saved-key"}
        )
        plugin.on_settings_save({"lampid": "1"})
        Bridge.assert_called_once_with("10.0.0.1", "saved-key")


# ===========================================================================
# on_event  –  flash behaviour
# ===========================================================================

class TestOnEventFlash:
    """
    on_event flash flag adds alert: lselect to the build_state call.
    When flash and turnoff are both set, the light flashes first and a second
    timer turns it off 15 seconds later.
    """

    @property
    def _timer(self):
        return sys.modules["octoprint.util"].ResettableTimer

    def _entry(self, event, turnoff=False, flash=False, colour="#FF0000",
                brightness=200, delay=0):
        return {
            "event": event,
            "colour": colour,
            "brightness": brightness,
            "delay": delay,
            "turnoff": turnoff,
            "flash": flash,
        }

    def test_flash_only_adds_alert_lselect(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [self._entry("PrintDone", flash=True)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["alert"] == "lselect"
        assert kwargs["kwargs"]["on"] is True

    def test_flash_false_does_not_add_alert(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [self._entry("PrintDone", flash=False)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        _, kwargs = self._timer.call_args
        assert "alert" not in kwargs["kwargs"]

    def test_flash_missing_key_does_not_add_alert(self, plugin):
        """Entries saved before flash feature had no flash key — must not crash."""
        entry = {
            "event": "PrintDone", "colour": "#FF0000",
            "brightness": 200, "delay": 0, "turnoff": False,
            # no 'flash' key
        }
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [entry],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        _, kwargs = self._timer.call_args
        assert "alert" not in kwargs["kwargs"]

    def test_flash_and_turnoff_schedules_two_timers(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [self._entry("PrintDone", turnoff=True, flash=True)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        assert self._timer.call_count == 2

    def test_flash_and_turnoff_first_timer_sends_alert(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [self._entry("PrintDone", turnoff=True, flash=True, delay=0)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        first_call = self._timer.call_args_list[0]
        assert first_call[1]["kwargs"]["alert"] == "lselect"
        assert first_call[1]["kwargs"]["on"] is True

    def test_flash_and_turnoff_second_timer_sends_off_after_15s(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "statusDict": [self._entry("PrintDone", turnoff=True, flash=True, delay=0)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        second_call = self._timer.call_args_list[1]
        assert second_call[0][0] == 15  # delay arg
        assert second_call[1]["kwargs"]["on"] is False


# ===========================================================================
# _is_night_mode_active
# ===========================================================================

class TestIsNightModeActive:
    """
    _is_night_mode_active returns True only when night mode is enabled and the
    current time falls within the configured window.  The window may span
    midnight (e.g. 22:00–07:00).
    """

    def _settings(self, plugin, start="22:00", end="07:00", enabled=True):
        plugin._settings.get.side_effect = make_settings_getter({
            "nightmode_enabled": enabled,
            "nightmode_start": start,
            "nightmode_end": end,
        })

    def _patch_time(self, hour, minute=0):
        """Return a patch context that fixes datetime.now().time() to HH:MM."""
        mock_dt = MagicMock()
        mock_dt.now.return_value.time.return_value = real_time(hour, minute)
        mock_dt.strptime.side_effect = real_datetime.strptime
        return patch("octoprint_octohue.datetime", mock_dt)

    def test_disabled_always_returns_false(self, plugin):
        self._settings(plugin, enabled=False)
        with self._patch_time(23):
            assert plugin._is_night_mode_active() is False

    def test_overnight_window_returns_true_after_start(self, plugin):
        self._settings(plugin, start="22:00", end="07:00")
        with self._patch_time(23):
            assert plugin._is_night_mode_active() is True

    def test_overnight_window_returns_true_before_end(self, plugin):
        self._settings(plugin, start="22:00", end="07:00")
        with self._patch_time(6):
            assert plugin._is_night_mode_active() is True

    def test_overnight_window_returns_false_during_day(self, plugin):
        self._settings(plugin, start="22:00", end="07:00")
        with self._patch_time(12):
            assert plugin._is_night_mode_active() is False

    def test_same_day_window_returns_true_inside(self, plugin):
        self._settings(plugin, start="08:00", end="20:00")
        with self._patch_time(14):
            assert plugin._is_night_mode_active() is True

    def test_same_day_window_returns_false_outside(self, plugin):
        self._settings(plugin, start="08:00", end="20:00")
        with self._patch_time(21):
            assert plugin._is_night_mode_active() is False

    def test_exactly_at_start_is_active(self, plugin):
        self._settings(plugin, start="22:00", end="07:00")
        with self._patch_time(22, 0):
            assert plugin._is_night_mode_active() is True

    def test_exactly_at_end_is_not_active(self, plugin):
        self._settings(plugin, start="22:00", end="07:00")
        with self._patch_time(7, 0):
            assert plugin._is_night_mode_active() is False

    def test_bad_time_format_returns_false(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({
            "nightmode_enabled": True,
            "nightmode_start": "not-a-time",
            "nightmode_end": "07:00",
        })
        assert plugin._is_night_mode_active() is False


# ===========================================================================
# build_state  –  night mode behaviour
# ===========================================================================

class TestBuildStateNightMode:
    """
    When night mode is active, build_state either skips the light change
    entirely (pause) or caps the brightness (dim).
    """

    def _make_plugin_with_night_mode(self, plugin, action, maxbri=64):
        plugin._is_night_mode_active = MagicMock(return_value=True)
        plugin._settings.get.side_effect = make_settings_getter({
            "nightmode_action": action,
            "nightmode_maxbri": maxbri,
            "lampisgroup": False,
            "lampid": "1",
            "plugid": "99",
        })
        plugin.pbridge = MagicMock()

    def test_pause_action_skips_set_state(self, plugin):
        self._make_plugin_with_night_mode(plugin, "pause")
        plugin.set_state = MagicMock()
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        plugin.set_state.assert_not_called()

    def test_pause_action_returns_none(self, plugin):
        self._make_plugin_with_night_mode(plugin, "pause")
        result = plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        assert result is None

    def test_dim_action_caps_brightness_at_maxbri(self, plugin):
        self._make_plugin_with_night_mode(plugin, "dim", maxbri=50)
        plugin.set_state = MagicMock()
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        state_arg = plugin.set_state.call_args[0][0]
        assert state_arg["bri"] == 50

    def test_dim_action_does_not_increase_brightness(self, plugin):
        self._make_plugin_with_night_mode(plugin, "dim", maxbri=200)
        plugin.set_state = MagicMock()
        plugin.build_state(on=True, bri=100, colour="#FF0000", deviceid="1")
        state_arg = plugin.set_state.call_args[0][0]
        assert state_arg["bri"] == 100  # already below max, unchanged

    def test_night_mode_inactive_passes_through_unchanged(self, plugin):
        plugin._is_night_mode_active = MagicMock(return_value=False)
        plugin._settings.get.side_effect = make_settings_getter({
            "lampisgroup": False, "lampid": "1", "plugid": "99",
        })
        plugin.pbridge = MagicMock()
        plugin.set_state = MagicMock()
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        state_arg = plugin.set_state.call_args[0][0]
        assert state_arg["bri"] == 255


# ===========================================================================
# get_settings_defaults  –  nightmode keys present
# ===========================================================================

class TestGetSettingsDefaultsNightMode:

    def test_nightmode_keys_present(self, plugin):
        defaults = plugin.get_settings_defaults()
        for key in ["nightmode_enabled", "nightmode_start", "nightmode_end",
                    "nightmode_action", "nightmode_maxbri"]:
            assert key in defaults, f"Missing nightmode key: {key!r}"

    def test_nightmode_defaults(self, plugin):
        d = plugin.get_settings_defaults()
        assert d["nightmode_enabled"] is False
        assert d["nightmode_start"] == "22:00"
        assert d["nightmode_end"] == "07:00"
        assert d["nightmode_action"] == "pause"
        assert d["nightmode_maxbri"] == 64


# ===========================================================================
# on_settings_load  –  nightmode keys returned
# ===========================================================================

class TestOnSettingsLoadNightMode:

    def test_nightmode_keys_in_returned_dict(self, plugin):
        sys.modules["octoprint.events"].all_events.return_value = []
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.get_configured_events = MagicMock(return_value=[])
        result = plugin.on_settings_load()
        for key in ["nightmode_enabled", "nightmode_start", "nightmode_end",
                    "nightmode_action", "nightmode_maxbri"]:
            assert key in result, f"Missing nightmode key in on_settings_load: {key!r}"


# ===========================================================================
# on_settings_migrate  –  flash key in default statusDict entries
# ===========================================================================

class TestOnSettingsMigrateFlash:

    def test_default_entries_include_flash_false(self, plugin):
        plugin.on_settings_migrate(target=1, current=None)
        set_calls = [
            c for c in plugin._settings.set.call_args_list
            if c[0][0] == ["statusDict"]
        ]
        entries = set_calls[0][0][1]
        for entry in entries:
            assert "flash" in entry, f"Entry {entry['event']!r} missing flash key"
            assert entry["flash"] is False
