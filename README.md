# OctoPrint-OctoHue

Illuminate your print job and signal its status using a Philips Hue light.

## New in 0.4.0
* Optional Navbar Icon allowing the user to toggle On/Off
* User configurable Statuses and colour/brightness/state configurations.
* Added turning lights off as an option for printer statuses.

## Features
* Set Colour, Brightness, and On/Off state for any Octoprint state event e.g Connected, Printing, PrintCompleted.
* Optional Navbar Icon allowing the user to toggle On/Off
* Configure light colour using colour picker or HTML hex colour codes
* Control individual lights, or Rooms/Zones
* Support to switch off lights when OctoPrint quits.
* Customisable default brightness

See the TODO list at the end of this page for features on the roadmap

## Setup

### For install troubleshooting please see the "Known Issues" section at the bottom of this Readme.

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/entrippy/OctoPrint-OctoHue/archive/master.zip

### Hue Bridge Configuration

Octohue requires 3 settings to function
1. The IP Address of you Hue Bridge
2. A User for octoprint to use when contacting your bridge
3. The numberic ID of your Hue light or light group.

Steps to find or configure these can be found in [How to Develop for Hue - Getting Started](https://developers.meethue.com/develop/get-started-2/)

Should you run into problems using the bridges own built in REST interface, the steps can also be completed using a desktop interface such as [Postman](https://www.getpostman.com/)

### Light and Group ID's

The list of available Light ID's can be found at:
`https://<bridgeaddr>/api/<hueusername>/lights`

#### To control multiple lights:

If a the lights are not yet grouped, use the Hue app (or API directly if you're feeling hardcore) to create a room or zone consisting of the intended lights.

Once done, the list of available Group ID's can be found at:
`https://<bridgeaddr>/api/<hueusername>/groups`


## Configuration

Once you have the Hue IP, Username, and Light ID, enter these into the appropriate field in Octohues menu in settings.

![Screenshot](https://github.com/entrippy/OctoPrint-OctoHue/blob/master/Settings-Screenshot.png)

## Known Issues
* Octohue uses numpy, which reportedly can take a long time to install, occasionally timing out. This can be rectified by reinstalling octohue once numpy completes, or alternatively manually installing Octohue using pip.
* Octohue will log an error as a result of sending xy colour coordinates to non-rbg bulbs. however ther bulb will still illuminate.

### Manual pip (re)installation instructions
1. Log into you Octohue server via the command line.
2. Activate OctoPrints python virtualenv e.g in octopi:
    ```source ~/oprint/bin/activate```
3. Reinstall Octohue using pip:
    ```pip install --upgrade --force-reinstall https://github.com/entrippy/OctoPrint-OctoHue/archive/master.zip```

## TODO
* LightID Discovery
* Light Capability Discovery


