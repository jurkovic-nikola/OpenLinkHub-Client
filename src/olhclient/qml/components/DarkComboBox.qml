import QtQuick
import QtQuick.Controls
import "../theme"

// Combo box over an array of {value, text} objects.
ComboBox {
    id: control
    textRole: "text"
    valueRole: "value"
    implicitHeight: 30
    font.pixelSize: Theme.fontNormal

    delegate: ItemDelegate {
        id: item
        required property var modelData
        required property int index
        width: ListView.view ? ListView.view.width : control.width
        height: 28
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: item.modelData.text
            color: item.highlighted ? Theme.accentInk : Theme.text
            font: control.font
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { color: item.highlighted ? Theme.accent : "transparent" }
    }

    indicator: Text {
        x: control.width - width - 10
        y: (control.height - height) / 2
        text: "▾"
        color: control.enabled ? Theme.text : Theme.textMuted
        font.pixelSize: 14
    }

    contentItem: Text {
        leftPadding: 10
        rightPadding: 28
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.accent : Theme.textMuted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        color: Theme.field
        border.color: control.activeFocus || control.popup.visible ? Theme.accent : Theme.borderStrong
        radius: Theme.radius
    }

    popup: Popup {
        y: control.height
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 2, 340)
        padding: 1
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
        background: Rectangle {
            color: "#202020"
            border.color: Theme.borderStrong
        }
    }
}
