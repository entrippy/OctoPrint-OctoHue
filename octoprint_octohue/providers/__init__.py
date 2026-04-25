from .base import LightProvider
from .hue import HueProvider

# Registry mapping the ``provider`` settings key to its implementation class.
# Add new providers here as they are implemented.
PROVIDERS: dict[str, type[LightProvider]] = {
    "hue": HueProvider,
}
