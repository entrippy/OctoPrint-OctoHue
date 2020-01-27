# OctoPrint-OctoHue

Illuminate your print job and signal its status using a Philips Hue light.

## Features
* Light on and off in coordination with the connection between Octoprint and your printer
* Configure "Connected" light colour using colour picker or HTML hex colour codes
* Customisable default brightness
* Available Customisable Statuses:
  * Connected -  Default White
  * Print Finished - Default Green
  * Error - Default Red

See the TODO list at the end of this page for features on the roadmap

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/entrippy/OctoPrint-OctoHue/archive/master.zip

**Hue Bridge Configuration** 

Octohue requires 3 settings to function
1. The IP Address of you Hue Bridge
2. A User for octoprint to use when contacting your bridge
3. The numberic ID of your Hue light.

Steps to find or configure these can be found in [How to Develop for Hue - Getting Started](https://developers.meethue.com/develop/get-started-2/)

## Configuration

Once you have the Hue IP, Username, and Light ID, enter these into the appropriate field in Octohues menu in settings.

![Screenshot](https://github.com/entrippy/OctoPrint-OctoHue/blob/master/Settings-Screenshot.png)

## TODO
* Make all available statuses customisable
* Per status brightness
* LightID Discovery


