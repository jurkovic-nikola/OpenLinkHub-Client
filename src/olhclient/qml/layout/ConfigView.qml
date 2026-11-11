import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// The CONFIG tab: every setting of config.toml, from the file or its default (core/config_editor.py).
Panel {
    id: root
    required property var config
    title: "Configuration"
    highlighted: true

    readonly property var groups: [
        { id: "openlinkhub", title: "OPENLINKHUB CONNECTION" },
        { id: "client", title: "CLIENT" }
    ]

    ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.bottomMargin: footer.height
        contentWidth: availableWidth
        ScrollBar.vertical.policy: scroll.contentHeight > scroll.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff

        ColumnLayout {
            width: scroll.availableWidth
            spacing: 0

            ColumnLayout {
                Layout.margins: 16
                Layout.maximumWidth: 720
                spacing: 6

                Text {
                    Layout.fillWidth: true
                    text: "Settings file"
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                }
                TextEdit {
                    objectName: "configPath"
                    Layout.fillWidth: true
                    text: root.config.path
                    readOnly: true
                    selectByMouse: true
                    color: Theme.text
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.accentInk
                    font.pixelSize: Theme.fontNormal
                    wrapMode: TextEdit.WrapAnywhere
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.config.loadError !== ""
                    text: root.config.loadError
                    color: Theme.danger
                    font.pixelSize: Theme.fontNormal
                    wrapMode: Text.Wrap
                }

                Repeater {
                    model: root.groups.filter(g => root.config.fields.some(f => f.group === g.id))
                    ColumnLayout {
                        id: group
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.topMargin: 14
                        spacing: 0

                        Text {
                            text: group.modelData.title
                            color: Theme.accent
                            font.pixelSize: Theme.fontSmall
                            font.bold: true
                            Layout.bottomMargin: 4
                        }
                        Repeater {
                            model: root.config.fields.filter(f => f.group === group.modelData.id)
                            ConfigRow {
                                required property var modelData
                                Layout.fillWidth: true
                                config: root.config
                                field: modelData
                            }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 54
        color: Theme.panelAlt

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 10

            Text {
                Layout.fillWidth: true
                text: root.config.restartNeeded ? "Restart the client to apply the connection settings."
                    : root.config.dirty ? "Unsaved changes." : ""
                color: root.config.restartNeeded ? Theme.accent : Theme.textDim
                font.pixelSize: Theme.fontNormal
                elide: Text.ElideRight
            }
            AccentButton {
                visible: root.config.restartNeeded && root.config.canRestart
                text: "Restart now"
                onClicked: root.config.restart()
            }
            AccentButton {
                objectName: "configRevert"
                text: "Revert"
                enabled: root.config.dirty
                onClicked: root.config.revert()
            }
            AccentButton {
                objectName: "configSave"
                accent: true
                text: "Save"
                enabled: root.config.dirty && Object.keys(root.config.errors).length === 0
                onClicked: root.config.save()
            }
        }
    }

    component ConfigRow: Item {
        id: row
        property var config
        property var field
        readonly property var value: config.values[field.key]
        readonly property bool explicit: config.explicit[field.key] === true
        readonly property string error: config.errors[field.key] || ""
        implicitHeight: rowLayout.implicitHeight + 16

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.border
        }

        RowLayout {
            id: rowLayout
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            ColumnLayout {
                Layout.preferredWidth: 220
                Layout.minimumWidth: 220
                Layout.maximumWidth: 220
                Layout.alignment: Qt.AlignTop
                spacing: 2
                Text {
                    text: row.field.label
                    color: Theme.text
                    font.pixelSize: Theme.fontNormal
                }
                Text {
                    Layout.fillWidth: true
                    text: row.field.key + (row.field.restart ? " · needs a restart" : "")
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1  // share the row by fillWidth, not by the help text's length
                spacing: 4

                DarkTextField {
                    objectName: "config_" + row.field.key
                    visible: row.field.kind !== "bool"
                    Layout.fillWidth: true
                    text: row.field.kind !== "bool" ? row.value : ""
                    placeholderText: row.field.placeholder
                    onTextEdited: row.config.setValue(row.field.key, text)
                }
                DarkSwitch {
                    objectName: "config_" + row.field.key
                    visible: row.field.kind === "bool"
                    checked: row.field.kind === "bool" && row.value === true
                    text: checked ? "On" : "Off"
                    onToggled: row.config.setValue(row.field.key, checked)
                }
                Text {
                    Layout.fillWidth: true
                    text: row.error || row.field.help
                    color: row.error ? Theme.danger : Theme.textDim
                    font.pixelSize: Theme.fontSmall
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    visible: row.field.override !== ""
                    text: "Overridden by " + row.field.override + " on the command line for this run."
                    color: Theme.accent
                    font.pixelSize: Theme.fontSmall
                    wrapMode: Text.Wrap
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 90
                Layout.minimumWidth: 90
                Layout.alignment: Qt.AlignTop
                spacing: 2
                Text {
                    text: row.explicit ? "config file" : "default"
                    color: row.explicit ? Theme.accent : Theme.textMuted
                    font.pixelSize: Theme.fontSmall
                }
                Text {
                    objectName: "configDefault_" + row.field.key
                    visible: row.explicit
                    text: "Use default"
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                    font.underline: resetArea.containsMouse
                    MouseArea {
                        id: resetArea
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: row.config.useDefault(row.field.key)
                    }
                }
            }
        }
    }
}
