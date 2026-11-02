import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import respx

from olhclient import __version__, update
from olhclient.core.updater import Updater
from olhclient.core.worker import Worker

ASSET_URL = "https://github.com/mdmatthias/OpenLinkHub-Client/releases/download/v99.0.0/x.flatpak"
BUNDLE = b"flatpak bundle" * 1000


def release(tag: str = "v99.0.0", assets: bool = True) -> dict:
    name = f"OpenLinkHub-Client-{tag}.flatpak"
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/mdmatthias/OpenLinkHub-Client/releases/tag/{tag}",
        "assets": [{"name": name, "size": len(BUNDLE), "browser_download_url": ASSET_URL}] if assets else [],
    }


@pytest.fixture
def flatpak(monkeypatch, tmp_path):
    monkeypatch.setenv("FLATPAK_ID", update.APP_ID)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    runs = []

    def run(command, **kwargs):
        runs.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    return runs


@pytest.fixture
def no_flatpak(monkeypatch):
    monkeypatch.delenv("FLATPAK_ID", raising=False)


# -- versions ---------------------------------------------------------------

@pytest.mark.parametrize("version, expected", [
    ("0.2.1", ((0, 2, 1), "")),
    ("v0.2.1", ((0, 2, 1), "")),
    ("v0.2.1-dev", ((0, 2, 1), "dev")),
    ("0.x.1", ((0, 0, 1), "")),
])
def test_parse_version(version, expected):
    assert update.parse_version(version) == expected


@pytest.mark.parametrize("a, b, expected", [
    ("v0.1.0", "0.2.0", -1),
    ("0.10.0", "0.9.9", 1),
    ("v0.2.0", "0.2.0", 0),
    ("0.2", "0.2.0", 0),
    ("0.2.0-dev", "0.2.0", -1),
    ("0.2.0-dev", "0.1.9", 1),
])
def test_compare_versions(a, b, expected):
    assert update.compare_versions(a, b) == expected


def test_is_newer():
    assert update.is_newer(release("v99.0.0"))
    assert not update.is_newer(release(f"v{__version__}"))
    assert not update.is_newer({})


# -- release lookup -----------------------------------------------------------

@respx.mock
def test_latest_release():
    route = respx.get(update.LATEST_RELEASE_URL).respond(json=release())
    assert update.latest_release()["tag_name"] == "v99.0.0"
    assert route.calls.last.request.headers["User-Agent"].startswith("olh-client/")


@respx.mock
def test_latest_release_http_error():
    respx.get(update.LATEST_RELEASE_URL).respond(404)
    with pytest.raises(update.UpdateError):
        update.latest_release()


def test_update_asset():
    assert update.update_asset(release())["browser_download_url"] == ASSET_URL
    assert update.update_asset(release(assets=False)) is None
    assert update.update_asset({}) is None


# -- download and install ---------------------------------------------------------

@respx.mock
def test_download(tmp_path):
    respx.get(ASSET_URL).respond(content=BUNDLE, headers={"Content-Length": str(len(BUNDLE))})
    seen = []
    target = update.download(ASSET_URL, tmp_path / "a" / "x.flatpak", lambda r, t: seen.append((r, t)))
    assert target.read_bytes() == BUNDLE
    assert seen[-1] == (len(BUNDLE), len(BUNDLE))


@respx.mock
def test_cancelled_download_leaves_nothing(tmp_path):
    respx.get(ASSET_URL).respond(content=BUNDLE)
    with pytest.raises(update.Cancelled):
        update.download(ASSET_URL, tmp_path / "x.flatpak", cancelled=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_install_runs_on_the_host(flatpak, tmp_path):
    bundle = tmp_path / "x.flatpak"
    bundle.write_bytes(BUNDLE)
    update.install(bundle)
    assert flatpak == [["flatpak-spawn", "--host", "flatpak", "install", "--user", "-y", str(bundle)]]
    assert not bundle.exists()


def test_install_outside_flatpak(no_flatpak):
    assert update.install_command(Path("x.flatpak")) == ["flatpak", "install", "--user", "-y", "x.flatpak"]


def test_install_failure(flatpak, monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"))
    with pytest.raises(update.UpdateError, match="boom"):
        update.install(tmp_path / "x.flatpak")


def test_download_dir_is_under_the_cache(flatpak, tmp_path):
    assert update.download_dir() == tmp_path / "olh-client" / "updates"


# -- Updater -------------------------------------------------------------------

@pytest.fixture
def updater(qapp):
    return Updater(Worker(synchronous=True))


@respx.mock
def test_quiet_check_stays_closed_when_up_to_date(updater):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release(f"v{__version__}"))
    updater.checkQuietly()
    assert updater.state == "upToDate"
    assert not updater.dialogOpen
    assert not updater.updateAvailable


@respx.mock
def test_quiet_check_stays_closed_on_error(updater):
    respx.get(update.LATEST_RELEASE_URL).respond(500)
    updater.checkQuietly()
    assert updater.state == "error"
    assert not updater.dialogOpen


@respx.mock
def test_quiet_check_opens_dialog_for_update(updater):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release())
    updater.checkQuietly()
    assert (updater.state, updater.dialogOpen, updater.latestVersion) == ("available", True, "99.0.0")
    assert updater.updateAvailable


@respx.mock
def test_manual_check_shows_up_to_date(updater):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release(f"v{__version__}"))
    updater.check()
    assert (updater.state, updater.dialogOpen) == ("upToDate", True)


@respx.mock
def test_update_without_bundle_is_an_error_in_flatpak(updater, flatpak):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release(assets=False))
    updater.check()
    assert updater.state == "error"
    assert updater.updateAvailable  # the dialog links to the release page


@respx.mock
def test_install_outside_flatpak_does_nothing(updater, no_flatpak):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release())
    updater.check()
    assert not updater.canInstall
    updater.install()
    assert updater.state == "available"


@respx.mock
def test_install_downloads_and_installs(updater, flatpak, tmp_path):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release())
    respx.get(ASSET_URL).respond(content=BUNDLE, headers={"Content-Length": str(len(BUNDLE))})
    states = []
    updater.changed.connect(lambda: states.append(updater.state))
    updater.check()
    updater.install()
    assert states[-3:] == ["downloading", "installing", "installed"]
    assert updater.progress == 1.0
    bundle = tmp_path / "olh-client" / "updates" / "OpenLinkHub-Client-v99.0.0.flatpak"
    assert flatpak == [["flatpak-spawn", "--host", "flatpak", "install", "--user", "-y", str(bundle)]]


@respx.mock
def test_failed_install_shows_error(updater, flatpak, monkeypatch):
    respx.get(update.LATEST_RELEASE_URL).respond(json=release())
    respx.get(ASSET_URL).respond(content=BUNDLE)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="nope"))
    updater.check()
    updater.install()
    assert updater.state == "error"
    assert "nope" in updater.message


def test_restart_starts_the_new_version_and_quits(updater, flatpak, monkeypatch):
    started, quit = [], []
    monkeypatch.setattr(subprocess, "Popen", lambda command, **kwargs: started.append(command))
    monkeypatch.setattr("olhclient.core.updater.QCoreApplication.quit", lambda: quit.append(True))
    updater.restart()  # not installed yet: ignored
    assert started == []
    updater._set_state("installed")
    updater.restart()
    assert started == [["flatpak-spawn", "--host", "flatpak", "run", update.APP_ID]]
    assert quit == [True]
