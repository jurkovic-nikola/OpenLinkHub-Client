import pytest

from olhclient.api.models import MouseState
from olhclient.devices.base import resolve_image
from olhclient.devices.registry import Registry

SCIMITARS = [m for m in Registry.discover().modules if m.id.startswith("scimitar")]


def layout_buttons(module):
    layout = module.layout
    names = set(layout.button_list) | {n for row in layout.keypad for n in row}
    names |= {spot.button for view in layout.views for spot in view.hotspots}
    return names


@pytest.mark.parametrize("module", SCIMITARS, ids=lambda m: m.id)
def test_layout_buttons_exist_on_both_generations(module, se_device, legacy_device):
    for device in (se_device, legacy_device):
        names = {k.name for k in MouseState.from_json(device).keys}
        assert layout_buttons(module) <= names
        # and every device button is reachable from the layout
        assert names <= layout_buttons(module)


@pytest.mark.parametrize("module", SCIMITARS, ids=lambda m: m.id)
def test_hotspots_are_normalised_and_images_exist(module):
    assert module.layout.thumbnail.is_file()
    for view in module.layout.views:
        assert view.image.is_file()
        for spot in view.hotspots:
            assert 0 <= spot.x and spot.x + spot.w <= 1
            assert 0 <= spot.y and spot.y + spot.h <= 1


def test_keypad_is_3x4_with_all_g_keys():
    keypad = SCIMITARS[0].layout.keypad
    assert [len(row) for row in keypad] == [4, 4, 4]
    assert sorted(n for row in keypad for n in row) == sorted(f"Side Button {i}" for i in range(1, 13))
    assert SCIMITARS[0].button_label("Side Button 11") == "G11"


def test_locked_buttons():
    by_id = {m.id: m for m in SCIMITARS}
    assert by_id["scimitar-elite"].locked_buttons == {"Left Button"}
    assert by_id["scimitar-elite-se"].locked_buttons == {"Left Button"}
    # the wireless models have only the DPI button on top
    assert by_id["scimitar-elite-se"].missing_buttons == {"Profile Switch"}
    assert by_id["scimitar-elite-wireless"].missing_buttons == {"Profile Switch"}
    assert by_id["scimitar-rgb-elite"].missing_buttons == set()


def test_resolve_image_prefers_raster_and_variant_dir(tmp_path):
    shared, variant = tmp_path / "assets", tmp_path / "assets" / "v1"
    variant.mkdir(parents=True)
    (shared / "side.svg").write_text("<svg/>")
    assert resolve_image([variant, shared], "side.svg") == shared / "side.svg"
    (shared / "side.png").write_bytes(b"")
    assert resolve_image([variant, shared], "side.svg") == shared / "side.png"
    (variant / "side.svg").write_text("<svg/>")
    assert resolve_image([variant, shared], "side.svg") == variant / "side.svg"
    with pytest.raises(FileNotFoundError):
        resolve_image([variant, shared], "top.svg")
