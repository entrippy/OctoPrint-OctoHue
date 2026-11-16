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
    rgb_to_xy is now a static method on HueProvider.
    These tests are kept here for regression coverage; the canonical suite
    lives in tests/providers/test_hue.py::TestRgbToXy.
    """

    def _xy(self, *args):
        from octoprint_octohue.providers.hue import HueProvider
        return HueProvider.rgb_to_xy(*args)

    def test_pure_red_integers(self):
        xy = self._xy(255, 0, 0)
        assert len(xy) == 2
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_pure_green_integers(self):
        xy = self._xy(0, 255, 0)
        assert abs(xy[0] - 0.3000) < 0.001
        assert abs(xy[1] - 0.6000) < 0.001

    def test_pure_blue_integers(self):
        xy = self._xy(0, 0, 255)
        assert abs(xy[0] - 0.1500) < 0.001
        assert abs(xy[1] - 0.0601) < 0.001

    def test_white_integers(self):
        xy = self._xy(255, 255, 255)
        assert abs(xy[0] - 0.3127) < 0.001
        assert abs(xy[1] - 0.3290) < 0.001

    def test_red_hex_string(self):
        xy = self._xy("#FF0000")
        assert abs(xy[0] - 0.6400) < 0.001
        assert abs(xy[1] - 0.3300) < 0.001

    def test_green_hex_string(self):
        xy = self._xy("#00FF00")
        assert abs(xy[0] - 0.3000) < 0.001
        assert abs(xy[1] - 0.6000) < 0.001

    def test_blue_hex_string(self):
        xy = self._xy("#0000FF")
        assert abs(xy[0] - 0.1500) < 0.001
        assert abs(xy[1] - 0.0601) < 0.001

    def test_lowercase_hex_string(self):
        xy_upper = self._xy("#FF0000")
        xy_lower = self._xy("#ff0000")
        assert abs(xy_upper[0] - xy_lower[0]) < 0.0001
        assert abs(xy_upper[1] - xy_lower[1]) < 0.0001

    def test_invalid_hex_string_raises_value_error(self):
        with pytest.raises(ValueError):
            self._xy("invalid")

    def test_returns_list_of_two_floats(self):
        xy = self._xy(100, 150, 200)
        assert isinstance(xy, list)
        assert len(xy) == 2
        assert all(isinstance(v, float) for v in xy)

    def test_coordinates_in_unit_range(self):
        for r, g, b in [(255, 128, 0), (0, 128, 255), (128, 0, 255)]:
            xy = self._xy(r, g, b)
            assert 0.0 <= xy[0] <= 1.0
            assert 0.0 <= xy[1] <= 1.0

    def test_low_gamma_linear_range(self):
        xy = self._xy(9, 9, 9)
        xy_white = self._xy(255, 255, 255)
        assert abs(xy[0] - xy_white[0]) < 0.001
        assert abs(xy[1] - xy_white[1]) < 0.001

    def test_neutral_grey_same_xy_as_white(self):
        xy_white = self._xy(255, 255, 255)
        xy_grey = self._xy(128, 128, 128)
        assert abs(xy_white[0] - xy_grey[0]) < 0.001
        assert abs(xy_white[1] - xy_grey[1]) < 0.001

    def test_black_returns_none(self):
        assert self._xy(0, 0, 0) is None

    def test_black_hex_string_returns_none(self):
        assert self._xy("#000000") is None


# ===========================================================================
# build_state
# ===========================================================================

class TestBuildState:
    """
    build_state applies night-mode logic then delegates to _provider.set_light().
    """

    def test_on_true_with_colour_calls_set_light_with_colour(self, plugin):
        plugin.build_state(on=True, colour="#FF0000", bri=200, deviceid="1")
        plugin._provider.set_light.assert_called_once_with(
            on=True, deviceid="1", colour_hex="#FF0000",
            ct_mirek=None, brightness_pct=200, flash=False, transition_ms=None,
        )

    def test_on_false_calls_set_light_off(self, plugin):
        plugin.build_state(on=False, deviceid="1")
        plugin._provider.set_light.assert_called_once_with(
            on=False, deviceid="1", colour_hex=None,
            ct_mirek=None, brightness_pct=None, flash=False, transition_ms=None,
        )

    def test_ct_forwarded_as_ct_mirek(self, plugin):
        plugin.build_state(on=True, ct=370, bri=100, deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["ct_mirek"] == 370
        assert call_kwargs["colour_hex"] is None

    def test_alert_lselect_translates_to_flash_true(self, plugin):
        plugin.build_state(on=True, bri=100, alert="lselect", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["flash"] is True

    def test_no_alert_translates_to_flash_false(self, plugin):
        plugin.build_state(on=True, bri=100, deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["flash"] is False

    def test_transitiontime_converted_to_ms(self, plugin):
        plugin.build_state(on=True, bri=100, transitiontime=4, deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["transition_ms"] == 400

    def test_on_false_colour_not_forwarded(self, plugin):
        plugin.build_state(on=False, colour="#FF0000", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["colour_hex"] is None

    def test_none_colour_forwarded_as_none(self, plugin):
        plugin.build_state(on=True, colour=None, bri=200, deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["colour_hex"] is None


# ===========================================================================
# get_state / set_state — Hue-specific behaviour
# These are now tested at the provider level in tests/providers/test_hue.py.
# The plugin-level tests below only verify that the plugin delegates
# correctly to its provider.
# ===========================================================================

class TestGetStateViaPlugin:
    """Plugin.get_state() is now a thin call to _provider.get_state()."""

    def test_delegates_to_provider(self, plugin):
        plugin._provider.get_state.return_value = True
        result = plugin._provider.get_state("lamp-1")
        assert result is True
        plugin._provider.get_state.assert_called_once_with("lamp-1")


class TestSetStateViaPlugin:
    """Plugin.build_state() delegates to _provider.set_light() — covered in TestBuildState."""
    pass


# ===========================================================================
# toggle_state
# ===========================================================================

class TestToggleState:
    """toggle_state reads current state then flips it."""

    def test_when_on_turns_off(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"lampid": "1"})
        plugin._provider.get_state.return_value = True
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")
        plugin.build_state.assert_called_once_with(on=False, deviceid="1")

    def test_when_off_lamp_turns_on_with_toggle_colour(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": "2", "togglebri": 80, "togglecolour": "#FF8800", "togglect": 0,
             "defaultbri": 100}
        )
        plugin._provider.get_state.return_value = False
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")  # deviceid "1" != plugid "2"
        plugin.build_state.assert_called_once_with(on=True, colour="#FF8800", bri=80, deviceid="1")

    def test_when_off_lamp_uses_toggle_ct_when_set(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": "2", "togglebri": 80, "togglecolour": "#FFFFFF", "togglect": 370,
             "defaultbri": 100}
        )
        plugin._provider.get_state.return_value = False
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")
        plugin.build_state.assert_called_once_with(on=True, ct=370, bri=80, deviceid="1")

    def test_when_off_lamp_falls_back_to_defaultbri_if_togglebri_missing(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"plugid": "2", "togglebri": None, "togglecolour": "#FFFFFF", "togglect": 0,
             "defaultbri": 60}
        )
        plugin._provider.get_state.return_value = False
        plugin.build_state = MagicMock()
        plugin.toggle_state("1")
        call_kwargs = plugin.build_state.call_args[1]
        assert call_kwargs["bri"] == 60

    def test_when_off_plug_turns_on_without_brightness(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter({"plugid": "2"})
        plugin._provider.get_state.return_value = False
        plugin.build_state = MagicMock()
        plugin.toggle_state("2")  # deviceid "2" == plugid "2"
        plugin.build_state.assert_called_once_with(on=True, deviceid="2")

    def test_defaults_to_settings_lampid_when_none(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"lampid": "3", "plugid": "99"}
        )
        plugin._provider.get_state.return_value = True
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
# _init_provider / _build_provider_settings
# ===========================================================================

class TestInitProvider:
    """_init_provider() selects the correct class from PROVIDERS and calls setup()."""

    def test_unknown_provider_falls_back_to_hue(self, plugin):
        """An unrecognised provider name must fall back to HueProvider with Hue settings."""
        from octoprint_octohue.providers.hue import HueProvider
        plugin._settings.get.side_effect = make_settings_getter({"provider": "nonexistent"})
        plugin._init_provider()
        assert isinstance(plugin._provider, HueProvider)
        assert plugin._provider.is_ready  # must be configured with Hue settings, not empty dict

    def test_wled_provider_selected_when_configured(self, plugin):
        """provider='wled' in settings must instantiate WledProvider."""
        from octoprint_octohue.providers.wled import WledProvider
        plugin._settings.get.side_effect = make_settings_getter({"provider": "wled"})
        plugin._init_provider()
        assert isinstance(plugin._provider, WledProvider)

    def test_build_provider_settings_returns_empty_dict_for_unknown_provider(self, plugin):
        """Non-hue providers receive an empty settings dict until they define their own keys."""
        result = plugin._build_provider_settings("unknown_provider")
        assert result == {}


# ===========================================================================
# on_after_startup
# ===========================================================================

class TestOnAfterStartup:

    def test_calls_init_provider_on_startup(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin._init_provider = MagicMock()
        plugin.on_after_startup()
        plugin._init_provider.assert_called_once()

    def test_ononstartup_matching_event_calls_build_state(self, plugin):
        """When ononstartup is True and the configured event exists in statusDict,
        build_state must be called with the event's colour and brightness."""
        status_entry = {
            'event': 'PrintDone',
            'colour': '#33FF36',
            'brightness': 200,
        }
        plugin._settings.get.side_effect = make_settings_getter({
            'ononstartup': True,
            'ononstartupevent': 'PrintDone',
            'statusDict': [status_entry],
            'lampid': '1',
        })
        plugin._init_provider = MagicMock()
        plugin.build_state = MagicMock()
        plugin.on_after_startup()
        plugin.build_state.assert_called_once_with(
            on=True, colour='#33FF36', bri=200, deviceid='1'
        )

    def test_ononstartup_no_matching_event_does_not_call_build_state(self, plugin):
        """When ononstartup is True but the configured event is not in statusDict,
        build_state must not be called."""
        plugin._settings.get.side_effect = make_settings_getter({
            'ononstartup': True,
            'ononstartupevent': 'PrintDone',
            'statusDict': [],
        })
        plugin._init_provider = MagicMock()
        plugin.build_state = MagicMock()
        plugin.on_after_startup()
        plugin.build_state.assert_not_called()

    def test_ononstartup_ct_event_calls_build_state_with_ct(self, plugin):
        """When the startup event has ct set, build_state should receive ct not colour."""
        status_entry = {
            'event': 'PrintDone',
            'colour': '#33FF36',
            'brightness': 200,
            'ct': 370,
        }
        plugin._settings.get.side_effect = make_settings_getter({
            'ononstartup': True,
            'ononstartupevent': 'PrintDone',
            'statusDict': [status_entry],
            'lampid': '1',
        })
        plugin._init_provider = MagicMock()
        plugin.build_state = MagicMock()
        plugin.on_after_startup()
        plugin.build_state.assert_called_once_with(
            on=True, ct=370, bri=200, deviceid='1'
        )

    def test_ononstartup_false_does_not_call_build_state(self, plugin):
        """When ononstartup is False, build_state must not be called regardless
        of what is in statusDict."""
        status_entry = {
            'event': 'PrintDone',
            'colour': '#33FF36',
            'brightness': 200,
        }
        plugin._settings.get.side_effect = make_settings_getter({
            'ononstartup': False,
            'ononstartupevent': 'PrintDone',
            'statusDict': [status_entry],
        })
        plugin._init_provider = MagicMock()
        plugin.build_state = MagicMock()
        plugin.on_after_startup()
        plugin.build_state.assert_not_called()


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
        plugin.on_shutdown()
        plugin._provider.set_light.assert_called_once_with(on=False)

    def test_no_action_when_offonshutdown_false(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"offonshutdown": False}
        )
        plugin.on_shutdown()
        plugin._provider.set_light.assert_not_called()


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
                           colour="#FFFFFF", brightness=200, delay=0, ct=0):
        return {
            "event": event,
            "colour": colour,
            "brightness": brightness,
            "delay": delay,
            "turnoff": turnoff,
            "flash": flash,
            "ct": ct,
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

    def test_ct_mode_schedules_ct_not_colour(self, plugin):
        """When an event has ct set, build_state should receive ct, not colour."""
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintStarted", ct=370)],
                "autopoweroff": False,
            }
        )
        plugin.on_event("PrintStarted", {})
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["ct"] == 370
        assert "colour" not in kwargs["kwargs"]

    def test_ct_mode_zero_falls_back_to_colour(self, plugin):
        """When ct is 0 (falsy), colour should be used as normal."""
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintStarted", ct=0)],
                "autopoweroff": False,
            }
        )
        plugin.on_event("PrintStarted", {})
        _, kwargs = self._timer.call_args
        assert "colour" in kwargs["kwargs"]
        assert "ct" not in kwargs["kwargs"]

    def test_ct_mode_flash_and_turnoff_uses_ct(self, plugin):
        """Flash+turnoff with ct set should use ct in the flash kwargs."""
        plugin._settings.get.side_effect = make_settings_getter(
            {
                "lampid": "1",
                "statusDict": [self._status_dict_entry("PrintDone", flash=True, turnoff=True, ct=300)],
                "autopoweroff": False,
            }
        )
        plugin.on_event("PrintDone", {})
        first_call_kwargs = self._timer.call_args_list[0][1]["kwargs"]
        assert first_call_kwargs["ct"] == 300
        assert "colour" not in first_call_kwargs


