import QtQuick
import QtQuick.Layouts
import "../theme"

// Section header in the style of iCUE: icon tile, upper-case title, optional actions.
Rectangle {
    id: root
    property string title
    property url icon
    property bool highlighted: false
    default property alias actions: actionRow.data

    implicitHeight: Theme.headerHeight
    color: Theme.header

    RowLayout {
        anchors.fill: parent
        anchors.rightMargin: 10
        spacing: 10

        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: height
            color: root.highlighted ? Theme.accent : "#3a3a3a"
            Image {
                anchors.centerIn: parent
                source: root.icon
                sourceSize: Qt.size(18, 18)
                visible: root.icon.toString() !== ""
                opacity: root.highlighted ? 0 : 1
            }
            Text {
                anchors.centerIn: parent
                visible: root.highlighted
                text: root.title.length ? root.title[0] : ""
                color: Theme.accentInk
                font.bold: true
                font.pixelSize: Theme.fontLarge
            }
        }
        Text {
            Layout.fillWidth: true
            text: root.title.toUpperCase()
            color: root.highlighted ? Theme.accent : Theme.text
            font.pixelSize: Theme.fontHeader
            elide: Text.ElideRight
        }
        RowLayout {
            id: actionRow
            spacing: 6
        }
    }
}
