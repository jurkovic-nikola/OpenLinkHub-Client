import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Compact stand-in for the artwork stage, for devices without artwork: what the
// device is, its state, and a way out to OpenLinkHub's own page for it.
Rectangle {
    id: root
    property var session

    implicitHeight: 120
    gradient: Gradient {
        GradientStop { position: 0.0; color: Theme.stageTop }
        GradientStop { position: 1.0; color: Theme.stageBottom }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        spacing: 20

        Image {
            Layout.preferredWidth: 72
            Layout.preferredHeight: 72
            source: root.session ? root.session.thumbnail : ""
            sourceSize: Qt.size(144, 144)
            fillMode: Image.PreserveAspectFit
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: root.session ? root.session.product : ""
                color: Theme.text
                font.pixelSize: Theme.fontHeader + 3
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: {
                    if (!root.session)
                        return ""
                    const parts = [root.session.kindTitle]
                    if (root.session.firmware)
                        parts.push("firmware " + root.session.firmware)
                    if (root.session.battery >= 0)
                        parts.push(root.session.connectionMode, "battery " + root.session.battery + "%")
                    if (!root.session.connected)
                        parts.push("offline")
                    return parts.join("  ·  ")
                }
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
                elide: Text.ElideRight
            }
        }

        AccentButton {
            text: "Open in OpenLinkHub"
            enabled: root.session !== null
            onClicked: root.session.openInBrowser()
        }
    }
}
