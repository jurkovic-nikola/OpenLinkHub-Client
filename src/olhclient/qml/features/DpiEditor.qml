import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Edit all DPI stages (value and LED colour) at once; only changed stages are sent on Save.
Item {
    id: root
    property var controller
    property var session

    property var draft: []
    property var colorDraft: []
    readonly property var stages: controller ? controller.stages : null

    readonly property bool dirty: {
        if (!stages)
            return false
        for (let i = 0; i < stages.count; ++i) {
            if (draft[i] !== undefined && draft[i] !== stages.get(i).value)
                return true
            if (colorDraft[i] !== undefined && colorDraft[i] !== stages.get(i).color.toLowerCase())
                return true
        }
        return false
    }

    function revert() {
        const values = []
        const colors = []
        if (stages)
            for (let i = 0; i < stages.count; ++i) {
                values.push(stages.get(i).value)
                colors.push(stages.get(i).color.toLowerCase())
            }
        draft = values
        colorDraft = colors
    }

    function setColor(i, color) {
        const copy = colorDraft.slice()
        copy[i] = color
        colorDraft = copy
    }

    function setValue(i, value) {
        if (draft[i] === value)
            return
        const copy = draft.slice()
        copy[i] = value
        draft = copy
    }

    onControllerChanged: revert()
    Connections {
        target: root.stages
        // pick up values saved elsewhere, but never clobber unsaved edits
        function onDataChanged() { if (!root.dirty) root.revert() }
        function onModelReset() { root.revert() }
    }

    ColorPicker {
        id: picker
        anchors.centerIn: parent
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 42
            color: Theme.panel
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 10
                Image {
                    source: "../icons/dpi.svg"
                    sourceSize: Qt.size(20, 20)
                }
                Text {
                    Layout.fillWidth: true
                    text: "DPI STAGES"
                    color: Theme.accent
                    font.pixelSize: Theme.fontLarge
                }
                Text {
                    text: root.controller ? root.controller.minDpi + " – " + root.controller.maxDpi + " DPI, step " + root.controller.step : ""
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                }
                AccentButton {
                    text: "Revert"
                    enabled: root.dirty
                    onClicked: root.revert()
                }
                AccentButton {
                    accent: true
                    text: root.controller && root.controller.saving ? "Saving…" : "Save"
                    enabled: root.dirty && !(root.controller && root.controller.saving)
                    onClicked: root.controller.save(root.draft, root.colorDraft)
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 6

                Item { implicitHeight: 10 }

                Repeater {
                    model: root.stages
                    RowLayout {
                        id: stageRow
                        required property int index
                        required property string name
                        required property bool active
                        required property bool sniper
                        readonly property int draftValue: root.draft[index] !== undefined ? root.draft[index] : 0
                        readonly property string draftColor: root.colorDraft[index] !== undefined ? root.colorDraft[index] : "#000000"
                        Layout.fillWidth: true
                        Layout.leftMargin: 24
                        Layout.rightMargin: 24
                        spacing: 14

                        ColorSwatch {
                            implicitWidth: 22
                            implicitHeight: 22
                            color: stageRow.draftColor
                            selected: stageRow.active
                            onClicked: picker.pick(stageRow.draftColor, c => root.setColor(stageRow.index, c))
                        }
                        Text {
                            Layout.preferredWidth: 90
                            text: stageRow.name
                            color: stageRow.active ? Theme.accent : Theme.text
                            font.pixelSize: Theme.fontNormal
                            font.bold: stageRow.active
                        }
                        DarkSlider {
                            Layout.fillWidth: true
                            from: root.controller ? root.controller.minDpi : 0
                            to: root.controller ? root.controller.maxDpi : 1
                            stepSize: root.controller ? root.controller.step : 1
                            value: stageRow.draftValue
                            onMoved: root.setValue(stageRow.index, Math.round(value))
                        }
                        DarkSpinBox {
                            from: root.controller ? root.controller.minDpi : 0
                            to: root.controller ? root.controller.maxDpi : 1
                            stepSize: root.controller ? root.controller.step : 1
                            value: stageRow.draftValue
                            onValueModified: root.setValue(stageRow.index, value)
                        }
                    }
                }

                Text {
                    Layout.leftMargin: 24
                    Layout.topMargin: 6
                    text: "Click a colour to change it. The DPI LED shows the colour of the active stage."
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
                Item { implicitHeight: 10 }
            }
        }
    }
}
