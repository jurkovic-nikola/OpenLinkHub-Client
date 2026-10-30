import QtQuick
import QtQuick.Layouts
import "../theme"

// Overview of the DPI stages; the active stage is highlighted.
ListView {
    id: root
    property var controller
    property var session

    topMargin: 10
    clip: true
    model: controller ? controller.stages : null

    delegate: Item {
        id: row
        required property string name
        required property int value
        required property string color
        required property bool active
        width: ListView.view.width
        height: 30

        Rectangle {
            anchors.fill: parent
            color: row.active ? Theme.accent : "transparent"
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Rectangle {
                implicitWidth: 12
                implicitHeight: 12
                radius: 6
                color: row.color
                border.color: "#000000"
            }
            Text {
                Layout.fillWidth: true
                text: row.name + (row.active ? "  (active)" : "")
                color: row.active ? Theme.accentInk : Theme.text
                font.pixelSize: Theme.fontNormal
            }
            Text {
                text: row.value + " DPI"
                color: row.active ? Theme.accentInk : Theme.textDim
                font.pixelSize: Theme.fontNormal
            }
        }
    }
}
