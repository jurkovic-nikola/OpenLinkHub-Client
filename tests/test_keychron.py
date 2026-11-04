"""Keychron keyboards: hidraw discovery, the raw HID protocol, keycodes, the session and its controllers."""

import os
import stat

import pytest

from olhclient.keychron import keycodes
from olhclient.keychron.boards import BOARDS
from olhclient.keychron.device import identify, read_state, scan
from olhclient.keychron.hidraw import HidError, HidrawDevice, enumerate_devices, has_usage
from olhclient.keychron.protocol import KeychronClient, KeychronError, RgbValue
from tests.fake_keychron import RECEIVER, RECEIVER_SERIAL, SERIAL, V3_ANSI, FakeKeyboard, device, interface, receiver

#: the raw HID descriptor of Keychron's firmware (zmk_hid_launcher_report_desc)
VIA_DESCRIPTOR = bytes.fromhex("0660ff0961a101096215002600ff95207508810209631500" "2600ff952075089102c0")
#: a boot keyboard descriptor (start of it)
KEYBOARD_DESCRIPTOR = bytes.fromhex("05010906a101050719e029e71500250175019508810295017508810305081901")


# -- hidraw -----------------------------------------------------------------


def test_report_descriptor_usage():
    assert has_usage(VIA_DESCRIPTOR, 0xFF60, 0x61)
    assert not has_usage(VIA_DESCRIPTOR, 0xFF60, 0x99)
    assert not has_usage(KEYBOARD_DESCRIPTOR, 0xFF60, 0x61)
    assert not has_usage(b"\x06\x60", 0xFF60, 0x61)  # cut short


def _node(sysfs, name, hid_id, descriptor, phys="usb-0000:00:14.0-2/input1"):
    device = sysfs / name / "device"
    device.mkdir(parents=True)
    (device / "uevent").write_text(f"HID_ID={hid_id}\nHID_NAME=Keychron Keychron V3 Ultra 8K\nHID_PHYS={phys}\nHID_UNIQ=\n")
    (device / "report_descriptor").write_bytes(descriptor)


def test_enumerate_finds_the_via_interface(tmp_path):
    sysfs = tmp_path / "sys"
    _node(sysfs, "hidraw0", "0003:00003434:00000C30", KEYBOARD_DESCRIPTOR, "usb-0000:00:14.0-2/input0")
    _node(sysfs, "hidraw1", "0003:00003434:00000C30", VIA_DESCRIPTOR)
    _node(sysfs, "hidraw2", "0003:0000046D:0000C52B", VIA_DESCRIPTOR)  # another vendor
    _node(sysfs, "hidraw3", "0005:00003434:00000C30", VIA_DESCRIPTOR)  # Bluetooth
    (sysfs / "hidraw9").mkdir()  # no device

    found = enumerate_devices(0x3434, sysfs=sysfs, dev_dir=tmp_path / "dev")
    assert [(i.path, i.product_id, i.phys) for i in found] == [
        (str(tmp_path / "dev" / "hidraw1"), 0x0C30, "usb-0000:00:14.0-2/input1")]
    assert len(enumerate_devices(None, sysfs=sysfs)) == 2
    assert enumerate_devices(0x3434, sysfs=tmp_path / "missing") == []


def test_scan_keeps_known_boards_and_receivers():
    other = interface(0x0D30)
    dongle = interface(RECEIVER)
    devices = scan(lambda vendor: [interface(), other, dongle])
    assert list(devices) == [SERIAL, "keychron-d028-usb-0000:00:14.0-2/input1"]
    assert devices[SERIAL].board is V3_ANSI and not devices[SERIAL].receiver
    assert devices["keychron-d028-usb-0000:00:14.0-2/input1"].board is None


def test_hidraw_device_framing(tmp_path):
    fifo = tmp_path / "hidraw0"
    os.mkfifo(fifo)
    with HidrawDevice(str(fifo)) as hid:
        hid.write(b"\x01\x02")
        assert hid.read(0.5) == b"\x00\x01\x02" + bytes(30)  # report id 0, padded to 32 bytes
        assert hid.read(0.01) is None
    with pytest.raises(HidError, match="closed"):
        hid.write(b"\x01")


