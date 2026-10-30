import QtQuick
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root
    property alias title: header.title
    property alias icon: header.icon
    property alias highlighted: header.highlighted
    default property alias content: body.data

    color: Theme.panel

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        PanelHeader {
            id: header
            Layout.fillWidth: true
        }
        Item {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
        }
    }
}
