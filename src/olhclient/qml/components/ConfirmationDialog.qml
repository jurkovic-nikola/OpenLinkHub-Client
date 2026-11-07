import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Dialog {
    id: control
    property string message: ""
    property string confirmText: "Confirm"
    property string cancelText: "Cancel"
    property bool destructive: false

    parent: Overlay.overlay
    width: Math.min(440, parent ? parent.width - 32 : 440)
    padding: 16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    onOpened: {
        x = Math.max(0, (parent.width - width) / 2)
        y = Math.max(0, (parent.height - height) / 2)
        cancelButton.forceActiveFocus()
    }

    background: Rectangle {
        color: Theme.panel
        border.color: Theme.border
        radius: Theme.radius
    }
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.6) }

    header: Rectangle {
        MouseArea {
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point pressPosition
            property point popupPosition
            onPressed: mouse => {
                pressPosition = mapToItem(control.parent, mouse.x, mouse.y)
                popupPosition = Qt.point(control.x, control.y)
            }
            onPositionChanged: mouse => {
                if (!pressed) return
                const position = mapToItem(control.parent, mouse.x, mouse.y)
                control.x = Math.max(0, Math.min(control.parent.width - control.width,
                    popupPosition.x + position.x - pressPosition.x))
                control.y = Math.max(0, Math.min(control.parent.height - control.height,
                    popupPosition.y + position.y - pressPosition.y))
            }
        }
        implicitHeight: Theme.headerHeight
        color: Theme.header
        border.color: Theme.border
        Text {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            verticalAlignment: Text.AlignVCenter
            text: control.title
            color: Theme.accent
            font.pixelSize: Theme.fontHeader
            elide: Text.ElideRight
        }
    }

    contentItem: ColumnLayout {
        spacing: 18
        Text {
            Layout.fillWidth: true
            text: control.message
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: Theme.text
            font.pixelSize: Theme.fontNormal
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            AccentButton {
                id: cancelButton
                text: control.cancelText
                onClicked: control.reject()
            }
            AccentButton {
                text: control.confirmText
                accent: true
                onClicked: control.accept()
            }
        }
    }
    footer: Item {}
}
