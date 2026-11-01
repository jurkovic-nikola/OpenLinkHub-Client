import QtQuick
import QtQuick.Layouts
import "../theme"

// Channels of a hub or AIO cooler with their live speed and temperature.
ListView {
    id: root
    property var controller
    property var session

    topMargin: 10
    clip: true
    model: controller ? controller.channels : null

    delegate: Rectangle {
        id: row
        required property string key
        required property string title
        required property int rpm
        required property string temperature
        required property string speedProfile
        required property string rgbProfile
        readonly property bool current: root.controller && root.controller.selectedKey === key
        width: ListView.view.width
        height: 44
        color: current ? Theme.accent : rowMouse.containsMouse ? Theme.hover : "transparent"

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            anchors.topMargin: 4
            anchors.bottomMargin: 4
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: row.title
                    color: row.current ? Theme.accentInk : Theme.text
                    font.pixelSize: Theme.fontNormal
                    elide: Text.ElideRight
                }
                Text {
                    text: [row.rpm >= 0 ? row.rpm + " RPM" : "", row.temperature].filter(t => t).join("  ·  ")
                    color: row.current ? Theme.accentInk : Theme.accent
                    font.pixelSize: Theme.fontNormal
                }
            }
            Text {
                Layout.fillWidth: true
                text: [row.speedProfile, row.rgbProfile].filter(t => t).join("  ·  ")
                color: row.current ? Theme.accentInk : Theme.textDim
                font.pixelSize: Theme.fontSmall
                elide: Text.ElideRight
            }
        }
        MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.controller.selectedKey = row.key
        }
    }
}
