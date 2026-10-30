import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

Panel {
    id: root
    property var session
    title: "Profiles"
    icon: Qt.resolvedUrl("../icons/profile.svg")
    implicitHeight: Theme.headerHeight + 84

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
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: root.session ? root.session.profileName : "—"
                color: Theme.text
                font.pixelSize: Theme.fontLarge
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                visible: root.session !== null
                text: root.session ? root.session.profiles.length + (root.session.profiles.length === 1 ? " profile" : " profiles") + " on this device" : ""
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
            }
        }
    }
}
