# coding=utf-8
from qhue import Bridge, QhueException, create_new_username
from colorpy import colormodels
import json

bridgeaddress = "10.0.0.157"
husername = "9Iqu776auy5YGA9hMZ6AktfEfzYZoeFw7aaPodSk"
lightID = 9
lcolour = "#33FF36"
brightness = 128



class HuePrinterLight(Bridge):

    state = None
    

    def __init__(self, plightID, bridgeaddress, husername):
        self.plightID = plightID
        self.bridgeaddress = bridgeaddress
        self.husername = husername
        self.pbridge = Bridge(self.bridgeaddress, self.husername)

    def rgb(self, red, green=None, blue=None, transitiontime=5, bri=128):
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
        print("%s, %s, %s" % (redScale, greenScale, blueScale))
        xyz = colormodels.irgb_color(red, green, blue)
        print("Irgb: %s" % xyz)
        xyz = colormodels.xyz_from_rgb(xyz)
        print("XYZ: %s " % xyz)
        xyz = colormodels.xyz_normalize(xyz)
        print("Normalised XYZ: %s" % xyz)
        state['xy'] = [xyz[0], xyz[1]]

        return self.set_state(state)
        
    def set_state(self, state):
        self.pbridge.lights[self.plightID].state(**state)

pl = HuePrinterLight(lightID, bridgeaddress, husername)
pl.rgb(lcolour)

