import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

Panel {
    id: root
    property var backend
    title: "Devices"
    icon: Qt.resolvedUrl("../icons/devices.svg")
    implicitHeight: Theme.headerHeight + 92

    ListView {
        anchors.fill: parent
        anchors.leftMargin: 8
        orientation: ListView.Horizontal
        spacing: 6
        model: root.backend ? root.backend.devices : null
        delegate: Item {
            id: tile
            required property string serial
            required property string product
            required property string thumbnail
            required property int battery
            readonly property bool current: root.backend.selectedSerial === serial
            width: 160
            height: ListView.view.height

            Rectangle {
                anchors.fill: parent
                anchors.topMargin: 6
                color: tileMouse.containsMouse && !tile.current ? Theme.hover : "transparent"
            }
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 10
                width: 130
                height: 50
                source: tile.thumbnail
                sourceSize: Qt.size(220, 100)
                fillMode: Image.PreserveAspectFit
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 62
                width: parent.width - 8
                horizontalAlignment: Text.AlignHCenter
                text: tile.product + (tile.battery >= 0 ? "  " + tile.battery + "%" : "")
                color: tile.current ? Theme.text : Theme.textDim
                font.pixelSize: Theme.fontSmall
                elide: Text.ElideRight
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 3
                color: Theme.accent
                visible: tile.current
            }
            MouseArea {
                id: tileMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.backend.selectDevice(tile.serial)
            }
        }
    }
}