def test_hidraw_open_errors(tmp_path):
    locked = tmp_path / "hidraw1"
    locked.write_bytes(b"")
    locked.chmod(0)
    if os.access(locked, os.R_OK):  # running as root
        pytest.skip("permissions are not enforced")
    with pytest.raises(HidError, match="udev rule"):
        HidrawDevice(str(locked))
    locked.chmod(stat.S_IRUSR | stat.S_IWUSR)
    with pytest.raises(HidError, match="not accessible"):
        HidrawDevice(str(tmp_path / "hidraw2"))


# -- protocol ---------------------------------------------------------------


@pytest.fixture
def keyboard():
    return FakeKeyboard()


@pytest.fixture
def client(keyboard):
    return KeychronClient(keyboard, timeout=0.01)


def test_keymap_and_keycodes(client, keyboard):
    board = V3_ANSI
    codes = client.keymap(4, board.rows, board.cols)
    assert len(codes) == 4 * 6 * 17
    assert codes[0] == keyboard.keymap[(0, 0, 0)]
    assert codes[6 * 17 + 3] == keyboard.keymap[(1, 0, 3)]
    client.set_keycode(2, 1, 1, 0x0129)
    assert keyboard.keymap[(2, 1, 1)] == 0x0129
    assert client.keycode(2, 1, 1) == 0x0129
    client.set_encoder(0, 0, False, 0x00AE)
    assert client.encoder(0, 0, False) == 0x00AE
    assert client.encoder(0, 0, True) == 0x00A9


def test_device_information(client):
    assert client.protocol_version() == 12
    assert client.firmware_version() == "v1.0.2-ZK May 24 2025 10:00:00"
    assert client.layer_count() == 4
    assert client.default_layer() == 2


def test_lighting(client, keyboard):
    rgb = client.rgb()
    assert (rgb.brightness, rgb.effect, rgb.speed, rgb.hue, rgb.saturation) == (200, 5, 128, 0, 255)
    client.set_rgb(RgbValue.COLOR, 85, 200)
    assert keyboard.rgb[4] == [85, 200]
    assert keyboard.rgb_saved == 1
    client.set_rgb(RgbValue.EFFECT, 1, save=False)
    assert keyboard.rgb_saved == 1


def test_polling_rate_with_a_separate_wireless_rate(client, keyboard):
    rate = client.polling_rate()
    assert (rate.usb, rate.wireless) == (3, 2)
    assert rate.usb_supported == (0, 1, 2, 3, 4, 5, 6)
    client.set_polling_rate(rate.usb, 0)
    assert (keyboard.usb_div, keyboard.ppt_div) == (3, 0)  # the USB rate stays


def test_polling_rate_of_older_firmware():
    keyboard = FakeKeyboard(separate_wireless=False)
    rate = KeychronClient(keyboard, timeout=0.01).polling_rate()
    assert (rate.usb, rate.wireless, rate.wireless_supported) == (3, None, ())


def test_debounce_and_sleep(client, keyboard):
    assert (client.debounce().press, client.debounce().release) == (10, 50)
    client.set_debounce(5, 20)
    assert keyboard.debounce == [5, 20]
    with pytest.raises(KeychronError, match="refused"):
        client.set_debounce(5, 0)
    assert client.sleep_time().idle == 600
    client.set_sleep_time(300, 3600)
    assert keyboard.sleep == [300, 3600]


def test_unhandled_unsolicited_and_silent(client, keyboard):
    with pytest.raises(KeychronError, match="does not support"):
        client.request(0x42)
    keyboard.unsolicited = [b"\xa7\x0d\x00" + bytes(29), b"\xa3\x00\xff" + bytes(29)]
    assert client.layer_count() == 4  # notifications in between are skipped
    keyboard.silent = True
    with pytest.raises(KeychronError, match="did not answer"):
        client.layer_count()
    assert keyboard.requests[-1] == keyboard.requests[-2]  # sent twice


def test_a_lost_report_is_sent_again(client, keyboard):
    real_write = keyboard.write
    lost = []

    def lose_first(report):
        if not lost:
            lost.append(report)  # dropped on the way
            return
        real_write(report)

    keyboard.write = lose_first
    assert client.layer_count() == 4


