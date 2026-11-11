"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QProcess, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from olhclient import __version__
from olhclient.api.client import ApiClient
from olhclient.config import Config, default_path
from olhclient.core.backend import Backend
from olhclient.core.config_editor import ConfigEditor
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


def create_engine(backend: Backend, updater: Updater | None = None, username: str = "",
                  config: ConfigEditor | None = None, visible: bool = True) -> QQmlApplicationEngine:
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend, "updater": updater, "defaultUsername": username,
                                 "config": config, "visible": visible})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def restart(argv: list[str]) -> None:
    """Start a new instance with the same arguments, then quit this one."""
    QProcess.startDetached(sys.executable, ["-m", "olhclient", *argv])
    QCoreApplication.quit()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    edition = current(args.edition)
    config_path = args.config or default_path()
    config = Config.load(config_path)
    overrides = {}
    if args.url:
        config.base_url = args.url
        overrides["base_url"] = "--url"
    if args.insecure:
        config.verify_tls, config.ca_file = False, ""
        overrides["verify_tls"] = overrides["ca_file"] = "--insecure"

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
    editor = ConfigEditor(config_path, openlinkhub=edition.openlinkhub, overrides=overrides,
                          apply=lambda saved: backend.set_poll_interval(saved.poll_interval),
                          restart=lambda: restart(argv))
    engine = create_engine(backend, updater, config.username, editor, visible=not config.start_minimized)
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    tray = create_tray(app, window, updater.check, backend.devices)
    if config.start_minimized and tray is None:
        window.showMinimized()  # no tray to restore a hidden window from
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
