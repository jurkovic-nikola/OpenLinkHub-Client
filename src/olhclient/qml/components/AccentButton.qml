import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: control
    property bool accent: false

    implicitHeight: 30
    leftPadding: 18
    rightPadding: 18
    font.pixelSize: Theme.fontNormal

    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? Theme.textMuted : control.accent ? Theme.accentInk : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        color: !control.enabled ? "#262626"
             : control.accent ? (control.down ? Theme.accentDim : Theme.accent)
             : control.down ? "#222" : control.hovered ? Theme.hover : "#2a2a2a"
        border.color: control.accent && control.enabled ? Theme.accent : Theme.borderStrong
        radius: Theme.radius
    }
}
