"""Graphics cards: I2C discovery, the RGB Fusion 2 protocol, the stored lighting, the session and the backend."""

import json

import pytest

from olhclient.gpu.cards import CARDS
from olhclient.gpu.device import LightingStore, scan
from olhclient.gpu.fusion2 import BRIGHTNESS_MAX, Fusion2Gpu, Lighting, ModeValue, packets
from olhclient.gpu.i2c import I2cDevice, I2cError, enumerate_buses
from tests.fake_gpu import ELITE, SERIAL, FakeCard, bus, device

# -- I2C ----------------------------------------------------------------------


def _pci(root, slot, ids):
    path = root / "devices" / "pci0000:00" / slot
    path.mkdir(parents=True)
    for name, value in zip(("vendor", "device", "subsystem_vendor", "subsystem_device"), ids):
        (path / name).write_text(f"0x{value:04x}\n")
    return path


def _adapter(root, parent, number, name):
    path = parent / f"i2c-{number}"
    path.mkdir(parents=True)
    (path / "name").write_text(name + "\n")
    (root / "bus").mkdir(exist_ok=True)
    (root / "bus" / f"i2c-{number}").symlink_to(path)


def test_enumerate_buses_finds_the_pci_device(tmp_path):
    card = _pci(tmp_path, "0000:0a:00.0", ELITE.ids)
    _adapter(tmp_path, card, 9, "AMDGPU DM i2c OEM bus")
    _adapter(tmp_path, card / "drm" / "card1", 12, "AMDGPU DM aux hw bus 2")  # below an intermediate device
    _adapter(tmp_path, card, 13, "DPMST")
    _adapter(tmp_path, tmp_path / "devices" / "platform", 1, "Synopsys DesignWare I2C adapter")
    buses = enumerate_buses(tmp_path / "bus")
    assert [b.number for b in buses] == [9, 12]
    assert buses[0] == bus()
    assert buses[0].path == "/dev/i2c-9"


def test_i2c_device_open_errors(tmp_path):
    with pytest.raises(I2cError, match="load the i2c-dev module"):
        I2cDevice(str(tmp_path / "i2c-42"), 0x73)
    node = tmp_path / "i2c-9"
    node.write_text("")
    with pytest.raises(I2cError, match="Cannot select address 0x73"):  # not an I2C bus
        I2cDevice(str(node), 0x73)


def test_scan_probes_known_cards_on_the_right_bus():
    cards = {}

    def open_fn(path, address, answer=FakeCard().answer):
        cards[path, address] = card = FakeCard(answer)
        return Fusion2Gpu(card)

    buses = [bus(5, "AMDGPU DM i2c hw bus 0"), bus(9), bus(10, "AMDGPU DM aux hw bus 0")]
    assert scan(lambda: buses, open_fn) == {SERIAL: device()}
    assert set(cards) == {("/dev/i2c-9", 0x73)}  # on AMD cards only the OEM bus has the controller
    assert cards["/dev/i2c-9", 0x73].closed
    assert cards["/dev/i2c-9", 0x73].writes == [bytes([0xAB] + [0] * 7)]
    # a bus that echoes the probe has no controller
    assert scan(lambda: [bus()], lambda path, address: open_fn(path, address, bytes([0xAB] * 4))) == {}


def test_scan_skips_unknown_cards_and_unopenable_buses():
    def refuse(path, address):
        raise I2cError(f"No permission to open {path}")

    other = bus()
    other = type(other)(9, other.name, other.pci_slot, 0x1002, 0x7550, 0x1458, 0x9999)
    assert scan(lambda: [other], lambda p, a: pytest.fail("probed an unknown card")) == {}
    assert scan(lambda: [bus()], refuse) == {}


def test_card_table():
    assert len(CARDS) == 103
    assert len({(card.ids, card.address) for card in CARDS}) == len(CARDS)
    assert ELITE.ids == (0x1002, 0x7550, 0x1458, 0x2426) and ELITE.address == 0x73


# -- protocol -------------------------------------------------------------------


def test_static_colours_per_zone():
    zones = ((1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12), (13, 14, 15))
    writes = packets(Lighting(brightness=50, zones=zones))
    assert [w.hex(" ") for w in writes] == [
        "88 01 02 32 00 01 00 00", "b0 01 01 02 03 04 05 06",
        "88 01 02 32 00 02 00 00", "b0 01 01 02 03 04 05 06",
        "88 01 02 32 00 03 00 00", "b1 01 07 08 09 00 00 00",
        "88 01 02 32 00 04 00 00", "40 0a 0b 0c 04 00 00 00",
        "88 01 02 32 00 05 00 00", "40 0d 0e 0f 05 00 00 00",
    ]


