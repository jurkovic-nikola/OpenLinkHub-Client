import QtQuick
import QtQuick.Layouts
import "../theme"

// Header bar of an editor panel: icon, title, then any buttons given as children.
Rectangle {
    id: root
    property alias title: label.text
    property alias icon: image.source
    default property alias actions: actionRow.data

    implicitHeight: 42
    color: Theme.panel

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 10
        Image {
            id: image
            sourceSize: Qt.size(20, 20)
        }
        Text {
            id: label
            Layout.fillWidth: true
            color: Theme.accent
            font.pixelSize: Theme.fontLarge
            elide: Text.ElideRight
        }
        RowLayout {
            id: actionRow
            spacing: 10
        }
    }
}
