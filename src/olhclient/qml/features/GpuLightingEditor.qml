import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Graphics card lighting: every change applies at once; "Save to card" keeps it after a power cycle.
Item {
    id: root
    property var controller
    property var session

    function effectIndex() {
        if (!controller)
            return -1
        const effects = controller.effects
        for (let i = 0; i < effects.length; i++)
            if (effects[i].value === controller.effect)
                return i
        return -1
    }

    Connections {
        target: root.controller
        // controls lose their bindings once the user changes them; restore them
        function onChanged() {
            if (!brightnessSlider.pressed)
                brightnessSlider.value = root.controller.brightness
            if (!speedSlider.pressed)
                speedSlider.value = root.controller.speed
            effectBox.currentIndex = Qt.binding(() => root.effectIndex())
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
            AccentButton {
                text: "Save to card"
                accent: true
                onClicked: root.controller.saveToCard()
            }
        }

        GridLayout {
            Layout.margins: 24
            visible: root.controller !== null
            columns: 3
            columnSpacing: 18
            rowSpacing: 12

            Text { text: "Mode"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkComboBox {
                id: effectBox
                Layout.preferredWidth: 220
                model: root.controller ? root.controller.effects : []
                currentIndex: root.effectIndex()
                onActivated: index => root.controller.setEffect(model[index].value)
            }
            Item { implicitWidth: 1 }

            Text {
                visible: brightnessSlider.visible
                text: "Brightness"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            DarkSlider {
                id: brightnessSlider
                visible: root.controller !== null && root.controller.hasBrightness
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
                visible: brightnessSlider.visible
                text: Math.round(brightnessSlider.value) + " %"
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }

            Text {
                visible: speedSlider.visible
                text: "Speed"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            DarkSlider {
                id: speedSlider
                visible: root.controller !== null && root.controller.hasSpeed
                Layout.preferredWidth: 220
                from: 0
                to: root.controller ? root.controller.speedMax : 1
                stepSize: 1
                snapMode: Slider.SnapAlways
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
                visible: speedSlider.visible
                text: Math.round(speedSlider.value) + " / " + speedSlider.to
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }

            Text {
                Layout.alignment: Qt.AlignTop
                visible: colorRow.visible
                text: "Colours"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            Flow {
                id: colorRow
                Layout.columnSpan: 2
                Layout.maximumWidth: 420
                visible: root.controller !== null && root.controller.colors.length > 0
                spacing: 12
                Repeater {
                    model: root.controller ? root.controller.colors : []
                    Column {
                        id: colorItem
                        required property int index
                        required property string modelData
                        spacing: 4
                        ColorSwatch {
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: colorItem.modelData
                            onClicked: picker.pick(colorItem.modelData, c => root.controller.setColor(colorItem.index, c))
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: (root.controller && root.controller.zoneColors ? "Zone " : "") + (colorItem.index + 1)
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }
                    }
                }
                Column {
                    visible: root.controller !== null && root.controller.zoneColors
                    spacing: 4
                    ColorSwatch {
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: root.controller && root.controller.colors.length ? root.controller.colors[0] : "#000000"
                        onClicked: picker.pick(root.controller.colors[0], c => root.controller.setColor(-1, c))
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "All"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                }
            }

            Item { implicitHeight: 1 }
            Text {
                Layout.columnSpan: 2
                Layout.maximumWidth: 420
                text: "The card cannot report its lighting: shown is what this app last set. Changes last until the "
                      + "computer is switched off; “Save to card” keeps them."
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }
        }

        Item { Layout.fillHeight: true }
    }
}
