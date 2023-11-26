# OctoPrint-OctoHue Change Log

## Added in 0.5.0
* Added option to "Light On" on Octoprint startup by selecting an already configured light event

## Fixed in 0.4.4
* It is recommended that you remove your existing octohue settings, or at the very least remove statusDict from config.yaml
* Back from the dead after several years of inactivity (thanks covid)
* Fixed bug preventing changes to initial example configuration from being changed. No example events are configured in this version, but they will return in future.
* Changed persistent statusDict settins to a list of dicts instead of a dict of dicts, this was what played hell with the above
* Moved from using the term "status" to "events" in line with octoprint terminology
* Added new Event Add modal with "Event" dropdown populated from native octoprint events.

## Fixed in 0.4.3
* Renamed rgb() to build_state() as it better describes its function
* Fixed brightness not being passed properly to build_state meaning it always defaulted to 255
* Fixed bridge object not being reinitialised on settings save, requiring a restart to pickup bridge and user changes.
* Default brightness now works as planned and sets the brightness when it is not defined for a particular status. 

## Added in 0.4.2
* Optional Navbar Icon allowing the user to toggle On/Off
* Reworked settings allows user configurable Statuses and colour/brightness/state configurations.
* Added turning lights off as an option for printer statuses.
* Added debug logging option to allow logging or raw status events to aid configuration

