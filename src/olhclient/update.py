"""Update check and install for the Flatpak release.

Asks GitHub for the latest stable release, compares it with the running version and installs
the release's ``.flatpak`` bundle the way the README does::

    flatpak install --user OpenLinkHub-Client-vX.Y.Z.flatpak -y

One release carries a bundle per edition (see edition.py); each app installs its own.

Inside the Flatpak sandbox the install runs on the host through ``flatpak-spawn --host``. Other
installs (pip, from source) only get a link to the release page.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

import httpx

from olhclient import __version__
from olhclient.edition import OPENLINKHUB, Edition

GITHUB_REPO = "mdmatthias/OpenLinkHub-Client"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
ASSET_NAME = "{bundle}-{tag}.flatpak"

REQUEST_TIMEOUT = 15
INSTALL_TIMEOUT = 600
# GitHub's API refuses requests without a User-Agent.
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": f"olh-client/{__version__}"}


class UpdateError(Exception):
    pass


class Cancelled(UpdateError):
    pass


def is_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID"))


def can_install() -> bool:
    """Only the Flatpak can install an update itself."""
    return is_flatpak()


def parse_version(version: str) -> tuple[tuple[int, ...], str]:
    """``v0.2.1-dev`` -> ``((0, 2, 1), "dev")``; non-numeric parts count as 0."""
    text, _, prerelease = version.strip().lstrip("vV").partition("-")
    parts = tuple(int(part) if part.isdigit() else 0 for part in text.split("."))
    return parts, prerelease


def compare_versions(a: str, b: str) -> int:
    """-1, 0 or 1 as ``a`` is older than, equal to or newer than ``b``.

    With equal numbers a prerelease (``0.2.0-dev``) is older than the release.
    """
    a_nums, a_pre = parse_version(a)
    b_nums, b_pre = parse_version(b)
    width = max(len(a_nums), len(b_nums))
    a_nums += (0,) * (width - len(a_nums))
    b_nums += (0,) * (width - len(b_nums))
    if a_nums != b_nums:
        return -1 if a_nums < b_nums else 1
    if bool(a_pre) != bool(b_pre):
        return -1 if a_pre else 1
    return 0


def is_newer(release: dict[str, Any], current: str = __version__) -> bool:
    return compare_versions(release.get("tag_name", ""), current) > 0


def latest_release(timeout: float = REQUEST_TIMEOUT) -> dict[str, Any]:
    """The latest stable release (GitHub skips prereleases and drafts here)."""
    try:
        response = httpx.get(LATEST_RELEASE_URL, headers=HEADERS, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise UpdateError(f"Cannot reach GitHub: {exc}") from exc
    return response.json()


def update_asset(release: dict[str, Any], edition: Edition = OPENLINKHUB) -> dict[str, Any] | None:
    """The release's ``.flatpak`` bundle of ``edition``, or None."""
    tag = release.get("tag_name", "")
    if not tag:
        return None
    name = ASSET_NAME.format(bundle=edition.bundle, tag=tag)
    return next((asset for asset in release.get("assets", []) if asset.get("name") == name), None)


def download_dir() -> Path:
    """Under the cache dir, which the host sees at the same path when the app runs in the sandbox
    (``~/.var/app/<id>/cache``), so the host's ``flatpak install`` can read the bundle."""
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "olh-client" / "updates"


def download(url: str, target: Path, progress: Callable[[int, int], None] | None = None,
             cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Download ``url`` to ``target``; ``progress(received, total)`` with total 0 when unknown."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with httpx.stream("GET", url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=REQUEST_TIMEOUT,
                          follow_redirects=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            with partial.open("wb") as out:
                for chunk in response.iter_bytes(64 * 1024):
                    if cancelled():
                        raise Cancelled("Download cancelled")
                    out.write(chunk)
                    received += len(chunk)
                    if progress is not None:
                        progress(received, total)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"Download failed: {exc}") from exc
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(target)
    return target


def host_command(*command: str) -> list[str]:
    """Run ``command`` on the host when inside the sandbox."""
    return ["flatpak-spawn", "--host", *command] if is_flatpak() else list(command)


def install_command(bundle: Path) -> list[str]:
    return host_command("flatpak", "install", "--user", "-y", str(bundle))


def install(bundle: Path) -> None:
    """Install a downloaded bundle; blocks, so run it on a worker thread."""
    try:
        result = subprocess.run(install_command(bundle), capture_output=True, text=True, timeout=INSTALL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError(f"Installing failed: {exc}") from exc
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise UpdateError(f"Installing failed: {output or f'flatpak exited with {result.returncode}'}")
    bundle.unlink(missing_ok=True)


def restart(edition: Edition = OPENLINKHUB) -> None:
    """Start the installed version; the caller quits this one."""
    subprocess.Popen(host_command("flatpak", "run", edition.app_id), start_new_session=True)
