"""Controls and member devices of the OpenLinkHub RGB cluster."""

from PySide6.QtCore import QObject, Property, Signal, Slot

from olhclient.core.features.effect_profile import EffectProfile


class Cluster(QObject):
    """Also stands in for the feature controller and session that ``EffectProfile`` expects."""

    changed = Signal()
    failed = Signal(object)
    message = Signal(str, bool)
    serial = "cluster"

    def __init__(self, api, worker, parent):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self._busy = False
        self._data = {}
        self._effect_profile = EffectProfile(self)

    @property
    def session(self):
        return self

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property("QVariantMap", notify=changed)
    def data(self):
        return self._data

    @Property(QObject, constant=True)
    def effectProfile(self):
        return self._effect_profile

    def _refresh(self, write=None, *args):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()

        def fetch():
            if write is not None:
                write("cluster", *args)
            device = self.api.get_device("cluster")
            profile = device["DeviceProfile"]
            return {
                "brightness": profile["BrightnessSlider"],
                "effect": profile["RGBProfile"],
                "modes": device.get("RGBModes") or [],
                "members": device.get("Controllers") or [],
            }

        def done(data):
            self._data = data
            self._busy = False
            self.changed.emit()
            self._effect_profile.load(data.get("effect", ""))

        def failed(exc):
            done({})
            self.failed.emit(exc)

        self.worker.submit(fetch, on_done=done, on_error=failed, owner=self)

    @Slot()
    def reload(self):
        self._refresh()

    @Slot(int)
    def setBrightness(self, value):
        if 0 <= value <= 100 and value != self._data.get("brightness"):
            self._refresh(self.api.set_brightness, value)

    @Slot(str)
    def setEffect(self, effect):
        if effect in self._data.get("modes", []) and effect != self._data.get("effect"):
            self._refresh(self.api.set_rgb_effect, effect, 0)

    def report_message(self, text, *, error=False):
        self.message.emit(text, error)

    def report_error(self, exc):
        self.failed.emit(exc)

    def write(self, call, success, *, done=None):
        """Like ``FeatureController.write``: report the outcome and reload either way."""

        def finished(_):
            if done:
                done(True)
            self.report_message(success)
            self.reload()

        def failed(exc):
            if done:
                done(False)
            self.report_error(exc)
            self.reload()

        self.worker.submit(call, on_done=finished, on_error=failed, owner=self)
