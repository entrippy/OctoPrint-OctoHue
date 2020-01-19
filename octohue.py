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
        """This is all someones prior art, but I should understand it

        This function takes RGB as either numerically as a set of a R,G and B value, or as a hex string
        """
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
        
        #return self.set_state([xyz[0], xyz[1]], transitiontime=transitiontime, bri=bri)
        return self.set_state(
            {"on": True, "xy": [xyz[0], xyz[1]], "transitiontime": transitiontime, "bri": bri }
        )
        
    def set_state(self, state):
        print("Bridge %s" % self.bridgeaddress)
        print("U %s" % self.husername)
        print("Light %i" % self.plightID)
        print("PBridge: %s" % self.pbridge)

        #newstate = ''.join([('%s=%s,' % x) for x in kwargs.iteritems()])
        #state = newstate[:-1]
        #print("State"+ json.dumps(state))
        self.pbridge.lights[self.plightID].state(transitiontime=5,on=True,xy=[0.37949361297741163, 0.4599316758104256])

pl = HuePrinterLight(lightID, bridgeaddress, husername)
pl.rgb(lcolour)


#b = Bridge(bridgeaddress, husername)
#b.lights[9].state(transitiontime=5,on=True,xy=[0.37949361297741163, 0.4599316758104256])