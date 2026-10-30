pragma Singleton
import QtQuick

// iCUE-inspired dark palette. Colours only; no vendor logos or assets.
QtObject {
    readonly property color window: "#161616"
    readonly property color topBar: "#0d0d0d"
    readonly property color panel: "#242424"
    readonly property color panelAlt: "#1c1c1c"
    readonly property color header: "#2e2e2e"
    readonly property color field: "#1a1a1a"
    readonly property color border: "#3c3c3c"
    readonly property color borderStrong: "#5a5a5a"
    readonly property color hover: "#333333"
    readonly property color text: "#d6d6d6"
    readonly property color textDim: "#8c8c8c"
    readonly property color textMuted: "#5e5e5e"
    readonly property color accent: "#f2c500"
    readonly property color accentDim: "#8a7200"
    readonly property color accentInk: "#141414"
    readonly property color danger: "#e5534b"
    readonly property color success: "#7bc950"
    readonly property color stageTop: "#45464a"
    readonly property color stageBottom: "#232427"

    readonly property int headerHeight: 36
    readonly property int gap: 12
    readonly property int radius: 2
    readonly property int fontSmall: 11
    readonly property int fontNormal: 13
    readonly property int fontLarge: 16
    readonly property int fontHeader: 17
}