def test_modes_without_zone_colours():
    cycle = packets(Lighting(mode=ModeValue.COLOR_CYCLE, speed=5))
    assert [w.hex(" ") for w in cycle] == [f"88 03 05 63 00 0{zone} 00 00" for zone in range(1, 6)]

    tricolor = packets(Lighting(mode=ModeValue.TRICOLOR, speed=0))
    assert len(tricolor) == 5 * 5
    assert tricolor[0].hex(" ") == "88 0b 00 63 08 01 00 00"
    assert tricolor[1].hex(" ") == "b0 0b ff 00 00 ff 80 00"  # first two palette colours
    assert tricolor[2].hex(" ") == "b1 0b ff ff 00 00 00 00"  # third, then black
    assert tricolor[-1].hex(" ") == "c3 0b 00 00 00 00 00 00"  # zone 5, last bank

    shift = packets(Lighting(mode=ModeValue.COLOR_SHIFT))
    assert shift[0].hex(" ") == "88 06 02 63 08 01 00 00"  # flag: number of colours
    assert shift[4].hex(" ") == "b3 06 80 00 ff ff 00 ff"


def test_pulse_runs_at_full_brightness_and_gradient_sets_its_flag():
    assert packets(Lighting(mode=ModeValue.BREATHING, brightness=0))[0][3] == BRIGHTNESS_MAX
    assert packets(Lighting(mode=ModeValue.GRADIENT))[0].hex(" ") == "88 05 02 63 08 01 00 00"
    with pytest.raises(ValueError):
        packets(Lighting(mode=0x42))


def test_client():
    card = FakeCard()
    gpu = Fusion2Gpu(card)
    assert gpu.probe()
    gpu.apply(Lighting())
    gpu.save()
    assert len(card.writes) == 1 + 10 + 1
    assert card.writes[-1] == bytes([0xAA] + [0] * 7)
    assert not Fusion2Gpu(FakeCard(bytes([0xAB, 0xAB, 0xAB, 0xAB]))).probe()
    assert not Fusion2Gpu(FakeCard(b"")).probe()


# -- stored lighting ------------------------------------------------------------


def test_lighting_store(tmp_path):
    store = LightingStore(tmp_path / "state" / "gpu-lighting.json")
    assert store.load(SERIAL) is None
    lighting = Lighting(mode=ModeValue.WAVE, brightness=10, speed=4, zones=((1, 2, 3),) * 5)
    store.save(SERIAL, lighting)
    store.save("gpu-other", Lighting())
    assert store.load(SERIAL) == lighting
    assert LightingStore(store.path).load("gpu-other") == Lighting()

    data = json.loads(store.path.read_text())
    data[SERIAL]["zones"] = [[1, 2, 300]] * 5
    data["gpu-other"]["mode"] = 0x42
    store.path.write_text(json.dumps(data))
    assert store.load(SERIAL) is None and store.load("gpu-other") is None
    store.path.write_text("{")
    assert store.load(SERIAL) is None


# -- session ----------------------------------------------------------------


@pytest.fixture
def card():
    return FakeCard()


@pytest.fixture
def store(tmp_path):
    return LightingStore(tmp_path / "gpu-lighting.json")


@pytest.fixture
def session(qtbot, card, store):
    from olhclient.core.gpu import GpuSession
    from olhclient.core.worker import Worker

    session = GpuSession(Fusion2Gpu(card), Worker(synchronous=True), device(), store)
    messages = []
    session.message.connect(lambda text, error: messages.append((text, error)))
    session.messages = messages
    return session


def test_session(session):
    assert [f["id"] for f in session.features] == ["lighting"]
    assert session.product == "Gigabyte AORUS Radeon RX 9070 XT Elite"
    assert session.kindTitle == "Graphics card"
    assert not session.hasArtwork and not session.hasKeyboardLayout and not session.hasWebPage
    assert session.controller("dpi") is None


