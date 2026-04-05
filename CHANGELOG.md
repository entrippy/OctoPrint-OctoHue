# OctoPrint-OctoHue Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-04-05

### Fixed
- `signify-root-ca.pem` was missing from the installed package — `MANIFEST.in` did not include `*.pem` files, so the Signify root CA certificate was not shipped. This caused a `FileNotFoundError` on first use, leaving `self._session` uninitialised and causing all subsequent API calls to fail with `'NoneType' object has no attribute 'request'`. Closes #62.

---

## [1.0.0] - 2026-04-05

### Changed
- **Breaking:** Migrated from the deprecated Hue v1 CLIP API (end-of-life 2024) to the Hue v2 CLIP API — all communication now uses HTTPS with TLS chain verification against the bundled Signify root CA certificate
- **Breaking:** Lamp and group IDs are now UUID strings (v2 format); existing integer IDs from v1 are cleared automatically on first run — reselect your light or group in Settings → Lights after upgrading
- **Breaking:** Brightness values are now stored as percentages (0–100) instead of the old 1–255 scale — existing settings are migrated automatically on first run
- Groups are now fetched via the v2 `room`/`zone` resources; the previous v1 group endpoint is no longer used
- Lights and groups are combined into a single dropdown in the Lights tab — no more manual "Use group" checkbox; the type is detected automatically from your selection
- Removed `qhue` dependency — API calls are now made directly with `requests`
- Brightness inputs throughout the UI now use a 1–100% scale

### Added
- **Configurable toggle colour and brightness** — when the navbar Hue toggle button turns the light on, it now uses a dedicated colour, CT, and brightness configured in Settings → General, rather than always restoring the last state at default brightness
- **Guided bridge pairing flow** — after a successful pairing the Bridge tab shows a persistent success message and a "Select your light →" button; clicking it fetches your lights and switches directly to the Lights tab, no save/re-enter cycle required
- `getgroups` API command — returns all Hue rooms and zones as named group entries with their `grouped_light` UUIDs (admin only)

### Fixed
- Pairing timeout error path referenced an undefined variable (`pairing_bridge_button`) — would throw a `ReferenceError` when 30 pairing attempts were exhausted without success
- Brightness value of 255 (maximum on the old scale) sent as 100.39% to the v2 API, which rejected it with HTTP 400 (schema validation: maximum is 100)
- Power tab cooldown delay fields were wrapped in a `<tbody>` with no enclosing `<table>` — invalid HTML
- `statusDict` entries missing the `delay` key (created before delay was added in 0.7.0) would raise a `KeyError` when an event fired
- Temperature cooldown check would crash with `ValueError` if no extruder temperatures were available

### Security
- The SimpleAPI endpoint is intentionally left open (`is_api_protected = False`) to allow unauthenticated access to light-control commands (`togglehue`, `turnon`, `turnoff`, `cooldown`) — this is by design so the API can be used from external scripts and tools without requiring an OctoPrint session
- Sensitive commands (`bridge`, `getdevices`, `getgroups`, `getstate`) enforce admin-only access explicitly via `Permissions.ADMIN` checks regardless of the endpoint protection setting

### Upgrading from 0.x
1. After updating, open **Settings → Lights** and reselect your light or group from the dropdown — your previous integer ID is no longer valid with the v2 API
2. Brightness values in your event table have been automatically converted to percentages — review them to confirm they look correct
3. If you use the navbar toggle button, set your preferred toggle-on colour and brightness in **Settings → General**

---

## [0.9.0] - 2026-04-03

### Added
- Colour temperature (CT) mode for RGBCCT light support — each status event can now be toggled between RGB and CT mode. CT mode sends the `ct` parameter (153–500 mirek) to the Hue API, activating the white channel on RGBCCT lights instead of the RGB LEDs. Closes #53.
- Warm-to-cool gradient slider replaces the colour picker when CT mode is active — no numeric values needed, the gradient communicates the range visually.

### Changed
- Migrated from legacy `setup.py` / `octoprint_setuptools` to `pyproject.toml` — fixes installation failures with pip 25.3+ which enables build isolation by default
- Minimum Python version raised to 3.9 to match current OctoPrint requirements
- `Taskfile.yml` added for common development tasks (build, install, translations)

---

## [0.8.0] - 2026-04-03

### Added
- Flash/blink feature for status events — configure any event to trigger a 15-second Hue alert cycle (`lselect`), optionally followed by switching the light off
- Night mode — define an active time window during which light changes are either paused entirely or brightness is capped at a configurable maximum (1–255)
- Admin-only restriction on sensitive API endpoints (`bridge`, `getdevices`, `getstate`) — non-admin callers receive 403 Forbidden; light-control commands (`turnon`, `turnoff`, `togglehue`, `cooldown`) remain available to any authenticated user

### Fixed
- Flash observable not present on statusDict items saved before the flash feature was added — now normalised on load
- Plugin version not displaying in the settings header — wrong Jinja2 variable name and missing entry in `get_template_vars()`
- Malformed HTML on power settings tab div

### Improved
- Night mode time input boxes widened to prevent value truncation
- Default brightness input now shows a 1–255 range hint
- All plugin functions now have accurate docstrings
- Test suite expanded to 127 Python tests and 40 JS tests

---

## [0.7.0] - 2026-03-28

> It has been a while — apologies for the long gap since 0.6.0. This release brings a significant number of new features, bug fixes, and code quality improvements. Getting here was greatly helped by AI-assisted development, which made it possible to add a full test suite, catch long-standing bugs, and ship a much more solid release than would otherwise have been feasible.

### Added
- Smart plug / power socket control — configure a separate Hue plug device to cut power to the printer after it cools down
- Auto power-off — automatically switch off the plug once all extruders drop below a configurable temperature (or 40 °C) after a print completes
- In-plugin bridge discovery and pairing UI — click Discover to find your bridge on the network, then press the bridge button and click Pair to generate an API key without ever leaving OctoPrint settings
- `cooldown` API command — manually trigger the temperature-monitored power-down sequence
- `togglehue` API command now accepts an optional `deviceid` parameter to target a specific device
- "Lights On at Startup" feature — selecting a configured event in General settings now correctly triggers that light state when OctoPrint starts
- Full unit test suite covering Python plugin logic and the KnockoutJS viewmodel

### Changed
- Replaced numpy-based RGB→XY colour conversion with a dependency-free implementation — numpy is no longer required
- Minimum Python version raised to 3.6 (f-strings were already in use; the declared `>=2.7` compatibility was incorrect)
- `printer_check_temp_power_down` now polls on a 30-second timer rather than blocking a thread in a `while True` loop
- Temperature cooldown check now considers all extruder tools, not just `tool0`
- `on_settings_save` now calls `establishBridge()` consistently rather than duplicating bridge initialisation logic
- `getstatus` bridge check simplified and now always returns a response (previously could return `None` if bridge was set but API key was empty)
- Device dropdowns in settings now populate correctly — light and plug lists are fetched each time the settings panel opens rather than once at page load
- Status event table redesigned: colour picker and hex value combined into one column, consistent column widths, and clearer headings

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
