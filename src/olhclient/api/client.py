"""Thin synchronous client for the OpenLinkHub HTTP API.

The server answers almost everything with HTTP 200 and signals success via the
``status`` field of a JSON envelope (1 = ok, 0 = error). This module hides that
convention and raises :class:`ApiError` instead.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

INPUT_KINDS = ("media", "keyboard", "mouse")


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

    def list_mice(self) -> dict[str, str]:
        """Return ``{serial: product name}`` for every connected mouse."""
        return self._call("GET", "/api/devices/mouse").get("data") or {}

    def get_device(self, serial: str) -> dict[str, Any]:
        # This endpoint never sets status=1; presence of "device" means success.
        body = self._request("GET", f"/api/devices/{serial}")
        device = body.get("device")
        if not device:
            raise ApiError(body.get("message") or f"Device {serial} not found")
        return device

    def input_actions(self, kind: str) -> dict[int, str]:
        """Return ``{code: name}`` for ``media``, ``keyboard`` or ``mouse`` actions."""
        if kind not in INPUT_KINDS:
            raise ValueError(f"unknown input kind {kind!r}")
        data = self._call("GET", f"/api/input/{kind}").get("data") or {}
        return {int(code): action.get("Name", str(code)) for code, action in data.items()}

    def macros(self) -> dict[int, str]:
        data = self._call("GET", "/api/macro/").get("data") or {}
        return {int(macro_id): macro.get("name", str(macro_id)) for macro_id, macro in data.items()}

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
    ) -> None:
        self._call(
            "POST",
            "/api/mouse/updateKeyAssignment",
            {
                "deviceId": serial,
                "keyIndex": key_index,
                "enabled": use_default,
                "pressAndHold": press_and_hold,
                "keyAssignmentType": action_type,
                "keyAssignmentValue": action_value,
                "onRelease": on_release,
            },
        )

    def save_dpi(self, serial: str, stages: dict[int, int]) -> None:
        self._call(
            "POST",
            "/api/mouse/dpi",
            {"deviceId": serial, "stages": {str(index): value for index, value in stages.items()}},
        )
