"""Keychron keyboards that run Keychron's ZMK firmware (the "Ultra 8K" series).

Unlike everything else in the client these do not go through OpenLinkHub: the
client talks to the keyboard's raw HID interface itself, with the VIA protocol
plus Keychron's own commands (see ``protocol.py``).
"""
