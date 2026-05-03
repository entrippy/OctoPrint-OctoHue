from __future__ import annotations

import requests

from .base import LightProvider

# Mirek (reciprocal megakelvin) range supported by colour-temperature lights.
# 153 mirek ≈ 6500 K (cool white); 500 mirek ≈ 2000 K (warm white).
_MIREK_MIN = 153
_MIREK_MAX = 500

# WLED CCT range: 0 = cool white, 255 = warm white.
_WLED_CCT_MIN = 0
_WLED_CCT_MAX = 255


def _mirek_to_wled_cct(mirek: int) -> int:
    """Convert a mirek colour-temperature value to a WLED CCT byte (0–255)."""
    clamped = max(_MIREK_MIN, min(_MIREK_MAX, mirek))
    normalised = (clamped - _MIREK_MIN) / (_MIREK_MAX - _MIREK_MIN)
    return round(_WLED_CCT_MIN + normalised * (_WLED_CCT_MAX - _WLED_CCT_MIN))


def _pct_to_wled_bri(pct: float) -> int:
    """Convert a brightness percentage (0–100) to a WLED brightness byte (0–255)."""
    clamped = max(0.0, min(100.0, pct))
    return round(clamped * 255 / 100)


def _hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
    """Parse a ``'#RRGGBB'`` hex string and return an ``(r, g, b)`` tuple."""
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class WledProvider(LightProvider):
    """
    Light provider for WLED controllers via the JSON API.

    Communicates over plain HTTP with no authentication or pairing step.
    A single WLED controller is addressed by its hostname or IP address;
    the ``deviceid`` parameter on ``set_light`` / ``get_state`` is ignored
    because WLED does not have individually addressable sub-devices.

    WLED API reference: https://kno.wled.ge/interfaces/json-api/

    Settings keys expected by ``setup()``:
        ``bridgeaddr`` — hostname or IP address of the WLED controller
        (shared generic key across all providers).
    """

    def __init__(self, logger) -> None:
        super().__init__(logger)
        self._address: str | None = None
        self._session: requests.Session | None = None

    def setup(self, settings: dict) -> None:
        """
        Initialise or reinitialise the provider from settings.

        Expected key: ``bridgeaddr`` — the hostname or IP of the WLED
        controller (shared generic key across all providers).
        An empty or missing value leaves the provider not ready.
        """
        address = (settings.get("bridgeaddr") or "").strip()
        self._logger.debug(
            f"WLED address is {address if address else 'not set — please configure in settings'}"
        )
        if address:
            self._address = address
            self._session = requests.Session()
            self._logger.debug(f"WLED provider configured for {address}")
        else:
            self._address = None
            self._session = None

    @property
    def is_ready(self) -> bool:
        return self._address is not None and self._session is not None

    # ------------------------------------------------------------------
    # Internal HTTP transport
    # ------------------------------------------------------------------

    def _get(self, path: str) -> dict:
        """Send a GET to the WLED JSON API and return the parsed response."""
        if not self.is_ready:
            return {}
        url = f"http://{self._address}/{path}"
        self._logger.info(f"WLED GET {url}")
        try:
            r = self._session.get(url, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._logger.error(f"WLED GET {path} failed: {e}")
            return {}

    def _post(self, path: str, payload: dict) -> dict:
        """Send a POST to the WLED JSON API and return the parsed response."""
        if not self.is_ready:
            return {}
        url = f"http://{self._address}/{path}"
        self._logger.debug(f"WLED POST {url} payload={payload}")
        try:
            r = self._session.post(url, json=payload, timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self._logger.error(f"WLED POST {path} failed: {e}")
            return {}

    # ------------------------------------------------------------------
    # LightProvider interface
    # ------------------------------------------------------------------

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
        Set the state of the WLED controller.

        The ``deviceid`` parameter is ignored; WLED has a single addressable
        state per controller.  Brightness is converted from percentage to
        the 0–255 byte scale WLED expects.  Colour temperature (mirek) is
        converted to WLED's CCT byte (0 = cool, 255 = warm).

        Note: WLED's ``transition`` field is in units of 100 ms, so
        ``transition_ms`` is divided by 100 and rounded.

        Note: WLED does not have a native single-shot alert/breathe effect
        equivalent; the ``flash`` parameter is not implemented and is silently
        ignored.
        """
        payload: dict = {"on": on}

        if on:
            if brightness_pct is not None:
                payload["bri"] = _pct_to_wled_bri(brightness_pct)

            seg: dict = {}

            if ct_mirek is not None:
                seg["cct"] = _mirek_to_wled_cct(ct_mirek)
            elif colour_hex is not None:
                r, g, b = _hex_to_rgb(colour_hex)
                seg["col"] = [[r, g, b]]

            if seg:
                payload["seg"] = [seg]

        if transition_ms is not None:
            # WLED transition is in 100 ms units
            payload["transition"] = round(transition_ms / 100)

        self._post("json/state", payload)

    def get_state(self, deviceid: str | None = None) -> bool | None:
        """
        Query the on/off state of the WLED controller.

        Returns True if on, False if off, None if the controller is unreachable
        or the response is malformed.
        """
        response = self._get("json/state")
        try:
            return bool(response["on"])
        except (KeyError, TypeError):
            return None

    def get_lights(self) -> list[dict]:
        """
        Return a single-entry list representing the WLED controller.

        Uses ``GET /json/info`` to retrieve the controller name.  Falls back to
        the configured address if the info call fails.
        """
        info = self._get("json/info")
        name = info.get("name") or self._address or "WLED"
        return [{"id": "wled", "name": name}]

    def get_groups(self) -> list[dict]:
        """WLED has no concept of groups; always returns an empty list."""
        return []

    def pair(self, **kwargs) -> dict:
        """
        WLED requires no pairing.

        Returns a success response immediately so the UI pairing flow can
        treat WLED as already paired on initial setup.
        """
        return {"response": "success"}
