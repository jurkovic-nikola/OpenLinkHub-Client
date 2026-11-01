import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Equalizer bands, edited as a draft and saved together.
Item {
    id: root
    property var controller
    property var session

    readonly property var bands: controller ? controller.bands : []
    property var draft: []
    readonly property bool dirty: {
        for (let i = 0; i < bands.length; ++i)
            if (draft[i] !== undefined && Math.abs(draft[i] - bands[i].value) > 0.05)
                return true
        return false
    }

    function revert() {
        draft = bands.map(band => band.value)
    }
    function setBand(index, value) {
        const copy = draft.slice()
        copy[index] = Math.round(value * 10) / 10
        draft = copy
    }

    onBandsChanged: revert()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        EditorHeader {
            Layout.fillWidth: true
            title: "EQUALIZER"
            icon: "../icons/equalizer.svg"
            AccentButton {
                text: "Flat"
                onClicked: root.draft = root.bands.map(() => 0)
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
                onClicked: root.controller.save(root.draft)
            }
        }

        GridLayout {
            Layout.margins: 24
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 48
            rowSpacing: 8
            flow: GridLayout.TopToBottom
            rows: Math.ceil(root.bands.length / 2)

            Repeater {
                model: root.bands
                RowLayout {
                    id: band
                    required property var modelData
                    required property int index
                    readonly property real value: root.draft[index] !== undefined ? root.draft[index] : modelData.value
                    spacing: 12
                    Text {
                        Layout.preferredWidth: 70
                        text: band.modelData.name
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkSlider {
                        Layout.preferredWidth: 220
                        from: root.controller ? root.controller.minDb : -12
                        to: root.controller ? root.controller.maxDb : 12
                        stepSize: 0.5
                        value: band.value
                        onMoved: root.setBand(band.index, value)
                    }
                    Text {
                        Layout.preferredWidth: 64
                        text: (band.value > 0 ? "+" : "") + band.value.toFixed(1) + " dB"
                        color: Theme.accent
                        font.pixelSize: Theme.fontNormal
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
