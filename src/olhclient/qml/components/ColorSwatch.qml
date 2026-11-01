import QtQuick
import "../theme"

// Clickable colour square.
Rectangle {
    id: root
    property bool selected: false
    signal clicked()

    implicitWidth: 26
    implicitHeight: 26
    radius: Theme.radius
    border.color: selected || area.containsMouse ? Theme.accent : Theme.borderStrong
    border.width: selected ? 2 : 1

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
}
