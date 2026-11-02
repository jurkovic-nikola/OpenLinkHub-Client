"""Thin synchronous client for the OpenLinkHub HTTP API.

The server answers almost everything with HTTP 200 and signals success via the
``status`` field of a JSON envelope (1 = ok, 0 = error). This module hides that
convention and raises :class:`ApiError` instead.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from olhclient.api.models import DeviceInfo, Macro, MacroAction
from olhclient.api.receiver_page import parse_receiver_page

INPUT_KINDS = ("media", "keyboard", "mouse")

#: product names OpenLinkHub gives the (hidden) Slipstream receivers
RECEIVER_PRODUCTS = ("SLIPSTREAM", "SLIPSTREAM V2")


class ApiError(Exception):
    """Raised when the server rejects a request or cannot be reached."""

    def __init__(self, message: str, *, http_status: int | None = None, auth_required: bool = False):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.auth_required = auth_required


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class ApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:27003",
        *,
        origin: str | None = None,
        verify: bool | str = True,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        # OpenLinkHub with auth enabled demands an Origin header on every
        # non-GET request that exactly matches its configured authOrigin.
        self.origin = origin or _origin_of(self.base_url)
        self._http = httpx.Client(
            base_url=self.base_url,
            verify=verify,
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._http.close()

    # -- low level ---------------------------------------------------------

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {}
        if method != "GET":
            headers["Origin"] = self.origin
        try:
            response = self._http.request(method, path, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise ApiError(f"Cannot reach OpenLinkHub at {self.base_url}: {exc}") from exc

        if response.status_code == 401:
            raise ApiError("Authentication required", http_status=401, auth_required=True)
        if response.status_code >= 400:
            raise ApiError(response.text.strip() or response.reason_phrase, http_status=response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"Invalid response from {path}") from exc

    def _get_text(self, path: str) -> str:
        """GET a dashboard page (HTML) instead of an API endpoint."""
        try:
            response = self._http.get(path, headers={"Accept": "text/html"})
        except httpx.HTTPError as exc:
            raise ApiError(f"Cannot reach OpenLinkHub at {self.base_url}: {exc}") from exc
        if response.status_code == 401:
            raise ApiError("Authentication required", http_status=401, auth_required=True)
        if response.status_code != 200:
            raise ApiError(response.text.strip() or response.reason_phrase, http_status=response.status_code)
        return response.text

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Request that must come back with ``status == 1``."""
        body = self._request(method, path, payload)
        if body.get("status") != 1:
            raise ApiError(body.get("message") or f"Request to {path} failed")
        return body

    # -- auth --------------------------------------------------------------

    def login(self, username: str, password: str) -> None:
        try:
            response = self._http.post(
                "/auth/login",
                json={"username": username, "password": password},
                headers={"Origin": self.origin},
            )
        except httpx.HTTPError as exc:
            raise ApiError(f"Cannot reach OpenLinkHub at {self.base_url}: {exc}") from exc
        if response.status_code != 204:
            raise ApiError(response.text.strip() or "Login failed", http_status=response.status_code)

    def logout(self) -> None:
        self._request("POST", "/auth/logout")

    # -- reads -------------------------------------------------------------

    def list_devices(self) -> dict[str, DeviceInfo]:
        """Every device OpenLinkHub knows, hidden ones (receivers, clusters) included."""
        devices = self._request("GET", "/api/").get("device") or {}
        return {serial: DeviceInfo.from_json(serial, data or {}) for serial, data in devices.items()}

    def get_device(self, serial: str) -> dict[str, Any]:
        # This endpoint never sets status=1; presence of "device" means success.
        body = self._request("GET", f"/api/devices/{serial}")
        device = body.get("device")
        if not device:
            raise ApiError(body.get("message") or f"Device {serial} not found")
        return device

    def get_receiver(self, serial: str) -> dict[str, Any]:
        """Receiver JSON; read from its dashboard page while the API cannot encode it."""
        try:
            return self.get_device(serial)
        except ApiError as exc:
            if exc.auth_required:
                raise
        try:
            return parse_receiver_page(self._get_text(f"/device/{serial}"))
        except ValueError as exc:
            raise ApiError(f"Receiver {serial} not found") from exc

    def input_actions(self, kind: str) -> dict[int, str]:
        """Return ``{code: name}`` for ``media``, ``keyboard`` or ``mouse`` actions."""
        if kind not in INPUT_KINDS:
            raise ValueError(f"unknown input kind {kind!r}")
        data = self._call("GET", f"/api/input/{kind}").get("data") or {}
        return {int(code): action.get("Name", str(code)) for code, action in data.items()}

    def macros(self) -> dict[int, str]:
        data = self._call("GET", "/api/macro/").get("data") or {}
        return {int(macro_id): macro.get("name", str(macro_id)) for macro_id, macro in data.items()}

    def macro_profiles(self) -> list[Macro]:
        """Every macro with its actions, by id."""
        data = self._call("GET", "/api/macro/").get("data") or {}
        return sorted((Macro.from_json(macro or {}) for macro in data.values()), key=lambda m: m.id)

    def temperature_profiles(self) -> list[str]:
        """Names of the fan/pump speed profiles (this endpoint answers with status 0)."""
        data = self._request("GET", "/api/temperatures/").get("data") or {}
        return sorted(data, key=str.lower)

    def battery_levels(self) -> dict[str, int]:
        data = self._call("GET", "/api/batteryStats").get("data") or {}
        return {serial: int(stats.get("Level", 0)) for serial, stats in data.items()}

    # -- writes ------------------------------------------------------------

    def update_key_assignment(
        self,
        serial: str,
        key_index: int,
        *,
        use_default: bool,
        action_type: int,
        action_value: int,
        press_and_hold: bool = False,
        on_release: bool = False,
        modifier: int = 0,
        kind: str = "mouse",
    ) -> None:
        """``kind`` is the endpoint family (mouse, headset, keyboard, controller); one server handler."""
        payload = {
            "deviceId": serial,
            "keyIndex": key_index,
            "enabled": use_default,
            "pressAndHold": press_and_hold,
            "keyAssignmentType": action_type,
            "keyAssignmentValue": action_value,
            "onRelease": on_release,
        }
        if modifier:
            payload["keyAssignmentModifier"] = modifier
        self._call("POST", f"/api/{kind}/updateKeyAssignment", payload)

    def save_dpi(self, serial: str, stages: dict[int, int]) -> None:
        self._call(
            "POST",
            "/api/mouse/dpi",
            {"deviceId": serial, "stages": {str(index): value for index, value in stages.items()}},
        )

    def save_dpi_colors(self, serial: str, colors: dict[int, str]) -> None:
        """Set the LED colour per DPI stage; ``colors`` maps stage index -> ``#rrggbb``."""
        self._call("POST", "/api/mouse/dpiColors", {"deviceId": serial, "colorZones": _rgb_map(colors)})

    # -- lighting ----------------------------------------------------------

    def set_rgb_effect(self, serial: str, effect: str, channel: int = 0) -> None:
        """``channel`` only matters for hubs; -1 is every channel."""
        self._call("POST", "/api/color", {"deviceId": serial, "channelId": channel, "profile": effect})

    def set_brightness(self, serial: str, percent: int) -> None:
        self._call("POST", "/api/brightness/gradual", {"deviceId": serial, "brightness": percent})

    def set_brightness_mode(self, serial: str, mode: int) -> None:
        """Stepped brightness, a key of the device's ``Brightness`` map."""
        self._call("POST", "/api/brightness", {"deviceId": serial, "brightness": mode})

    def save_zone_colors(self, serial: str, colors: dict[int, str], kind: str = "mouse") -> None:
        """Set the colour per lighting zone; ``colors`` maps zone index -> ``#rrggbb``."""
        self._call("POST", f"/api/{kind}/zoneColors", {"deviceId": serial, "colorZones": _rgb_map(colors)})

    def set_rgb_cluster(self, serial: str, enabled: bool) -> None:
        self._call("POST", "/api/color/setCluster", {"deviceId": serial, "mode": int(enabled)})

    def set_openrgb(self, serial: str, enabled: bool) -> None:
        self._call("POST", "/api/color/setOpenRgbIntegration", {"deviceId": serial, "mode": int(enabled)})

    # -- device settings ---------------------------------------------------

    def set_setting(self, serial: str, endpoint: str, values: dict[str, Any]) -> None:
        """POST ``values`` to ``/api/<endpoint>``, e.g. ``mouse/pollingRate`` with ``{"pollingRate": 2}``."""
        self._call("POST", f"/api/{endpoint}", {"deviceId": serial, **values})

    def set_equalizer(self, serial: str, bands: dict[int, float]) -> None:
        """All ten bands, -12..12 dB."""
        self._call("POST", "/api/headset/equalizer",
                   {"deviceId": serial, "equalizers": {str(i): float(v) for i, v in bands.items()}})

    # -- hubs and coolers ----------------------------------------------------

    def set_speed_profile(self, serial: str, channel: int, profile: str) -> None:
        """Fan/pump speed profile of one channel; -1 is every channel."""
        self._call("POST", "/api/speed", {"deviceId": serial, "channelId": channel, "profile": profile})

    def set_label(self, serial: str, channel: int, label: str, *, rgb_device: bool = False) -> None:
        self._call("POST", "/api/label",
                   {"deviceId": serial, "channelId": channel, "label": label, "deviceType": int(rgb_device)})

    # -- keyboard profiles -------------------------------------------------

    def new_keyboard_profile(self, serial: str, name: str) -> None:
        """Copy the current key layout into a new keyboard profile."""
        self._call("PUT", "/api/keyboard/profile/new", {"deviceId": serial, "keyboardProfileName": name, "new": True})

    def switch_keyboard_profile(self, serial: str, name: str) -> None:
        self._call("POST", "/api/keyboard/profile/change", {"deviceId": serial, "keyboardProfileName": name})

    def delete_keyboard_profile(self, serial: str, name: str) -> None:
        self._call("DELETE", "/api/keyboard/profile/delete", {"deviceId": serial, "keyboardProfileName": name})

    # -- user profiles -----------------------------------------------------

    def switch_user_profile(self, serial: str, name: str) -> None:
        self._call("POST", "/api/userProfile/change", {"deviceId": serial, "userProfileName": name})

    def save_user_profile(self, serial: str, name: str) -> None:
        """Store the current settings as a new user profile called ``name``."""
        self._call("PUT", "/api/userProfile", {"deviceId": serial, "userProfileName": name})

    def delete_user_profile(self, serial: str, name: str) -> None:
        self._call("DELETE", "/api/userProfile/delete", {"deviceId": serial, "userProfileName": name})

    # -- macros ------------------------------------------------------------

    def new_macro(self, name: str) -> None:
        """An empty macro; the server picks its id."""
        self._call("PUT", "/api/macro/new", {"macroName": name})

    def delete_macro(self, macro_id: int) -> None:
        self._call("DELETE", "/api/macro/profile", {"macroId": macro_id})

    def update_macro_settings(self, macro_id: int, repeat: int, repeat_delay: int) -> None:
        """``repeat`` -1 loops the macro until its button is pressed again."""
        self._call("POST", "/api/macro/updateSettings",
                   {"macroId": macro_id, "macroRepeat": repeat, "macroRepeatDelay": repeat_delay})

    def add_macro_action(self, macro_id: int, action: MacroAction) -> None:
        """Append an action; the server gives it the index ``len(actions)``."""
        self._call("POST", "/api/macro/newValue", {
            "macroId": macro_id,
            "macroType": action.action_type,
            "macroValue": action.command,
            "macroDelay": action.delay,
            "macroText": action.text,
            "mousePositionX": action.x,
            "mousePositionY": action.y,
            "mousePositionAbsolute": action.absolute,
        })

    def update_macro_action(self, macro_id: int, index: int, action: MacroAction) -> None:
        """Hold, repeat and mouse position of an action; its type, key, delay and text stay."""
        self._call("POST", "/api/macro/updateValue", {
            "macroId": macro_id,
            "macroIndex": index,
            "pressAndHold": action.hold,
            "actionRepeatValue": action.repeat,
            "actionRepeatDelay": action.repeat_delay,
            "mousePositionX": action.x,
            "mousePositionY": action.y,
            "mousePositionAbsolute": action.absolute,
        })

    def delete_macro_action(self, macro_id: int, index: int) -> None:
        self._call("DELETE", "/api/macro/value", {"macroId": macro_id, "macroIndex": index})


def _rgb_map(colors: dict[int, str]) -> dict[str, dict[str, int]]:
    result = {}
    for index, color in colors.items():
        value = color.lstrip("#")
        if len(value) != 6:
            raise ValueError(f"invalid colour {color!r}")
        result[str(index)] = {"red": int(value[0:2], 16), "green": int(value[2:4], 16), "blue": int(value[4:6], 16)}
    return result
