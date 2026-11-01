import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Simple device settings; each change is sent right away.
Item {
    id: root
    property var controller
    property var session

    function indexIn(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value)
                return i
        return -1
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        EditorHeader {
            Layout.fillWidth: true
            title: "DEVICE SETTINGS"
            icon: "../icons/settings.svg"
            Text {
                text: root.controller && root.controller.busy ? "Applying…" : "Changes apply immediately"
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
            }
        }

        Text {
            Layout.margins: 24
            visible: !root.controller || root.controller.items.length === 0
            text: "This device has no adjustable settings in its current connection mode."
            color: Theme.textDim
            font.pixelSize: Theme.fontNormal
        }

        ColumnLayout {
            Layout.margins: 24
            spacing: 12

            Repeater {
                model: root.controller ? root.controller.items : []
                RowLayout {
                    id: settingRow
                    required property var modelData
                    readonly property bool choice: modelData.kind === "choice" || modelData.kind === "textChoice"
                    spacing: 18
                    opacity: modelData.enabled ? 1 : 0.5
                    Text {
                        Layout.preferredWidth: 240
                        text: settingRow.modelData.title
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkComboBox {
                        visible: settingRow.choice
                        Layout.preferredWidth: 220
                        enabled: !root.controller.busy && settingRow.modelData.enabled
                        model: settingRow.choice ? settingRow.modelData.options : []
                        currentIndex: root.indexIn(model, settingRow.modelData.value)
                        displayText: currentIndex < 0 ? "Not set" : currentText
                        onActivated: index => root.controller.apply(settingRow.modelData.key, model[index].value)
                    }
                    DarkSwitch {
                        visible: settingRow.modelData.kind === "toggle"
                        enabled: !root.controller.busy && settingRow.modelData.enabled
                        checked: settingRow.modelData.value === 1
                        onToggled: root.controller.apply(settingRow.modelData.key, checked ? 1 : 0)
                    }
                    DarkSlider {
                        id: slider
                        visible: settingRow.modelData.kind === "slider"
                        Layout.preferredWidth: 220
                        enabled: !root.controller.busy && settingRow.modelData.enabled
                        from: settingRow.modelData.min
                        to: Math.max(settingRow.modelData.min + 1, settingRow.modelData.max)
                        stepSize: 1
                        value: settingRow.modelData.value
                        // send once the handle is let go, not on every step
                        onPressedChanged: if (!pressed) root.controller.apply(settingRow.modelData.key, Math.round(value))
                    }
                    Text {
                        visible: settingRow.modelData.kind === "slider"
                        text: Math.round(slider.value)
                        color: Theme.accent
                        font.pixelSize: Theme.fontNormal
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
