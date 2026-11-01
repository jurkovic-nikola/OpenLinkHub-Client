import QtQuick
import QtQuick.Layouts
import "../theme"

// Overview of the current device settings.
ListView {
    id: root
    property var controller
    property var session

    function valueText(item) {
        if (item.kind === "toggle")
            return item.value ? "On" : "Off"
        for (const option of item.options)
            if (option.value === item.value)
                return option.text
        return "Not set"
    }

    topMargin: 10
    clip: true
    model: controller ? controller.items : []

    delegate: Item {
        id: row
        required property var modelData
        width: ListView.view.width
        height: 30

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: row.modelData.title
                color: Theme.text
                font.pixelSize: Theme.fontNormal
                elide: Text.ElideRight
            }
            Text {
                text: root.valueText(row.modelData)
                color: Theme.accent
                font.pixelSize: Theme.fontNormal
            }
        }
    }
}
