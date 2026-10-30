import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: control
    implicitHeight: 30
    color: Theme.text
    placeholderTextColor: Theme.textMuted
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentInk
    font.pixelSize: Theme.fontNormal
    leftPadding: 8
    background: Rectangle {
        color: Theme.field
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
        radius: Theme.radius
    }
}
