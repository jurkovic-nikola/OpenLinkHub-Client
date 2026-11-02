import QtQuick
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root
    property var backend
    property var updater: null
    implicitHeight: 40
    color: Theme.topBar

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 26

        Row {
            spacing: 8
            Image {
                source: "../icons/app.svg"
                sourceSize: Qt.size(22, 22)
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "OpenLinkHub"
                color: Theme.text
                font.pixelSize: Theme.fontLarge
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Text {
            text: "DEVICES"
            color: Theme.accent
            font.pixelSize: Theme.fontNormal
            Rectangle {
                anchors.top: parent.bottom
                anchors.topMargin: 6
                width: parent.width
                height: 2
                color: Theme.accent
            }
        }
        Item { Layout.fillWidth: true }
        Text {
            visible: root.updater !== null && root.updater.updateAvailable
            text: root.updater ? "Update " + root.updater.latestVersion + " available" : ""
            color: Theme.accent
            font.pixelSize: Theme.fontSmall
            font.underline: updateArea.containsMouse
            MouseArea {
                id: updateArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.updater.open()
            }
        }
        Row {
            spacing: 8
            Rectangle {
                width: 8
                height: 8
                radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: root.backend && root.backend.connected ? Theme.success : Theme.danger
            }
            Text {
                text: root.backend ? root.backend.serverUrl : ""
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}
