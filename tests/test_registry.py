import pytest

from olhclient.devices.registry import Registry


@pytest.fixture(scope="module")
def registry():
    return Registry.discover()


def test_discovers_all_scimitar_variants(registry):
    ids = {m.id for m in registry.modules}
    assert {
        "scimitar-elite",
        "scimitar-rgb-elite",
        "scimitar-pro-rgb",
        "scimitar-rgb",
        "scimitar-elite-wireless",
        "scimitar-elite-se",
        "generic-mouse",
    } <= ids


def test_fixtures_match(registry, se_device, legacy_device):
    assert registry.match(se_device).id == "scimitar-elite-se"
    assert registry.match(legacy_device).id == "scimitar-rgb-elite"


@pytest.mark.parametrize(
    "pid, template, expected",
    [
        (7139, "scimitar.html", "scimitar-elite"),
        (7051, "scimitarrgbelite.html", "scimitar-rgb-elite"),
        (6974, "scimitarprorgb.html", "scimitar-pro-rgb"),
        (6942, "scimitarrgb.html", "scimitar-rgb"),
        (7131, "scimitarEliteW.html", "scimitar-elite-wireless"),
        (11042, "scimitarEliteWSE.html", "scimitar-elite-se"),
        # template changed upstream: product id alone still wins over the generic module
        (7131, "somethingNew.html", "scimitar-elite-wireless"),
    ],
)
def test_match_by_product_id(registry, pid, template, expected):
    assert registry.match({"ProductId": pid, "Template": template, "KeyAssignment": {}}).id == expected


def test_unknown_mouse_falls_back_to_generic(registry):
    assert registry.match({"ProductId": 1, "Template": "m65.html", "KeyAssignment": {}}).id == "generic-mouse"


def test_non_mouse_is_rejected(registry):
    with pytest.raises(LookupError):
        registry.match({"ProductId": 1, "Template": "k70.html"})