def test_read_state(client, keyboard):
    state = read_state(client, device())
    assert state.layers == 4
    assert state.keymap[(2, 0, 0)] == keyboard.keymap[(2, 0, 0)]
    assert state.encoders[(1, 0, False)] == 0x00AA
    assert state.firmware.startswith("v1.0.2")
    settings = state.settings
    assert settings.active_layer == 2
    assert settings.rgb.effect == 5
    assert settings.polling.wireless == 2
    assert settings.debounce.press == 10
    keyboard.features = 0  # no dynamic debounce
    assert read_state(client, device()).settings.debounce is None


@pytest.mark.parametrize("product_id", sorted(BOARDS))
def test_identify_the_keyboard_behind_a_receiver(product_id):
    board = BOARDS[product_id]
    keyboard = FakeKeyboard(board)
    client = KeychronClient(keyboard, timeout=0.01)
    assert identify(client, 4)[0] is board
    keyboard.keymap.update({(layer, 0, 1): 0 for layer in range(4)})  # a key set to "None" everywhere
    state = read_state(client, receiver())
    assert state.board is board and state.receiver


def test_identify_refuses_unknown_keyboards():
    keyboard = FakeKeyboard()
    keyboard.keymap = {position: 0x04 for position in keyboard.keymap}  # every matrix position used
    with pytest.raises(KeychronError, match="not supported"):
        identify(KeychronClient(keyboard, timeout=0.01), 4)


# -- keycodes ---------------------------------------------------------------


def test_keycode_names():
    assert keycodes.describe(0x29) == "Escape"
    assert keycodes.cap(0x2A) == "Bksp"
    assert keycodes.describe(0x0106) == "Ctrl+C"
    assert keycodes.describe(0x1A06) == "Right Shift+Win/Cmd+C"
    assert keycodes.cap(0x0306) == "CS+C"
    assert keycodes.describe(0x5221, ("macOS", "macOS Fn")) == "Hold for layer 1 (macOS Fn)"
    assert keycodes.cap(0x5221) == "MO 1"
    assert keycodes.describe(0x2104) == "A when tapped, Ctrl when held"
    assert keycodes.describe(0x7702) == "Macro 2"
    assert keycodes.describe(0x7E18) == "Siri"
    assert keycodes.describe(0x6123) == "Keycode 0x6123"


def test_keycode_categories_and_mods():
    assert keycodes.category(0x04) == "Basic"
    assert keycodes.category(0x0204) == "Basic"
    assert keycodes.category(0x00A9) == "Media"
    assert keycodes.category(0x5262) == "Layers"
    assert keycodes.category(0x2104) == ""
    assert keycodes.with_mods(0x06, 0x01) == 0x0106
    assert keycodes.with_mods(0x0106, 0) == 0x06
    assert keycodes.mods_of(0x0306) == 0x03
    layers = keycodes.options("Layers", ("a", "b"))
    assert {"value": 0x5221, "text": "Hold for layer 1 (b)"} in layers
    assert all(o["value"] < 0x100 for o in keycodes.options("Basic"))
    every = {o["value"] for c in keycodes.CATEGORIES for o in keycodes.options(c, ("a",))}
    assert len(every) == sum(len(keycodes.options(c, ("a",))) for c in keycodes.CATEGORIES)  # no duplicates


def test_board_layouts():
    for board in BOARDS.values():
        positions = [(k.row, k.col) for k in board.keys]
        assert len(positions) == len(set(positions))
        assert all(0 <= row < board.rows and 0 <= col < board.cols for row, col in positions)
        assert max(k.x + k.w for k in board.keys) == 18.25
    assert len(BOARDS[0x0C30].keys) == 88  # 87 keys with an LED, and the knob


# -- session ----------------------------------------------------------------


@pytest.fixture
def session(qtbot, client):
    from olhclient.core.keychron import KeychronSession
    from olhclient.core.worker import Worker

    session = KeychronSession(client, Worker(synchronous=True), read_state(client, device()))
    messages = []
    session.message.connect(lambda text, error: messages.append((text, error)))
    session.messages = messages
    return session


