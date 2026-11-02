#!/usr/bin/env bash
# Build OpenLinkHub-Client-<version>.flatpak, as the release workflow does.
set -euo pipefail

cd "$(dirname "$0")/.."

MANIFEST="flatpak/io.github.mdmatthias.OpenLinkHub-Client.yaml"
APP_ID="io.github.mdmatthias.OpenLinkHub-Client"
VERSION="v$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/olhclient/__init__.py)"
BUNDLE="OpenLinkHub-Client-${VERSION}.flatpak"

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y --noninteractive flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --force-clean --install-deps-from=flathub \
    --repo=repo build-dir "$MANIFEST"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo repo "$BUNDLE" "$APP_ID"
echo "Built $BUNDLE"
