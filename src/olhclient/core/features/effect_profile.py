from __future__ import annotations

import copy
import re
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.core.features.base import FeatureController

#: effects without settings of their own (the device-named ones use zone or key colours)
NOT_EDITABLE = {"off", "custom", "controller", "led", "mouse", "keyboard", "headset", "stand", "mousepad"}
#: effects that make their own colours
NO_COLORS = {"rainbow", "pastelrainbow", "spiralrainbow", "pastelspiralrainbow", "rainbowwave", "watercolor",
             "nebula"}
#: effects that only use the start colour
START_ONLY = {"static", "rotator"}
#: effects whose colours are tied to a temperature each
TEMPERATURE = {"cpu-temperature", "gpu-temperature", "liquid-temperature"}
#: effects whose speed OpenLinkHub does not let you change
FIXED_SPEED = {"static", "storm", *TEMPERATURE}
#: effects with a 1-3 speed (keyboard hardware effects); the rest have 1-10 in steps of 0.1
STEPPED_SPEED = {"tlk", "tlr", "spiralrainbow", "rainbowwave", "rain", "visor", "colorwave"}
#: effects with OpenLinkHub's alternate colours option (Slipstream devices only)
ALTERNATE = {"colorpulse", "colorshift", "tlk", "tlr", "rain", "visor", "colorwave", "watercolor"}
DIRECTIONS = {1: "Top to bottom", 2: "Bottom to top", 4: "Left to right", 5: "Right to left"}
SLOT_NAMES = {"start": "Start", "middle": "Middle", "end": "End"}
#: the drivers accept colour temperatures up to 105 °C, and a temperature range up to 100 °C
MAX_COLOR_TEMPERATURE = 105
MAX_TEMPERATURE = 100
HEX = re.compile(r"^#[0-9a-f]{6}$")


def effect_title(effect: str) -> str:
    return effect.replace("-", " ").capitalize()


def color_slots(effect: str) -> tuple[str, ...]:
    if effect in NO_COLORS:
        return ()
    if effect in START_ONLY:
        return ("start",)
    if effect in TEMPERATURE:
        return ("start", "middle", "end")
    return ("start", "end")


def hex_color(color: dict[str, Any] | None) -> str:
    color = color or {}
    return "#" + "".join(f"{max(0, min(255, round(color.get(c, 0)))):02x}" for c in ("red", "green", "blue"))


def rgb(value: str) -> dict[str, int]:
    return {"red": int(value[1:3], 16), "green": int(value[3:5], 16), "blue": int(value[5:7], 16)}


