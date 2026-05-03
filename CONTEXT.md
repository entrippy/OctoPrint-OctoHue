# OctoHue

An OctoPrint plugin that controls lights in response to print events. It translates printer state into light commands via a provider-agnostic interface, supporting multiple light ecosystems (Hue, WLED, and others).

## Language

**Provider**:
A concrete implementation that communicates with a specific light ecosystem (e.g. Philips Hue, WLED). Responsible for translating light commands into vendor-specific API calls.
_Avoid_: adapter, driver, integration, backend.

**LightController**:
The domain module that translates print events and user actions into light commands, then issues them via the active provider. Owns event→light mapping, night mode response, and toggle behaviour. Has no dependency on OctoPrint.
_Avoid_: dispatcher, manager, orchestrator.

**LightConfig**:
A typed configuration struct constructed by the plugin adapter from OctoPrint settings. Passed to LightController on startup and on every settings save. LightController never reads OctoPrint settings directly.
_Avoid_: settings dict, config object, options.

**Night mode**:
A user-configured time window during which light changes are either suppressed entirely (pause) or brightness-capped (dim). The window definition lives in LightConfig; whether the window is currently active is evaluated per-event by a pure function.
_Avoid_: quiet hours, do-not-disturb.

**Event**:
An OctoPrint lifecycle signal (e.g. `PrintDone`, `PrintFailed`, `Connected`) that may trigger a light change. Each event can be mapped to a colour, brightness, and behaviour in the user's configuration.
_Avoid_: hook, callback, trigger.

**statusDict**:
The user's configured mapping of events to light settings (colour, brightness, colour temperature, flash, delay, turn-off). Stored as a list of entries in OctoPrint settings. Owned and interpreted by LightController.
_Avoid_: event config, colour map.

**Toggle**:
A user-initiated on/off action issued from the OctoPrint navbar, independent of any print event. Uses its own configured colour, brightness, and colour temperature.
_Avoid_: manual override, button press.

## Relationships

- A **LightController** holds exactly one active **Provider** and one **LightConfig**
- A **LightConfig** contains one **statusDict** and one night mode definition
- An **Event** is looked up in the **statusDict** to produce a light command
- A **Provider** is the only module that communicates with hardware or a vendor API

## Example dialogue

> **Dev:** "When `PrintDone` fires during night mode, what happens?"
> **Domain expert:** "The LightController checks whether the current time falls in the night mode window. If it does and the action is pause, the event is suppressed. If the action is dim, the brightness from the statusDict entry is capped before the command is sent to the provider."

## Flagged ambiguities

- "bridge" appears in settings (`bridgeaddr`) as a Hue-specific term but is used as the generic controller-address field for all providers. The field name is historical; the concept is generic.
