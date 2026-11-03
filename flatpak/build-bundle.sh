#!/usr/bin/env bash
# Build <bundle name>-<version>.flatpak, as the release workflow does.
# Usage: build-bundle.sh [openlinkhub|plus|devices]
set -euo pipefail

cd "$(dirname "$0")/.."
source flatpak/edition.sh "${1:-openlinkhub}"
VERSION="v$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/olhclient/__init__.py)"
BUNDLE="${BUNDLE_NAME}-${VERSION}.flatpak"

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y --noninteractive flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --force-clean --install-deps-from=flathub \
    --repo=repo "build-dir/$EDITION" "$MANIFEST"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo repo "$BUNDLE" "$APP_ID"
echo "Built $BUNDLE"
