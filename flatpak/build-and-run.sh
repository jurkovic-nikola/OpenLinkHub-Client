#!/usr/bin/env bash
# Build, install (per user) and run the Flatpak from this checkout.
set -euo pipefail

cd "$(dirname "$0")/.."

MANIFEST="flatpak/io.github.mdmatthias.OpenLinkHub-Client.yaml"
APP_ID="io.github.mdmatthias.OpenLinkHub-Client"

# org.flatpak.Builder from Flathub bundles its own flatpak, so distro flatpak regressions don't matter.
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y --noninteractive flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --install --force-clean --install-deps-from=flathub \
    build-dir "$MANIFEST"
flatpak run "$APP_ID" "$@"
