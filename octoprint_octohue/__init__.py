import octoprint.plugin
from datetime import datetime
import os
import ssl
import flask
import requests
from requests.adapters import HTTPAdapter
from octoprint.util import ResettableTimer
from octoprint.access.permissions import Permissions

# ---------------------------------------------------------------------------
# Custom HTTPS adapter that verifies the Hue bridge certificate chain against
# the bundled Signify root CA, but skips hostname verification.
#
# Hostname verification cannot succeed because the bridge certificate uses
# the bridge serial number as its CN/SAN, not the IP address.  Verifying the
# chain is still a meaningful improvement over verify=False: it confirms the
# certificate was issued by Signify rather than by an arbitrary attacker.
# ---------------------------------------------------------------------------
_CA_BUNDLE = os.path.join(os.path.dirname(__file__), "signify-root-ca.pem")


class _SignifyAdapter(HTTPAdapter):
    """Mounts a custom SSLContext that checks the Signify CA chain."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=_CA_BUNDLE)
        ctx.check_hostname = False
        kwargs["ssl_context"] = ctx
        kwargs["assert_hostname"] = False
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        ctx = ssl.create_default_context(cafile=_CA_BUNDLE)
        ctx.check_hostname = False
        proxy_kwargs["ssl_context"] = ctx
        proxy_kwargs["assert_hostname"] = False
        return super().proxy_manager_for(proxy, **proxy_kwargs)


class OctohuePlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.SettingsPlugin,
					octoprint.plugin.SimpleApiPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.EventHandlerPlugin):


	pbridge = None
	_session = None
	discoveryurl = 'https://discovery.meethue.com/'

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

	def _bridge_ready(self):
		'''
		Returns True if the Hue bridge has been initialised, False otherwise.
		Logs a warning and returns False if pbridge is None.
		'''
		if self.pbridge is None:
			self._logger.warning("Hue bridge not yet initialised — skipping.")
			return False
		return True

	def _hue_request(self, method, path, payload=None):
		'''
		Sends an HTTPS request to the Hue v2 CLIP API using a session that
		verifies the certificate chain against the bundled Signify root CA.

			Parameters:
				method (str): HTTP method ('GET', 'PUT', etc.)
				path (str): Resource path relative to /clip/v2/resource/ (e.g. 'light/uuid').
				payload (dict, optional): JSON body for PUT requests.

			Returns:
				dict: Parsed JSON response, or an empty dict on error.
		'''
		url = f"https://{self.pbridge['addr']}/clip/v2/resource/{path}"
		headers = {"hue-application-key": self.pbridge['key']}
		self._logger.info(f"Hue API {method} {url}" + (f" payload={payload}" if payload else ""))
		try:
			r = self._session.request(method, url, headers=headers, json=payload)
			body = r.json()
			if r.status_code not in (200, 207):
				self._logger.warning(f"Hue API {method} {path} returned HTTP {r.status_code}: {body}")
			else:
				errors = body.get('errors', [])
				if errors:
					self._logger.warning(f"Hue API {method} {path} returned errors: {errors}")
			return body
		except Exception as e:
			self._logger.error(f"Hue API error ({method} {path}): {e}")
			return {}

	def establishBridge(self, bridgeaddr, husername):
		'''
		Stores the Hue bridge connection details. If both address and key are present,
		pbridge is set to a dict with 'addr' and 'key'; otherwise pbridge is set to None.
		Called on startup and whenever settings are saved with updated credentials.

			Parameters:
				bridgeaddr (str): IP address or hostname of the Hue bridge.
				husername (str): Hue API key (application key) for authentication.
		'''
		self._logger.debug(f"Bridge Address is {bridgeaddr if bridgeaddr else 'Please set Bridge Address in settings'}")
		self._logger.debug(f"Hue Username is {husername if husername else 'Please set Hue Username in settings'}")
		if bridgeaddr and husername:
			self.pbridge = {'addr': bridgeaddr, 'key': husername}
			session = requests.Session()
			session.mount("https://", _SignifyAdapter())
			self._session = session
			self._logger.debug(f"Bridge established at: {bridgeaddr}")
		else:
			self.pbridge = None
			self._session = None

	def rgb_to_xy(self, red: int, green: int = None, blue: int = None):
		'''
		Converts an RGB colour to CIE 1931 xy chromaticity coordinates for the Hue API.
		Accepts either three 8-bit integers or a single '#RRGGBB' hex string as red.

			Parameters:
				red (int | str): Red channel value (0–255), or a '#RRGGBB' hex string.
				green (int): Green channel value (0–255). Ignored when red is a hex string.
				blue (int): Blue channel value (0–255). Ignored when red is a hex string.

			Returns:
				list | None: [x, y] chromaticity coordinates, or None for black (#000000)
				             since black has no chromaticity and the caller should skip the
				             colour change entirely.

			Raises:
				ValueError: If red is a string that is not a valid '#RRGGBB' hex value.
		'''
		if isinstance(red, str):
			try:
				red, green, blue = int(red[1:3], 16), int(red[3:5], 16), int(red[5:], 16)
			except ValueError:
				raise ValueError("Invalid hex string format")

		self._logger.debug(f"RGB Split Input - R:{red} G:{green} B:{blue}")

		# We need to convert the RGB value to Yxz.
		redScale = float(red) / 255.0
		greenScale = float(green) / 255.0
		blueScale = float(blue) / 255.0

		# Apply gamma correction (sRGB standard)
		if redScale <= 0.04045:
			redScale = redScale / 12.92
		else:
			redScale = ((redScale + 0.055) / 1.055) ** 2.4

		if greenScale <= 0.04045:
			greenScale = greenScale / 12.92
		else:
			greenScale = ((greenScale + 0.055) / 1.055) ** 2.4

		if blueScale <= 0.04045:
			blueScale = blueScale / 12.92
		else:
			blueScale = ((blueScale + 0.055) / 1.055) ** 2.4

		# Transformation matrix (sRGB to XYZ) - Manual matrix multiplication
		x = 0.4124 * redScale + 0.3576 * greenScale + 0.1805 * blueScale
		y = 0.2126 * redScale + 0.7152 * greenScale + 0.0722 * blueScale
		z = 0.0193 * redScale + 0.1192 * greenScale + 0.9505 * blueScale

		#To use only X and Y, we need to noralize using Z i.e value = value / ( X + Y + Z)
		if x + y + z == 0:
			# Black has no chromaticity; caller should treat None as "no colour change"
			return None

		normx = x / ( x + y + z)
		normy = y / ( x + y + z)

		xy = [normx, normy]

		return xy

	def build_state(self, **kwargs):
		'''
		Assembles a Hue API state payload from keyword arguments and calls set_state().

			Keyword Args:
				on (bool): True to turn the light on, False to turn it off.
				bri (int): Brightness, 1–254. 254 is maximum.
				colour (str): '#RRGGBB' hex string converted to CIE xy for the Hue API.
				              Ignored when on=False or when the colour resolves to black.
				              Mutually exclusive with ct — if ct is provided, colour is ignored.
				ct (int): Colour temperature in mirek (153–500). 153 = coolest (~6500K),
				          500 = warmest (~2000K). Uses the white channel on RGBCCT lights.
				          Mutually exclusive with colour.
				deviceid (str): UUID of the Hue device or group to target.
				alert (str): Hue alert effect. 'lselect' is mapped to the v2 'breathe' action.
				transitiontime (int): Transition duration in units of 100 ms.

		Night mode:
			If night mode is active and the action is 'pause', returns immediately without
			changing the lights. If the action is 'dim', brightness is capped at
			nightmode_maxbri before the state is sent.

		Note:
			'deviceid' and 'colour' are consumed internally and not forwarded to the Hue
			API. All other kwargs (including alert, transitiontime, etc.) pass through
			to set_state() unchanged.
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

		exclude_keys = {"deviceid", "colour"}
		state = {key: value for key, value in kwargs.items() if key not in exclude_keys}
		self._logger.debug(f"Initial state: {state}")
		if kwargs['on']:
			if "colour" in kwargs and kwargs['colour'] is not None:
				colour = kwargs['colour']
				xy = self.rgb_to_xy(colour)
				if xy is not None:
					state['xy'] = xy

		self._logger.debug(f"Final State: {state}")
		return self.set_state(state, kwargs['deviceid'])

	def get_state(self, deviceid=None):
		'''
		Queries the on/off state of a Hue device or group via the v2 API.

			Parameters:
				deviceid (str, optional): UUID of the device to query.
				                          Defaults to the configured lampid.

			Returns:
				bool: True if the device is on, False if off.
				None: If the bridge is not ready or the response is unexpected.
		'''
		if not self._bridge_ready():
			return None

		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		self._logger.debug(f"Getting state of {deviceid}")
		if self._settings.get(['lampisgroup']):
			response = self._hue_request('GET', f"grouped_light/{deviceid}")
		else:
			response = self._hue_request('GET', f"light/{deviceid}")

		data = response.get('data', [])
		if data:
			return data[0]['on']['on']
		return None

	def set_state(self, state, deviceid=None):
		'''
		Converts a v1-style state dict to a Hue v2 CLIP API payload and PUTs it to
		the appropriate light or grouped_light resource.

		Brightness is converted from the 1–254 scale to the v2 0–100% scale.
		xy colour coordinates are wrapped in the v2 {"x": ..., "y": ...} object.
		CT is wrapped in color_temperature.mirek.
		The v1 "lselect" alert value is mapped to the v2 "breathe" action.

			Parameters:
				state (dict): State attributes using v1 key names:
				              on, bri (1-254), xy ([x, y]), ct, alert, transitiontime.
				deviceid (str, optional): UUID of the device or group to target.
				                          Defaults to the configured lampid.
		'''
		if not self._bridge_ready():
			return

		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		self._logger.debug(f"Setting lampid: {deviceid} Is Group: {self._settings.get(['lampisgroup'])} with State: {state}")

		# Build v2 nested payload
		payload = {}
		if 'on' in state:
			payload['on'] = {'on': state['on']}
		if 'bri' in state:
			payload['dimming'] = {'brightness': min(float(state['bri']), 100.0)}
		if 'xy' in state:
			payload['color'] = {'xy': {'x': state['xy'][0], 'y': state['xy'][1]}}
		if 'ct' in state:
			payload['color_temperature'] = {'mirek': state['ct']}
		if 'alert' in state:
			# v1 'lselect' (15s cycle) maps to v2 'breathe' (single pulse)
			payload['alert'] = {'action': 'breathe'}
		if 'transitiontime' in state:
			payload['dynamics'] = {'duration': state['transitiontime'] * 100}

		if self._settings.get(['lampisgroup']) and self._settings.get(['plugid']) != deviceid:
			self._hue_request('PUT', f"grouped_light/{deviceid}", payload)
		else:
			self._hue_request('PUT', f"light/{deviceid}", payload)

	def toggle_state(self, deviceid=None):
		'''
		Flips the on/off state of a device. When turning on, lamps use the configured
		default brightness; plugs (plugid) are switched on without a brightness argument.

			Parameters:
				deviceid (str, optional): UUID of the device to toggle.
				                          Defaults to the configured lampid.
		'''
		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		if self.get_state(deviceid):
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
		configured_events = [ sub['event'] for sub in self._settings.get(['statusDict']) ]
		return configured_events

	def on_after_startup(self):
		'''
		OctoPrint startup hook. Establishes the Hue bridge connection and, if
		"Lights On at Startup" is configured, triggers the corresponding statusDict
		light state.
		'''
		self._logger.info("Octohue is alive!")
		self.establishBridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
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
		OctoPrint shutdown hook. Turns off the configured lamp if offonshutdown is True.
		'''
		self._logger.info("Ladies and Gentlemen, thank you and goodnight!")
		if self._settings.get(['offonshutdown']):
			self.set_state({"on": False})

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
		Shutdown if below temp or not defined.  Reschedules itself every 30 s
		until the temperature condition is met rather than blocking in a loop.
		'''
		deviceid = self._settings.get(['plugid'])
		target_temp = int(self._settings.get(['powerofftemp']) or 0)
		temps = self._printer.get_current_temperatures()
		current_temp = max(int(v['actual']) for k, v in temps.items() if k.startswith('tool'))
		self._logger.debug(f"Safe Shutdown Requested! Tool Temp: {current_temp}, Looking for Safe Cooldown Temp: {target_temp}")
		# Check if current_temp is below shutdowntemp OR below 40 (whichever happens first)
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
		# and suppresses OctoPrint's future-deprecation warning.
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
				bridge     (admin) getstatus / discover / pair sub-commands for bridge management.
				getdevices (admin) Returns Hue lights, optionally filtered by archetype.
				getgroups  (admin) Returns Hue rooms and zones as named group entries.
				getstate   (admin) Returns the current on/off state of the configured lamp.
				togglehue  Toggles the lamp (or a specific device) between on and off.
				turnon     Turns a device on, optionally applying a colour hex value.
				turnoff    Turns a device off.
				cooldown   Triggers the temperature-monitored power-down sequence immediately.
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
				r = requests.get(self.discoveryurl)
				discoveredbridge = r.json()
				self._logger.debug(discoveredbridge)
				return flask.jsonify(discoveredbridge)

			elif "pair" in data:
				self._logger.debug(data['bridgeaddr'])
				bridgeaddr = data['bridgeaddr']
				# Pairing still uses the v1 endpoint — this is correct and unchanged in v2
				pair_session = requests.Session()
				pair_session.mount("https://", _SignifyAdapter())
				r = pair_session.post("https://{}/api".format(bridgeaddr), json={"devicetype":"octoprint#octohue"})
				result = r.json()[0]
				if "error" in result:
					response = [{
						'response': 'error'
					}]
					return flask.jsonify(response)
				elif "success" in result:
					token = result['success']['username']
					response = [{
						'response': 'success',
						'bridgeaddr': bridgeaddr,
						'husername': token
					}]
					self._logger.debug(f"New Huesername {token}")
					self._settings.set(['husername'], token)
					self._settings.set(['bridgeaddr'], bridgeaddr)
					self._settings.save()
					self.establishBridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
					return flask.jsonify(response)

			else:
				return flask.jsonify(status="ok")

		elif command == 'getdevices':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)
			if not self._bridge_ready():
				return flask.jsonify(devices=[])
			self._logger.debug("Getting Devices")
			response = self._hue_request('GET', 'light')
			devices = response.get('data', [])
			if 'archetype' in data:
				self._logger.debug(f"Archetype: {data['archetype']}")
				device_elements = [
					{"id": d['id'], "name": d['metadata']['name'], "archetype": d['metadata']['archetype']}
					for d in devices
					if d.get('metadata', {}).get('archetype') == data['archetype']
				]
			else:
				device_elements = [
					{"id": d['id'], "name": d['metadata']['name'], "archetype": d.get('metadata', {}).get('archetype', '')}
					for d in devices
				]
			return flask.jsonify(devices=device_elements)

		elif command == 'getgroups':
			if not Permissions.ADMIN.can():
				return flask.make_response(flask.jsonify(error="Forbidden"), 403)
			if not self._bridge_ready():
				return flask.jsonify(groups=[])
			self._logger.debug("Getting Groups")
			groups = []
			for resource_type in ('room', 'zone'):
				response = self._hue_request('GET', resource_type)
				for item in response.get('data', []):
					name = item.get('metadata', {}).get('name', '')
					grouped_light_id = next(
						(s['rid'] for s in item.get('services', []) if s.get('rtype') == 'grouped_light'),
						None
					)
					if grouped_light_id and name:
						groups.append({'id': grouped_light_id, 'name': name})
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
			if self.get_state():
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
		schedules the appropriate light change (on/off/flash) after the configured delay.
		Also triggers auto power-off if enabled and the event is PrintDone.
		'''
		self._logger.debug(f"Recieved Status: {event} from Printer")
		my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == event), None)
		if my_statusEvent:
			self._logger.info(f"Received Configured Status Event: {event}")
			delay = my_statusEvent['delay'] or 0
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
		return dict(admin=[["bridgeaddr"],["husername"]])

	def get_settings_version(self):
		'''
		Returns the current settings schema version. OctoPrint uses this to detect
		when on_settings_migrate needs to be called.
		'''
		return 4

	def on_settings_migrate(self, target, current=None):
		'''
		Migrates settings from an older schema version.

		current=None (first install): writes example statusDict entries.
		current<2  (v1→v2): clears lampid/plugid — Hue v2 uses UUIDs, not integer IDs.
		current<3  (v2→v3): converts all brightness values from 1–255 scale to
		                     0–100 percentage scale used by the Hue v2 API.

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
		}
		return my_settings

	def on_settings_save(self, data):
		'''
		Persists settings and re-establishes the bridge connection with any updated
		credentials. Strips availableEvents (frontend-only) before passing to the base class.
		'''
		data.pop("availableEvents", None)
		self._logger.debug(f"Saving: {data} to settings")
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self.establishBridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))

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
		Provides configuration for OctoPrint's Software Update plugin to check for new
		releases on GitHub and install them via pip.
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
