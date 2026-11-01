import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Effect, brightness and toggles apply at once; zone colours are saved together.
Item {
    id: root
    property var controller
    property var session

    property var draft: []
    readonly property var zones: controller ? controller.zones : null

    readonly property bool dirty: {
        if (!zones)
            return false
        for (let i = 0; i < zones.count; ++i)
            if (draft[i] !== undefined && draft[i] !== zones.get(i).color.toLowerCase())
                return true
        return false
    }

    function revert() {
        const colors = []
        if (zones)
            for (let i = 0; i < zones.count; ++i)
                colors.push(zones.get(i).color.toLowerCase())
        draft = colors
    }

    function setColor(i, color) {
        const copy = draft.slice()
        copy[i] = color
        draft = copy
    }

    onControllerChanged: revert()
    Connections {
        target: root.zones
        function onDataChanged() { if (!root.dirty) root.revert() }
        function onModelReset() { root.revert() }
    }
    Connections {
        target: root.controller
        // controls lose their bindings once the user changes them; restore them
        function onChanged() {
            if (!brightnessSlider.pressed)
                brightnessSlider.value = root.controller.brightness
            effectBox.currentIndex = Qt.binding(() => effectBox.indexOfEffect())
            clusterSwitch.checked = Qt.binding(() => root.controller.rgbCluster)
            openRgbSwitch.checked = Qt.binding(() => root.controller.openRgb)
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
            AccentButton {
                text: "Revert"
                enabled: root.dirty
                onClicked: root.revert()
            }
            AccentButton {
                accent: true
                text: root.controller && root.controller.saving ? "Saving…" : "Save colours"
                enabled: root.dirty && !(root.controller && root.controller.saving)
                onClicked: root.controller.saveZoneColors(root.draft)
            }
        }

        Text {
            Layout.margins: 24
            visible: !root.controller || !root.controller.available
            text: "This device reports no lighting settings."
            color: Theme.textDim
            font.pixelSize: Theme.fontNormal
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 24
            visible: root.controller !== null && root.controller.available
            spacing: 48

            // -- effect -------------------------------------------------------
            GridLayout {
                Layout.alignment: Qt.AlignTop
                columns: 2
                columnSpacing: 18
                rowSpacing: 12

                Text { text: "Effect"; color: Theme.text; font.pixelSize: Theme.fontNormal }
                DarkComboBox {
                    id: effectBox
                    function indexOfEffect() {
                        for (let i = 0; i < model.length; ++i)
                            if (model[i].value === root.controller.effect)
                                return i
                        return -1
                    }
                    Layout.preferredWidth: 220
                    model: root.controller ? root.controller.effects : []
                    currentIndex: indexOfEffect()
                    onActivated: index => root.controller.setEffect(model[index].value)
                }

                Text { text: "Brightness"; color: Theme.text; font.pixelSize: Theme.fontNormal }
                // drivers have either a 0-100 slider or stepped brightness
                DarkComboBox {
                    visible: root.controller !== null && !root.controller.hasBrightness
                    Layout.preferredWidth: 220
                    model: root.controller ? root.controller.brightnessModes : []
                    currentIndex: {
                        for (let i = 0; i < model.length; ++i)
                            if (model[i].value === root.controller.brightnessMode)
                                return i
                        return -1
                    }
                    displayText: currentIndex < 0 ? "Not available" : currentText
                    enabled: model.length > 0
                    onActivated: index => root.controller.setBrightnessMode(model[index].value)
                }
                RowLayout {
                    visible: root.controller !== null && root.controller.hasBrightness
                    spacing: 10
                    DarkSlider {
                        id: brightnessSlider
                        Layout.preferredWidth: 170
                        from: 0
                        to: 100
                        stepSize: 1
                        value: root.controller ? root.controller.brightness : 0
                        // apply when the slider is let go, or shortly after keyboard/wheel changes
                        onPressedChanged: if (!pressed) root.controller.setBrightness(Math.round(value))
                        onMoved: if (!pressed) brightnessTimer.restart()
                    }
                    Text {
                        Layout.preferredWidth: 40
                        text: Math.round(brightnessSlider.value) + " %"
                        color: Theme.accent
                        font.pixelSize: Theme.fontNormal
                    }
                    Timer {
                        id: brightnessTimer
                        interval: 400
                        onTriggered: root.controller.setBrightness(Math.round(brightnessSlider.value))
                    }
                }

                Text {
                    visible: clusterSwitch.visible
                    text: "RGB cluster"; color: Theme.text; font.pixelSize: Theme.fontNormal
                }
                DarkSwitch {
                    id: clusterSwitch
                    visible: root.controller !== null && root.controller.hasRgbCluster
                    checked: root.controller ? root.controller.rgbCluster : false
                    onToggled: root.controller.setRgbCluster(checked)
                }

                Text {
                    visible: openRgbSwitch.visible
                    text: "OpenRGB integration"; color: Theme.text; font.pixelSize: Theme.fontNormal
                }
                DarkSwitch {
                    id: openRgbSwitch
                    visible: root.controller !== null && root.controller.hasOpenRgb
                    checked: root.controller ? root.controller.openRgb : false
                    onToggled: root.controller.setOpenRgb(checked)
                }

                Item { implicitHeight: 1 }
                Text {
                    Layout.maximumWidth: 260
                    visible: root.controller !== null && (root.controller.openRgb || root.controller.rgbCluster)
                    text: root.controller && root.controller.openRgb
                          ? "OpenRGB controls the LEDs; effect and colours are not used."
                          : "The RGB cluster controls the LEDs; effect and colours are not used."
                    wrapMode: Text.Wrap
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                }
            }

            // -- zone colours -------------------------------------------------
            ColumnLayout {
                visible: root.zones !== null && root.zones.count > 0
                Layout.alignment: Qt.AlignTop
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: "ZONE COLOURS"
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                    font.bold: true
                }
                Repeater {
                    model: root.zones
                    RowLayout {
                        id: zoneRow
                        required property int index
                        required property string name
                        readonly property string draftColor: root.draft[index] !== undefined ? root.draft[index] : "#000000"
                        spacing: 12
                        ColorSwatch {
                            color: zoneRow.draftColor
                            onClicked: picker.pick(zoneRow.draftColor, c => root.setColor(zoneRow.index, c))
                        }
                        Text {
                            Layout.preferredWidth: 90
                            text: zoneRow.name
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                        Text {
                            text: zoneRow.draftColor
                            color: Theme.textDim
                            font.pixelSize: Theme.fontNormal
                            font.family: "monospace"
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    text: root.session && root.session.kind === "mouse"
                          ? "Zone colours are used by the \"Mouse\" effect. The DPI LED always shows the colour of the active DPI stage."
                          : "Which effects use the zone colours depends on the device."
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
