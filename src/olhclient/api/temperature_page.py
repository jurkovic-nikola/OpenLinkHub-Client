"""Read hardware selectors rendered by OpenLinkHub's temperature dashboard."""

from html.parser import HTMLParser


class TemperatureOptions(HTMLParser):
    selectors = {"hwmonDeviceId", "probeData", "hwmon-probeData", "gpuIndex"}

    def __init__(self):
        super().__init__()
        self.graph_mode = None
        self.options = {}
        self.selector = None
        self.value = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "canvas" and attrs.get("id") == "graphPump":
            self.graph_mode = True
        if tag == "table" and attrs.get("id") == "table":
            self.graph_mode = False
        if tag == "select":
            self.selector = attrs.get("id")
        elif tag == "option" and self.selector in self.selectors:
            self.value = attrs.get("value")
            self.label = []

    def handle_data(self, data):
        if self.value is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.value is not None:
            if self.value != "0;0":  # dashboard's unselected probe
                self.options.setdefault(self.selector, []).append({
                    "value": self.value, "text": "".join(self.label).strip(),
                })
            self.value = None
        elif tag == "select":
            self.selector = None
