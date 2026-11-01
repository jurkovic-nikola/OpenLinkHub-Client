"""Read a Slipstream receiver from its OpenLinkHub dashboard page.

OpenLinkHub cannot serve the receiver as JSON: its driver struct
(src/devices/slipstream/slipstream.go) has an exported func field, so
``json.Marshal`` fails and ``GET /api/devices/{serial}`` answers with an empty
body. The page ``/device/{serial}`` (web/slipstream.html) renders the same data;
this module turns it back into the JSON shape of the driver struct, so
:meth:`ReceiverState.from_json` reads both.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


class _ReceiverPage(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.serial: str | None = None
        self.product: str | None = None
        self.firmware: str | None = None
        self.rates: dict[int, str] = {}
        self.selected = 0
        self.rows: list[list[str]] = []
        self._in_main = False
        self._in_select = False
        self._in_body = False
        self._row: list[str] | None = None
        self._option: int | None = None
        # (field, closing tag) of the element whose text is being collected
        self._capture: tuple[str, str] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "input" and attr.get("id") == "deviceId":
            self.serial = attr.get("value") or ""
        if tag == "main":
            self._in_main = True
        if not self._in_main:  # the sidebar also has meta-value fields
            return
        classes = (attr.get("class") or "").split()
        if tag == "div" and "card-header" in classes and self.product is None:
            self._start("product", "div")
        elif tag == "span" and "meta-value" in classes and self.firmware is None:
            self._start("firmware", "span")
        elif tag == "select" and attr.get("id") == "pollingRate":
            self._in_select = True
        elif tag == "option" and self._in_select:
            self._option = int(attr.get("value") or 0)
            if "selected" in attr:
                self.selected = self._option
            self._start("option", "option")
        elif tag == "tbody":
            self._in_body = True
        elif tag == "tr" and self._in_body:
            self._row = []
        elif tag == "td" and self._row is not None:
            self._start("cell", "td")

    def handle_endtag(self, tag: str) -> None:
        if self._capture and self._capture[1] == tag:
            name = self._capture[0]
            text = " ".join("".join(self._text).split())
            self._capture = None
            if name == "product":
                self.product = text
            elif name == "firmware":
                self.firmware = text
            elif name == "option" and self._option is not None:
                self.rates[self._option] = text
            elif name == "cell" and self._row is not None:
                self._row.append(text)
        elif tag == "select":
            self._in_select = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "tbody":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._text.append(data)

    def _start(self, name: str, closing_tag: str) -> None:
        self._capture = (name, closing_tag)
        self._text = []


def parse_receiver_page(html: str) -> dict[str, Any]:
    """Device JSON (``serial``, ``product``, ``PollingRates``...) from the page HTML."""
    page = _ReceiverPage()
    page.feed(html)
    page.close()
    if not page.serial or page.product is None:
        raise ValueError("not a Slipstream receiver page")
    paired = {}
    for row in page.rows:  # ID (product id), device, serial
        if len(row) >= 3 and row[0].isdigit():
            paired[row[0]] = {"product": row[1], "serial": row[2]}
    return {
        "serial": page.serial,
        "product": page.product,
        "firmware": page.firmware or "",
        "PollingRates": {str(k): v for k, v in page.rates.items()},
        "DeviceProfile": {"PollingRate": page.selected},
        "PairedDevices": paired,
    }