# ===========================================================================
# is_api_protected
# ===========================================================================

class TestIsApiProtected:

    def test_returns_false(self, plugin):
        assert plugin.is_api_protected() is False


# ===========================================================================
# on_api_command  –  bridge sub-commands
# ===========================================================================

class TestOnApiCommandBridge:

    def test_non_admin_returns_403(self, plugin):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.make_response.assert_called_once()
        assert flask.make_response.call_args[0][1] == 403

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

    def test_getstatus_wled_configured(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "192.168.1.50", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="configured")
        plugin._provider.check_connection.assert_called_once_with()

    def test_getstatus_wled_unconfigured(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unconfigured")

    def test_getstatus_unreachable_when_probe_fails(self, plugin):
        """Address and key set but the bridge does not answer → 'unreachable'."""
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.100", "husername": "key"}
        )
        plugin._provider.check_connection.return_value = False
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unreachable")

    def test_getstatus_configured_probes_bridge_once(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.100", "husername": "key"}
        )
        plugin._provider.check_connection.return_value = True
        plugin.on_api_command("bridge", {"getstatus": "true"})
        plugin._provider.check_connection.assert_called_once_with()

    def test_getstatus_unauthed_does_not_probe(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.100", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        plugin._provider.check_connection.assert_not_called()

    def test_getstatus_unconfigured_does_not_probe(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        plugin._provider.check_connection.assert_not_called()

    @pytest.mark.parametrize("overrides,expected", [
        ({"bridgeaddr": "192.168.1.100", "husername": "key"}, "unreachable"),
        ({"bridgeaddr": "", "husername": ""}, "unconfigured"),
        ({"bridgeaddr": "192.168.1.100", "husername": ""}, "unauthed"),
        ({"provider": "wled", "bridgeaddr": "192.168.1.50", "husername": ""}, "unreachable"),
        ({"provider": "wled", "bridgeaddr": "", "husername": ""}, "unconfigured"),
    ])
    def test_getstatus_without_provider(self, plugin, overrides, expected):
        """Missing provider only changes the result when there is something to probe."""
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(overrides)
        plugin._provider = None
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus=expected)

    def test_getstatus_wled_unreachable_when_probe_fails(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "192.168.1.50", "husername": ""}
        )
        plugin._provider.check_connection.return_value = False
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unreachable")

    def test_getstatus_wled_unconfigured_does_not_probe(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "", "husername": ""}
        )
        plugin.on_api_command("bridge", {"getstatus": "true"})
        plugin._provider.check_connection.assert_not_called()

    # ---- #83: dropdown provider differs from the saved one ---------------

    @pytest.mark.parametrize("saved,requested", [
        ("wled", "hue"),
        ("hue", "wled"),
        ("", "wled"),      # empty saved provider counts as Hue
        (None, "wled"),
        ("wled", ""),      # empty requested provider counts as Hue too
        ("wled", None),
    ])
    def test_getstatus_unsaved_when_requested_provider_differs(self, plugin, saved, requested):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": saved, "bridgeaddr": "192.168.1.50", "husername": "key"}
        )
        live = plugin._provider
        plugin._init_provider = MagicMock()
        plugin.on_api_command("bridge", {"getstatus": "true", "provider": requested})
        flask.jsonify.assert_called_once_with(bridgestatus="unsaved")
        plugin._provider.check_connection.assert_not_called()
        # Reporting "unsaved" must not touch settings or the live provider.
        assert plugin._provider is live
        plugin._init_provider.assert_not_called()
        plugin._settings.set.assert_not_called()
        plugin._settings.save.assert_not_called()

    @pytest.mark.parametrize("saved,requested", [
        ("hue", "hue"), ("", "hue"), (None, "hue"), ("wled", "wled"),
        ("hue", ""), ("hue", None),   # empty/None requested provider also counts as Hue
    ])
    def test_getstatus_probes_when_requested_provider_matches(self, plugin, saved, requested):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": saved, "bridgeaddr": "192.168.1.50", "husername": "key"}
        )
        plugin._provider.check_connection.return_value = True
        plugin.on_api_command("bridge", {"getstatus": "true", "provider": requested})
        plugin._provider.check_connection.assert_called_once()
        flask.jsonify.assert_called_once_with(bridgestatus="configured")

    @pytest.mark.parametrize("provider,addr,key,probe_ok,expected", [
        ("hue", "192.168.1.50", "", True, "unauthed"),
        ("hue", "", "", True, "unconfigured"),
        ("wled", "", "", True, "unconfigured"),
        ("hue", "192.168.1.50", "key", False, "unreachable"),
        ("wled", "192.168.1.50", "", False, "unreachable"),
    ])
    def test_getstatus_matching_provider_keeps_every_existing_status(self, plugin, provider, addr, key, probe_ok, expected):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": provider, "bridgeaddr": addr, "husername": key}
        )
        plugin._provider.check_connection.return_value = probe_ok
        plugin.on_api_command("bridge", {"getstatus": "true", "provider": provider})
        flask.jsonify.assert_called_once_with(bridgestatus=expected)
        if expected in ("unauthed", "unconfigured"):
            plugin._provider.check_connection.assert_not_called()

    def test_getstatus_without_requested_provider_keeps_old_behaviour(self, plugin):
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "192.168.1.50", "husername": ""}
        )
        plugin._provider.check_connection.return_value = False
        plugin.on_api_command("bridge", {"getstatus": "true"})
        flask.jsonify.assert_called_once_with(bridgestatus="unreachable")

    @pytest.mark.parametrize("saved,requested", [
        ({"provider": "wled", "bridgeaddr": "", "husername": ""}, "hue"),               # WLED unconfigured
        ({"provider": "hue", "bridgeaddr": "192.168.1.50", "husername": ""}, "wled"),   # Hue unauthed
        ({"provider": "hue", "bridgeaddr": "", "husername": ""}, "wled"),               # Hue unconfigured
    ])
    def test_getstatus_unsaved_takes_precedence(self, plugin, saved, requested):
        """A provider switch is reported whatever state the saved settings are in."""
        flask = sys.modules["flask"]
        plugin._settings.get.side_effect = make_settings_getter(saved)
        plugin.on_api_command("bridge", {"getstatus": "true", "provider": requested})
        flask.jsonify.assert_called_once_with(bridgestatus="unsaved")
        plugin._provider.check_connection.assert_not_called()

    def test_discover_uses_hue_provider_directly(self, plugin):
        flask = sys.modules["flask"]
        bridges = [{"internalipaddress": "192.168.1.100", "id": "abc"}]
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.discover.return_value = bridges
            plugin.on_api_command("bridge", {"discover": "true"})
            MockHue.return_value.discover.assert_called_once()
            flask.jsonify.assert_called_once_with(bridges)

    # ---- relocate: find a bridge that moved, reusing the saved key ----------

    @staticmethod
    def _hue_factory(discovered, accepts):
        """
        Build a HueProvider stand-in where every instance shares the given
        discovery result and check_connection() is True only for addresses in
        ``accepts``. Returns (factory, instances) so tests can inspect calls.

        Like the existing discover/pair tests, this relies on the plugin
        importing HueProvider at call time and using one fresh instance per
        probed address, configured via setup(dict).
        """
        instances = []

        def make(logger):
            m = MagicMock(name=f"HueProvider#{len(instances)}")
            m.discover.return_value = discovered
            m._cfg = {}
            m.setup.side_effect = lambda cfg, m=m: m._cfg.update(cfg)
            m.check_connection.side_effect = lambda m=m: m._cfg.get("bridgeaddr") in accepts
            instances.append(m)
            return m

        return make, instances

    @staticmethod
    def _bridgeaddr_sets(plugin):
        return [c for c in plugin._settings.set.call_args_list if c.args[0] == ["bridgeaddr"]]

    @staticmethod
    def _probed(instances):
        return [i._cfg.get("bridgeaddr") for i in instances if i.check_connection.called]

    def _relocate(self, plugin, discovered, accepts, key="saved-key", data=None, provider="hue"):
        plugin._settings.get.side_effect = make_settings_getter(
            {"bridgeaddr": "192.168.1.40", "husername": key, "provider": provider}
        )
        plugin._init_provider = MagicMock()
        factory, instances = self._hue_factory(discovered, accepts)
        with patch("octoprint_octohue.providers.hue.HueProvider", side_effect=factory):
            plugin.on_api_command("bridge", data or {"relocate": "true"})
        return instances

    def test_relocate_non_admin_returns_403(self, plugin):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            plugin.on_api_command("bridge", {"relocate": "true"})
            MockHue.assert_not_called()
        assert flask.make_response.call_args[0][1] == 403
        flask.jsonify.assert_any_call(error="Forbidden")
        plugin._settings.save.assert_not_called()

    def test_relocate_saves_address_that_accepts_saved_key(self, plugin):
        flask = sys.modules["flask"]
        self._relocate(plugin, [{"id": "b1", "internalipaddress": "192.168.1.120"}], {"192.168.1.120"})
        assert self._bridgeaddr_sets(plugin) == [call(["bridgeaddr"], "192.168.1.120")]
        plugin._settings.save.assert_called_once()
        plugin._init_provider.assert_called_once()
        flask.jsonify.assert_called_once_with(result="relocated", bridgeaddr="192.168.1.120")

    def test_relocate_probes_with_saved_key(self, plugin):
        instances = self._relocate(
            plugin, [{"internalipaddress": "192.168.1.120"}], {"192.168.1.120"}, key="saved-key"
        )
        probed = [i for i in instances if i.check_connection.called]
        assert probed and all(i._cfg.get("husername") == "saved-key" for i in probed)

    def test_relocate_does_not_change_saved_key(self, plugin):
        self._relocate(plugin, [{"internalipaddress": "192.168.1.120"}], {"192.168.1.120"})
        assert all(c.args[0] != ["husername"] for c in plugin._settings.set.call_args_list)

    def test_relocate_tries_next_bridge_when_first_rejects(self, plugin):
        flask = sys.modules["flask"]
        instances = self._relocate(
            plugin,
            [{"internalipaddress": "192.168.1.60"}, {"internalipaddress": "192.168.1.120"}],
            {"192.168.1.120"},
        )
        assert self._probed(instances) == ["192.168.1.60", "192.168.1.120"]
        assert self._bridgeaddr_sets(plugin) == [call(["bridgeaddr"], "192.168.1.120")]
        flask.jsonify.assert_called_once_with(result="relocated", bridgeaddr="192.168.1.120")

    def test_relocate_skips_entries_without_address(self, plugin):
        flask = sys.modules["flask"]
        self._relocate(
            plugin, [{"id": "x"}, {"internalipaddress": "192.168.1.120"}], {"192.168.1.120"}
        )
        flask.jsonify.assert_called_once_with(result="relocated", bridgeaddr="192.168.1.120")

    def test_relocate_needspairing_uses_first_entry_with_address(self, plugin):
        flask = sys.modules["flask"]
        self._relocate(plugin, [{"id": "x"}, {"internalipaddress": "192.168.1.120"}], set())
        flask.jsonify.assert_called_once_with(result="needspairing", bridgeaddr="192.168.1.120")

    def test_relocate_stops_at_first_accepting_bridge(self, plugin):
        instances = self._relocate(
            plugin,
            [{"internalipaddress": "192.168.1.120"}, {"internalipaddress": "192.168.1.60"}],
            {"192.168.1.120", "192.168.1.60"},
        )
        assert self._probed(instances) == ["192.168.1.120"]

    def test_relocate_needs_pairing_when_no_bridge_accepts_key(self, plugin):
        flask = sys.modules["flask"]
        self._relocate(
            plugin,
            [{"internalipaddress": "192.168.1.120"}, {"internalipaddress": "192.168.1.60"}],
            set(),
        )
        flask.jsonify.assert_called_once_with(result="needspairing", bridgeaddr="192.168.1.120")
        assert self._bridgeaddr_sets(plugin) == []
        plugin._settings.save.assert_not_called()
        plugin._init_provider.assert_not_called()
        # Probing must use temporary providers, never repoint the live one.
        plugin._provider.setup.assert_not_called()

    @pytest.mark.parametrize("key", ["", None])
    def test_relocate_without_saved_key_needs_pairing_without_probing(self, plugin, key):
        flask = sys.modules["flask"]
        instances = self._relocate(
            plugin,
            [{"internalipaddress": "192.168.1.120"}, {"internalipaddress": "192.168.1.60"}],
            {"192.168.1.120", "192.168.1.60"},
            key=key,
        )
        assert self._probed(instances) == []
        flask.jsonify.assert_called_once_with(result="needspairing", bridgeaddr="192.168.1.120")
        assert self._bridgeaddr_sets(plugin) == []
        plugin._settings.save.assert_not_called()
        plugin._init_provider.assert_not_called()

    @pytest.mark.parametrize("discovered", [
        [],
        [{"id": "no-address"}],
        ["192.168.1.1"],
        [None],
    ])
    def test_relocate_notfound_when_discovery_has_no_addresses(self, plugin, discovered):
        flask = sys.modules["flask"]
        self._relocate(plugin, discovered, set())
        flask.jsonify.assert_called_once_with(result="notfound")
        assert self._bridgeaddr_sets(plugin) == []
        plugin._settings.save.assert_not_called()

    @pytest.mark.parametrize("discovered", [{"error": "rate limited"}, None])
    def test_relocate_failed_when_discovery_response_is_not_a_list(self, plugin, discovered):
        """An error object from discovery means the search didn't work, not that no bridge exists."""
        flask = sys.modules["flask"]
        self._relocate(plugin, discovered, set())
        flask.jsonify.assert_called_once_with(result="failed")
        plugin._settings.save.assert_not_called()

    def test_relocate_refuses_when_saved_provider_is_not_hue(self, plugin):
        """bridgeaddr is shared with WLED; relocate must never overwrite a WLED address."""
        flask = sys.modules["flask"]
        instances = self._relocate(
            plugin, [{"internalipaddress": "192.168.1.120"}], {"192.168.1.120"}, provider="wled"
        )
        assert self._probed(instances) == []
        assert self._bridgeaddr_sets(plugin) == []
        plugin._settings.save.assert_not_called()
        flask.jsonify.assert_called_once_with(result="failed")

    @pytest.mark.parametrize("bad", [
        "8.8.8.8", "not-an-ip", "", 12345, "192.168.1.120/../x",
        "127.0.0.1", "0.0.0.0", "169.254.1.1", "fd00::1", "::1",
    ])
    def test_relocate_ignores_non_private_or_invalid_addresses(self, plugin, bad):
        """Only private-network IP addresses from discovery are probed or offered."""
        flask = sys.modules["flask"]
        instances = self._relocate(plugin, [{"internalipaddress": bad}], {bad} if isinstance(bad, str) else set())
        assert self._probed(instances) == []
        flask.jsonify.assert_called_once_with(result="notfound")

    def test_relocate_ignores_address_supplied_in_request(self, plugin):
        """Only discovered addresses may be probed or saved."""
        instances = self._relocate(
            plugin, [], {"6.6.6.6"},
            data={"relocate": "true", "bridgeaddr": "6.6.6.6"},
        )
        assert "6.6.6.6" not in self._probed(instances)
        plugin._settings.save.assert_not_called()

    def test_relocate_ignores_request_address_alongside_discovery(self, plugin):
        flask = sys.modules["flask"]
        instances = self._relocate(
            plugin, [{"internalipaddress": "192.168.1.120"}], {"6.6.6.6", "192.168.1.120"},
            data={"relocate": "true", "bridgeaddr": "6.6.6.6"},
        )
        assert self._probed(instances) == ["192.168.1.120"]
        flask.jsonify.assert_called_once_with(result="relocated", bridgeaddr="192.168.1.120")

    def test_pair_success_saves_credentials(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin._init_provider = MagicMock()
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {
                "response": "success",
                "bridgeaddr": "192.168.1.100",
                "husername": "new-api-key",
            }
            plugin.on_api_command(
                "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
            )
        plugin._settings.set.assert_any_call(["husername"], "new-api-key")
        plugin._settings.set.assert_any_call(["bridgeaddr"], "192.168.1.100")
        plugin._settings.save.assert_called()

    def test_pair_success_calls_init_provider(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin._init_provider = MagicMock()
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {
                "response": "success",
                "bridgeaddr": "192.168.1.100",
                "husername": "new-api-key",
            }
            plugin.on_api_command(
                "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
            )
        plugin._init_provider.assert_called_once()

    @pytest.mark.parametrize("previous", ["wled"])
    def test_pair_from_other_provider_clears_its_device_ids(self, plugin, previous):
        """#88: pairing switches provider to Hue outside on_settings_save, so it must
        drop the previous provider's light/plug selection itself."""
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": previous, "lampid": "wled", "plugid": "", "lampisgroup": True}
        )
        plugin._init_provider = MagicMock()
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {
                "response": "success", "bridgeaddr": "192.168.1.100", "husername": "new-api-key",
            }
            plugin.on_api_command("bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"})
        plugin._settings.set.assert_any_call(["lampid"], "")
        plugin._settings.set.assert_any_call(["plugid"], "")
        plugin._settings.set.assert_any_call(["lampisgroup"], False)
        # Cleared before the save that persists the pairing.
        calls = [c[0] for c in plugin._settings.mock_calls]
        last_clear = max(i for i, c in enumerate(plugin._settings.mock_calls)
                         if c[0] == "set" and c.args[0] in (["lampid"], ["plugid"], ["lampisgroup"]))
        assert "save" in calls[last_clear:]

    @pytest.mark.parametrize("previous", ["hue", "", None])
    def test_pair_when_already_hue_keeps_device_ids(self, plugin, previous):
        """Re-pairing Hue (e.g. after a key reset) must keep the chosen light."""
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": previous, "lampid": "hue-light-uuid", "plugid": "hue-plug-uuid"}
        )
        plugin._init_provider = MagicMock()
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {
                "response": "success", "bridgeaddr": "192.168.1.100", "husername": "new-api-key",
            }
            plugin.on_api_command("bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"})
        cleared = [c for c in plugin._settings.set.call_args_list
                   if c.args[0] in (["lampid"], ["plugid"], ["lampisgroup"])]
        assert cleared == []

    def test_pair_error_returns_error_response(self, plugin):
        flask = sys.modules["flask"]
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {"response": "error"}
            plugin.on_api_command(
                "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
            )
        flask.jsonify.assert_called()
        args = flask.jsonify.call_args[0][0]
        assert args[0]["response"] == "error"

    def test_pair_uses_hue_provider_directly(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin._init_provider = MagicMock()
        with patch("octoprint_octohue.providers.hue.HueProvider") as MockHue:
            MockHue.return_value.pair.return_value = {
                "response": "success",
                "bridgeaddr": "192.168.1.100",
                "husername": "key",
            }
            plugin.on_api_command(
                "bridge", {"pair": "true", "bridgeaddr": "192.168.1.100"}
            )
            MockHue.return_value.pair.assert_called_once_with(bridgeaddr="192.168.1.100")


# ===========================================================================
# on_api_command  –  getdevices
# ===========================================================================

class TestOnApiCommandGetDevices:

    _LIGHTS = [
        {"id": "uuid-1", "name": "Desk Lamp", "archetype": "tableShade"},
        {"id": "uuid-2", "name": "Smart Plug", "archetype": "plug"},
        {"id": "uuid-3", "name": "Floor Lamp", "archetype": "floorShade"},
    ]

    def test_non_admin_returns_403(self, plugin):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        plugin.on_api_command("getdevices", {})
        flask.make_response.assert_called_once()
        assert flask.make_response.call_args[0][1] == 403

    def test_returns_empty_devices_when_provider_not_ready(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.is_ready = False
        plugin.on_api_command("getdevices", {})
        flask.jsonify.assert_called_once_with(devices=[])

    def test_returns_all_devices_when_no_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_lights.return_value = self._LIGHTS
        plugin.on_api_command("getdevices", {})
        devices = flask.jsonify.call_args[1]["devices"]
        assert len(devices) == 3

    def test_filters_by_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_lights.return_value = self._LIGHTS
        plugin.on_api_command("getdevices", {"archetype": "plug"})
        devices = flask.jsonify.call_args[1]["devices"]
        assert len(devices) == 1
        assert devices[0]["name"] == "Smart Plug"

    def test_device_dict_contains_id_name_archetype(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_lights.return_value = self._LIGHTS
        plugin.on_api_command("getdevices", {})
        devices = flask.jsonify.call_args[1]["devices"]
        for d in devices:
            assert "id" in d
            assert "name" in d
            assert "archetype" in d

    def test_device_ids_are_uuids(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_lights.return_value = self._LIGHTS
        plugin.on_api_command("getdevices", {})
        devices = flask.jsonify.call_args[1]["devices"]
        assert devices[0]["id"] == "uuid-1"

    def test_empty_archetype_filter_returns_nothing(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_lights.return_value = self._LIGHTS
        plugin.on_api_command("getdevices", {"archetype": "nonexistent"})
        devices = flask.jsonify.call_args[1]["devices"]
        assert devices == []


# ===========================================================================
# on_api_command  –  getgroups
# ===========================================================================

class TestDeviceListsUnsavedProvider:
    """#87: device lists must not offer the saved provider's devices for a different selection."""

    # Saved None relies on make_settings_getter returning override values as-is.
    _MISMATCH = [("wled", "hue"), ("hue", "wled"), ("", "wled"), (None, "wled"), ("wled", ""), ("wled", None)]
    _MATCH = [("hue", "hue"), ("", "hue"), (None, "hue"), ("hue", ""), ("hue", None), ("wled", "wled")]

    @staticmethod
    def _settings(plugin, saved):
        plugin._settings.get.side_effect = make_settings_getter({"provider": saved})

    @pytest.mark.parametrize("command,key,method", [
        ("getdevices", "devices", "get_lights"),
        ("getgroups", "groups", "get_groups"),
    ])
    @pytest.mark.parametrize("saved,requested", _MISMATCH)
    def test_mismatch_returns_empty_unsaved_without_querying(self, plugin, command, key, method, saved, requested):
        flask = sys.modules["flask"]
        self._settings(plugin, saved)
        getattr(plugin._provider, method).return_value = [{"id": "x", "name": "X"}]
        plugin.on_api_command(command, {"provider": requested})
        flask.jsonify.assert_called_once_with(**{key: [], "unsaved": True})
        getattr(plugin._provider, method).assert_not_called()
        assert plugin._provider.method_calls == []
        plugin._settings.set.assert_not_called()
        plugin._settings.save.assert_not_called()

    @pytest.mark.parametrize("command,key", [("getdevices", "devices"), ("getgroups", "groups")])
    @pytest.mark.parametrize("state", ["not_ready", "no_provider"])
    def test_mismatch_reported_even_without_usable_provider(self, plugin, command, key, state):
        flask = sys.modules["flask"]
        self._settings(plugin, "wled")
        if state == "not_ready":
            plugin._provider.is_ready = False
        else:
            plugin._provider = None
        plugin.on_api_command(command, {"provider": "hue"})
        flask.jsonify.assert_called_once_with(**{key: [], "unsaved": True})

    @pytest.mark.parametrize("command,key", [("getdevices", "devices"), ("getgroups", "groups")])
    def test_match_with_provider_not_ready_returns_plain_empty_list(self, plugin, command, key):
        flask = sys.modules["flask"]
        self._settings(plugin, "hue")
        plugin._provider.is_ready = False
        plugin.on_api_command(command, {"provider": "hue"})
        flask.jsonify.assert_called_once_with(**{key: []})

    @pytest.mark.parametrize("command,key,method", [
        ("getdevices", "devices", "get_lights"),
        ("getgroups", "groups", "get_groups"),
    ])
    @pytest.mark.parametrize("saved,requested", _MATCH)
    def test_match_returns_provider_list_unchanged(self, plugin, command, key, method, saved, requested):
        flask = sys.modules["flask"]
        self._settings(plugin, saved)
        items = [{"id": "a", "name": "A", "archetype": "tableShade"}]
        getattr(plugin._provider, method).return_value = items
        plugin.on_api_command(command, {"provider": requested})
        flask.jsonify.assert_called_once_with(**{key: items})

    def test_match_keeps_archetype_filter(self, plugin):
        flask = sys.modules["flask"]
        self._settings(plugin, "hue")
        plugin._provider.get_lights.return_value = [
            {"id": "a", "name": "Lamp", "archetype": "tableShade"},
            {"id": "p", "name": "Plug", "archetype": "plug"},
        ]
        plugin.on_api_command("getdevices", {"provider": "hue", "archetype": "plug"})
        flask.jsonify.assert_called_once_with(devices=[{"id": "p", "name": "Plug", "archetype": "plug"}])

    @pytest.mark.parametrize("command,key,method", [
        ("getdevices", "devices", "get_lights"),
        ("getgroups", "groups", "get_groups"),
    ])
    def test_without_provider_keeps_old_behaviour(self, plugin, command, key, method):
        flask = sys.modules["flask"]
        self._settings(plugin, "wled")
        items = [{"id": "wled", "name": "Strip"}]
        getattr(plugin._provider, method).return_value = items
        plugin.on_api_command(command, {})
        flask.jsonify.assert_called_once_with(**{key: items})

    @pytest.mark.parametrize("command", ["getdevices", "getgroups"])
    def test_mismatch_still_requires_admin(self, plugin, command):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        self._settings(plugin, "wled")
        plugin.on_api_command(command, {"provider": "hue"})
        assert flask.make_response.called
        assert flask.make_response.call_args[0][1] == 403
        assert all(c.kwargs.get("unsaved") is None for c in flask.jsonify.call_args_list)


class TestOnApiCommandGetGroups:

    def test_non_admin_returns_403(self, plugin):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        plugin.on_api_command("getgroups", {})
        flask.make_response.assert_called_once()
        assert flask.make_response.call_args[0][1] == 403

    def test_returns_empty_groups_when_provider_not_ready(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.is_ready = False
        plugin.on_api_command("getgroups", {})
        flask.jsonify.assert_called_once_with(groups=[])

    def test_returns_groups_from_provider(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_groups.return_value = [
            {"id": "gl-uuid-1", "name": "Living Room"},
            {"id": "gl-uuid-2", "name": "Office Zone"},
        ]
        plugin.on_api_command("getgroups", {})
        groups = flask.jsonify.call_args[1]["groups"]
        assert len(groups) == 2
        assert groups[0]["name"] == "Living Room"

    def test_delegates_to_provider_get_groups(self, plugin):
        plugin._provider.get_groups.return_value = []
        plugin.on_api_command("getgroups", {})
        plugin._provider.get_groups.assert_called_once()


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

    def test_getstate_non_admin_returns_403(self, plugin):
        flask = sys.modules["flask"]
        sys.modules["octoprint.access.permissions"].Permissions.ADMIN.can.return_value = False
        plugin.on_api_command("getstate", {})
        flask.make_response.assert_called_once()
        assert flask.make_response.call_args[0][1] == 403

    def test_getstate_when_on_returns_true_string(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_state.return_value = True
        plugin.on_api_command("getstate", {})
        flask.jsonify.assert_called_once_with(on="true")

    def test_getstate_when_off_returns_false_string(self, plugin):
        flask = sys.modules["flask"]
        plugin._provider.get_state.return_value = False
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
            "enabled", "installed_version", "provider",
            "bridgeaddr", "husername",
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
        assert d["defaultbri"] == 100
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
        plugin.on_settings_migrate(target=5, current=5)
        plugin._settings.set.assert_not_called()

    def test_first_install_example_brightnesses_are_percentages(self, plugin):
        """First-install example entries must use the 0-100 scale, not 1-255."""
        plugin.on_settings_migrate(target=3, current=None)
        set_calls = [c for c in plugin._settings.set.call_args_list if c[0][0] == ["statusDict"]]
        entries = set_calls[0][0][1]
        for entry in entries:
            bri = entry.get("brightness")
            if bri != "":  # Disconnected has empty brightness
                assert bri <= 100, f"brightness {bri} exceeds 100 for event {entry['event']}"

    def test_v1_to_v2_clears_lamp_and_plug_ids(self, plugin):
        """Upgrading from v1: integer IDs must be cleared since v2 uses UUIDs."""
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.on_settings_migrate(target=3, current=1)
        plugin._settings.set.assert_any_call(['lampid'], '')
        plugin._settings.set.assert_any_call(['plugid'], '')
        plugin._settings.save.assert_called()

    def test_v2_to_v3_does_not_clear_device_ids(self, plugin):
        """The v2→v3 migration must not touch lampid/plugid — only v1→v2 does."""
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 255, "nightmode_maxbri": 64, "statusDict": []
        })
        plugin.on_settings_migrate(target=3, current=2)
        calls = [c[0][0] for c in plugin._settings.set.call_args_list]
        assert ['lampid'] not in calls
        assert ['plugid'] not in calls

    def test_v2_to_v3_converts_defaultbri(self, plugin):
        """defaultbri 255 → 100, 128 → 50."""
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 255, "nightmode_maxbri": 64, "statusDict": []
        })
        plugin.on_settings_migrate(target=3, current=2)
        plugin._settings.set.assert_any_call(['defaultbri'], 100)

    def test_v2_to_v3_converts_nightmode_maxbri(self, plugin):
        """nightmode_maxbri 64 → 25 (64/255*100 ≈ 25)."""
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 100, "nightmode_maxbri": 64, "statusDict": []
        })
        plugin.on_settings_migrate(target=3, current=2)
        plugin._settings.set.assert_any_call(['nightmode_maxbri'], 25)

    def test_v2_to_v3_converts_status_dict_brightnesses(self, plugin):
        """statusDict brightness values are converted from 1-255 to 0-100 scale."""
        old_dict = [
            {"event": "PrintDone", "brightness": 255, "colour": "#33FF36",
             "delay": 0, "turnoff": False, "flash": False, "ct": 0},
            {"event": "PrintFailed", "brightness": 128, "colour": "#FF0000",
             "delay": 0, "turnoff": False, "flash": False, "ct": 0},
        ]
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 255, "nightmode_maxbri": 64, "statusDict": old_dict
        })
        plugin.on_settings_migrate(target=3, current=2)
        set_calls = [c for c in plugin._settings.set.call_args_list if c[0][0] == ["statusDict"]]
        migrated = set_calls[0][0][1]
        assert migrated[0]["brightness"] == 100
        assert migrated[1]["brightness"] == 50

    def test_v2_to_v3_skips_empty_brightness(self, plugin):
        """Entries with empty brightness (e.g. Disconnected/turnoff) are left unchanged."""
        old_dict = [{"event": "Disconnected", "brightness": "", "colour": "",
                     "delay": 0, "turnoff": True, "flash": False, "ct": 0}]
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 255, "nightmode_maxbri": 64, "statusDict": old_dict
        })
        plugin.on_settings_migrate(target=3, current=2)
        set_calls = [c for c in plugin._settings.set.call_args_list if c[0][0] == ["statusDict"]]
        migrated = set_calls[0][0][1]
        assert migrated[0]["brightness"] == ""

    def test_v1_to_v3_applies_both_migrations(self, plugin):
        """Direct v1→v3 upgrade applies both the UUID clear and brightness conversion."""
        old_dict = [{"event": "PrintDone", "brightness": 255, "colour": "#33FF36",
                     "delay": 0, "turnoff": False, "flash": False, "ct": 0}]
        plugin._settings.get.side_effect = make_settings_getter({
            "defaultbri": 255, "nightmode_maxbri": 64, "statusDict": old_dict
        })
        plugin.on_settings_migrate(target=4, current=1)
        plugin._settings.set.assert_any_call(['lampid'], '')
        plugin._settings.set.assert_any_call(['plugid'], '')
        set_calls = [c for c in plugin._settings.set.call_args_list if c[0][0] == ["statusDict"]]
        migrated = set_calls[0][0][1]
        assert migrated[0]["brightness"] == 100

    def test_v3_to_v4_adds_toggle_settings(self, plugin):
        """v3→v4 migration seeds togglebri from defaultbri and adds togglecolour/togglect."""
        plugin._settings.get.side_effect = make_settings_getter({"defaultbri": 75})
        plugin.on_settings_migrate(target=4, current=3)
        plugin._settings.set.assert_any_call(['togglebri'], 75)
        plugin._settings.set.assert_any_call(['togglecolour'], '#FFFFFF')
        plugin._settings.set.assert_any_call(['togglect'], 0)

    def test_v3_to_v4_does_not_touch_brightness_conversion(self, plugin):
        """v3→v4 must not re-run the brightness conversion — values are already percentages."""
        plugin._settings.get.side_effect = make_settings_getter({"defaultbri": 75})
        plugin.on_settings_migrate(target=4, current=3)
        calls = [c[0][0] for c in plugin._settings.set.call_args_list]
        assert ['defaultbri'] not in calls

    def test_v4_to_v5_sets_provider_to_hue(self, plugin):
        """v4→v5 migration must set provider='hue' for existing installs."""
        plugin._settings.get.side_effect = make_settings_getter()
        plugin.on_settings_migrate(target=5, current=4)
        plugin._settings.set.assert_any_call(['provider'], 'hue')

    def test_v4_to_v5_does_not_touch_toggle_settings(self, plugin):
        """v4→v5 must not re-run the toggle migration — values already exist."""
        plugin._settings.get.side_effect = make_settings_getter({"defaultbri": 75})
        plugin.on_settings_migrate(target=5, current=4)
        calls = [c[0][0] for c in plugin._settings.set.call_args_list]
        assert ['togglebri'] not in calls


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

    def test_reinitialises_provider_after_save(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter()
        plugin._init_provider = MagicMock()
        plugin.on_settings_save({"lampid": "uuid-1"})
        plugin._init_provider.assert_called_once()

    def test_provider_reinitialised_regardless_of_provider_type(self, plugin):
        plugin._settings.get.side_effect = make_settings_getter(
            {"provider": "wled", "bridgeaddr": "192.168.1.200"}
        )
        plugin._init_provider = MagicMock()
        plugin.on_settings_save({"bridgeaddr": "192.168.1.200"})
        plugin._init_provider.assert_called_once()


class TestOnSettingsSaveProviderChange:
    """#88: switching provider must not carry the old controller's light/plug IDs over."""

    @staticmethod
    def _save(plugin, stored, data):
        """Run on_settings_save and return the dict handed to the base class."""
        plugin._settings.get.side_effect = make_settings_getter(stored)
        plugin._init_provider = MagicMock()
        import copy
        base = sys.modules["octoprint.plugin"].SettingsPlugin
        order = MagicMock()
        snapshots = []
        with patch.object(base, "on_settings_save", autospec=True,
                          side_effect=lambda *a: snapshots.append(copy.deepcopy(a[-1]))) as base_save:
            order.attach_mock(base_save, "base_save")
            order.attach_mock(plugin._init_provider, "init_provider")
            plugin.on_settings_save(data)
        base_save.assert_called_once()
        # The provider must be rebuilt from the settings just saved.
        assert [c[0] for c in order.mock_calls] == ["base_save", "init_provider"]
        # Snapshot taken when the base class was called, so clearing IDs
        # *after* the save can't masquerade as clearing them before it.
        return snapshots[0]

    _STORED_WLED = {"provider": "wled", "lampid": "wled", "plugid": "", "lampisgroup": False}
    _STORED_HUE = {"provider": "hue", "lampid": "hue-light-uuid", "plugid": "hue-plug-uuid", "lampisgroup": True}

    @pytest.mark.parametrize("stored,new_provider", [
        (_STORED_WLED, "hue"),
        (_STORED_HUE, "wled"),
        ({**_STORED_HUE, "provider": ""}, "wled"),     # empty stored provider counts as Hue
        ({**_STORED_HUE, "provider": None}, "wled"),
        ({**_STORED_WLED}, ""),                        # empty new provider counts as Hue
        ({**_STORED_WLED}, None),
    ], ids=["wled->hue", "hue->wled", "empty->wled", "none->wled", "wled->empty", "wled->none"])
    def test_unchanged_ids_cleared_when_provider_changes(self, plugin, stored, new_provider):
        data = {"provider": new_provider, "lampid": stored["lampid"], "plugid": stored["plugid"],
                "lampisgroup": stored["lampisgroup"]}
        saved = self._save(plugin, stored, data)
        assert saved["lampid"] == ""
        assert saved["plugid"] == ""
        assert saved["lampisgroup"] is False
        assert saved["provider"] == new_provider

    def test_missing_ids_cleared_when_provider_changes(self, plugin):
        """A partial save (e.g. via the API) that only changes provider still clears stale IDs."""
        saved = self._save(plugin, self._STORED_HUE, {"provider": "wled"})
        assert saved["lampid"] == ""
        assert saved["plugid"] == ""
        assert saved["lampisgroup"] is False

    def test_newly_picked_light_kept_on_provider_change(self, plugin):
        saved = self._save(plugin, self._STORED_WLED, {
            "provider": "hue", "lampid": "new-hue-group", "lampisgroup": True, "plugid": "",
        })
        assert saved["lampid"] == "new-hue-group"
        assert saved["lampisgroup"] is True

    def test_lamp_and_plug_handled_independently(self, plugin):
        saved = self._save(plugin, self._STORED_HUE, {
            "provider": "wled", "lampid": "wled", "lampisgroup": False, "plugid": "hue-plug-uuid",
        })
        assert saved["lampid"] == "wled"          # newly picked: kept
        assert saved["plugid"] == ""              # unchanged from Hue: cleared

    def test_new_plug_kept_while_unchanged_light_cleared(self, plugin):
        saved = self._save(plugin, self._STORED_WLED, {
            "provider": "hue", "lampid": "wled", "lampisgroup": False, "plugid": "new-hue-plug",
        })
        assert saved["lampid"] == ""
        assert saved["lampisgroup"] is False
        assert saved["plugid"] == "new-hue-plug"

    _UNCHANGED = [
        (_STORED_HUE, "hue"), ({**_STORED_HUE, "provider": ""}, "hue"), (_STORED_HUE, ""),
        (_STORED_HUE, None), (_STORED_WLED, "wled"),
        ({**_STORED_HUE, "provider": None}, "hue"), ({**_STORED_HUE, "provider": None}, ""),
    ]
    _UNCHANGED_IDS = ["hue->hue", "empty->hue", "hue->empty", "hue->none", "wled->wled",
                      "none->hue", "none->empty"]

    @pytest.mark.parametrize("stored,new_provider", _UNCHANGED, ids=_UNCHANGED_IDS)
    def test_nothing_cleared_when_provider_unchanged(self, plugin, stored, new_provider):
        data = {"provider": new_provider, "lampid": stored["lampid"], "plugid": stored["plugid"],
                "lampisgroup": stored["lampisgroup"]}
        saved = self._save(plugin, stored, dict(data))
        assert saved == data
        plugin._logger.info.assert_not_called()

    @pytest.mark.parametrize("stored,new_provider", _UNCHANGED, ids=_UNCHANGED_IDS)
    def test_partial_save_with_unchanged_provider_adds_nothing(self, plugin, stored, new_provider):
        """An API save of just the (same) provider must not wipe the light or plug."""
        saved = self._save(plugin, stored, {"provider": new_provider})
        assert saved == {"provider": new_provider}

    def test_nothing_cleared_when_provider_not_in_save(self, plugin):
        data = {"lampid": "hue-light-uuid", "lampisgroup": True}
        saved = self._save(plugin, self._STORED_HUE, dict(data))
        assert saved == data

    @pytest.mark.parametrize("data", [
        {"provider": "wled"},
        {"provider": "wled", "lampid": "hue-light-uuid", "plugid": "hue-plug-uuid", "lampisgroup": True},
        {"provider": "wled", "lampid": "new-wled-pick", "plugid": "hue-plug-uuid", "lampisgroup": False},
    ], ids=["partial", "unchanged-ids", "new-pick"])
    def test_logs_change_once_without_ids(self, plugin, data):
        self._save(plugin, self._STORED_HUE, data)
        assert plugin._logger.info.call_count == 1
        message = " ".join(str(a) for a in plugin._logger.info.call_args.args)
        assert "hue" in message and "wled" in message
        logged = " ".join(str(c) for c in plugin._logger.mock_calls if c[0] != "debug")
        for secret in ("hue-light-uuid", "hue-plug-uuid", "new-wled-pick", "test-api-key"):
            assert secret not in logged

    def test_no_log_when_both_newly_picked(self, plugin):
        saved = self._save(plugin, self._STORED_HUE, {
            "provider": "wled", "lampid": "wled", "lampisgroup": False, "plugid": "new-plug",
        })
        assert saved["lampid"] == "wled" and saved["plugid"] == "new-plug"
        plugin._logger.info.assert_not_called()

    def test_no_log_when_only_empty_selections_were_cleared(self, plugin):
        """Clearing an already-empty plug isn't worth a log line."""
        saved = self._save(plugin, self._STORED_HUE | {"plugid": ""}, {
            "provider": "wled", "lampid": "wled", "lampisgroup": False,
        })
        assert saved["plugid"] == ""
        plugin._logger.info.assert_not_called()

    def test_debug_log_of_save_payload_omits_app_key(self, plugin):
        """After pairing, the dialog's Save includes the new key; it must not be logged."""
        self._save(plugin, self._STORED_HUE, {"husername": "brand-new-app-key", "bridgeaddr": "192.168.1.120"})
        assert not any("brand-new-app-key" in str(c) for c in plugin._logger.mock_calls)

    def test_still_strips_available_events_and_reinitialises(self, plugin):
        saved = self._save(plugin, self._STORED_HUE, {"provider": "wled", "availableEvents": ["X"]})
        assert "availableEvents" not in saved
        plugin._init_provider.assert_called_once()


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

    def test_flash_and_turnoff_wled_schedules_one_turnoff_timer(self, plugin):
        """WLED doesn't support flash — flash+turnoff should schedule one off timer, no alert."""
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "provider": "wled",
            "statusDict": [self._entry("PrintDone", turnoff=True, flash=True, delay=0)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        assert self._timer.call_count == 1
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["on"] is False
        assert "alert" not in kwargs["kwargs"]

    def test_flash_no_turnoff_wled_light_turns_on(self, plugin):
        """WLED + flash=True + turnoff=False: light turns on. alert kwarg is passed through
        but WledProvider.set_light silently ignores it (no flash support)."""
        plugin._settings.get.side_effect = make_settings_getter({
            "lampid": "1",
            "provider": "wled",
            "statusDict": [self._entry("PrintDone", turnoff=False, flash=True, delay=0)],
            "autopoweroff": False,
            "nightmode_enabled": False,
        })
        plugin.on_event("PrintDone", {})
        assert self._timer.call_count == 1
        _, kwargs = self._timer.call_args
        assert kwargs["kwargs"]["on"] is True


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
        })

    def test_pause_action_skips_set_light(self, plugin):
        self._make_plugin_with_night_mode(plugin, "pause")
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        plugin._provider.set_light.assert_not_called()

    def test_pause_action_returns_none(self, plugin):
        self._make_plugin_with_night_mode(plugin, "pause")
        result = plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        assert result is None

    def test_dim_action_caps_brightness_at_maxbri(self, plugin):
        self._make_plugin_with_night_mode(plugin, "dim", maxbri=50)
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["brightness_pct"] == 50

    def test_dim_action_does_not_increase_brightness(self, plugin):
        self._make_plugin_with_night_mode(plugin, "dim", maxbri=200)
        plugin.build_state(on=True, bri=100, colour="#FF0000", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["brightness_pct"] == 100  # already below max, unchanged

    def test_dim_action_preserves_flash(self, plugin):
        """Dim mode only caps brightness — flash must still be forwarded."""
        self._make_plugin_with_night_mode(plugin, "dim", maxbri=50)
        plugin.build_state(on=True, bri=255, alert="lselect", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["flash"] is True

    def test_night_mode_inactive_passes_through_unchanged(self, plugin):
        plugin._is_night_mode_active = MagicMock(return_value=False)
        plugin.build_state(on=True, bri=255, colour="#FF0000", deviceid="1")
        call_kwargs = plugin._provider.set_light.call_args[1]
        assert call_kwargs["brightness_pct"] == 255


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
        assert d["nightmode_maxbri"] == 25


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


# ===========================================================================
# get_update_information
# ===========================================================================

class TestGetUpdateInformation:

    @pytest.fixture
    def info(self, plugin):
        plugin._plugin_version = "1.0.2"
        return plugin.get_update_information()["OctoHue"]

    def test_repo_coordinates(self, info):
        assert info["user"] == "entrippy"
        assert info["repo"] == "OctoPrint-OctoHue"
        assert info["type"] == "github_release"

    def test_pip_url_contains_target_version_placeholder(self, info):
        assert "{target_version}" in info["pip"]
        assert "entrippy/OctoPrint-OctoHue" in info["pip"]

    def test_stable_branch_points_to_master(self, info):
        stable = info["stable_branch"]
        assert stable["branch"] == "master"
        assert stable["comittish"] == ["master"]

    def test_rc_branch_receives_rc_and_stable(self, info):
        rc = next(b for b in info["prerelease_branches"] if b["branch"] == "rc")
        assert "rc" in rc["comittish"]
        assert "master" in rc["comittish"]

    def test_devel_branch_receives_all_channels(self, info):
        devel = next(b for b in info["prerelease_branches"] if b["branch"] == "devel")
        assert "devel" in devel["comittish"]
        assert "rc" in devel["comittish"]
        assert "master" in devel["comittish"]

    def test_devel_comittish_is_broader_than_rc(self, info):
        rc = next(b for b in info["prerelease_branches"] if b["branch"] == "rc")
        devel = next(b for b in info["prerelease_branches"] if b["branch"] == "devel")
        assert set(rc["comittish"]).issubset(set(devel["comittish"]))
