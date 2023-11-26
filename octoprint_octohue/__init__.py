# coding=utf-8
from __future__ import absolute_import
from qhue import Bridge, QhueException
from colormath.color_objects import XYZColor, sRGBColor
from colormath.color_conversions import convert_color
from octoprint.util import ResettableTimer
import octoprint.plugin
import flask


class OctohuePlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.ShutdownPlugin,
					octoprint.plugin.SettingsPlugin,
					octoprint.plugin.SimpleApiPlugin,
					octoprint.plugin.AssetPlugin,
					octoprint.plugin.TemplatePlugin,
					octoprint.plugin.EventHandlerPlugin):

	# Hue Functions
	pbridge=''

	def rgb_to_xy(self, red, green=None, blue=None):
		self._logger.debug("RGB Input - R:%s G:%s B:%s" % (red, green, blue))

		if isinstance(red, str):
		# If Red is a string or unicode assume a hex string is passed and convert it to numberic 
			rstring = red
			red = int(rstring[1:3], 16)
			green = int(rstring[3:5], 16)
			blue = int(rstring[5:], 16)

		# We need to convert the RGB value to Yxz.
		redScale = float(red) / 255.0
		greenScale = float(green) / 255.0
		blueScale = float(blue) / 255.0
		
		rgb = sRGBColor(redScale, greenScale, blueScale)
		xyz = convert_color(rgb, XYZColor)

		x = xyz.get_value_tuple()[0]
		y = xyz.get_value_tuple()[1]
		z = xyz.get_value_tuple()[2]
		#To use only X and Y, we need to noralize using Z i.e value = value / ( X + Y + Z)
		normx = x / ( x + y + z)
		normy = y / ( x + y + z) 
		
		xy = [normx, normy]
		
		return xy

	def build_state(self, colour=None, transitiontime=5, bri=None, illuminate=True):

		state = {}
		state['on'] = illuminate
		
		if illuminate == True:
			if bri is None:
				bri = int(self._settings.get(['defaultbri']))
			state['bri'] = bri
			
			if colour is not None:
				state['xy'] = self.rgb_to_xy(colour)

		state['transitiontime'] = transitiontime

		return self.set_state(state)

	def get_state(self):
		if self._settings.get(['lampisgroup']) == True:
			self._state = self.pbridge.groups[self._settings.get(['lampid'])]().get("action")['on']
		else:
			self._state = self.pbridge.lights[self._settings.get(['lampid'])]().get("state")['on']
		self._logger.debug("Get State is %s" % self._state )
		return self._state

	def set_state(self, state):
		self._logger.debug("Setting lampid: %s  Is Group: %s with State: %s" % (self._settings.get(['lampid']),self._settings.get(['lampisgroup']), state))
		if self._settings.get(['lampisgroup']) == True:
			self.pbridge.groups[self._settings.get(['lampid'])].action(**state)
		else:
			self.pbridge.lights[self._settings.get(['lampid'])].state(**state)

	def toggle_state(self):
		if self.get_state():
			self.build_state(illuminate=False)
		else:
			self.build_state(illuminate=True, bri=int(self._settings.get(['defaultbri'])))

	def get_configured_events(self):
		configuredEvents = [ sub['event'] for sub in self._settings.get(['statusDict']) ]
		return configuredEvents

	def on_after_startup(self):
		self._logger.info("Octohue is alive!")
		self._logger.debug("Bridge Address is %s" % self._settings.get(['bridgeaddr']) if self._settings.get(['bridgeaddr']) else "Please set Bridge Address in settings")
		self._logger.debug("Hue Username is %s" % self._settings.get(['husername']) if self._settings.get(['husername']) else "Please set Hue Username in settings")
		self.pbridge = Bridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
		self._logger.debug("Bridge established at: %s" % self.pbridge.url)
		#if self._settings.get(['ononstartup']) == True:
		#	my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == self._settings.get(['ononstartupevent'])), None)
		#	self.build_state(illuminate=True, colour=my_statusEvent['colour'], bri=int(self._settings.get(['defaultbri'])))

	def on_shutdown(self):
		self._logger.info("Ladies and Gentlemen, thank you and goodnight!")
		if self._settings.get(['offonshutdown']) == True:
			self.set_state({"on": False})

	def get_api_commands(self):
		return dict(
			togglehue=[],
			getstate=[]
		)
	
	def on_api_command(self, command, data):
		import flask
		if command == 'togglehue':
			self.toggle_state()
		
	def on_api_get(self, request):
		if request.args.get("getstate"):
			self._logger.debug("Recieved API Get: %s" % request)
			return flask.jsonify(foo="bar")
		

	# Trigger state on Status match
	def on_event(self, event, payload):
		self._logger.debug("Recieved Status: %s from Printer" % event)
		my_statusEvent = next((statusEvent for statusEvent in self._settings.get(['statusDict']) if statusEvent['event'] == event), None)
		if my_statusEvent: 
			self._logger.info("Received Configured Status Event: %s" % event)
			delay = my_statusEvent['delay'] or 0

			if my_statusEvent['turnoff'] == False:
				brightness = my_statusEvent['brightness'] or self._settings.get(['defaultbri'])
				colour = my_statusEvent['colour']

				delayedtask = ResettableTimer(delay, self.build_state, args=[colour], kwargs={'bri':int(brightness)})

			else:
				delayedtask = ResettableTimer(delay, self.build_state, kwargs={'illuminate':False})
		
			delayedtask.start()

	# General Octoprint Hooks Below

	def get_settings_defaults(self):
		return dict(
			bridgeaddr="",
			husername="",
			lampid="",
			lampisgroup="",
			defaultbri=255,
			ononstartup=False,
			ononstartupevent="",
			offonshutdown=True,
			showhuetoggle=True,
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
			"lampisgroup": self._settings.get(["lampisgroup"]),
			"defaultbri": self._settings.get(["defaultbri"]),
			"ononstartup": self._settings.get(["ononstartup"]),
			"configuredEvents": self.get_configured_events(),
			"ononstartupevent": self._settings.get(["ononstartupevent"]),
			"offonshutdown": self._settings.get(["offonshutdown"]),
			"showhuetoggle": self._settings.get(["showhuetoggle"])
		}
		return my_settings

	def on_settings_save(self, data):
		data.pop("availableEvents", None)
		self._logger.debug("Saving: %s" % data) 
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self.pbridge = Bridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
		self._logger.info("New Bridge established at: %s" % self.pbridge.url)
		
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
__plugin_pythoncompat__ = ">=2.7,<4" # Compatible with python 2 and 3

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = OctohuePlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

