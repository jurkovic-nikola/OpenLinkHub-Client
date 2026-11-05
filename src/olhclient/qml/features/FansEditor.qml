import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// The selected channel of a hub or AIO: speed profile, lighting effect and label.
// Speed profiles themselves are edited in OpenLinkHub.
Item {
    id: root
    property var controller
    property var session

    readonly property var channel: controller ? controller.selected : null

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
            title: root.channel ? "FANS & PUMPS   ·   " + root.channel.title.toUpperCase() : "FANS & PUMPS"
            icon: "../icons/fans.svg"
            Text {
                text: root.channel ? [root.channel.rpm >= 0 ? root.channel.rpm + " RPM" : "",
                                      root.channel.temperature].filter(t => t).join("  ·  ") : ""
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
            }
        }

        // the effect settings can be long (gradients); scroll when the window is low
        ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            // the Basic style hides an idle scroll bar; keep it visible when there is more to see
            ScrollBar.vertical.policy: scroll.contentHeight > scroll.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff

            ColumnLayout {
                width: parent.width
                spacing: 0

                Text {
                    Layout.margins: 24
                    visible: root.channel === null
                    text: "Select a channel."
                    color: Theme.textDim
                    font.pixelSize: Theme.fontNormal
                }

                GridLayout {
                    Layout.margins: 24
                    visible: root.channel !== null
                    columns: 3
                    columnSpacing: 18
                    rowSpacing: 12

                    Text {
                        visible: speedBox.visible
                        text: "Speed profile"; color: Theme.text; font.pixelSize: Theme.fontNormal
                    }
                    DarkComboBox {
                        id: speedBox
                        visible: root.channel !== null && root.channel.hasSpeed
                        Layout.preferredWidth: 220
                        model: root.controller ? root.controller.speedProfiles : []
                        currentIndex: root.channel ? root.indexIn(model, root.channel.speedProfile) : -1
                        displayText: !model.length ? "Loading…" : currentIndex < 0 ? root.channel.speedProfile || "Not set" : currentText
                        onActivated: index => root.controller.setSpeedProfile(root.channel.channelId, model[index].value)
                    }
                    AccentButton {
                        visible: speedBox.visible
                        text: "Apply to all"
                        enabled: speedBox.currentIndex >= 0
                        onClicked: root.controller.setSpeedProfile(-1, speedBox.model[speedBox.currentIndex].value)
                    }

                    Text {
                        visible: effectBox.visible
                        text: "Lighting effect"; color: Theme.text; font.pixelSize: Theme.fontNormal
                    }
                    DarkComboBox {
                        id: effectBox
                        visible: root.channel !== null && root.channel.hasRgb
                        Layout.preferredWidth: 220
                        model: root.controller ? root.controller.effects : []
                        currentIndex: root.channel ? root.indexIn(model, root.channel.rgbProfile) : -1
                        displayText: currentIndex < 0 ? "Not set" : currentText
                        onActivated: index => root.controller.setRgbProfile(root.channel.channelId, model[index].value)
                    }
                    AccentButton {
                        visible: effectBox.visible
                        text: "Apply to all"
                        enabled: effectBox.currentIndex >= 0
                        onClicked: root.controller.setRgbProfile(-1, effectBox.model[effectBox.currentIndex].value)
                    }

                    Text { text: "Label"; color: Theme.text; font.pixelSize: Theme.fontNormal }
                    DarkTextField {
                        id: labelField
                        Layout.preferredWidth: 220
                        text: root.channel ? root.channel.label : ""
                        placeholderText: root.channel ? root.channel.title : ""
                    }
                    AccentButton {
                        text: "Rename"
                        enabled: root.channel !== null && labelField.text.trim() !== "" && labelField.text !== root.channel.label
                        onClicked: root.controller.setLabel(root.channel.channelId, root.channel.rgbDevice, labelField.text)
                    }
                }

                EffectProfileEditor {
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.bottomMargin: 24
                    profile: root.controller ? root.controller.effectProfile : null
                    note: "These settings apply to every channel with this effect."
                }

                Text {
                    Layout.leftMargin: 24
                    Layout.rightMargin: 24
                    Layout.fillWidth: true
                    visible: root.channel !== null && root.channel.hasSpeed
                    Layout.bottomMargin: 24
                    text: "Speed profiles are created and edited in OpenLinkHub."
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
