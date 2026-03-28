import octoprint.plugin
import flask
import requests
from qhue import Bridge
from octoprint.util import ResettableTimer
from urllib3.exceptions import InsecureRequestWarning
 
# Suppress the warnings from urllib3
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class OctohuePlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.SettingsPlugin,
					octoprint.plugin.SimpleApiPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.EventHandlerPlugin):


	pbridge = None
	discoveryurl = 'https://discovery.meethue.com/'

	def _bridge_ready(self):
		if self.pbridge is None:
			self._logger.warning("Hue bridge not yet initialised — skipping.")
			return False
		return True

	def establishBridge(self, bridgeaddr, husername):
		self._logger.debug(f"Bridge Address is {bridgeaddr if bridgeaddr else 'Please set Bridge Address in settings'}")
		self._logger.debug(f"Hue Username is {husername if husername else 'Please set Hue Username in settings'}")
		self.pbridge = Bridge(bridgeaddr, husername)
		self._logger.debug(f"Bridge established at: {self.pbridge.url}")
	
	def rgb_to_xy(self, red: int, green: int = None, blue: int = None):
		'''
		Converts RGB colour space to XY
		
			Parameters:
				red (int): 8bit int representing red value
				green (int): 8bit int representing green value
				blue (int): 8bit int representing blue
				 
			returns:
				xy (list): XY Colourspace Coordinates
		
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
		Assembles payload used to set a lights state

			Parameters:
				colour (string): 6 Char RBG Hex colour string
				transitiontime (int): Desired duration of the state transition time
				bri (int): 8bit int representing desired brightness, 255 = max brightness
				on (bool): True = Light On, False = Light Off
				deviceid (int): The ID of the device to set the state for

			Returns:
				set_state() with the assembled payload
		'''
		
		self._logger.debug(f"Build_state Called with: {kwargs}")

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
		Queries a device or devicegroups on/off state

			Returns:
				state (bool): True for on.
		'''
		if not self._bridge_ready():
			return None

		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		self._logger.debug(f"Getting state of {deviceid}")
		if self._settings.get(['lampisgroup']):
			return self.pbridge.groups[deviceid]().get("action")['on']
		else:
			return self.pbridge.lights[deviceid]().get("state")['on']

	def set_state(self, state, deviceid=None):
		'''
		Set a device or devicegroup to the desired state

			Parameters:
				state (dict): Dictionary of state settings; see build_state()
		'''
		if not self._bridge_ready():
			return

		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		self._logger.debug(f"Setting lampid: {deviceid} Is Group: {self._settings.get(['lampisgroup'])} with State: {state}")

		if self._settings.get(['lampisgroup']) and self._settings.get(['plugid']) != deviceid:
			self.pbridge.groups[deviceid].action(**state)
		else:
			self.pbridge.lights[deviceid].state(**state)

	def toggle_state(self, deviceid=None):
		'''
		Queries a device or devicegroup for its state and flips it to its opposite state.
		'''
		if deviceid is None:
			deviceid = self._settings.get(['lampid'])

		if self.get_state(deviceid):
			self.build_state(on=False, deviceid=deviceid)
		else:
			if deviceid != self._settings.get(['plugid']):
				self.build_state(on=True, bri=int(self._settings.get(['defaultbri'])), deviceid=deviceid)
			else:
				self.build_state(on=True, deviceid=deviceid)

	def get_configured_events(self):
		'''
		Fetch a list of events names the user has configured settings for

			Returns:
				configuredEvents (list): A list of event names the user has configured
		'''
		configured_events = [ sub['event'] for sub in self._settings.get(['statusDict']) ]
		return configured_events

	def on_after_startup(self):
		'''
		Commands to call on Plugin Startup
			pbridge : create bridge object.
		'''
		self._logger.info("Octohue is alive!")
		self.establishBridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
		if self._settings.get(['ononstartup']):
			my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == self._settings.get(['ononstartupevent'])), None)
			if my_statusEvent:
				self.build_state(on=True, colour=my_statusEvent['colour'], bri=int(my_statusEvent['brightness']), deviceid=self._settings.get(['lampid']))

	def on_shutdown(self):
		'''
		Commands to call on Plugin Shutdown
			offonshutdown : Turn off device if true
		'''
		self._logger.info("Ladies and Gentlemen, thank you and goodnight!")
		if self._settings.get(['offonshutdown']):
			self.set_state({"on": False})

	def printer_start_power_down(self):
		'''
		Commands to call on Printer Power Down
			offonshutdown : Turn off device if true
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
	
	def get_api_commands(self):
		return dict(
			bridge=[],
			getdevices=[],
			togglehue=[],
			getstate=[],
			turnon=[],
			turnoff=[],
			cooldown=[]
		)
	
	def on_api_command(self, command, data):
		self._logger.debug(f"Recieved API Command: {command}")
		if command == 'bridge':
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
				r = requests.post("https://{}/api".format(bridgeaddr), json={"devicetype":"octoprint#octohue"}, verify=False)
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
			if not self._bridge_ready():
				return flask.jsonify(devices=[])
			self._logger.debug("Getting Devices")
			devicedata = self.pbridge.lights()
			if 'archetype' in data:
				self._logger.debug(f"Archetype: {data['archetype']}")
				device_elements = [
					{"id": key, "name": value["name"], "archetype": value["config"]["archetype"]}
					for key, value in devicedata.items()
					if value["config"]["archetype"] == data['archetype']
				]
			else:
				device_elements = [
					{"id": key,"name": value["name"], "archetype": value["config"]["archetype"]}
					for key, value in devicedata.items()
				]
			return flask.jsonify(devices=device_elements)

		elif command == 'togglehue':
			self._logger.debug(f"Toggling Hue for {data}")
			if 'deviceid' in data:
				self.toggle_state(data['deviceid'])
			else:
				self.toggle_state(self._settings.get(['lampid']))

		elif command == 'getstate':
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
			
	# Trigger state on Status match
	def on_event(self, event, payload):
		self._logger.debug(f"Recieved Status: {event} from Printer")
		my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == event), None)
		if my_statusEvent: 
			self._logger.info(f"Received Configured Status Event: {event}")
			delay = my_statusEvent['delay'] or 0
			deviceid = self._settings.get(['lampid'])

			if not my_statusEvent['turnoff']:
				brightness = my_statusEvent['brightness']
				colour = my_statusEvent['colour']

				delayedtask = ResettableTimer(delay, self.build_state, kwargs={'on':True, 'colour':colour, 'bri':int(brightness), 'deviceid':deviceid})

			else:
				delayedtask = ResettableTimer(delay, self.build_state, kwargs={'on':False, 'deviceid':deviceid})

			try:
				delayedtask.start()
			except Exception as e:
				self._logger.error(f"Error starting delayed task: {e}")

		
		if self._settings.get(['autopoweroff']) and event == 'PrintDone':
			self.printer_start_power_down()

	# General Octoprint Hooks Below

	def get_settings_defaults(self):
		return dict(
			enabled=True,
			installed_version=self._plugin_version,
			bridgeaddr="",
			husername="",
			lampid="",
			plugid="",
			lampisgroup=False,
			defaultbri=255,
			ononstartup=False,
			ononstartupevent="",
			offonshutdown=True,
			showhuetoggle=True,
			showpowertoggle=False,
			autopoweroff=False,
			powerofftime=0,
			powerofftemp=0,
			statusDict=[]
		)

	def get_settings_restricted_paths(self):
		return dict(admin=[["bridgeaddr"],["husername"]])
	
	def get_settings_version(self):
		return 1

	def on_settings_migrate(self, target, current=None):
		if current is None:
			self._logger.info("Migrating Settings: Writing example settings")
			self._settings.set(["statusDict"], [
					{'event': 'Connected',
					'colour':'#FFFFFF',
					'brightness':255,
					'delay':0,
					'turnoff':False},
					{'event': 'Disconnected',
					'colour':'',
					'brightness':"",
					'delay':0,
					'turnoff':True},
					{'event': 'PrintStarted',
					'colour':'#FFFFFF',
					'brightness':255,
					'delay':0,
					'turnoff':False},
					{'event': 'PrintResumed',
					'colour':'#FFFFFF',
					'brightness':255,
					'delay':0,
					'turnoff':False},
					{'event': 'PrintDone',
					'colour':'#33FF36',
					'brightness':255,
					'delay':0,
					'turnoff':False},
					{'event': 'PrintFailed',
					'colour':'#FF0000',
					'brightness':255,
					'delay':0,
					'turnoff':False}
				])
			self._settings.save()
		elif current < self.get_settings_version():
			self._logger.info("Migrating Settings: Updating a setting")

	def on_settings_load(self):
		my_settings = {
			"availableEvents": octoprint.events.all_events(),
			"statusDict": self._settings.get(["statusDict"]),
			"bridgeaddr": self._settings.get(["bridgeaddr"]),
			"husername": self._settings.get(["husername"]),
			"lampid": self._settings.get(["lampid"]),
			"plugid": self._settings.get(["plugid"]),
			"lampisgroup": self._settings.get(["lampisgroup"]),
			"defaultbri": self._settings.get(["defaultbri"]),
			"ononstartup": self._settings.get(["ononstartup"]),
			"configuredEvents": self.get_configured_events(),
			"ononstartupevent": self._settings.get(["ononstartupevent"]),
			"offonshutdown": self._settings.get(["offonshutdown"]),
			"showhuetoggle": self._settings.get(["showhuetoggle"]),
			"showpowertoggle": self._settings.get(["showpowertoggle"]),
			"autopoweroff": self._settings.get(["autopoweroff"]),
			"powerofftime": self._settings.get(["powerofftime"]),
			"powerofftemp": self._settings.get(["powerofftemp"]),
		}
		return my_settings

	def on_settings_save(self, data):
		data.pop("availableEvents", None)
		self._logger.debug(f"Saving: {data} to settings")
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self.establishBridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
		
	def get_template_vars(self):
		return dict(
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
		return [
			dict(type="settings", custom_bindings=True)
		]

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/OctoHue.js"],
			css=["css/OctoHue.css"],
			less=["less/OctoHue.less"]
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
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
__plugin_pythoncompat__ = ">=3.6,<4"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = OctohuePlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

