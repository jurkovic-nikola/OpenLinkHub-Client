import QtQuick
import "../theme"

// Transient message in the bottom-right corner.
Rectangle {
    id: root
    property bool error: false

    function show(message, isError) {
        label.text = message
        error = isError
        opacity = 1
        hideTimer.restart()
    }

    width: Math.min(label.implicitWidth + 32, 460)
    height: label.implicitHeight + 20
    color: "#202020"
    border.color: error ? Theme.danger : Theme.accent
    border.width: 1
    opacity: 0
    visible: opacity > 0
    Behavior on opacity { NumberAnimation { duration: 180 } }

    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, 428)
        wrapMode: Text.Wrap
        color: root.error ? Theme.danger : Theme.text
        font.pixelSize: Theme.fontNormal
    }
    Timer {
        id: hideTimer
        interval: root.error ? 6000 : 3000
        onTriggered: root.opacity = 0
    }
    MouseArea {
        anchors.fill: parent
        onClicked: root.opacity = 0
    }
}
