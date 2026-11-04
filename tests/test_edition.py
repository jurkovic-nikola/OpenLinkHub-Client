"""The three apps built from this code (edition.py) and their Flatpak packaging."""

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from olhclient.edition import DEFAULT, DEVICES, EDITIONS, OPENLINKHUB, PLUS, current

FLATPAK = Path(__file__).parent.parent / "flatpak"


def test_a_flatpak_knows_its_edition(monkeypatch):
    for edition in EDITIONS.values():
        monkeypatch.setenv("FLATPAK_ID", edition.app_id)
        assert current("openlinkhub") is edition  # the flag cannot change an installed app


def test_outside_flatpak_the_flag_decides(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    assert current() is DEFAULT is PLUS
    assert current("devices") is DEVICES
    monkeypatch.setenv("FLATPAK_ID", "org.example.Other")
    assert current("openlinkhub") is OPENLINKHUB


def test_editions_differ():
    for field in ("app_id", "name", "bundle"):
        assert len({getattr(e, field) for e in EDITIONS.values()}) == 3
    assert not DEVICES.openlinkhub and not OPENLINKHUB.keychron and not OPENLINKHUB.gpu


# -- packaging ----------------------------------------------------------------

#: manifest lines that may differ between the editions: header comment, app id, permissions
EDITION_LINES = ("app-id:", "--device=all", "--filesystem=/opt/OpenLinkHub/certificates:ro")


def _shared_lines(manifest: Path) -> list[str]:
    return [line for line in manifest.read_text().splitlines()
            if not line.lstrip().startswith("#") and not any(part in line for part in EDITION_LINES)]


def test_one_manifest_per_edition_and_otherwise_equal():
    manifests = {e.key: FLATPAK / f"{e.app_id}.yaml" for e in EDITIONS.values()}
    for key, manifest in manifests.items():
        text = manifest.read_text()
        edition = EDITIONS[key]
        assert f"app-id: {edition.app_id}\n" in text
        assert ("--device=all" in text) == (edition.keychron or edition.gpu)
        assert ("/opt/OpenLinkHub/certificates" in text) == edition.openlinkhub
    shared = {key: _shared_lines(manifest) for key, manifest in manifests.items()}
    assert shared["plus"] == shared["openlinkhub"] == shared["devices"]


def test_desktop_and_metainfo_per_edition(tmp_path):
    source = FLATPAK / f"{OPENLINKHUB.app_id}.metainfo.xml"
    releases = [r.get("version") for r in ET.parse(source).getroot().iterfind("releases/release")]
    assert releases
    for edition in EDITIONS.values():
        desktop = (FLATPAK / f"{edition.app_id}.desktop").read_text()
        assert f"Name={edition.name}\n" in desktop
        assert f"Icon={edition.app_id}\n" in desktop and f"StartupWMClass={edition.app_id}\n" in desktop
        output = tmp_path / f"{edition.app_id}.metainfo.xml"
        subprocess.run([sys.executable, str(FLATPAK / "copy_releases.py"), str(source),
                        str(FLATPAK / f"{edition.app_id}.metainfo.xml"), str(output)], check=True)
        root = ET.parse(output).getroot()
        assert root.findtext("id") == edition.app_id
        assert root.findtext("name") == edition.name
        assert root.find("launchable").text == f"{edition.app_id}.desktop"
        assert [r.get("version") for r in root.iterfind("releases/release")] == releases


def test_copy_releases_needs_releases_on_both_sides():
    sys.path.insert(0, str(FLATPAK))
    try:
        from copy_releases import copy_releases
    finally:
        sys.path.remove(str(FLATPAK))
    with pytest.raises(ValueError, match="source"):
        copy_releases("<component/>", "<releases/>")
    with pytest.raises(ValueError, match="app metainfo"):
        copy_releases("<releases><release/></releases>", "<component/>")


def test_build_scripts_know_every_edition():
    script = (FLATPAK / "edition.sh").read_text()
    for edition in EDITIONS.values():
        assert f'{edition.key}) APP_ID="{edition.app_id}"; BUNDLE_NAME="{edition.bundle}" ;;' in script
    workflow = (FLATPAK.parent / ".github" / "workflows" / "flatpak.yml").read_text()
    for edition in EDITIONS.values():
        assert f"app-id: {edition.app_id}\n            bundle: {edition.bundle}\n" in workflow
