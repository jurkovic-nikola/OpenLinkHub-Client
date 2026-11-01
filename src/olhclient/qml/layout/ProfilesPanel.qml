import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Active user profile: switch, create (from the current settings) and delete.
Panel {
    id: root
    property var session
    readonly property var names: session ? session.profiles : []
    readonly property var deletable: {
        const result = []
        if (session)
            for (const name of names)
                if (session.canDeleteProfile(name))
                    result.push(name)
        return result
    }

    title: "Profiles"
    icon: Qt.resolvedUrl("../icons/profile.svg")
    implicitHeight: Theme.headerHeight + 92

    RowLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 14

        Rectangle {
            Layout.preferredWidth: 58
            Layout.preferredHeight: 58
            color: Theme.panelAlt
            border.color: Theme.border
            Image {
                anchors.centerIn: parent
                source: "../icons/app.svg"
                sourceSize: Qt.size(40, 40)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            DarkComboBox {
                id: profileBox
                Layout.fillWidth: true
                enabled: root.session !== null && !root.session.profileBusy
                model: root.names.map(name => ({ value: name, text: name }))
                currentIndex: root.names.indexOf(root.session ? root.session.profileName : "")
                displayText: root.session ? root.session.profileName : "—"
                onActivated: index => {
                    root.session.switchProfile(root.names[index])
                    // show the active profile until the switch is confirmed by a reload
                    currentIndex = Qt.binding(() => root.names.indexOf(root.session.profileName))
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    Layout.fillWidth: true
                    text: root.names.length + (root.names.length === 1 ? " profile" : " profiles")
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                }
                AccentButton {
                    implicitHeight: 22
                    leftPadding: 10
                    rightPadding: 10
                    font.pixelSize: Theme.fontSmall
                    text: "New"
                    enabled: root.session !== null && !root.session.profileBusy
                    onClicked: newPopup.open()
                }
                AccentButton {
                    implicitHeight: 22
                    leftPadding: 10
                    rightPadding: 10
                    font.pixelSize: Theme.fontSmall
                    text: "Delete…"
                    enabled: root.deletable.length > 0 && !root.session.profileBusy
                    onClicked: deletePopup.open()
                }
            }
        }
    }

    Popup {
        id: newPopup
        y: root.height
        width: root.width
        padding: 14
        modal: true
        focus: true
        onOpened: { nameField.text = ""; nameField.forceActiveFocus() }
        background: Rectangle { color: Theme.panel; border.color: Theme.accent }

        readonly property string problem: root.session && nameField.text ? root.session.profileNameProblem(nameField.text) : ""

        function create() {
            if (!nameField.text || problem)
                return
            root.session.createProfile(nameField.text)
            close()
        }

        contentItem: ColumnLayout {
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "New profile from the current settings"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
                wrapMode: Text.Wrap
            }
            DarkTextField {
                id: nameField
                Layout.fillWidth: true
                placeholderText: "Name (letters and numbers)"
                onAccepted: newPopup.create()
            }
            Text {
                Layout.fillWidth: true
                visible: newPopup.problem !== ""
                text: newPopup.problem
                color: Theme.danger
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AccentButton { text: "Cancel"; onClicked: newPopup.close() }
                AccentButton {
                    accent: true
                    text: "Create"
                    enabled: nameField.text !== "" && newPopup.problem === ""
                    onClicked: newPopup.create()
                }
            }
        }
    }

    Popup {
        id: deletePopup
        property string confirming: ""
        y: root.height
        width: root.width
        padding: 14
        modal: true
        onOpened: confirming = ""
        background: Rectangle { color: Theme.panel; border.color: Theme.danger }

        contentItem: ColumnLayout {
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "Delete a profile. The active and the default profile cannot be deleted."
                color: Theme.text
                font.pixelSize: Theme.fontNormal
                wrapMode: Text.Wrap
            }
            Repeater {
                model: root.deletable
                RowLayout {
                    id: deleteRow
                    required property string modelData
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: deleteRow.modelData
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                        elide: Text.ElideRight
                    }
                    AccentButton {
                        implicitHeight: 24
                        font.pixelSize: Theme.fontSmall
                        text: deletePopup.confirming === deleteRow.modelData ? "Confirm delete" : "Delete"
                        onClicked: {
                            if (deletePopup.confirming !== deleteRow.modelData) {
                                deletePopup.confirming = deleteRow.modelData
                                return
                            }
                            root.session.deleteProfile(deleteRow.modelData)
                            deletePopup.close()
                        }
                    }
                }
            }
            AccentButton {
                Layout.alignment: Qt.AlignRight
                text: "Close"
                onClicked: deletePopup.close()
            }
        }
    }
}
