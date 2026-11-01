import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// Small HSV colour picker. Call pick("#rrggbb", fn) and fn("#rrggbb") runs on OK.
Popup {
    id: root
    property real hue: 0
    property real saturation: 1
    property real brightness: 1
    property var callback: null
    readonly property color current: Qt.hsva(hue, saturation, brightness, 1)

    function hex(c) {
        const part = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + part(c.r) + part(c.g) + part(c.b)
    }

    function setColor(c) {
        if (c.hsvHue >= 0)
            hue = c.hsvHue
        saturation = c.hsvSaturation
        brightness = c.hsvValue
    }

    function pick(initial, fn) {
        setColor(Qt.color(initial))
        callback = fn
        hexField.text = hex(current)
        open()
    }

    modal: true
    focus: true
    padding: 14
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onCurrentChanged: if (!hexField.activeFocus) hexField.text = hex(current)

    background: Rectangle {
        color: Theme.panel
        border.color: Theme.accent
    }

    contentItem: ColumnLayout {
        spacing: 10

        // saturation (x) / brightness (y) square
        Rectangle {
            id: square
            Layout.preferredWidth: 220
            Layout.preferredHeight: 150
            color: Qt.hsva(root.hue, 1, 1, 1)
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#ffffffff" }
                    GradientStop { position: 1; color: "#00ffffff" }
                }
            }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: "#00000000" }
                    GradientStop { position: 1; color: "#ff000000" }
                }
            }
            Rectangle {
                x: root.saturation * parent.width - width / 2
                y: (1 - root.brightness) * parent.height - height / 2
                width: 12
                height: 12
                radius: 6
                color: "transparent"
                border.color: root.brightness > 0.5 ? "#000000" : "#ffffff"
                border.width: 2
            }
            MouseArea {
                anchors.fill: parent
                function update(mouse) {
                    root.saturation = Math.max(0, Math.min(1, mouse.x / width))
                    root.brightness = 1 - Math.max(0, Math.min(1, mouse.y / height))
                }
                onPressed: mouse => update(mouse)
                onPositionChanged: mouse => update(mouse)
            }
        }

        // hue strip
        Rectangle {
            Layout.preferredWidth: 220
            Layout.preferredHeight: 14
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0 / 6; color: "#ff0000" }
                GradientStop { position: 1 / 6; color: "#ffff00" }
                GradientStop { position: 2 / 6; color: "#00ff00" }
                GradientStop { position: 3 / 6; color: "#00ffff" }
                GradientStop { position: 4 / 6; color: "#0000ff" }
                GradientStop { position: 5 / 6; color: "#ff00ff" }
                GradientStop { position: 6 / 6; color: "#ff0000" }
            }
            Rectangle {
                x: root.hue * parent.width - width / 2
                y: -2
                width: 6
                height: parent.height + 4
                color: "transparent"
                border.color: "#ffffff"
                border.width: 2
            }
            MouseArea {
                anchors.fill: parent
                function update(mouse) { root.hue = Math.max(0, Math.min(0.999, mouse.x / width)) }
                onPressed: mouse => update(mouse)
                onPositionChanged: mouse => update(mouse)
            }
        }

        RowLayout {
            spacing: 8
            Rectangle {
                implicitWidth: 30
                implicitHeight: 30
                color: root.current
                border.color: Theme.borderStrong
            }
            DarkTextField {
                id: hexField
                Layout.preferredWidth: 90
                maximumLength: 7
                validator: RegularExpressionValidator { regularExpression: /#?[0-9a-fA-F]{0,6}/ }
                onTextEdited: {
                    const value = text.startsWith("#") ? text : "#" + text
                    if (value.length === 7)
                        root.setColor(Qt.color(value))
                }
            }
            Item { Layout.fillWidth: true }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            AccentButton {
                text: "Cancel"
                onClicked: root.close()
            }
            AccentButton {
                accent: true
                text: "OK"
                onClicked: {
                    if (root.callback)
                        root.callback(root.hex(root.current))
                    root.close()
                }
            }
        }
    }
}
