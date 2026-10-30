import QtQuick
import "../theme"

// Small key cap with a label, e.g. "G11". Yellow frame when selected.
Rectangle {
    id: root
    property string label
    property bool selected: false
    property bool locked: false
    property bool hovered: mouse.containsMouse
    signal clicked()

    implicitWidth: 44
    implicitHeight: 26
    color: selected ? "#2a2610" : hovered && !locked ? Theme.hover : "#2a2a2a"
    border.color: selected ? Theme.accent : Theme.borderStrong
    border.width: selected ? 2 : 1
    opacity: locked ? 0.45 : 1

    // corner tick like the iCUE key callouts
    Canvas {
        width: 8
        height: 8
        onPaint: {
            const ctx = getContext("2d")
            ctx.fillStyle = Theme.accent
            ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(8, 0); ctx.lineTo(0, 8); ctx.closePath(); ctx.fill()
        }
    }
    Text {
        anchors.centerIn: parent
        text: root.label
        color: root.selected ? Theme.accent : Theme.text
        font.pixelSize: Theme.fontSmall + 1
        font.bold: true
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
        onClicked: if (!root.locked) root.clicked()
    }
}
