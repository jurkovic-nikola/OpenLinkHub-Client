import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Shown when OpenLinkHub has dashboard authentication enabled.
Rectangle {
    id: root
    property alias username: userField.text
    signal login(string username, string password)

    width: 360
    height: content.implicitHeight + 40
    color: Theme.panel
    border.color: Theme.accent

    function submit() {
        if (userField.text && passwordField.text)
            root.login(userField.text, passwordField.text)
        passwordField.text = ""
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Text {
            text: "LOGIN REQUIRED"
            color: Theme.accent
            font.pixelSize: Theme.fontHeader
        }
        Text {
            Layout.fillWidth: true
            text: "OpenLinkHub has dashboard authentication enabled."
            color: Theme.textDim
            wrapMode: Text.Wrap
            font.pixelSize: Theme.fontNormal
        }
        DarkTextField {
            id: userField
            Layout.fillWidth: true
            placeholderText: "Username"
        }
        DarkTextField {
            id: passwordField
            Layout.fillWidth: true
            placeholderText: "Password"
            echoMode: TextInput.Password
            onAccepted: root.submit()
        }
        AccentButton {
            Layout.alignment: Qt.AlignRight
            accent: true
            text: "Log in"
            onClicked: root.submit()
        }
    }
}
