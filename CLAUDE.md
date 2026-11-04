# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Desktop client (Python, PySide6 + QML) for the [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub)
HTTP API, which drives Corsair devices on Linux. The client talks HTTP to OpenLinkHub (default
`http://127.0.0.1:27003`) and never touches Corsair devices itself. The exception is Keychron
keyboards with Keychron's ZMK firmware, which the client drives directly over `/dev/hidraw*`
(`keychron/`), and Gigabyte RGB Fusion 2 graphics cards, driven over `/dev/i2c-*` (`gpu/`).

## Commands

The local `.venv` uses the system PySide6 (`include-system-site-packages = true`), so run things
through `.venv/bin/python` rather than `uv run`:

```sh
.venv/bin/python -m pytest                                  # all tests (~5 s)
.venv/bin/python -m pytest tests/test_qml_smoke.py          # one file
.venv/bin/python -m pytest tests/test_features.py -k dpi    # one test / pattern
.venv/bin/olh-client --debug [--url URL] [--insecure]       # run the app (or: python -m olhclient)
```

With a PyPI PySide6 instead: `uv sync --extra dev` and `uv run pytest`. There is no linter or
formatter configured.

## Architecture

`src/olhclient/`:

- `api/` — `ApiClient` (synchronous httpx), typed models of the device JSON (`models.py`,
  `DeviceState.from_json`), `keyboard_grid.py` (port of OpenLinkHub's keyboard page CSS grid), and
  `receiver_page.py` (scrapes the Slipstream receiver's HTML dashboard page, because OpenLinkHub
  cannot return a receiver as JSON).
- `core/` — Qt objects exposed to QML:
  - `Worker`: runs blocking API calls on a `QThreadPool` and delivers callbacks on the GUI thread.
    Pass `owner=` so callbacks are dropped if that QObject was deleted. `Worker(synchronous=True)`
    runs inline; the tests use it.
  - `Backend`: root object given to QML; polls `GET /api/` on a timer, keeps the device list, owns
    the current `DeviceSession` or `ReceiverSession`.
  - `DeviceSession`: the selected device. Builds its feature controllers once, at open, from
    `CONTROLLERS` filtered by `controller.supports(state)` and `module.features`. `reload()`
    coalesces overlapping fetches.
  - `core/features/*`: one `FeatureController` per feature. Writes go through
    `FeatureController.write()`, which reports success/error and always reloads the device, so
    the UI falls back to the real device state after a refused write.
  - `core/features/settings.py`: table of simple settings (options map in the device JSON, value
    in `DeviceProfile`, write to `/api/<kind>/<setting>`).
  - `macros.py`: `MacroLibrary` (QML `backend.macros`, the MACROS tab, `layout/MacrosView.qml`).
    Macros are global, not per device. `plan_macro` turns a saved macro plus the edited action
    list into API writes (see the macro quirk below).
  - `artwork.py`: recolours SVG artwork by lighting zone (`class="zone-<zone>"`) and drops
    `class="button-<name>"` elements for `missing_buttons`.
- `devices/` — optional device modules (artwork, hotspots, labels, limits). `Registry.discover()`
  imports every sub-package exposing `MODULES` plus the `olhclient.devices` entry-point group, and
  picks the module with the highest `match_score(device_json)`; `generic/` is the fallback.
  `devices/features.py` maps each `Feature` to its list/editor QML pair.
- `keychron/` — Keychron keyboards, driven by the client itself (OpenLinkHub does not support
  them): `hidraw.py` (sysfs discovery and `/dev/hidrawN` I/O in pure Python), `protocol.py` (`KeychronClient`: VIA protocol 12 plus
  Keychron's 0xA1-0xA7 commands, from `app/src/launcher/launcher.c` in Keychron/zmk branch
  `rtl8762g`), `keycodes.py` (QMK keycodes), `boards.py` (per USB product id: matrix size, layers,
  key positions), `device.py` (`scan`, `read_state` -> `KeyboardState`). `core/keychron.py`
  `KeychronSession` mimics the QML API of `DeviceSession`; its controllers are in
  `core/features/keychron.py`. `Backend` scans for them on its poll timer, independently of
  OpenLinkHub being reachable (`keychron_scan`/`keychron_connect` are injectable for tests).
- `gpu/` — graphics card lighting, ported from OpenRGB's `GigabyteRGBFusion2GPUController`:
  `i2c.py` (sysfs bus discovery with PCI ids, `/dev/i2c-N` I/O), `cards.py` (OpenRGB's card list:
  PCI ids and address), `fusion2.py` (`Lighting` -> 8-byte writes, probe, save), `device.py`
  (`scan`, which probes and so runs once; `LightingStore`, because the card cannot be read back).
  `core/gpu.py` `GpuSession` mimics the QML API of `DeviceSession`; controller in
  `core/features/gpu.py`, editor `features/GpuLightingEditor.qml`. `Backend` takes
  `gpu_scan`/`gpu_connect`/`gpu_store`.
- `qml/` — `Main.qml`, `layout/` (views, panels), `features/` (list + editor per feature),
  `components/` (dark-themed controls), `theme/Theme.qml` (singleton via `qmldir`).

Data flow: device JSON → `DeviceState` (every part optional) → features whose `supports(state)` is
true → `DeviceSession.features` gives QML the list/editor QML URLs (a module may override the
editor via `qml_override`) and `session.controller(id)` returns the controller.

Adding a device or a feature: follow "Adding a device" / "Adding a feature" in `README.md`.
Layout hotspots are keyed by OpenLinkHub button **name**, not key index (indexes are bitmasks that
differ per Scimitar generation). Artwork must stay within SVG Tiny 1.2 (what Qt renders).

## Flatpak and releases

Three apps ("editions", `src/olhclient/edition.py`) come from this code: OpenLinkHub Client
(`openlinkhub`, OpenLinkHub only, the original app id), OpenLinkHub Client Plus (`plus`,
OpenLinkHub + Keychron + GPUs) and OpenDeviceHub (`devices`, Keychron and GPUs only: `Backend(api=None)`,
no macros tab). A Flatpak finds its edition through `FLATPAK_ID`; from source `--edition` picks one, default
`plus`.

`flatpak/` holds one manifest, desktop file and metainfo per app id (KDE runtime +
`io.qt.PySide.BaseApp`; the cleanup drops QtWebEngine, numpy and LLVM), `python-dependencies.json`
(httpx wheels with sha256; keep in sync with `pyproject.toml`) and the launcher. The manifests may
only differ in app id and permissions (`tests/test_edition.py` checks; only the Keychron/GPU editions
get `--device=all`). Release notes live only in the OpenLinkHub Client metainfo;
`flatpak/copy_releases.py` copies them into the others at build time. The app is copied to
`/app/share/olh-client` and started with `python3 -m olhclient`. `flatpak/build-and-run.sh
[edition]` builds and runs one locally; `flatpak/edition.sh` maps editions to ids and bundles.

Releasing: bump `__version__` in `src/olhclient/__init__.py` (the only version; `pyproject.toml`
reads it), add a `<release>` to the metainfo, push tag `v<version>`. `.github/workflows/flatpak.yml`
verifies tag/version/metainfo, builds `<bundle>-<tag>.flatpak` for each edition (a matrix) and
publishes one GitHub release with all three, whose description is the metainfo `<release>` notes
(`.github/scripts/release_notes.py`; `-dev` tags become prereleases). Each app's updater picks its
own bundle (`update.update_asset(release, edition)`).

Updates: `update.py` (GitHub latest release, download, `flatpak-spawn --host flatpak install`) and
`core/updater.py` (`Updater`, QML `updater`, state machine shown by `layout/UpdateDialog.qml`).
Only the Flatpak (`FLATPAK_ID` set) installs; other installs get a link to the release page.

## Testing

- `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` and provides `FakeApi`, an in-memory
  stand-in for `ApiClient` backed by `tests/fixtures/` (anonymised captures and fixtures built
  from OpenLinkHub's driver structs).
- `test_qml_smoke.py` loads the real `Main.qml`, opens every feature on every kind of device and
  **fails on any QML warning**, so QML changes must be warning-free.
- `QStandardPaths` test mode is on, so lit artwork is written to `~/.qttest`, not the real cache.
- `tests/fake_keychron.py` has `FakeKeyboard`, a transport that answers reports like the firmware.
- `tests/fake_gpu.py` has `FakeCard`, an I2C transport that records writes and answers the probe.

## OpenLinkHub API quirks

These shape much of the client code; the full list is in `README.md` ("Notes on the OpenLinkHub API").

- Errors come back as HTTP 200 with `"status": 0` and a `message`. `GET /api/devices/{serial}`
  always has `status` 0; success means a `device` key is present.
- Use `GET /api/` for the device list (it includes the kind icon); `/api/devices` omits it.
- Listed options do not prove the driver implements a setting; writes may still be refused.
- `POST /api/mouse/dpi` errors when nothing changed, so only changed stages/colours are sent.
- Keyboards use `/api/keyboard/updateKeyAssignment` and have no `InputActions`; action names come
  from `/api/input/*`.
- Macros: a new action gets index `len(actions)` and drivers play 0..len-1, so deleting a middle
  action leaves a gap. Saving rewrites the macro from the first changed action instead.
- PySide gotcha: return `"QVariant"` (not a QObject type) from slots that may return `None`, or QML
  receives an invalid object and crashes.
