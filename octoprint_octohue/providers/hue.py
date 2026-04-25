from __future__ import annotations

import os
import ssl

import requests
from requests.adapters import HTTPAdapter

from .base import LightProvider

# ---------------------------------------------------------------------------
# The Hue bridge TLS certificate uses the bridge serial number as its CN/SAN
# rather than its IP address, so hostname verification cannot succeed.
# We still verify the certificate chain against the bundled Signify root CA
# to confirm the cert was issued by Signify rather than an arbitrary attacker.
# ---------------------------------------------------------------------------
_CA_BUNDLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signify-root-ca.pem")


class _SignifyAdapter(HTTPAdapter):
    """Custom HTTPS adapter that verifies against the Signify root CA."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(cafile=_CA_BUNDLE)
        ctx.check_hostname = False
        kwargs["ssl_context"] = ctx
        kwargs["assert_hostname"] = False
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        ctx = ssl.create_default_context(cafile=_CA_BUNDLE)
        ctx.check_hostname = False
        proxy_kwargs["ssl_context"] = ctx
        proxy_kwargs["assert_hostname"] = False
        return super().proxy_manager_for(proxy, **proxy_kwargs)


class HueProvider(LightProvider):
    """
    Light provider for Philips Hue via the v2 CLIP API.

    Communicates over HTTPS, verified against the bundled Signify root CA
    certificate. Device and group IDs are UUIDs (Hue v2 format).
    """

    DISCOVERY_URL = "https://discovery.meethue.com/"

    def __init__(self, logger) -> None:
        super().__init__(logger)
        self._pbridge: dict | None = None
        self._session: requests.Session | None = None
        self._lampid: str | None = None
        self._lampisgroup: bool = False
        self._plugid: str = ""

    def setup(self, settings: dict) -> None:
        """
        Initialise from settings.

        Expected keys: ``bridgeaddr``, ``husername``, ``lampid``,
        ``lampisgroup``, ``plugid``.
        """
        bridgeaddr = settings.get("bridgeaddr") or ""
        husername = settings.get("husername") or ""
        self._lampid = settings.get("lampid") or None
        self._lampisgroup = bool(settings.get("lampisgroup", False))
        self._plugid = settings.get("plugid") or ""

        self._logger.debug(
            f"Bridge Address is {bridgeaddr if bridgeaddr else 'Please set Bridge Address in settings'}"
        )
        self._logger.debug(
            f"Hue Username is {husername if husername else 'Please set Hue Username in settings'}"
        )

        if bridgeaddr and husername:
            self._pbridge = {"addr": bridgeaddr, "key": husername}
            session = requests.Session()
            session.mount("https://", _SignifyAdapter())
            self._session = session
            self._logger.debug(f"Bridge established at: {bridgeaddr}")
        else:
            self._pbridge = None
            self._session = None

    @property
    def is_ready(self) -> bool:
        return self._pbridge is not None and self._session is not None

    # ------------------------------------------------------------------
    # Internal HTTP transport
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        """
        Send an HTTPS request to the Hue v2 CLIP API.

        Parameters:
            method:  HTTP method (``'GET'``, ``'PUT'``, etc.)
            path:    Resource path relative to ``/clip/v2/resource/``
                     (e.g. ``'light/uuid'``).
            payload: JSON body for PUT requests.

        Returns:
            Parsed JSON response dict, or an empty dict on error.
        """
        if not self.is_ready:
            return {}
        url = f"https://{self._pbridge['addr']}/clip/v2/resource/{path}"
        headers = {"hue-application-key": self._pbridge['key']}
        self._logger.info(f"Hue API {method} {url}" + (f" payload={payload}" if payload else ""))
        try:
            r = self._session.request(method, url, headers=headers, json=payload)
            body = r.json()
            if r.status_code not in (200, 207):
                self._logger.warning(f"Hue API {method} {path} returned HTTP {r.status_code}: {body}")
            else:
                errors = body.get("errors", [])
                if errors:
                    self._logger.warning(f"Hue API {method} {path} returned errors: {errors}")
            return body
        except Exception as e:
            self._logger.error(f"Hue API error ({method} {path}): {e}")
            return {}

    # ------------------------------------------------------------------
    # Colour conversion (Hue-specific: xy chromaticity)
    # ------------------------------------------------------------------

    @staticmethod
    def rgb_to_xy(red: int | str, green: int | None = None, blue: int | None = None) -> list[float] | None:
        """
        Convert an RGB colour to CIE 1931 xy chromaticity coordinates.

        Accepts either three 8-bit integers or a single ``'#RRGGBB'`` hex string
        as ``red``.

        Returns:
            ``[x, y]`` chromaticity coordinates, or ``None`` for black
            (``#000000``) — the caller should skip the colour change entirely
            when ``None`` is returned.

        Raises:
            ValueError: If ``red`` is a string that is not a valid ``'#RRGGBB'``
                        hex value, or if ``green``/``blue`` are omitted when
                        ``red`` is an integer.
        """
        if isinstance(red, str):
            try:
                red, green, blue = int(red[1:3], 16), int(red[3:5], 16), int(red[5:], 16)
            except ValueError:
                raise ValueError("Invalid hex string format")
        elif green is None or blue is None:
            raise ValueError("green and blue are required when red is an integer")

        red_s = float(red) / 255.0
        green_s = float(green) / 255.0
        blue_s = float(blue) / 255.0

        # Apply sRGB gamma correction
        red_s = red_s / 12.92 if red_s <= 0.04045 else ((red_s + 0.055) / 1.055) ** 2.4
        green_s = green_s / 12.92 if green_s <= 0.04045 else ((green_s + 0.055) / 1.055) ** 2.4
        blue_s = blue_s / 12.92 if blue_s <= 0.04045 else ((blue_s + 0.055) / 1.055) ** 2.4

        # sRGB → XYZ (Wide RGB D65)
        x = 0.4124 * red_s + 0.3576 * green_s + 0.1805 * blue_s
        y = 0.2126 * red_s + 0.7152 * green_s + 0.0722 * blue_s
        z = 0.0193 * red_s + 0.1192 * green_s + 0.9505 * blue_s

        if x + y + z == 0:
            return None  # Black has no chromaticity

        norm_x = x / (x + y + z)
        norm_y = y / (x + y + z)
        return [norm_x, norm_y]

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
        Set the state of a Hue light or grouped_light via the v2 API.

        Builds the nested v2 payload and PUTs it to the correct endpoint.
        Brightness is sent as a 0–100 percentage; ct is sent in mirek;
        colour is converted from hex to CIE xy chromaticity.
        """
        if not self.is_ready:
            return

        target = deviceid or self._lampid
        payload: dict = {"on": {"on": on}}

        if on:
            if brightness_pct is not None:
                payload["dimming"] = {"brightness": min(float(brightness_pct), 100.0)}
            if ct_mirek is not None:
                payload["color_temperature"] = {"mirek": ct_mirek}
            elif colour_hex is not None:
                xy = self.rgb_to_xy(colour_hex)
                if xy is not None:
                    payload["color"] = {"xy": {"x": xy[0], "y": xy[1]}}
            if flash:
                # v1 lselect → v2 breathe
                payload["alert"] = {"action": "breathe"}
            if transition_ms is not None:
                payload["dynamics"] = {"duration": transition_ms}

        # Plugs always use the light endpoint even when lampisgroup is True
        is_group = self._lampisgroup and target != self._plugid
        endpoint = f"grouped_light/{target}" if is_group else f"light/{target}"
        self._request("PUT", endpoint, payload)

    def get_state(self, deviceid: str | None = None) -> bool | None:
        """
        Query the on/off state of a Hue light or group via the v2 API.

        Returns True if on, False if off, None if the bridge is not ready
        or the API response is unexpected.
        """
        if not self.is_ready:
            return None

        target = deviceid or self._lampid
        if self._lampisgroup:
            response = self._request("GET", f"grouped_light/{target}")
        else:
            response = self._request("GET", f"light/{target}")

        data = response.get("data", [])
        if data:
            try:
                return data[0]["on"]["on"]
            except (KeyError, IndexError):
                self._logger.warning(f"Unexpected get_state response format: {data[0]}")
                return None
        return None

    def get_lights(self) -> list[dict]:
        """
        Return all Hue lights with their id, name, and archetype.

        Returns an empty list if the bridge is not ready.
        """
        response = self._request("GET", "light")
        return [
            {
                "id": d["id"],
                "name": d["metadata"]["name"],
                "archetype": d.get("metadata", {}).get("archetype", ""),
            }
            for d in response.get("data", [])
        ]

    def get_groups(self) -> list[dict]:
        """
        Return all Hue rooms and zones as named group entries.

        Each entry uses the ``grouped_light`` service UUID as its ``id`` so the
        same UUID can be used with the v2 grouped_light endpoint.
        """
        groups = []
        for resource_type in ("room", "zone"):
            response = self._request("GET", resource_type)
            for item in response.get("data", []):
                name = item.get("metadata", {}).get("name", "")
                grouped_light_id = next(
                    (s["rid"] for s in item.get("services", []) if s.get("rtype") == "grouped_light"),
                    None,
                )
                if grouped_light_id and name:
                    groups.append({"id": grouped_light_id, "name": name})
        return groups

    def get_plugs(self) -> list[dict]:
        """Return Hue devices whose archetype is ``'plug'``."""
        return [
            {"id": d["id"], "name": d["name"]}
            for d in self.get_lights()
            if d.get("archetype") == "plug"
        ]

    def discover(self) -> list[dict]:
        """
        Query the Meethue discovery service and return discovered bridges.

        Returns an empty list on network error.
        """
        try:
            r = requests.get(self.DISCOVERY_URL, timeout=5)
            return r.json()
        except Exception as e:
            self._logger.error(f"Hue bridge discovery failed: {e}")
            return []

    def pair(self, **kwargs) -> dict:
        """
        Pair with a Hue bridge using the v1 link-button flow.

        Expected kwarg: ``bridgeaddr`` — the IP address or hostname of the bridge.

        Returns:
            On success: ``{"response": "success", "bridgeaddr": str, "husername": str}``
            On error:   ``{"response": "error"}``

        Note:
            Pairing uses the v1 ``/api`` endpoint — this is correct and
            unchanged in v2. The resulting token is valid for all v2 API calls.
        """
        bridgeaddr = kwargs.get("bridgeaddr", "")
        self._logger.debug(f"Pairing with bridge at {bridgeaddr}")
        try:
            pair_session = requests.Session()
            pair_session.mount("https://", _SignifyAdapter())
            r = pair_session.post(
                f"https://{bridgeaddr}/api",
                json={"devicetype": "octoprint#octohue"},
            )
            result = r.json()[0]
        except Exception as e:
            self._logger.error(f"Hue pairing error: {e}")
            return {"response": "error"}

        if "error" in result:
            return {"response": "error"}

        if "success" in result:
            token = result["success"]["username"]
            self._logger.debug(f"New Hue API key acquired")
            return {"response": "success", "bridgeaddr": bridgeaddr, "husername": token}

        return {"response": "error"}
