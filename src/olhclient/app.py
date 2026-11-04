"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from olhclient import __version__
from olhclient.api.client import ApiClient
from olhclient.config import Config, default_path
from olhclient.core.backend import Backend
from olhclient.core.session import QML_DIR
from olhclient.core.updater import Updater
from olhclient.devices.registry import Registry
from olhclient.edition import EDITIONS, current
from olhclient.gpu.device import scan as scan_gpus
from olhclient.keychron.device import scan as scan_keychron
from olhclient.tray import create_tray


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="olh-client", description="Desktop client for OpenLinkHub")
    parser.add_argument("--url", help="OpenLinkHub base URL (default from config, else http://127.0.0.1:27003)")
    parser.add_argument("--config", type=Path, default=None, help=f"config file (default {default_path()})")
    parser.add_argument("--insecure", action="store_true", help="do not verify the server's TLS certificate")
    parser.add_argument("--edition", choices=sorted(EDITIONS),
                        help="which devices to drive (default: all; a Flatpak knows its own)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def create_engine(backend: Backend, updater: Updater | None = None, username: str = "") -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend, "updater": updater, "defaultUsername": username})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    edition = current(args.edition)
    config = Config.load(args.config)
    if args.url:
        config.base_url = args.url
    if args.insecure:
        config.verify_tls, config.ca_file = False, ""

    QQuickStyle.setStyle("Basic")
    # QApplication (not QGuiApplication): the tray menu is a QMenu.
    app = QApplication(sys.argv[:1])
    app.setApplicationName(edition.name)
    app.setOrganizationName("olh-client")
    app.setDesktopFileName(edition.app_id)  # lets Wayland compositors find the icon of the installed app
    app.setWindowIcon(QIcon(str(QML_DIR / "icons" / "app.svg")))

    api = ApiClient(config.base_url, origin=config.origin or None, verify=config.verify) if edition.openlinkhub else None
    backend = Backend(api, Registry.discover(), poll_interval=config.poll_interval,
                      keychron_scan=scan_keychron if edition.keychron else None,
                      gpu_scan=scan_gpus if edition.gpu else None, brand=edition.brand)
    updater = Updater(edition=edition)
    engine = create_engine(backend, updater, config.username)
    if not engine.rootObjects():
        return 1
    tray = create_tray(app, engine.rootObjects()[0], updater.check, backend.devices)  # noqa: F841 - keep alive
    backend.start()
    if config.check_updates:
        updater.checkQuietly()
    try:
        return app.exec()
    finally:
        if api is not None:
            api.close()


if __name__ == "__main__":
    sys.exit(main())
