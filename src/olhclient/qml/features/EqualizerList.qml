import QtQuick
import QtQuick.Layouts
import "../theme"

// Overview of the equalizer bands.
ListView {
    id: root
    property var controller
    property var session

    topMargin: 10
    clip: true
    model: controller ? controller.bands : []

    delegate: Item {
        id: row
        required property var modelData
        width: ListView.view.width
        height: 28

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: row.modelData.name
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            Text {
                text: (row.modelData.value > 0 ? "+" : "") + row.modelData.value.toFixed(1) + " dB"
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }
        }
    }
}