def test_session_features(session):
    assert [f["id"] for f in session.features] == ["keyboard_keys", "lighting", "settings"]
    assert session.product == "Keychron V3 Ultra 8K (ANSI)"
    assert session.firmware == "v1.0.2-ZK"
    assert session.hasKeyboardLayout and not session.hasWebPage
    assert session.controller("dpi") is None


def test_keys_controller(session, keyboard):
    keys = session.controller("keyboard_keys")
    assert keys.layer == 2  # the active base layer
    assert keys.layerNames == ["macOS", "macOS Fn", "Windows", "Windows Fn"]
    rows = keys.keys.items()
    assert len(rows) == 88 + 2
    names = [row["name"] for row in rows]
    assert len(names) == len(set(names))
    assert "Knob press" in names and names[-2:] == ["Knob clockwise", "Knob counter-clockwise"]
    assert session.selectedButton == names[0]
    assert len(keys.boardKeys) == 88 and keys.boardAspect == pytest.approx(18.25 / 6.25)

    keys.setLayer(1)
    assert keys.selected["action"] == "Transparent (lower layer)"
    keys.save(keys.selected["keyIndex"], 0x0106)
    assert keyboard.keymap[(1, 0, 0)] == 0x0106
    assert keys.selected["action"] == "Ctrl+C"
    assert keys.boardKeys[0]["label"] == "C+C"
    assert session.messages[-1] == ("Key saved", False)

    session.selectedButton = "Knob counter-clockwise"
    keys.save(keys.selected["keyIndex"], 0x00AB)
    assert keyboard.encoders[(1, 0, False)] == 0x00AB
    assert keys.selected["action"] == "Next Track"


def test_a_sleeping_keyboard_is_offline(session, keyboard):
    keyboard.silent = True
    session.reload()
    session.reload()
    assert not session.connected
    assert session.messages == [("The keyboard did not answer", True)]  # once, not on every poll
    keyboard.silent = False
    session.reload()
    assert session.connected


def test_keys_controller_reports_failures(session, keyboard):
    keys = session.controller("keyboard_keys")
    keyboard.silent = True
    keys.save(keys.selected["keyIndex"], 0x05)
    assert session.messages[-1] == ("The keyboard did not answer", True)
    assert not keys.saving


def test_lighting_controller(session, keyboard):
    lighting = session.controller("lighting")
    assert lighting.effectTitle == "Cycle left/right"
    assert lighting.brightness == 78
    assert lighting.color == "#ff0000"
    lighting.setEffect(1)
    lighting.setBrightness(100)
    lighting.setSpeed(0)
    lighting.setColor("#00ff00")
    assert keyboard.rgb == {1: [255], 2: [1], 3: [0], 4: [85, 255]}
    assert keyboard.rgb_saved == 4
    assert lighting.effectTitle == "Solid colour" and lighting.color == "#00ff00"
    lighting.setEffect(99)
    assert session.messages[-1] == ("Unknown effect 99", True)