def test_lighting_controller(session, card, store):
    lighting = session.controller("lighting")
    assert lighting.effectTitle == "Static" and lighting.brightness == 100
    assert not lighting.hasSpeed and lighting.zoneColors
    assert [z["name"] for z in lighting.zones.items()] == [f"Zone {i}" for i in range(1, 6)]

    lighting.setColor(2, "#ff8000")
    assert card.writes[5].hex(" ") == "b1 01 ff 80 00 00 00 00"
    assert lighting.colors[2] == "#ff8000"
    assert session.messages[-1] == ("Colour set", False)
    lighting.setColor(-1, "#0000ff")
    assert lighting.colors == ["#0000ff"] * 5
    card.writes.clear()
    lighting.setColor(0, "#0000ff")  # unchanged, still written: the card may show something else
    assert len(card.writes) == 10
    lighting.setBrightness(50)
    assert card.writes[-10][3] == round(BRIGHTNESS_MAX / 2)

    card.writes.clear()
    lighting.setEffect(ModeValue.TRICOLOR)
    assert lighting.effectTitle == "Tricolour" and not lighting.zoneColors
    assert lighting.colors == ["#ff0000", "#ff8000", "#ffff00"]
    assert [z["name"] for z in lighting.zones.items()] == ["Colour 1", "Colour 2", "Colour 3"]
    lighting.setSpeed(5)
    assert lighting.speed == 5 and card.writes[-25][2] == 5
    lighting.setColor(1, "#123456")
    assert store.load(SERIAL).palette[1] == (0x12, 0x34, 0x56)

    lighting.setEffect(ModeValue.WAVE)
    assert lighting.colors == [] and lighting.zones.count == 0

    card.writes.clear()
    lighting.saveToCard()
    assert card.writes == [bytes([0xAA] + [0] * 7)]
    assert session.messages[-1] == ("Lighting saved on the card", False)


def test_lighting_controller_refuses_bad_values(session, card):
    lighting = session.controller("lighting")
    lighting.setEffect(0x42)
    lighting.setBrightness(101)
    lighting.setSpeed(9)
    lighting.setColor(5, "#ffffff")
    lighting.setColor(0, "blue")
    assert card.writes == []
    assert [error for _, error in session.messages] == [True] * 5


def test_a_failed_write_keeps_the_lighting(session, card, store):
    lighting = session.controller("lighting")
    changes = []
    lighting.changed.connect(lambda: changes.append(lighting.effect))
    card.fail = True
    lighting.setEffect(ModeValue.WAVE)
    assert session.messages[-1] == ("Writing to /dev/i2c-9 failed: Remote I/O error", True)
    assert lighting.effect == ModeValue.STATIC and changes == [ModeValue.STATIC]  # the editor resets
    assert store.load(SERIAL) is None


def test_the_session_shows_the_stored_lighting(qtbot, card, store):
    from olhclient.core.gpu import GpuSession
    from olhclient.core.worker import Worker

    store.save(SERIAL, Lighting(mode=ModeValue.FLASHING))
    session = GpuSession(Fusion2Gpu(card), Worker(synchronous=True), device(), store)
    assert session.controller("lighting").effectTitle == "Flash"
    assert card.writes == []  # opening does not change the card


# -- backend ----------------------------------------------------------------


@pytest.fixture
def gpu_backend(qtbot, fake_api, registry, card, store):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    return Backend(fake_api, registry, worker=Worker(synchronous=True), gpu_scan=lambda: {SERIAL: device()},
                   gpu_connect=lambda d: Fusion2Gpu(card), gpu_store=store)


def test_backend_lists_and_opens_cards(gpu_backend, card):
    from olhclient.core.gpu import GpuSession

    gpu_backend.refresh()
    assert gpu_backend.selectedSerial == "SE0000000000TEST"  # OpenLinkHub devices come first
    items = gpu_backend.devices.items()
    assert items[-2]["product"] == "GIGABYTE AORUS RADEON RX 9070 XT ELITE"  # before the receiver
    assert items[-2]["name"] == "Graphics card"
    gpu_backend.selectDevice(SERIAL)
    assert isinstance(gpu_backend.session, GpuSession)
    gpu_backend.refresh()  # polls leave the card alone
    assert gpu_backend.selectedSerial == SERIAL and card.writes == []
    gpu_backend.selectDevice("SE0000000000TEST")
    assert card.closed


def test_backend_scans_for_cards_once(qtbot, registry, card, store):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    scans = []
    backend = Backend(None, registry, worker=Worker(synchronous=True), gpu_scan=lambda: scans.append(1) or {SERIAL: device()},
                      gpu_connect=lambda d: Fusion2Gpu(card), gpu_store=store, brand="OpenDeviceHub")
    backend.refresh()
    backend.refresh()
    assert scans == [1]
    assert backend.status == "1 device found"
    assert backend.session.product == "Gigabyte AORUS Radeon RX 9070 XT Elite"


def test_backend_reports_a_card_that_cannot_be_opened(qtbot, registry, store):
    from olhclient.core.backend import Backend
    from olhclient.core.worker import Worker

    def refuse(_):
        raise I2cError("No permission to open /dev/i2c-9; see the README (Graphics cards)")

    backend = Backend(None, registry, worker=Worker(synchronous=True), gpu_scan=lambda: {SERIAL: device()},
                      gpu_connect=refuse, gpu_store=store)
    messages = []
    backend.notify.connect(lambda text, error: messages.append((text, error)))
    backend.refresh()
    assert backend.session is None
    assert messages == [("No permission to open /dev/i2c-9; see the README (Graphics cards)", True)]
