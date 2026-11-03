import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Keychron lighting: every change applies at once and is stored on the keyboard.
Item {
    id: root
    property var controller
    property var session

    Connections {
        target: root.controller
        // controls lose their bindings once the user changes them; restore them
        function onChanged() {
            if (!brightnessSlider.pressed)
                brightnessSlider.value = root.controller.brightness
            if (!speedSlider.pressed)
                speedSlider.value = root.controller.speed
            effectBox.currentIndex = Qt.binding(() => root.controller ? root.controller.effect : -1)
        }
    }

    ColorPicker {
        id: picker
        anchors.centerIn: parent
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        EditorHeader {
            Layout.fillWidth: true
            title: "LIGHTING"
            icon: "../icons/lighting.svg"
            Text {
                text: "Changes apply immediately"
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
            }
        }

        GridLayout {
            Layout.margins: 24
            visible: root.controller !== null && root.controller.available
            columns: 3
            columnSpacing: 18
            rowSpacing: 12

            Text { text: "Effect"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkComboBox {
                id: effectBox
                Layout.preferredWidth: 220
                model: root.controller ? root.controller.effects : []
                // effects are numbered 0, 1, 2… in list order
                currentIndex: root.controller ? root.controller.effect : -1
                onActivated: index => root.controller.setEffect(model[index].value)
            }
            Item { implicitWidth: 1 }

            Text { text: "Brightness"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkSlider {
                id: brightnessSlider
                Layout.preferredWidth: 220
                from: 0
                to: 100
                stepSize: 1
                value: root.controller ? root.controller.brightness : 0
                // apply when the slider is let go, or shortly after keyboard/wheel changes
                onPressedChanged: if (!pressed) root.controller.setBrightness(Math.round(value))
                onMoved: if (!pressed) brightnessTimer.restart()
                Timer {
                    id: brightnessTimer
                    interval: 400
                    onTriggered: root.controller.setBrightness(Math.round(brightnessSlider.value))
                }
            }
            Text {
                text: Math.round(brightnessSlider.value) + " %"
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }

            Text { text: "Speed"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkSlider {
                id: speedSlider
                Layout.preferredWidth: 220
                from: 0
                to: 100
                stepSize: 1
                value: root.controller ? root.controller.speed : 0
                onPressedChanged: if (!pressed) root.controller.setSpeed(Math.round(value))
                onMoved: if (!pressed) speedTimer.restart()
                Timer {
                    id: speedTimer
                    interval: 400
                    onTriggered: root.controller.setSpeed(Math.round(speedSlider.value))
                }
            }
            Text {
                text: Math.round(speedSlider.value) + " %"
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }

            Text { text: "Colour"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            ColorSwatch {
                color: root.controller ? root.controller.color : "#000000"
                onClicked: picker.pick(root.controller.color, c => root.controller.setColor(c))
            }
            Text {
                text: root.controller ? root.controller.color : ""
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
                font.family: "monospace"
            }

            Item { implicitHeight: 1 }
            Text {
                Layout.columnSpan: 2
                Layout.maximumWidth: 360
                text: "The colour is used by single-colour effects (solid, breathing, reactive…). Brightness is set separately."
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }
        }

        Item { Layout.fillHeight: true }
    }
}
