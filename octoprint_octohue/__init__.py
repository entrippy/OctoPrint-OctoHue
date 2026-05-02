from __future__ import annotations

import octoprint.plugin
from datetime import datetime
import flask
from octoprint.util import ResettableTimer
from octoprint.access.permissions import Permissions

from octoprint_octohue.providers import PROVIDERS
from octoprint_octohue.providers.base import LightProvider


class OctohuePlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.SettingsPlugin,
					octoprint.plugin.SimpleApiPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.EventHandlerPlugin):

	_provider: LightProvider | None = None

	def _is_night_mode_active(self):
		'''
		Returns True if night mode is enabled and the current time falls within the
		configured window. Handles overnight spans (e.g. 22:00–07:00). Returns False
		if night mode is disabled or if the configured times cannot be parsed.
		'''
		if not self._settings.get(['nightmode_enabled']):
			return False
		try:
			now = datetime.now().time()
			start = datetime.strptime(self._settings.get(['nightmode_start']), '%H:%M').time()
			end = datetime.strptime(self._settings.get(['nightmode_end']), '%H:%M').time()
			if start <= end:
				return start <= now < end
			else:  # overnight span e.g. 22:00 - 07:00
				return now >= start or now < end
		except (ValueError, TypeError):
			self._logger.warning("Night mode times could not be parsed — night mode skipped.")
			return False

	def _init_provider(self):
		'''
		Instantiates the configured provider and calls setup() with the current
		settings. Falls back to Hue if the configured provider name is unknown.
		Called on startup and on every settings save.
		'''
		name = self._settings.get(['provider']) or 'hue'
		cls = PROVIDERS.get(name)
		if cls is None:
			self._logger.error(f"Unknown provider '{name}', falling back to Hue")
			cls = PROVIDERS['hue']
		self._provider = cls(self._logger)
		self._provider.setup(self._build_provider_settings(name))

	def _build_provider_settings(self, name: str) -> dict:
		'''
		Returns the settings dict for the named provider, reading from the
		plugin's settings store. Each provider documents which keys it expects.
		'''
		if name == 'hue':
			return {
				'bridgeaddr': self._settings.get(['bridgeaddr']),
				'husername': self._settings.get(['husername']),
				'lampid': self._settings.get(['lampid']),
				'lampisgroup': self._settings.get(['lampisgroup']),
				'plugid': self._settings.get(['plugid']),
			}
		if name == 'wled':
			# bridgeaddr is the generic controller-address field shared across providers
			return {
				'bridgeaddr': self._settings.get(['bridgeaddr']),
			}
		return {}

	def establishBridge(self, bridgeaddr, husername):
		'''
		Re-initialises the provider using the supplied Hue bridge credentials.
		Kept as a named method so that on_after_startup and on_settings_save
		can call it with explicit addr/key arguments, and tests can mock it.
		Creates the provider instance if it does not yet exist.
		'''
		if self._provider is None:
			self._init_provider()
		assert self._provider is not None
		name = self._settings.get(['provider']) or 'hue'
		settings = self._build_provider_settings(name)
		settings.update({'bridgeaddr': bridgeaddr, 'husername': husername})
		self._provider.setup(settings)

	def build_state(self, **kwargs):
		'''
		Night-mode-aware wrapper that translates old-style kwargs into a
		provider set_light() call.

			Keyword Args:
				on (bool): True to turn the light on, False to turn it off.
				bri (int): Brightness, 1–100%.
				colour (str): '#RRGGBB' hex string. Mutually exclusive with ct.
				ct (int): Colour temperature in mirek (153–500).
				deviceid (str): Provider-specific device identifier.
				alert (str): Pass 'lselect' to trigger a flash cycle.
				transitiontime (int): Transition in units of 100 ms.

		Night mode:
			If night mode is active and the action is 'pause', returns immediately
			without changing the lights. If the action is 'dim', brightness is
			capped at nightmode_maxbri before the state is sent.
		'''
		self._logger.debug(f"Build_state Called with: {kwargs}")

		if self._is_night_mode_active():
			action = self._settings.get(['nightmode_action'])
			if action == 'pause':
				self._logger.info("Night mode active — skipping light change.")
				return
			elif action == 'dim' and 'bri' in kwargs:
				maxbri = int(self._settings.get(['nightmode_maxbri']) or 64)
				kwargs['bri'] = min(kwargs['bri'], maxbri)
				self._logger.debug(f"Night mode active — brightness capped at {maxbri}.")

		on = kwargs['on']
		deviceid = kwargs.get('deviceid')
		brightness_pct = kwargs.get('bri')
		colour_hex = kwargs.get('colour') if on else None
		ct_mirek = int(kwargs.get('ct') or 0) or None
		flash = kwargs.get('alert') == 'lselect'
		raw_transition = int(kwargs.get('transitiontime') or 0)
		transition_ms = (raw_transition * 100) or None

		if self._provider is not None:
			self._provider.set_light(
				on=on,
				deviceid=deviceid,
				colour_hex=colour_hex,
				ct_mirek=ct_mirek,
				brightness_pct=brightness_pct,
				flash=flash,
				transition_ms=transition_ms,
			)

	def toggle_state(self, deviceid=None):
		'''
		Flips the on/off state of a device. When turning on, lamps use the
		configured toggle colour/CT and brightness; plugs (plugid) are switched
		on without a brightness or colour argument.

			Parameters:
				deviceid (str, optional): UUID of the device to toggle.
				                          Defaults to the configured lampid.
		'''
		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		if self._provider is not None and self._provider.get_state(deviceid):
			self.build_state(on=False, deviceid=deviceid)
		else:
			if deviceid != self._settings.get(['plugid']):
				ct = int(self._settings.get(['togglect']) or 0)
				bri = int(self._settings.get(['togglebri']) or self._settings.get(['defaultbri']))
				if ct:
					self.build_state(on=True, ct=ct, bri=bri, deviceid=deviceid)
				else:
					colour = self._settings.get(['togglecolour']) or None
					self.build_state(on=True, colour=colour, bri=bri, deviceid=deviceid)
			else:
				self.build_state(on=True, deviceid=deviceid)

	def get_configured_events(self):
		'''
		Returns a list of OctoPrint event names that have an entry in statusDict.

			Returns:
				list[str]: Event names the user has configured a light response for.
		'''
		configured_events = [sub['event'] for sub in self._settings.get(['statusDict'])]
		return configured_events

	def on_after_startup(self):
		'''
		OctoPrint startup hook. Establishes the provider connection and, if
		"Lights On at Startup" is configured, triggers the corresponding statusDict
		light state.
		'''
		self._logger.info("Octohue is alive!")
		self._init_provider()
		if self._settings.get(['ononstartup']):
			my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == self._settings.get(['ononstartupevent'])), None)
			if my_statusEvent:
				ct = int(my_statusEvent.get('ct') or 0)
				if ct:
					self.build_state(on=True, ct=ct, bri=int(my_statusEvent['brightness']), deviceid=self._settings.get(['lampid']))
				else:
					self.build_state(on=True, colour=my_statusEvent['colour'], bri=int(my_statusEvent['brightness']), deviceid=self._settings.get(['lampid']))

	def on_shutdown(self):
		'''
		OctoPrint shutdown hook. Turns off the configured lamp if offonshutdown
		is True. Bypasses night mode — we always want the light off on shutdown.
		'''
		self._logger.info("Ladies and Gentlemen, thank you and goodnight!")
		if self._settings.get(['offonshutdown']) and self._provider is not None:
			self._provider.set_light(on=False)

	def printer_start_power_down(self):
		'''
		Begins the temperature-monitored power-down sequence. Schedules
		printer_check_temp_power_down to run after the configured powerofftime delay.
		'''
		delay = self._settings.get(['powerofftime']) or 0
		delayedtask = ResettableTimer(delay, self.printer_check_temp_power_down)
		delayedtask.start()

	def printer_check_temp_power_down(self):
		'''
		Check if minimum temperature for shutdown is reached if defined.
		Shutdown if below temp or not defined. Reschedules itself every 30 s
		until the temperature condition is met rather than blocking in a loop.
		'''
		deviceid = self._settings.get(['plugid'])
		target_temp = int(self._settings.get(['powerofftemp']) or 0)
		temps = self._printer.get_current_temperatures()
		tool_temps = [int(v['actual']) for k, v in temps.items() if k.startswith('tool')]
		if not tool_temps:
			self._logger.warning("No extruder temperatures available — skipping cooldown check.")
			return
		current_temp = max(tool_temps)
		self._logger.debug(f"Safe Shutdown Requested! Tool Temp: {current_temp}, Looking for Safe Cooldown Temp: {target_temp}")
		if current_temp <= target_temp or current_temp <= 40:
			self._logger.debug(f"Safe Cooldown reached {current_temp}, shutting down.")
			self.build_state(on=False, deviceid=deviceid)
		else:
			self._logger.debug(f"Current temperature: {current_temp}, waiting 30 seconds...")
			ResettableTimer(30.0, self.printer_check_temp_power_down).start()

	def is_api_protected(self):
		# Commands that need admin access perform their own Permissions.ADMIN.can()
		# check inside on_api_command. Returning False here keeps the API open
		# for unauthenticated callers (e.g. togglehue/turnon/turnoff/cooldown)
		# and suppresses OctoPrint's deprecation warning about plugins that don't
		# explicitly declare their API protection preference.
		return False

	def get_api_commands(self):
		'''
		Declares the SimpleApi commands this plugin exposes.
		Required by OctoPrint's SimpleApiPlugin mixin.
		'''
		return dict(
			bridge=[],
			getdevices=[],
			getgroups=[],
			togglehue=[],
			getstate=[],
			turnon=[],
			turnoff=[],
			cooldown=[]
		)

	def on_api_command(self, command, data):
		'''
		Handles SimpleApi commands dispatched by OctoPrint.

			Commands:
				bridge     (admin) getstatus / discover / pair sub-commands.
				getdevices (admin) Returns lights, optionally filtered by archetype.
				getgroups  (admin) Returns rooms and zones as named group entries.
				getstate   (admin) Returns the current on/off state of the configured lamp.
				togglehue  Toggles the lamp (or a specific device) between on and off.
				turnon     Turns a device on, optionally applying a colour hex value.
				turnoff    Turns a device off.
				cooldown   Triggers the temperature-monitored power-down sequence.
		'''
		self._logger.debug(f"Recieved API Command: {command}")

		if command == 'bridge':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)

			if "getstatus" in data:
				bridge = self._settings.get(['bridgeaddr'])
				apikey = self._settings.get(['husername'])
				if bridge and apikey:
					return flask.jsonify(bridgestatus="configured")
				elif bridge and not apikey:
					return flask.jsonify(bridgestatus="unauthed")
				else:
					return flask.jsonify(bridgestatus="unconfigured")

			elif "discover" in data:
				discovered = self._provider.discover() if self._provider is not None else []
				self._logger.debug(discovered)
				return flask.jsonify(discovered)

			elif "pair" in data:
				result = self._provider.pair(bridgeaddr=data['bridgeaddr']) if self._provider is not None else {"response": "error"}
				if result.get('response') == 'success':
					self._settings.set(['husername'], result['husername'])
					self._settings.set(['bridgeaddr'], result['bridgeaddr'])
					self._settings.save()
					self.establishBridge(result['bridgeaddr'], result['husername'])
					return flask.jsonify([result])
				else:
					return flask.jsonify([result])

			else:
				return flask.jsonify(status="ok")

		elif command == 'getdevices':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)
			if not self._provider or not self._provider.is_ready:
				return flask.jsonify(devices=[])
			self._logger.debug("Getting Devices")
			all_lights = self._provider.get_lights()
			if 'archetype' in data:
				self._logger.debug(f"Archetype: {data['archetype']}")
				devices = [d for d in all_lights if d.get('archetype') == data['archetype']]
			else:
				devices = all_lights
			return flask.jsonify(devices=devices)

		elif command == 'getgroups':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)
			if not self._provider or not self._provider.is_ready:
				return flask.jsonify(groups=[])
			self._logger.debug("Getting Groups")
			groups = self._provider.get_groups()
			return flask.jsonify(groups=groups)

		elif command == 'togglehue':
			self._logger.debug(f"Toggling Hue for {data}")
			if 'deviceid' in data:
				self.toggle_state(data['deviceid'])
			else:
				self.toggle_state(self._settings.get(['lampid']))

		elif command == 'getstate':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)
			if self._provider is not None and self._provider.get_state():
				return flask.jsonify(on="true")
			else:
				return flask.jsonify(on="false")

		elif command == 'turnon':
			deviceid = data.get('deviceid') or self._settings.get(['lampid'])
			if "colour" in data:
				self.build_state(on=True, colour=data['colour'], bri=int(self._settings.get(['defaultbri'])), deviceid=deviceid)
			else:
				self.build_state(on=True, bri=int(self._settings.get(['defaultbri'])), deviceid=deviceid)

		elif command == 'turnoff':
			deviceid = data.get('deviceid') or self._settings.get(['lampid'])
			self.build_state(on=False, deviceid=deviceid)

		elif command == 'cooldown':
			self.printer_check_temp_power_down()

	def on_event(self, event, payload):
		'''
		OctoPrint event hook. If the event matches a configured statusDict entry,
		schedules the appropriate light change (on/off/flash) after the configured
		delay. Also triggers auto power-off if enabled and the event is PrintDone.
		'''
		self._logger.debug(f"Recieved Status: {event} from Printer")
		my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == event), None)
		if my_statusEvent:
			self._logger.info(f"Received Configured Status Event: {event}")
			delay = my_statusEvent.get('delay') or 0
			deviceid = self._settings.get(['lampid'])

			flash = my_statusEvent.get('flash', False)
			turnoff = my_statusEvent['turnoff']
			ct = int(my_statusEvent.get('ct') or 0)

			if turnoff and flash:
				# Flash first, then switch off after the alert cycle completes
				flash_kwargs = {'on': True, 'bri': int(my_statusEvent['brightness']), 'alert': 'lselect', 'deviceid': deviceid}
				if ct:
					flash_kwargs['ct'] = ct
				else:
					flash_kwargs['colour'] = my_statusEvent['colour']
				delayedtask = ResettableTimer(delay, self.build_state, kwargs=flash_kwargs)
				ResettableTimer(delay + 15, self.build_state, kwargs={'on': False, 'deviceid': deviceid}).start()
			elif not turnoff:
				brightness = my_statusEvent['brightness']
				build_kwargs = {'on': True, 'bri': int(brightness), 'deviceid': deviceid}
				if ct:
					build_kwargs['ct'] = ct
				else:
					build_kwargs['colour'] = my_statusEvent['colour']
				if flash:
					build_kwargs['alert'] = 'lselect'
				delayedtask = ResettableTimer(delay, self.build_state, kwargs=build_kwargs)
			else:
				delayedtask = ResettableTimer(delay, self.build_state, kwargs={'on': False, 'deviceid': deviceid})

			try:
				delayedtask.start()
			except Exception as e:
				self._logger.error(f"Error starting delayed task: {e}")

		if self._settings.get(['autopoweroff']) and event == 'PrintDone':
			self.printer_start_power_down()

	def get_settings_defaults(self):
		'''
		Returns the default values for all plugin settings.
		Required by OctoPrint's SettingsPlugin mixin.
		'''
		return dict(
			enabled=True,
			installed_version=self._plugin_version,
			provider='hue',
			bridgeaddr="",
			husername="",
			lampid="",
			plugid="",
			lampisgroup=False,
			defaultbri=100,
			togglebri=100,
			togglecolour='#FFFFFF',
			togglect=0,
			ononstartup=False,
			ononstartupevent="",
			offonshutdown=True,
			showhuetoggle=True,
			showpowertoggle=False,
			autopoweroff=False,
			powerofftime=0,
			powerofftemp=0,
			nightmode_enabled=False,
			nightmode_start="22:00",
			nightmode_end="07:00",
			nightmode_action="pause",
			nightmode_maxbri=25,
			statusDict=[]
		)

	def get_settings_restricted_paths(self):
		'''
		Restricts bridgeaddr and husername to admin users in OctoPrint's settings API.
		Required by OctoPrint's SettingsPlugin mixin.
		'''
		return dict(admin=[["bridgeaddr"], ["husername"]])

	def get_settings_version(self):
		'''
		Returns the current settings schema version. OctoPrint uses this to detect
		when on_settings_migrate needs to be called.
		'''
		return 5

	def on_settings_migrate(self, target, current=None):
		'''
		Migrates settings from an older schema version.

		current=None (first install): writes example statusDict entries.
		current<2  (v1→v2): clears lampid/plugid — Hue v2 uses UUIDs, not integer IDs.
		current<3  (v2→v3): converts all brightness values from 1–255 scale to
		                     0–100 percentage scale used by the Hue v2 API.
		current<4  (v3→v4): seeds toggle colour/brightness/CT settings.
		current<5  (v4→v5): sets provider to 'hue' for existing installs.

		Cascading if-blocks (not elif) ensure users upgrading across multiple
		versions in one step receive all intermediate migrations.
		'''
		if current is None:
			self._logger.info("Migrating Settings: Writing example settings")
			self._settings.set(["statusDict"], [
					{'event': 'Connected',
					'colour':'#FFFFFF',
					'brightness':100,
					'delay':0,
					'turnoff':False, 'flash': False, 'ct': 0},
					{'event': 'Disconnected',
					'colour':'',
					'brightness':"",
					'delay':0,
					'turnoff':True, 'flash': False, 'ct': 0},
					{'event': 'PrintStarted',
					'colour':'#FFFFFF',
					'brightness':100,
					'delay':0,
					'turnoff':False, 'flash': False, 'ct': 0},
					{'event': 'PrintResumed',
					'colour':'#FFFFFF',
					'brightness':100,
					'delay':0,
					'turnoff':False, 'flash': False, 'ct': 0},
					{'event': 'PrintDone',
					'colour':'#33FF36',
					'brightness':100,
					'delay':0,
					'turnoff':False, 'flash': False, 'ct': 0},
					{'event': 'PrintFailed',
					'colour':'#FF0000',
					'brightness':100,
					'delay':0,
					'turnoff':False, 'flash': False, 'ct': 0}
				])
			self._settings.save()
			return

		if current < 2:
			self._logger.info("Migrating Settings v1→v2: clearing device IDs (Hue v2 uses UUIDs, not integer IDs)")
			self._settings.set(['lampid'], '')
			self._settings.set(['plugid'], '')

		if current < 3:
			self._logger.info("Migrating Settings v2→v3: converting brightness values from 1–255 to 0–100 percentage scale")

			def to_pct(value):
				try:
					return min(round(int(value) / 255 * 100), 100)
				except (ValueError, TypeError):
					return value

			old_bri = self._settings.get(['defaultbri'])
			self._settings.set(['defaultbri'], to_pct(old_bri))

			old_maxbri = self._settings.get(['nightmode_maxbri'])
			self._settings.set(['nightmode_maxbri'], to_pct(old_maxbri))

			status_dict = self._settings.get(['statusDict'])
			for entry in status_dict:
				entry['brightness'] = to_pct(entry.get('brightness'))
			self._settings.set(['statusDict'], status_dict)

		if current < 4:
			self._logger.info("Migrating Settings v3→v4: adding toggle colour/brightness settings")
			self._settings.set(['togglebri'], self._settings.get(['defaultbri']))
			self._settings.set(['togglecolour'], '#FFFFFF')
			self._settings.set(['togglect'], 0)

		if current < 5:
			self._logger.info("Migrating Settings v4→v5: setting provider to 'hue' for existing installs")
			self._settings.set(['provider'], 'hue')

		self._settings.save()

	def on_settings_load(self):
		'''
		Returns all plugin settings to the frontend, supplemented with the list of
		available OctoPrint events and the pre-computed list of configured event names.
		'''
		my_settings = {
			"availableEvents": octoprint.events.all_events(),
			"statusDict": self._settings.get(["statusDict"]),
			"bridgeaddr": self._settings.get(["bridgeaddr"]),
			"husername": self._settings.get(["husername"]),
			"lampid": self._settings.get(["lampid"]),
			"plugid": self._settings.get(["plugid"]),
			"lampisgroup": self._settings.get(["lampisgroup"]),
			"defaultbri": self._settings.get(["defaultbri"]),
			"togglebri": self._settings.get(["togglebri"]),
			"togglecolour": self._settings.get(["togglecolour"]),
			"togglect": self._settings.get(["togglect"]),
			"ononstartup": self._settings.get(["ononstartup"]),
			"configuredEvents": self.get_configured_events(),
			"ononstartupevent": self._settings.get(["ononstartupevent"]),
			"offonshutdown": self._settings.get(["offonshutdown"]),
			"showhuetoggle": self._settings.get(["showhuetoggle"]),
			"showpowertoggle": self._settings.get(["showpowertoggle"]),
			"autopoweroff": self._settings.get(["autopoweroff"]),
			"powerofftime": self._settings.get(["powerofftime"]),
			"powerofftemp": self._settings.get(["powerofftemp"]),
			"nightmode_enabled": self._settings.get(["nightmode_enabled"]),
			"nightmode_start": self._settings.get(["nightmode_start"]),
			"nightmode_end": self._settings.get(["nightmode_end"]),
			"nightmode_action": self._settings.get(["nightmode_action"]),
			"nightmode_maxbri": self._settings.get(["nightmode_maxbri"]),
			"provider": self._settings.get(["provider"]),
		}
		return my_settings

	def on_settings_save(self, data):
		'''
		Persists settings and re-initialises the provider with any updated
		credentials. Strips availableEvents (frontend-only) before passing to
		the base class.
		'''
		data.pop("availableEvents", None)
		self._logger.debug(f"Saving: {data} to settings")
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self._init_provider()

	def get_template_vars(self):
		'''
		Exposes settings values to the Jinja2 settings template at render time.
		Required by OctoPrint's TemplatePlugin mixin.
		'''
		return dict(
			version=self._plugin_version,
			bridgeaddr=self._settings.get(["bridgeaddr"]),
			husername=self._settings.get(["husername"]),
			lampid=self._settings.get(["lampid"]),
			lampisgroup=self._settings.get(["lampisgroup"]),
			defaultbri=self._settings.get(["defaultbri"]),
			offonshutdown=self._settings.get(["offonshutdown"]),
			ononstartup=self._settings.get(['ononstartup']),
			ononstartupevent=self._settings.get(['ononstartupevent']),
			showhuetoggle=self._settings.get(["showhuetoggle"]),
			statusDict=self._settings.get(["statusDict"])
		)

	def is_template_autoescaped(self):
		return True

	def get_template_configs(self):
		'''
		Declares a custom-bound settings panel.
		Required by OctoPrint's TemplatePlugin mixin.
		'''
		return [
			dict(type="settings", custom_bindings=True)
		]

	def get_assets(self):
		'''
		Declares the JS, CSS, and Less assets to include in the OctoPrint UI.
		Required by OctoPrint's AssetPlugin mixin.
		'''
		return dict(
			js=["js/OctoHue.js"],
			css=["css/OctoHue.css"],
			less=["less/OctoHue.less"]
		)

	def get_update_information(self):
		'''
		Provides configuration for OctoPrint's Software Update plugin to check
		for new releases on GitHub and install them via pip.
		'''
		return dict(
			OctoHue=dict(
				displayName="Octohue Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="entrippy",
				repo="OctoPrint-OctoHue",
				current=self._plugin_version,

				stable_branch=dict(
					name="Stable",
					branch="master",
					comittish=["master"]
				),
				prerelease_branches=[
					dict(
						name="Release Candidate",
						branch="rc",
						comittish=["rc", "master"]
					),
					dict(
						name="Development",
						branch="devel",
						comittish=["devel", "rc", "master"]
					),
				],

				# update method: pip
				pip="https://github.com/entrippy/OctoPrint-OctoHue/archive/{target_version}.zip"
			)
		)


__plugin_name__ = "Octohue"
__plugin_pythoncompat__ = ">=3.9,<4"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = OctohuePlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
