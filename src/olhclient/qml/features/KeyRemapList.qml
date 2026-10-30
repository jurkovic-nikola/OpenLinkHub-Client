import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// iCUE-style list of remappable buttons with their current action.
Item {
    id: root
    property var controller
    property var session

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 10
        spacing: 8

        DarkTextField {
            id: filter
            Layout.fillWidth: true
            Layout.leftMargin: 10
            Layout.rightMargin: 10
            placeholderText: "Filter name or action"
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.controller ? root.controller.keys : null
            boundsBehavior: Flickable.StopAtBounds

            delegate: Rectangle {
                id: row
                required property string name
                required property string label
                required property string action
                required property bool locked
                readonly property bool current: root.session && root.session.selectedButton === name
                readonly property bool matches: {
                    const f = filter.text.trim().toLowerCase()
                    return !f || name.toLowerCase().includes(f) || label.toLowerCase().includes(f) || action.toLowerCase().includes(f)
                }
                width: ListView.view.width
                height: matches ? 28 : 0
                visible: matches
                color: current ? Theme.accent : rowMouse.containsMouse && !locked ? Theme.hover : "transparent"
                opacity: locked ? 0.45 : 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8
                    Text {
                        text: "A▸B"
                        font.pixelSize: Theme.fontSmall
                        font.bold: true
                        color: row.current ? Theme.accentInk : Theme.text
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.locked ? row.label + " (fixed)" : row.action === "Default" ? row.label : row.action
                        color: row.current ? Theme.accentInk : Theme.text
                        font.pixelSize: Theme.fontNormal
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        Layout.preferredWidth: Math.max(36, badgeText.implicitWidth + 12)
                        Layout.preferredHeight: 20
                        color: row.current ? "#1e1e1e" : "#1a1a1a"
                        border.color: row.current ? "#1e1e1e" : Theme.borderStrong
                        Text {
                            id: badgeText
                            anchors.centerIn: parent
                            text: row.label.length <= 4 ? row.label : row.label.split(" ")[0]
                            color: Theme.text
                            font.pixelSize: Theme.fontSmall
                            font.bold: true
                        }
                    }
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: row.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
                    onClicked: if (!row.locked) root.session.selectedButton = row.name
                }
            }
        }
    }
}
