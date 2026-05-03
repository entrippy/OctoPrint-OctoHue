# LightConfig as a typed dataclass passed to LightController

The plugin adapter (OctoPrint mixin class) reads all settings and constructs a typed `LightConfig` dataclass, which it passes to `LightController`. The controller never touches OctoPrint's settings object directly.

We chose this over passing the OctoPrint settings object into the domain because it creates a clean seam: the controller has no dependency on OctoPrint machinery, and its full configuration surface is visible in one place. Tests can construct a `LightConfig` directly without any OctoPrint infrastructure.

## Considered options

- **Pass OctoPrint settings object directly** — simpler initially, but pulls OctoPrint into the domain and makes unit testing the controller impossible without a running OctoPrint instance.
- **Pass a plain dict** — avoids OctoPrint dependency but leaves the controller reading string keys with no type safety and no visible interface.
