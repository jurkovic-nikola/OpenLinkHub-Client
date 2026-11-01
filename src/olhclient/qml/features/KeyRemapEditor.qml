import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Editor for the selected button. Edits a local draft; Save sends it to OpenLinkHub.
Item {
    id: root
    property var controller
    property var session

    readonly property var key: controller ? controller.selected : null

    property bool draftDefault: true
    property int draftType: 0
    property int draftValue: 0
    property bool draftHold: false
    property bool draftRelease: false
    property int draftModifier: 0
    // keyboards: a modifier key can be combined with the action
    readonly property var modifierOptions: controller ? controller.modifierOptions : []
    property var valueOptions: []
    // set when the user picks another action type: select the first value once options arrive
    property bool pickFirstValue: false

    readonly property bool dirty: key !== null && (draftDefault !== key.useDefault || draftType !== key.actionType
        || draftValue !== key.actionValue || draftHold !== key.pressAndHold || draftRelease !== key.onRelease
        || draftModifier !== key.modifier)
    readonly property string problem: controller ? controller.validate(draftType, draftHold, draftRelease) : ""

    function indexIn(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value)
                return i
        return -1
    }

    function revert() {
        if (!key)
            return
        draftDefault = key.useDefault
        draftType = key.actionType
        draftValue = key.actionValue
        draftHold = key.pressAndHold
        draftRelease = key.onRelease
        draftModifier = key.modifier
        pickFirstValue = false
        loadOptions()
    }

    function loadOptions() {
        const options = controller ? controller.valueOptions(draftType) : []
        valueOptions = options
        if (pickFirstValue && options.length) {
            pickFirstValue = false
            if (indexIn(options, draftValue) < 0)
                draftValue = options[0].value
        }
    }

    onKeyChanged: revert()
    onControllerChanged: revert()

    Connections {
        target: root.controller
        ignoreUnknownSignals: true
        function onOptionsLoaded(actionType) {
            if (actionType === root.draftType)
                root.loadOptions()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // header bar: what is being edited + revert
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 42
            color: Theme.panel
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 10
                Rectangle {
                    implicitWidth: 34
                    implicitHeight: 24
                    color: "#1a1a1a"
                    border.color: Theme.borderStrong
                    Text {
                        anchors.centerIn: parent
                        text: "A▸B"
                        color: Theme.text
                        font.pixelSize: Theme.fontSmall
                        font.bold: true
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: !root.key ? "SELECT A BUTTON"
                        : root.key.label === root.key.name ? "REMAP " + root.key.name.toUpperCase()
                        : "REMAP " + root.key.label.toUpperCase() + "   ·   " + root.key.name
                    color: Theme.accent
                    font.pixelSize: Theme.fontLarge
                    elide: Text.ElideRight
                }
                AccentButton {
                    text: "Revert"
                    enabled: root.dirty
                    onClicked: root.revert()
                }
                AccentButton {
                    accent: true
                    text: root.controller && root.controller.saving ? "Saving…" : "Save"
                    enabled: root.key !== null && !root.key.locked && root.dirty && root.problem === ""
                             && !(root.controller && root.controller.saving)
                    onClicked: root.controller.save(root.key.keyIndex, root.draftDefault, root.draftType,
                                                    root.draftValue, root.draftHold, root.draftRelease,
                                                    root.draftModifier)
                }
            }
        }

        // tab strip (single tab for now, keeps the iCUE look)
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 30
            color: Theme.panelAlt
            Rectangle {
                width: 110
                height: parent.height
                color: Theme.accent
                Text {
                    anchors.centerIn: parent
                    text: "SETTINGS"
                    color: Theme.accentInk
                    font.pixelSize: Theme.fontNormal
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.accent
            }
        }

        Text {
            Layout.margins: 24
            visible: root.key !== null && root.key.locked
            text: "This key is fixed and cannot be remapped on this device."
            color: Theme.textDim
            font.pixelSize: Theme.fontNormal
        }

        GridLayout {
            Layout.margins: 24
            Layout.fillWidth: true
            visible: root.key !== null && !root.key.locked
            columns: 2
            columnSpacing: 18
            rowSpacing: 12

            Text { text: "Use default action"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkSwitch {
                checked: root.draftDefault
                onToggled: root.draftDefault = checked
            }

            Text { text: "Action type"; color: Theme.text; font.pixelSize: Theme.fontNormal; opacity: root.draftDefault ? 0.5 : 1 }
            DarkComboBox {
                Layout.preferredWidth: 300
                enabled: !root.draftDefault
                model: root.controller ? root.controller.typeOptions : []
                currentIndex: root.indexIn(model, root.draftType)
                onActivated: index => {
                    root.draftType = model[index].value
                    root.draftValue = 0
                    root.pickFirstValue = true
                    root.loadOptions()
                }
            }

            Text { text: "Action"; color: Theme.text; font.pixelSize: Theme.fontNormal; opacity: root.draftDefault ? 0.5 : 1 }
            DarkComboBox {
                Layout.preferredWidth: 300
                enabled: !root.draftDefault && root.valueOptions.length > 1
                model: root.valueOptions
                currentIndex: root.indexIn(root.valueOptions, root.draftValue)
                displayText: !root.valueOptions.length ? "Loading…"
                           : currentIndex < 0 ? "Unknown (" + root.draftValue + ")" : currentText
                onActivated: index => root.draftValue = root.valueOptions[index].value
            }

            Text {
                visible: root.modifierOptions.length > 0
                text: "Modifier"; color: Theme.text; font.pixelSize: Theme.fontNormal; opacity: root.draftDefault ? 0.5 : 1
            }
            DarkComboBox {
                visible: root.modifierOptions.length > 0
                Layout.preferredWidth: 300
                enabled: !root.draftDefault
                model: root.modifierOptions
                currentIndex: root.indexIn(model, root.draftModifier)
                displayText: currentIndex < 0 ? "None" : currentText
                onActivated: index => root.draftModifier = model[index].value
            }

            Text { text: "Press and hold"; color: Theme.text; font.pixelSize: Theme.fontNormal; opacity: root.draftDefault ? 0.5 : 1 }
            DarkSwitch {
                enabled: !root.draftDefault
                checked: root.draftHold
                onToggled: root.draftHold = checked
            }

            Text { text: "Trigger on release"; color: Theme.text; font.pixelSize: Theme.fontNormal; opacity: root.draftDefault ? 0.5 : 1 }
            DarkSwitch {
                enabled: !root.draftDefault
                checked: root.draftRelease
                onToggled: root.draftRelease = checked
            }

            Item { implicitHeight: 1 }
            Text {
                visible: root.problem !== ""
                text: root.problem
                color: Theme.danger
                font.pixelSize: Theme.fontNormal
            }

        }

        Item { Layout.fillHeight: true }
    }
}