def test_settings_controller(session, keyboard):
    settings = session.controller("settings")
    items = {item["key"]: item for item in settings.items}
    assert list(items) == ["pollingUsb", "pollingWireless", "debouncePress", "debounceRelease", "idle", "sleep"]
    assert items["pollingUsb"]["options"][0] == {"value": 0, "text": "8000 Hz"}
    settings.apply("pollingWireless", 0)
    assert (keyboard.usb_div, keyboard.ppt_div) == (3, 0)
    settings.apply("debounceRelease", 20)
    assert keyboard.debounce == [10, 20]
    settings.apply("idle", 10800 // 6)
    assert keyboard.sleep == [1800, 7200]
    settings.apply("sleep", 600)
    assert session.messages[-1] == ("The sleep time must be longer than the idle time", True)
    assert {item["key"]: item["value"] for item in settings.items}["pollingWireless"] == 0


# -- backend ----------------------------------------------------------------


@pytest.fixture
def keychron_backend(qtbot, fake_api, registry, keyboard):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    found = {SERIAL: device()}
    backend = Backend(fake_api, registry, worker=Worker(synchronous=True), keychron_scan=lambda: dict(found),
                      keychron_connect=lambda d: KeychronClient(keyboard, timeout=0.01))
    backend.found = found
    return backend


def test_backend_lists_and_opens_keychron_keyboards(keychron_backend, fake_api, keyboard):
    from olhclient.api.client import ApiError
    from olhclient.core.keychron import KeychronSession

    fake_api.fail_with = ApiError("Cannot reach OpenLinkHub")  # no OpenLinkHub: the keyboard still works
    keychron_backend.refresh()
    assert not keychron_backend.connected
    assert isinstance(keychron_backend.session, KeychronSession)
    assert keychron_backend.selectedSerial == SERIAL
    assert keychron_backend.devices.get(0)["product"] == "KEYCHRON V3 ULTRA 8K"

    fake_api.fail_with = None
    keychron_backend.refresh()  # OpenLinkHub devices show up; the keyboard stays selected
    assert keychron_backend.selectedSerial == SERIAL
    assert [d["serial"] for d in keychron_backend.devices.items()][-2] == SERIAL  # before the receiver

    keyboard.active_layer = 0
    keyboard.rgb[2] = [7]
    keychron_backend.refresh()  # a poll reads the settings again
    assert keychron_backend.session.controller("lighting").effect == 7

    keychron_backend.selectDevice("SE0000000000TEST")
    assert keyboard.closed
    assert keychron_backend.session.serial == "SE0000000000TEST"


def test_backend_drops_an_unplugged_keyboard(keychron_backend, keyboard):
    keychron_backend.selectDevice(SERIAL)  # not scanned yet
    assert keychron_backend.session is None
    keychron_backend.refresh()
    keychron_backend.selectDevice(SERIAL)
    assert keychron_backend.selectedSerial == SERIAL
    keychron_backend.found.clear()
    keychron_backend.refresh()
    assert keyboard.closed
    assert keychron_backend.selectedSerial != SERIAL
    assert SERIAL not in [d["serial"] for d in keychron_backend.devices.items()]


def test_backend_names_the_keyboard_behind_a_receiver(qtbot, fake_api, registry, keyboard):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    backend = Backend(fake_api, registry, worker=Worker(synchronous=True),
                      keychron_scan=lambda: {RECEIVER_SERIAL: receiver()},
                      keychron_connect=lambda d: KeychronClient(keyboard, timeout=0.01))
    keyboard.silent = True  # asleep: the receiver is listed, the keyboard not yet known
    backend._scan_keychron()
    assert backend.session is None
    assert backend.devices.get(0)["product"] == "KEYCHRON ULTRA-LINK 8K"
    keyboard.silent = False
    keyboard.closed = False  # each connect opens the hidraw node anew
    backend.selectDevice(RECEIVER_SERIAL)
    assert backend.session.product == "Keychron V3 Ultra 8K (ANSI)"
    assert backend.session.connectionMode == "Wireless"
    assert backend.devices.get(0)["product"] == "KEYCHRON V3 ULTRA 8K"


def test_backend_reports_a_keyboard_that_cannot_be_opened(keychron_backend, fake_api, registry):
    from olhclient.api.client import ApiError
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    def refuse(_):
        raise HidError("No permission to open /dev/hidraw7")

    backend = Backend(fake_api, registry, worker=Worker(synchronous=True), keychron_scan=lambda: {SERIAL: device()},
                      keychron_connect=refuse)
    messages = []
    backend.notify.connect(lambda text, error: messages.append((text, error)))
    fake_api.fail_with = ApiError("Cannot reach OpenLinkHub")
    backend.refresh()
    assert backend.session is None
    assert messages == [("No permission to open /dev/hidraw7", True)]


def test_backend_without_openlinkhub(qtbot, registry, keyboard):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    backend = Backend(None, registry, worker=Worker(synchronous=True), keychron_scan=lambda: {SERIAL: device()},
                      keychron_connect=lambda d: KeychronClient(keyboard, timeout=0.01), brand="OpenDeviceHub")
    assert not backend.openLinkHub and backend.macros is None and backend.serverUrl == ""
    backend.refresh()  # no OpenLinkHub to poll: only the keyboards
    assert backend.status == "1 device found"
    assert backend.session.product == "Keychron V3 Ultra 8K (ANSI)"


def test_openlinkhub_devices_are_shown_first(keychron_backend):
    keychron_backend.refresh()  # the Keychron scan finishes before OpenLinkHub answers
    assert keychron_backend.selectedSerial == "SE0000000000TEST"
