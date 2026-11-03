import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Editor for the selected key of a Keychron keyboard, on the layer chosen in the list.
// Edits a local draft; Save writes the keycode to the keyboard.
Item {
    id: root
    property var controller
    property var session

    readonly property var key: controller ? controller.selected : null
    readonly property var layerNames: controller ? controller.layerNames : []
    readonly property int layerIndex: controller ? controller.layer : 0

    property string draftCategory: ""
    property int draftBase: 0
    property int draftMods: 0
    property var keyOptions: []
    readonly property bool hasMods: draftCategory === "Basic"
    readonly property int draftCode: controller && hasMods ? controller.withMods(draftBase, draftMods) : draftBase
    readonly property bool dirty: key !== null && draftCode !== key.keycode
    // modifier bits of a QMK keycode
    readonly property var modifiers: [{ bit: 1, text: "Ctrl" }, { bit: 2, text: "Shift" }, { bit: 4, text: "Alt" },
                                      { bit: 8, text: "Win/Cmd" }]

    function indexIn(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value)
                return i
        return -1
    }

    function revert() {
        if (!key || !controller)
            return
        draftCategory = key.category
        draftMods = key.mods
        draftBase = key.mods ? key.keycode & 0xff : key.keycode
        keyOptions = draftCategory ? controller.keyOptions(draftCategory) : []
    }

    function pickCategory(category) {
        draftCategory = category
        draftMods = 0
        keyOptions = controller.keyOptions(category)
        if (keyOptions.length)
            draftBase = keyOptions[0].value
    }

    function setMod(bit, on) {
        draftMods = on ? draftMods | bit : draftMods & ~bit
        if ((draftMods & 0x0f) === 0)
            draftMods = 0  // "right-hand" alone means nothing
    }

    onKeyChanged: revert()
    onControllerChanged: revert()
    onLayerIndexChanged: revert()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        EditorHeader {
            Layout.fillWidth: true
            title: !root.key ? "SELECT A KEY"
                : "REMAP " + root.key.name.toUpperCase() + "   ·   " + (root.layerNames[root.layerIndex] || "")
            icon: "../icons/keyboard_keys.svg"
            AccentButton {
                text: "Revert"
                enabled: root.dirty
                onClicked: root.revert()
            }
            AccentButton {
                accent: true
                text: root.controller && root.controller.saving ? "Saving…" : "Save"
                enabled: root.dirty && !(root.controller && root.controller.saving)
                onClicked: root.controller.save(root.key.keyIndex, root.draftCode)
            }
        }

        GridLayout {
            Layout.margins: 24
            Layout.fillWidth: true
            visible: root.key !== null
            columns: 2
            columnSpacing: 18
            rowSpacing: 12

            Text { text: "Now"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            Text {
                text: root.key ? root.key.action : ""
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
            }

            Text { text: "Category"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkComboBox {
                Layout.preferredWidth: 300
                model: root.controller ? root.controller.categories : []
                currentIndex: root.indexIn(model, root.draftCategory)
                displayText: currentIndex < 0 ? "Other" : currentText
                onActivated: index => root.pickCategory(model[index].value)
            }

            Text { text: "Key"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            DarkComboBox {
                Layout.preferredWidth: 300
                model: root.keyOptions
                currentIndex: root.indexIn(root.keyOptions, root.draftBase)
                displayText: currentIndex >= 0 ? currentText
                           : root.controller ? root.controller.describe(root.draftBase) : ""
                onActivated: index => root.draftBase = root.keyOptions[index].value
            }

            Text {
                visible: root.hasMods
                text: "With"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            Flow {
                visible: root.hasMods
                Layout.preferredWidth: 420
                spacing: 14
                Repeater {
                    model: root.modifiers
                    Row {
                        id: modRow
                        required property var modelData
                        spacing: 6
                        DarkSwitch {
                            checked: (root.draftMods & modRow.modelData.bit) !== 0
                            onToggled: root.setMod(modRow.modelData.bit, checked)
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modRow.modelData.text
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                    }
                }
                Row {
                    spacing: 6
                    DarkSwitch {
                        enabled: (root.draftMods & 0x0f) !== 0
                        checked: (root.draftMods & 0x10) !== 0
                        onToggled: root.setMod(0x10, checked)
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Right-hand"
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                    }
                }
            }

            Text { text: "Becomes"; color: Theme.text; font.pixelSize: Theme.fontNormal }
            Text {
                text: root.controller ? root.controller.describe(root.draftCode) : ""
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }

            Item { implicitHeight: 1 }
            Text {
                Layout.maximumWidth: 420
                text: "Changes apply at once and are stored on the keyboard. “Transparent” keys use the key of the layer below."
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: Theme.fontSmall
            }
        }

        Item { Layout.fillHeight: true }
    }
}
