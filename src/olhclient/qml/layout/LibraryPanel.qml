import QtQuick
import QtQuick.Layouts
import "../theme"

// Feature switcher at the bottom of the left column ("actions library" in iCUE).
ColumnLayout {
    id: root
    property var features: []
    property string currentId
    signal activated(string featureId)
    spacing: 1

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: Theme.headerHeight
        color: "#3a3a3a"
        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 14
            text: "FEATURES"
            color: Theme.text
            font.pixelSize: Theme.fontLarge
        }
    }
    Repeater {
        model: root.features
        Rectangle {
            id: row
            required property var modelData
            readonly property bool current: modelData.id === root.currentId
            Layout.fillWidth: true
            implicitHeight: 34
            color: current ? Theme.header : mouse.containsMouse ? Theme.hover : Theme.panel

            Rectangle {
                width: 3
                height: parent.height
                color: Theme.accent
                visible: row.current
            }
            Rectangle {
                id: iconTile
                x: 3
                width: 30
                height: parent.height
                color: "transparent"
                Image {
                    anchors.centerIn: parent
                    source: "../icons/" + row.modelData.id + ".svg"
                    sourceSize: Qt.size(18, 18)
                    opacity: row.current ? 1 : 0.6
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: iconTile.right
                anchors.leftMargin: 8
                text: row.modelData.title.toUpperCase()
                color: row.current ? Theme.accent : Theme.textDim
                font.pixelSize: Theme.fontLarge
            }
            MouseArea {
                id: mouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.activated(row.modelData.id)
            }
        }
    }
}