class EffectProfile(QObject):
    """Settings of one lighting effect: OpenLinkHub's RGB profile of that effect.

    The profile belongs to the device, so every zone or channel showing the
    effect uses the same settings. They are edited as a draft and saved
    together, like OpenLinkHub's RGB editor does.

    ``values`` is what QML edits: ``colors`` and ``temperatures`` (one per
    entry of ``colorNames``), ``speed``, ``minTemp``/``maxTemp``,
    ``direction``, ``alternate`` and ``gradient`` (``{color, position,
    brightness}`` per stop, position and brightness 0-1).
    """

    changed = Signal()
    savingChanged = Signal()

    def __init__(self, controller: FeatureController):
        super().__init__(controller)
        self._controller = controller
        self._effect = ""
        self._profile: dict[str, Any] | None = None
        self._saving = False

    def load(self, effect: str) -> None:
        """Show the settings of ``effect``; fetched only when the effect changes."""
        if effect == self._effect:
            return
        self._effect = effect
        self._set_profile(None)
        if effect and effect not in NOT_EDITABLE:
            self._fetch()

    def _fetch(self) -> None:
        session, effect = self._controller.session, self._effect

        def done(profile: dict[str, Any]) -> None:
            if effect == self._effect:
                self._set_profile(profile)

        # A driver without RGB profiles refuses: then there is nothing to edit.
        session.worker.submit(lambda: session.api.rgb_profile(session.serial, effect),
                              on_done=done, on_error=lambda exc: None, owner=self)

    def _set_profile(self, profile: dict[str, Any] | None) -> None:
        if profile != self._profile:
            self._profile = profile
            self.changed.emit()

    def _slots(self) -> tuple[str, ...]:
        return () if self.hasGradient else color_slots(self._effect)

    # -- QML API -----------------------------------------------------------

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return bool(self._profile)

    @Property(str, notify=changed)
    def effectTitle(self) -> str:
        return effect_title(self._effect)

    @Property("QStringList", notify=changed)
    def colorNames(self) -> list[str]:
        return [SLOT_NAMES[slot] for slot in self._slots()]

    @Property(bool, notify=changed)
    def hasTemperatures(self) -> bool:
        return self._effect in TEMPERATURE

    @Property(bool, notify=changed)
    def hasTempRange(self) -> bool:
        return self._effect == "probe-temperature"

    @Property(bool, notify=changed)
    def hasSpeed(self) -> bool:
        return self._effect not in FIXED_SPEED

    @Property(int, notify=changed)
    def speedMax(self) -> int:
        return 3 if self._effect in STEPPED_SPEED else 10

    @Property(float, notify=changed)
    def speedStep(self) -> float:
        return 1 if self._effect in STEPPED_SPEED else 0.1

    @Property(bool, notify=changed)
    def hasDirection(self) -> bool:
        return bool(self._profile and self._profile.get("rgbDirection"))

    @Property("QVariantList", constant=True)
    def directions(self) -> list[dict[str, Any]]:
        return [{"value": value, "text": text} for value, text in DIRECTIONS.items()]

    @Property(bool, notify=changed)
    def hasAlternate(self) -> bool:
        return self._effect in ALTERNATE

    @Property(bool, notify=changed)
    def hasGradient(self) -> bool:
        return bool(self._profile and self._profile.get("gradients"))

    @Property("QVariantMap", notify=changed)
    def values(self) -> dict[str, Any]:
        profile = self._profile or {}
        stops = sorted((profile.get("gradients") or {}).values(), key=lambda s: s.get("position", 0))
        slots = self._slots()
        return {
            "colors": [hex_color(profile.get(slot)) for slot in slots],
            "temperatures": [round((profile.get(slot) or {}).get("temperature", 0)) for slot in slots],
            "speed": round(float(profile.get("speed") or 1), 1),
            "minTemp": round(profile.get("minTemp") or 0),
            "maxTemp": round(profile.get("maxTemp") or 0),
            "direction": int(profile.get("rgbDirection") or 0),
            "alternate": bool(profile.get("alternateColors")),
            "gradient": [{"color": hex_color(stop), "position": round(stop.get("position", 0), 2),
                          "brightness": round(stop.get("brightness", 1), 2)} for stop in stops],
        }

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    @Slot("QVariantMap")
    def save(self, values: dict[str, Any]) -> None:
        """Save a draft of ``values``. Nothing is sent when nothing changed."""
        session = self._controller.session
        if not self._profile:
            return
        try:
            draft = self._normalise(values)
        except ValueError as exc:
            session.report_message(str(exc), error=True)
            return
        if draft == self.values:
            session.report_message("No changes to save")
            return
        serial, effect, profile = session.serial, self._effect, self._apply(draft)

        def finished(ok: bool) -> None:
            self._set_saving(False)
            if ok and effect == self._effect:
                self._fetch()

        self._set_saving(True)
        self._controller.write(lambda: session.api.save_rgb_profile(serial, effect, profile),
                               f"{effect_title(effect)} saved", done=finished)

    def _normalise(self, values: dict[str, Any]) -> dict[str, Any]:
        """``values`` from QML, checked and rounded like ``self.values``."""
        current = self.values
        colors = [str(c).lower() for c in values.get("colors", current["colors"])]
        if len(colors) != len(current["colors"]) or not all(HEX.match(c) for c in colors):
            raise ValueError("Invalid colour")
        temperatures = [round(float(t)) for t in values.get("temperatures", current["temperatures"])]
        if len(temperatures) != len(colors) or not all(0 <= t <= MAX_COLOR_TEMPERATURE for t in temperatures):
            raise ValueError(f"Temperatures must be between 0 and {MAX_COLOR_TEMPERATURE} °C")
        speed = round(float(values.get("speed", current["speed"])), 1)
        if self.hasSpeed and not 1 <= speed <= self.speedMax:
            raise ValueError(f"Speed must be between 1 and {self.speedMax}")
        min_temp = round(float(values.get("minTemp", current["minTemp"])))
        max_temp = round(float(values.get("maxTemp", current["maxTemp"])))
        if not 0 <= min_temp <= max_temp <= MAX_TEMPERATURE:
            raise ValueError(f"The temperature range must lie between 0 and {MAX_TEMPERATURE} °C, lowest first")
        direction = int(values.get("direction", current["direction"]))
        if self.hasDirection and direction not in DIRECTIONS:
            raise ValueError("Unknown direction")
        gradient = [{"color": str(stop["color"]).lower(), "position": round(float(stop["position"]), 2),
                     "brightness": round(float(stop["brightness"]), 2)}
                    for stop in values.get("gradient", current["gradient"])]
        if self.hasGradient and len(gradient) < 2:
            raise ValueError("A gradient needs at least two colours")
        if not all(HEX.match(s["color"]) and 0 <= s["position"] <= 1 and 0 <= s["brightness"] <= 1 for s in gradient):
            raise ValueError("Invalid gradient colour")
        return {
            "colors": colors,
            "temperatures": temperatures,
            "speed": speed,
            "minTemp": min_temp,
            "maxTemp": max_temp,
            "direction": direction,
            "alternate": bool(values.get("alternate", current["alternate"])),
            "gradient": sorted(gradient, key=lambda s: s["position"]),
        }

    def _apply(self, draft: dict[str, Any]) -> dict[str, Any]:
        """The fetched profile with ``draft`` applied."""
        profile = copy.deepcopy(self._profile)
        for slot, color, temperature in zip(self._slots(), draft["colors"], draft["temperatures"]):
            profile[slot] = {**(profile.get(slot) or {}), **rgb(color), "temperature": temperature}
        profile.update(speed=draft["speed"], minTemp=draft["minTemp"], maxTemp=draft["maxTemp"],
                       rgbDirection=draft["direction"], alternateColors=draft["alternate"])
        if self.hasGradient:
            profile["gradients"] = {
                str(i): {**rgb(s["color"]), "brightness": s["brightness"], "position": s["position"],
                         "Hex": s["color"].upper()}
                for i, s in enumerate(draft["gradient"])}
        return profile

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
