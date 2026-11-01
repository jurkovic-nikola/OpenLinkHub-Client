import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Keyboard keys: the keyboard profile (per-key layout) on top, then the key list.
ColumnLayout {
    id: root
    property var controller
    property var session
    spacing: 0

    readonly property var names: controller ? controller.keyboardProfiles : []
    readonly property string problem: controller && nameField.text ? controller.keyboardProfileProblem(nameField.text) : ""

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 10
        visible: root.names.length > 0
        spacing: 6
        DarkComboBox {
            Layout.fillWidth: true
            model: root.names.map(name => ({ value: name, text: name }))
            currentIndex: root.names.indexOf(root.controller ? root.controller.keyboardProfile : "")
            displayText: root.controller ? root.controller.keyboardProfile : ""
            onActivated: index => root.controller.switchKeyboardProfile(root.names[index])
        }
        AccentButton {
            text: "Delete"
            enabled: root.controller !== null && root.controller.keyboardProfile !== "default"
            onClicked: root.controller.deleteKeyboardProfile(root.controller.keyboardProfile)
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 6
        visible: root.names.length > 0
        spacing: 6
        DarkTextField {
            id: nameField
            Layout.fillWidth: true
            placeholderText: "New keyboard profile"
        }
        AccentButton {
            text: "Create"
            enabled: nameField.text !== "" && root.problem === ""
            onClicked: {
                root.controller.newKeyboardProfile(nameField.text)
                nameField.text = ""
            }
        }
    }
    Text {
        Layout.leftMargin: 10
        visible: root.problem !== ""
        text: root.problem
        color: Theme.danger
        font.pixelSize: Theme.fontSmall
    }

    KeyRemapList {
        Layout.fillWidth: true
        Layout.fillHeight: true
        controller: root.controller
        session: root.session
    }
}
