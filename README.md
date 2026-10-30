# OpenLinkHub Client

A desktop client for [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub), built with
PySide6 and QML. It talks to the OpenLinkHub HTTP API only: no direct USB access, no changes
to OpenLinkHub itself. The UI follows the iCUE layout (device artwork with clickable buttons,
an action list and a settings panel) but uses its own artwork.

**Status:** first version. It supports the Scimitar family and does two things: **key remapping**
and **DPI stages**.

| Module | Devices (USB product id) |
|---|---|
| `scimitar-elite` | Scimitar Elite (7139) |
| `scimitar-rgb-elite` | Scimitar RGB Elite (7051) |
| `scimitar-pro-rgb` | Scimitar Pro RGB (6974) |
| `scimitar-rgb` | Scimitar RGB (6942) |
| `scimitar-elite-wireless` | Scimitar Elite Wireless, cable and Slipstream dongle (7131) |
| `scimitar-elite-se` | Scimitar Elite Wireless SE, cable and Slipstream dongle (11042) |

Other mice reported by OpenLinkHub fall back to a generic module. You get the same features
as a plain list, with no hotspots.

## Running

Requirements:
- Python 3.11+
- PySide6 6.8+
- httpx
- a running OpenLinkHub, by default on `http://127.0.0.1:27003`

With PySide6 from PyPI:

```sh
uv sync --extra dev
uv run olh-client --url http://127.0.0.1:27003
```

With a distribution PySide6 (Arch: `pyside6`, `python-httpx`, `python-pytest-qt`, `python-respx`):

```sh
uv venv --system-site-packages --python /usr/bin/python3
uv pip install --python .venv/bin/python -e . --no-deps
.venv/bin/olh-client             # or: .venv/bin/python -m olhclient
```

### Configuration

Optional settings live in `~/.config/olh-client/config.toml`:

```toml
base_url = "http://127.0.0.1:27003"
poll_interval = 5            # seconds

# Only needed when OpenLinkHub's dashboard authentication is enabled (HTTPS):
# origin   = "https://127.0.0.1:27003"   # must equal authOrigin in dashboard.json
# ca_file  = "/opt/OpenLinkHub/certificates/server.crt"
# username = "admin"
```

`--insecure` turns off TLS verification for the self-signed certificate. When the server asks
for a login, the client shows a login dialog. The session lives in memory only.

## Architecture

```
src/olhclient/
  api/        ApiClient (httpx) + typed models parsed from the device JSON
  core/       Worker (thread pool), Backend (polling, device list), DeviceSession,
              feature controllers (core/features/*) exposed to QML
  devices/    device modules: base.py, registry.py, generic/, scimitar/
  qml/        Main.qml, theme/, components/, layout/, features/
```

A **device module** describes what a device looks like: its artwork, its hotspots, button labels
and which buttons are locked. A **feature** describes what you can do with it: a controller and
two generic QML panels. Modules declare which features they support. They never talk to the API
themselves.

### Adding a device

1. Create a package `src/olhclient/devices/<family>/` that exposes `MODULES`, a list of
   `DeviceModule` instances. Implement `match_score(device_json)`, usually by checking
   `ProductId` and `Template` from `GET /api/devices/{serial}`.
2. Add a `layout.json` with one entry per view. Each view has an image and hotspots. Hotspot
   rects are in the image's pixel space (`size`), and each hotspot is keyed by the button
   **name** OpenLinkHub reports in `KeyAssignment`. Two optional callouts are available:
   `keypad` (a grid) and `button_list`.
3. Put the artwork in `assets/`. A `side.png` next to `side.svg` is used instead of the SVG, and
   `assets/<module id>/` overrides the shared images. That is where real renders go.

The registry discovers modules automatically. Modules can also ship in another package through
the `olhclient.devices` entry-point group.

### Adding a feature

1. Add a member to `Feature` in `devices/features.py`.
2. Write a controller in `core/features/` and register it in `CONTROLLERS`.
3. Write its list and editor QML in `qml/features/`.
4. Add the feature to the `features` of the modules that support it. A module can replace the
   generic editor by returning a QML file from `qml_override(feature)`.

## Tests

```sh
uv run pytest              # or .venv/bin/python -m pytest with a system PySide6
```

The fixtures in `tests/fixtures/` were captured from a real Scimitar Elite SE, with serials and
paths anonymised. The legacy fixture is derived from it using the bitmasks of the
`scimitarrgbelite` driver. The QML smoke test runs on the `offscreen` platform.

## Notes on the OpenLinkHub API

- Errors come back as HTTP 200 with `"status": 0` and a `message`.
- `GET /api/devices/{serial}` always has `status` 0. Success means a `device` key is present.
- Key indexes are bitmasks that differ between Scimitar generations. Button names do not, which
  is why layouts are keyed by name.
- `POST /api/mouse/dpi` answers with an error when nothing changed, so the client only sends
  stages that differ.

## Licence

GPL-3.0, same as OpenLinkHub. The artwork in `devices/*/assets` is original to this project.
Corsair, iCUE and Scimitar are trademarks of their respective owner. This project is not
affiliated with them.
