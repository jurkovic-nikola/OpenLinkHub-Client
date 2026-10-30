import QtQuick
import "../theme"

Row {
    id: root
    property int count: 0
    property int current: 0
    signal selected(int index)
    spacing: 6

    Repeater {
        model: root.count
        Rectangle {
            required property int index
            width: 12
            height: 12
            radius: 6
            color: index === root.current ? Theme.accent : "transparent"
            border.color: Theme.accent
            border.width: 2
            MouseArea {
                anchors.fill: parent
                anchors.margins: -4
                cursorShape: Qt.PointingHandCursor
                onClicked: root.selected(parent.index)
            }
        }
    }
}
