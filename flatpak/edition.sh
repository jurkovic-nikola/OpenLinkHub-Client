# Sourced by the build scripts: EDITION (first argument, default openlinkhub) -> APP_ID, MANIFEST, BUNDLE_NAME.
# The editions are defined in src/olhclient/edition.py.
EDITION="${1:-openlinkhub}"
case "$EDITION" in
    openlinkhub) APP_ID="io.github.mdmatthias.OpenLinkHub-Client"; BUNDLE_NAME="OpenLinkHub-Client" ;;
    plus) APP_ID="io.github.mdmatthias.OpenLinkHub-Client-Plus"; BUNDLE_NAME="OpenLinkHub-Client-Plus" ;;
    devices) APP_ID="io.github.mdmatthias.OpenDeviceHub"; BUNDLE_NAME="OpenDeviceHub" ;;
    *) echo "Unknown edition $EDITION (openlinkhub, plus or devices)" >&2; exit 2 ;;
esac
MANIFEST="flatpak/${APP_ID}.yaml"
