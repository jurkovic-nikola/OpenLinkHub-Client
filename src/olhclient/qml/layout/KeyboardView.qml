import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// A keyboard drawn from the key layout OpenLinkHub sends (see api/keyboard_grid.py):
// the same keys in the same places as on OpenLinkHub's own keyboard page.
Rectangle {
    id: root
    property var session
    readonly property var controller: session ? session.controller("keyboard_keys") : null
    readonly property var keys: controller ? controller.boardKeys : []
    readonly property real aspect: controller ? controller.boardAspect : 0
    signal keyActivated(string name)

    gradient: Gradient {
        GradientStop { position: 0.0; color: Theme.stageTop }
        GradientStop { position: 1.0; color: Theme.stageBottom }
    }
    clip: true

    AccentButton {
        id: openButton
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 10
        visible: root.session !== null
        text: "Open in OpenLinkHub"
        onClicked: root.session.openInBrowser()
    }
    Text {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        text: root.session ? [root.session.product, root.session.firmware ? "firmware " + root.session.firmware : ""]
                             .filter(t => t).join("  ·  ") : ""
        color: Theme.textDim
        font.pixelSize: Theme.fontSmall
    }

    Item {
        id: board
        readonly property real availableWidth: root.width - 48
        readonly property real availableHeight: root.height - openButton.height - 40
        width: root.aspect > 0 ? Math.min(availableWidth, availableHeight * root.aspect) : 0
        height: root.aspect > 0 ? width / root.aspect : 0
        // size of a plain key, for the text
        readonly property real unit: root.keys.length ? Math.min(...root.keys.filter(k => !k.bar).map(k => k.h)) * height : 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: openButton.height / 2

        Repeater {
            model: root.keys
            Rectangle {
                id: key
                required property var modelData
                readonly property bool current: root.session !== null && root.session.selectedButton === modelData.name
                readonly property bool clickable: !modelData.locked && !modelData.bar
                x: modelData.x * board.width
                y: modelData.y * board.height
                width: modelData.w * board.width
                height: modelData.h * board.height
                radius: Math.min(width, height) * 0.12
                color: modelData.bar ? modelData.color
                     : current ? "#2a2610" : keyMouse.containsMouse && clickable ? "#262626" : "#1c1c1c"
                opacity: modelData.bar ? 0.55 : modelData.locked ? 0.5 : 1
                border.color: current ? Theme.accent : keyMouse.containsMouse && clickable ? Theme.accentDim : "#474747"
                border.width: current ? 2 : 1

                Text {
                    anchors.fill: parent
                    anchors.margins: 2
                    visible: !key.modelData.bar
                    text: key.modelData.label
                    color: key.modelData.color
                    font.pixelSize: Math.max(7, board.unit * 0.24)
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: 6
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                }
                // remapped keys
                Rectangle {
                    visible: key.modelData.remapped && !key.modelData.bar
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: Math.max(2, parent.height * 0.08)
                    width: Math.max(4, parent.height * 0.12)
                    height: width
                    radius: width / 2
                    color: Theme.accent
                }
                MouseArea {
                    id: keyMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: key.clickable
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.session.selectedButton = key.modelData.name
                        root.keyActivated(key.modelData.name)
                    }
                }
            }
        }
    }
}
