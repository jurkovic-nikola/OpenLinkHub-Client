import QtQuick
import QtQuick.Controls
import "../theme"

Switch {
    id: control
    font.pixelSize: Theme.fontNormal
    spacing: 10

    indicator: Rectangle {
        implicitWidth: 40
        implicitHeight: 20
        x: control.leftPadding
        y: (control.height - height) / 2
        radius: 10
        color: control.checked ? Theme.accent : "#3a3a3a"
        opacity: control.enabled ? 1 : 0.4
        Rectangle {
            x: control.checked ? parent.width - width - 2 : 2
            y: 2
            width: 16
            height: 16
            radius: 8
            color: control.checked ? Theme.accentInk : "#bbbbbb"
            Behavior on x { NumberAnimation { duration: 120 } }
        }
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.enabled ? Theme.text : Theme.textMuted
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + control.spacing
    }
}
