from __future__ import annotations
from abc import ABC, abstractmethod


class LightProvider(ABC):
    """
    Abstract base class for light providers.

    Every provider must implement this interface so the OctoHue plugin can
    control lights without knowing which underlying vendor or protocol is in
    use. The plugin delegates all light operations to an instance of a concrete
    subclass; it never calls vendor-specific code directly.
    """

    def __init__(self, logger) -> None:
        self._logger = logger

    @abstractmethod
    def setup(self, settings: dict) -> None:
        """
        Initialise or reinitialise the provider from a settings dict.

        Called on plugin startup and on every settings save. The keys present
        in ``settings`` are provider-specific; each provider documents what it
        expects.
        """
        ...

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """True if the provider is fully configured and ready to accept commands."""
        ...

    @abstractmethod
    def set_light(
        self,
        *,
        on: bool,
        deviceid: str | None = None,
        colour_hex: str | None = None,
        ct_mirek: int | None = None,
        brightness_pct: float | None = None,
        flash: bool = False,
        transition_ms: int | None = None,
    ) -> None:
        """
        Set the state of a light or group.

        Parameters:
            on:             True to turn the light on, False to turn it off.
            deviceid:       Provider-specific device or group identifier.
                            Defaults to the configured primary light when omitted.
            colour_hex:     ``'#RRGGBB'`` hex colour string. Ignored when
                            ``on=False`` or when ``ct_mirek`` is also provided.
            ct_mirek:       Colour temperature in mirek (153–500). Takes
                            precedence over ``colour_hex`` when both are given.
            brightness_pct: Brightness as a percentage (0–100).
            flash:          If True, trigger a brief alert/strobe cycle.
            transition_ms:  Transition duration in milliseconds.
        """
        ...

    @abstractmethod
    def get_state(self, deviceid: str | None = None) -> bool | None:
        """
        Return the on/off state of a device.

        Returns:
            True if the device is on, False if off, None if the state is
            unknown or unavailable (e.g. provider not ready, API error).
        """
        ...

    @abstractmethod
    def get_lights(self) -> list[dict]:
        """
        Return all individually addressable lights.

        Returns:
            List of dicts containing at minimum ``{"id": str, "name": str}``.
            May include additional provider-specific keys such as ``"archetype"``.
        """
        ...

    @abstractmethod
    def get_groups(self) -> list[dict]:
        """
        Return all light groups (rooms, zones, scenes, etc.).

        Returns:
            List of dicts: ``{"id": str, "name": str}``.
        """
        ...

    def get_plugs(self) -> list[dict]:
        """
        Return smart plugs or switchable outlets.

        Default implementation returns an empty list. Override in providers
        that support plug devices.

        Returns:
            List of dicts: ``{"id": str, "name": str}``.
        """
        return []

    def discover(self) -> list[dict]:
        """
        Discover controllers or bridges on the local network.

        Default implementation returns an empty list. Override in providers
        that support automatic discovery.
        """
        return []

    def pair(self, **kwargs) -> dict:
        """
        Perform a pairing or authentication flow.

        Default returns an error dict. Override in providers that require a
        pairing step before normal operation.

        Returns:
            dict with at minimum ``{"response": "success" | "error"}``.
        """
        return {"response": "error", "message": "Pairing not supported for this provider"}
