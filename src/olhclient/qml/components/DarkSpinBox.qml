import QtQuick
import QtQuick.Controls
import "../theme"

SpinBox {
    id: control
    editable: true
    implicitWidth: 120
    implicitHeight: 30
    font.pixelSize: Theme.fontNormal
    // plain integers: no locale thousands separators for DPI values
    textFromValue: (value, locale) => value.toString()
    valueFromText: (text, locale) => parseInt(text, 10) || 0
    validator: IntValidator { bottom: control.from; top: control.to }

    contentItem: TextInput {
        text: control.displayText
        font: control.font
        color: Theme.text
        selectionColor: Theme.accent
        selectedTextColor: Theme.accentInk
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: Qt.ImhDigitsOnly
    }
    up.indicator: Rectangle {
        x: control.width - width
        height: control.height
        implicitWidth: 26
        color: control.up.pressed ? Theme.hover : "#2a2a2a"
        border.color: Theme.borderStrong
        Text { anchors.centerIn: parent; text: "+"; color: Theme.text; font.pixelSize: 15 }
    }
    down.indicator: Rectangle {
        x: 0
        height: control.height
        implicitWidth: 26
        color: control.down.pressed ? Theme.hover : "#2a2a2a"
        border.color: Theme.borderStrong
        Text { anchors.centerIn: parent; text: "−"; color: Theme.text; font.pixelSize: 15 }
    }
    background: Rectangle {
        color: Theme.field
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
    }
}
