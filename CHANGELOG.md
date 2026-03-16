# OctoPrint-OctoHue Changelog

All notable changes to this project will be documented in this file.

## [0.7.0] - Unreleased

### Added
- Smart plug / power socket control — configure a separate Hue plug device to cut power to the printer after it cools down
- Auto power-off — automatically switch off the plug once all extruders drop below a configurable temperature (or 40 °C) after a print completes
- In-plugin bridge discovery and pairing UI — click Discover to find your bridge on the network, then press the bridge button and click Pair to generate an API key without ever leaving OctoPrint settings
- `cooldown` API command — manually trigger the temperature-monitored power-down sequence
- `togglehue` API command now accepts an optional `deviceid` parameter to target a specific device

### Changed
- Replaced numpy-based RGB→XY colour conversion with a dependency-free implementation — numpy is no longer required
- Minimum Python version raised to 3.6 (f-strings were already in use; the declared `>=2.7` compatibility was incorrect)
- `printer_check_temp_power_down` now polls on a 30-second timer rather than blocking a thread in a `while True` loop
- Temperature cooldown check now considers all extruder tools, not just `tool0`
- `on_settings_save` now calls `establishBridge()` consistently rather than duplicating bridge initialisation logic
- `getstatus` bridge check simplified and now always returns a response (previously could return `None` if bridge was set but API key was empty)

### Fixed
- `set_state` was using `get['plugid']` (subscript syntax) instead of `get(['plugid'])`, causing a `TypeError`
- `turnon` and `turnoff` API commands referenced an undeclared `deviceid` variable
- `turnon` had a misplaced parenthesis that caused `deviceid` to be passed as an argument to `int()` instead of `build_state()`
- `printer_start_power_down` was calling `ResettableTimer(delay, self.printer_check_temp_power_down(self))`, invoking the function immediately and passing its return value instead of the function itself
- `rgb_to_xy` could divide by zero for black (`#000000`); now returns `None` and the caller skips the colour change
- `pbridge` initialised to empty string instead of `None`, causing `_bridge_ready()` checks to pass incorrectly before the bridge was configured
- `get_state` and `set_state` stored result as `self._state` instance variable rather than returning it directly
- Settings defaults for `lampisgroup`, `powerofftime`, and `powerofftemp` were empty strings instead of `False`/`0`

### Removed
- `numpy` dependency (replaced with built-in arithmetic)
- Accidental `PrinterInterface` inheritance — the plugin uses a printer, it doesn't implement one

---

## [0.6.0]

### Added
- `getstate` API command — returns `{"on": true|false}` representing the current light state
- `turnon` API command — turns the light on; accepts an optional `colour` hex parameter
- `turnoff` API command — turns the light off

---

## [0.5.0]

### Added
- Option to trigger a configured light event when OctoPrint starts up

---

## [0.4.4]

### Fixed
- Fixed bug preventing changes to the initial example configuration from being saved
- Changed `statusDict` storage from a dict-of-dicts to a list-of-dicts, resolving persistent settings corruption
- Moved from the term "status" to "event" in line with OctoPrint terminology
- New event add modal with an "Event" dropdown populated from native OctoPrint events

> **Note:** It is recommended that you remove your existing OctoHue settings, or at minimum remove `statusDict` from `config.yaml` before upgrading from an earlier version.

---

## [0.4.3]

### Changed
- Renamed `rgb()` to `build_state()` to better describe its function

### Fixed
- Brightness was not being passed correctly to `build_state`, causing it to always default to 255
- Bridge object was not reinitialised on settings save, requiring a restart to pick up bridge and username changes
- Default brightness now correctly applies when brightness is not defined for a particular event

---

## [0.4.2]

### Added
- Optional navbar icon to toggle lights on/off
- Reworked settings UI with user-configurable events and colour/brightness/state configuration
- Option to turn lights off as an action for printer events
- Customisable default brightness
