"""Artwork lit in the colours of the lighting zones."""

from pathlib import Path
from urllib.parse import urlparse

from olhclient.api.models import DeviceState
from olhclient.core.artwork import UNLIT, lit, tint, zone_colors
from olhclient.core.backend import Backend
from olhclient.core.worker import Worker

from tests.conftest import SE

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <linearGradient id="glow" class="zone-side"><stop offset="0" stop-color="#8fe35a"/></linearGradient>
  <text class="zone-side" fill="#8fe35a">1</text>
  <path class="zone-logo" d="M 0 0 L 1 1" fill="none" stroke="#8fe35a"/>
  <rect class="zone-side" fill="url(#glow)" width="1" height="1"/>
  <path d="M 0 0" stroke="#8fe35a"/>
</svg>"""


def path_of(url: str) -> Path:
    return Path(urlparse(url).path)


def test_zone_colors(se_device):
    assert zone_colors(DeviceState.from_json(se_device)) == {"side": "#aa0802", "logo": "#aa0802"}
    se_device["DeviceProfile"]["RGBProfile"] = "off"
    assert set(zone_colors(DeviceState.from_json(se_device)).values()) == {UNLIT}
    del se_device["DeviceProfile"]["RGBProfile"]  # no lighting support
    assert zone_colors(DeviceState.from_json(se_device)) == {}


def test_tint_only_touches_zone_elements():
    result = tint(SVG, {"side": "#0000ff"})
    assert result.count("#0000ff") == 2  # gradient stop and text
    assert 'fill="url(#glow)"' in result and 'fill="none"' in result
    assert result.count("#8fe35a") == 2  # unknown zone (logo) and the unmarked path keep their colour
    assert "ns0:" not in result


def test_lit_writes_one_file_per_colour_set(tmp_path):
    image = tmp_path / "side.svg"
    image.write_text(SVG)
    red, blue = lit(image, {"side": "#ff0000"}), lit(image, {"side": "#0000ff"})
    assert red != blue and red != image and "#ff0000" in red.read_text()
    assert lit(image, {"side": "#ff0000"}) == red
    assert lit(image, {}) == image
    png = tmp_path / "top.png"
    assert lit(png, {"side": "#ff0000"}) == png


def test_session_artwork_follows_zone_colours(make_session, fake_api):
    session = make_session()
    assert "#aa0802" in path_of(session.views[0]["image"]).read_text()
    fake_api.save_zone_colors(SE, {0: "#123456"})
    session.reload()
    side = path_of(session.views[0]["image"]).read_text()
    assert "#123456" in side and "#8fe35a" not in side
    assert "#123456" in path_of(session.thumbnail).read_text()


def test_device_strip_thumbnail_follows_session(qtbot, fake_api, registry):
    backend = Backend(fake_api, registry, worker=Worker(synchronous=True))
    backend.refresh()
    backend.selectDevice(SE)
    fake_api.save_zone_colors(SE, {0: "#123456"})
    backend.session.reload()
    tile = backend.devices.get(backend.devices.indexOf("serial", SE))
    assert tile["thumbnail"] == backend.session.thumbnail


def test_tint_drops_missing_buttons():
    svg = SVG.replace("</svg>", '<g class="button-profile-switch"><rect width="1" height="1"/></g></svg>')
    assert "button-profile-switch" in tint(svg, {})
    assert "button-profile-switch" not in tint(svg, {}, frozenset({"Profile Switch"}))


def test_wireless_models_have_no_profile_switch(make_session):
    from tests.conftest import LEGACY

    se, legacy = make_session(), make_session(LEGACY)
    top = {session: next(v for v in session.views if v["id"] == "top") for session in (se, legacy)}
    assert "Profile Switch" not in [spot["button"] for spot in top[se]["hotspots"]]
    assert "Profile Switch" not in [b["button"] for b in se.buttonList]
    assert "Profile Switch" not in [k["name"] for k in se.controller("key_remap").keys.items()]
    assert "button-profile-switch" not in path_of(top[se]["image"]).read_text()

    assert "Profile Switch" in [spot["button"] for spot in top[legacy]["hotspots"]]
    assert "button-profile-switch" in path_of(top[legacy]["image"]).read_text()
