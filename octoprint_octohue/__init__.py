# coding=utf-8
from __future__ import absolute_import
from qhue import Bridge, QhueException
from colorpy import colormodels
import octoprint.plugin


class OctohuePlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.SettingsPlugin,
                    octoprint.plugin.AssetPlugin,
                    octoprint.plugin.TemplatePlugin,
					octoprint.plugin.EventHandlerPlugin):

	# Hue Functions
	pbridge=''

	def rgb(self, red, green=None, blue=None, transitiontime=5, bri=255):
		state = {"on": True, "xy": None, "transitiontime": transitiontime, "bri": bri }
        
		if isinstance(red, basestring):
		# If Red is a string or unicode assume a hex string is passed and convert it to numberic 
			rstring = red
			red = int(rstring[1:3], 16)
			green = int(rstring[3:5], 16)
			blue = int(rstring[5:], 16)

		# We need to convert the RGB value to Yxy.
		redScale = float(red) / 255.0
		greenScale = float(green) / 255.0
		blueScale = float(blue) / 255.0
		colormodels.init(
			phosphor_red=colormodels.xyz_color(0.64843, 0.33086),
			phosphor_green=colormodels.xyz_color(0.4091, 0.518),
			phosphor_blue=colormodels.xyz_color(0.167, 0.04))
		self._logger.debug("%s, %s, %s" % (redScale, greenScale, blueScale))
		xyz = colormodels.irgb_color(red, green, blue)
		self._logger.debug("Irgb: %s" % xyz)
		xyz = colormodels.xyz_from_rgb(xyz)
		self._logger.debug("XYZ: %s " % xyz)
		xyz = colormodels.xyz_normalize(xyz)
		self._logger.debug("Normalised XYZ: %s" % xyz)
		state['xy'] = [xyz[0], xyz[1]]
		
		return self.set_state(state)

	def set_state(self, state):
		self._logger.debug("Setting lampid: %s with State: %s" % (self._settings.get(['lampid']), state))
		self.pbridge.lights[self._settings.get(['lampid'])].state(**state)

	

	def on_after_startup(self):
		self._logger.info("Octohue is alive!")
		self._logger.info("Bridge Address is %s" % self._settings.get(['bridgeaddr']) if self._settings.get(['bridgeaddr']) else "Please set Bridge Address in settings")
		self._logger.info("Hue Username is %s" % self._settings.get(['husername']) if self._settings.get(['husername']) else "Please set Hue Username in settings")
		self.pbridge = Bridge(self._settings.get(['bridgeaddr']), self._settings.get(['husername']))
		self._logger.info("Bridge established at: %s" % self.pbridge.url)

	# State to Light mappings
	def on_event(self, event, payload):
		self._logger.info("Received Event: %s" % event)
		if event == "Connected":
			self.rgb(self._settings.get(['connectedc']),bri=128)
		if event == "OFFLINE":
			self.set_state({"on": False})
		if event == "PrinterStateChanged":
			self._logger.info("New State: %s" % payload['state_id'])
			if payload['state_id'] == "PRINTING":
				self.rgb(self._settings.get(['connectedc']))
		if event == "PrintDone":
			self.rgb(self._settings.get(["completec"]))
		if event == "PrintFailed":
			self.rgb(self._settings.get(["errorc"]))

	def get_settings_defaults(self):
		return dict(
			bridgeaddr="",
			husername="",
			lampid="",
			defaultbri="",
			connectedc="#FFFFFF",
			printingc="#FFFFFF",
			completec="#33FF36",
			errorc="#FF0000",
			warningc="#FFC300"
		)

	def get_template_vars(self):
		return dict(
			bridgeaddr=self._settings.get(["bridgeaddr"]),
			husername=self._settings.get(["husername"]),
			lampid=self._settings.get(["lampid"]),
			defaultbri=self._settings.get(["defaultbri"]),
			connectedc=self._settings.get(["connectedc"]),
			printingc=self._settings.get(["printingc"]),
			completec=self._settings.get(["completec"]),
			errorc=self._settings.get(["errorc"]),
			warningc=self._settings.get(["warningc"])
		)
	
	def get_template_configs(self):
		return [
			dict(type="settings", custom_bindings=False)
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



# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Octohue"

# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
#__plugin_pythoncompat__ = ">=2.7,<3" # only python 2
#__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = OctohuePlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

