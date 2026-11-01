Keyboard layouts copied unchanged from OpenLinkHub's `database/keyboard/` (GPL-3.0, like this
project): `k70core.json` (US), `k65plus-iso.json` (ISO Enter) and `k100.json` (LED bars, G keys,
media row).

`openlinkhub_page.json` holds where OpenLinkHub's own keyboard page draws every key of those
layouts: OpenLinkHub's template and `static/css/themes/default.css` rendered in a browser at the
page's 60 px key size, each key measured with `getBoundingClientRect()`. `tests/test_keyboard_grid.py`
checks `olhclient.api.keyboard_grid` against it.
