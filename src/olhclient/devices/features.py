"""Features a device module can declare.

Each feature has a generic QML panel pair (sidebar list + editor) under
``qml/features`` and a controller in :mod:`olhclient.core.features`. Device
modules only declare which features they support; they can override the QML
for a feature through :meth:`DeviceModule.qml_override`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class FeatureInfo:
    title: str
    list_qml: str
    editor_qml: str


class Feature(Enum):
    KEY_REMAP = FeatureInfo("Key remapping", "features/KeyRemapList.qml", "features/KeyRemapEditor.qml")
    KEYBOARD_KEYS = FeatureInfo("Keys", "features/KeyboardKeysList.qml", "features/KeyRemapEditor.qml")
    DPI = FeatureInfo("DPI", "features/DpiList.qml", "features/DpiEditor.qml")
    LIGHTING = FeatureInfo("Lighting", "features/LightingList.qml", "features/LightingEditor.qml")
    FANS = FeatureInfo("Fans & pumps", "features/FansList.qml", "features/FansEditor.qml")
    EQUALIZER = FeatureInfo("Equalizer", "features/EqualizerList.qml", "features/EqualizerEditor.qml")
    SETTINGS = FeatureInfo("Device settings", "features/SettingsList.qml", "features/SettingsEditor.qml")

    @property
    def id(self) -> str:
        return self.name.lower()

    @property
    def title(self) -> str:
        return self.value.title
