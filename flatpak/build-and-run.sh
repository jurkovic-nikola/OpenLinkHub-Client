#!/usr/bin/env bash
# Build, install (per user) and run the Flatpak from this checkout.
# Usage: build-and-run.sh [openlinkhub|plus|devices] [app arguments...]
set -euo pipefail

cd "$(dirname "$0")/.."
source flatpak/edition.sh "${1:-openlinkhub}"
shift $(( $# > 0 ? 1 : 0 ))

# org.flatpak.Builder from Flathub bundles its own flatpak, so distro flatpak regressions don't matter.
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y --noninteractive flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --install --force-clean --install-deps-from=flathub \
    "build-dir/$EDITION" "$MANIFEST"
flatpak run "$APP_ID" "$@"
