# OpenLinkHub Client

A desktop client for [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub), built with
PySide6 and QML. It talks to the OpenLinkHub HTTP API only: no direct USB access, no changes
to OpenLinkHub itself. The UI follows the iCUE layout (device artwork with clickable buttons,
an action list and a settings panel) but uses its own artwork.

**Status:** it supports the Scimitar family with:

- **Key remapping** for every remappable button.
- **DPI**: stage values and stage colours.
- **Lighting**: effect, brightness, zone colours, RGB cluster and OpenRGB integration.
- **Device settings**: polling rate, lift-off distance, sleep timer, angle snapping and button
  response optimization, as far as the model and connection mode support them.
- **Profiles**: switch the active OpenLinkHub user profile, create one from the current
  settings, delete one.
- **Slipstream receiver**: the USB dongle gets its own tile in the device list, like the
  receiver card in iCUE's Device Settings. It shows the firmware, the paired devices and the USB
  receiver polling rate, which applies to every device on the dongle. Changing the rate restarts
  the receiver; its devices reconnect after 5–8 seconds.

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

OpenLinkHub hides Slipstream receivers from its dashboard and cannot return them as JSON
(`GET /api/devices/{serial}` answers with an empty body). The client finds them through
`/api/devices` and reads their state from the dashboard page `/device/{serial}`. The polling
rate can only be changed on receivers whose OpenLinkHub driver supports it (product ids 7132,
11008 and 11035 at the time of writing); other receivers reject the change.

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
   **name** OpenLinkHub reports in `KeyAssignment`. `button_list` names the buttons listed in
   the callout next to the artwork; `keypad` holds the rows of a button grid (e.g. G1–G12),
   which are only reached through their hotspots.
3. Put the artwork in `assets/`. A `side.png` next to `side.svg` is used instead of the SVG, and
   `assets/<module id>/` overrides the shared images. That is where real renders go.
4. Declare `features`, and in `settings` the device settings the hardware supports
   (`pollingRate`, `liftHeight`, `sleepMode`, `angleSnapping`, `buttonOptimization`).

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
  stages that differ. Colours (DPI and zones) are only sent for stages and zones that changed.
- Zone colours are only shown by the `mouse` effect. The DPI LED always shows the colour of the
  active stage.
- Which device settings appear follows the OpenLinkHub web UI: the polling rate only when the
  driver lists `PollingRates` (not over the Slipstream dongle), the sleep timer only for
  wireless models on the dongle. The polling rate "Not Set" (0) is left out because the server
  refuses it.
- User profile names must be letters and numbers only. The active and the `default` profile
  cannot be deleted. Creating a profile copies the current settings; it does not switch to it.

## Licence

GPL-3.0, same as OpenLinkHub. The artwork in `devices/*/assets` is original to this project.
Corsair, iCUE and Scimitar are trademarks of their respective owner. This project is not
affiliated with them.
