import QtQuick
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root
    property var backend
    readonly property var session: backend ? backend.session : null
    implicitHeight: 28
    color: Theme.topBar

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 18

        Text {
            Layout.fillWidth: true
            text: root.backend ? root.backend.status : ""
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
            elide: Text.ElideRight
        }
        Text {
            visible: root.backend && root.backend.busy
            text: "Working…"
            color: Theme.accent
            font.pixelSize: Theme.fontSmall
        }
        Text {
            visible: root.session !== null
            text: root.session ? root.session.product + "  ·  " + root.session.connectionMode : ""
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
        }
        Row {
            visible: root.session !== null && root.session.battery >= 0
            spacing: 4
            Image {
                source: "../icons/battery.svg"
                sourceSize: Qt.size(16, 16)
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: root.session ? root.session.battery + "%" : ""
                color: root.session && root.session.battery <= 15 ? Theme.danger : Theme.text
                font.pixelSize: Theme.fontSmall
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}
