import QtQuick
import QtQuick.Layouts
import "../theme"

// Overview of the lighting: effect, brightness and the zone colours.
ListView {
    id: root
    property var controller
    property var session

    topMargin: 10
    clip: true
    model: controller ? controller.zones : null

    header: ColumnLayout {
        width: ListView.view.width
        spacing: 2
        Repeater {
            model: root.controller && root.controller.available
                   ? [["Effect", root.controller.effectTitle], ["Brightness", root.controller.brightness + " %"]]
                   : []
            RowLayout {
                required property var modelData
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                Layout.preferredHeight: 30
                Text {
                    Layout.fillWidth: true
                    text: parent.modelData[0]
                    color: Theme.text
                    font.pixelSize: Theme.fontNormal
                }
                Text {
                    text: parent.modelData[1]
                    color: Theme.accent
                    font.pixelSize: Theme.fontNormal
                }
            }
        }
        Text {
            Layout.leftMargin: 12
            Layout.topMargin: 8
            Layout.bottomMargin: 4
            visible: root.count > 0
            text: "ZONES"
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            font.bold: true
        }
    }

    delegate: Item {
        id: row
        required property string name
        required property string color
        width: ListView.view.width
        height: 30

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Rectangle {
                implicitWidth: 12
                implicitHeight: 12
                radius: 2
                color: row.color
                border.color: "#000000"
            }
            Text {
                Layout.fillWidth: true
                text: row.name
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            Text {
                text: row.color
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
            }
        }
    }
}
