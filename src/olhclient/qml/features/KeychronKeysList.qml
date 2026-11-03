import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

// Keychron keys: the layer being edited on top, then the key list.
ColumnLayout {
    id: root
    property var controller
    property var session
    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 10
        Layout.rightMargin: 10
        Layout.topMargin: 10
        spacing: 10
        Text {
            text: "Layer"
            color: Theme.text
            font.pixelSize: Theme.fontNormal
        }
        DarkComboBox {
            Layout.fillWidth: true
            model: root.controller ? root.controller.layerNames.map((name, i) => ({ value: i, text: name })) : []
            currentIndex: root.controller ? root.controller.layer : -1
            onActivated: index => root.controller.setLayer(index)
        }
    }

    KeyRemapList {
        Layout.fillWidth: true
        Layout.fillHeight: true
        controller: root.controller
        session: root.session
    }
}
