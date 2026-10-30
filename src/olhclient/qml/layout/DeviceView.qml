import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import "../theme"
import "../components"

// The device "stage": artwork with clickable hotspots, a button list callout on
// the left, a keypad grid callout on the right and carousel dots for the views.
Rectangle {
    id: root
    property var session
    property int viewIndex: 0
    signal buttonActivated(string button)

    readonly property var views: session ? session.views : []
    readonly property var view: views.length ? views[Math.min(viewIndex, views.length - 1)] : null
    readonly property string selected: session ? session.selectedButton : ""

    gradient: Gradient {
        GradientStop { position: 0.0; color: Theme.stageTop }
        GradientStop { position: 1.0; color: Theme.stageBottom }
    }
    clip: true

    function activate(button) {
        if (!session || session.isLocked(button))
            return
        session.selectedButton = button
        buttonActivated(button)
    }

    function hotspotIn(v, button) {
        if (!v)
            return null
        for (let i = 0; i < v.hotspots.length; ++i)
            if (v.hotspots[i].button === button)
                return v.hotspots[i]
        return null
    }

    // Bring the view that shows the selected button to the front.
    onSelectedChanged: {
        if (hotspotIn(view, selected))
            return
        for (let i = 0; i < views.length; ++i) {
            if (hotspotIn(views[i], selected)) {
                viewIndex = i
                return
            }
        }
    }
    onSessionChanged: viewIndex = 0

    // subtle diagonal sheen
    Rectangle {
        anchors.fill: parent
        opacity: 0.08
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: "#ffffff" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // -- left callout: buttons outside the keypad ---------------------------
    Column {
        id: buttonCallout
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        width: 170
        spacing: 1
        visible: root.session !== null

        Repeater {
            model: root.session ? root.session.buttonList : []
            Rectangle {
                id: entry
                required property var modelData
                required property int index
                readonly property bool current: modelData.button === root.selected
                width: buttonCallout.width
                height: 29
                color: current ? "#2a2610" : entryMouse.containsMouse && !modelData.locked ? Theme.hover : "#1c1c1c"
                border.color: current ? Theme.accent : "#2e2e2e"
                opacity: modelData.locked ? 0.45 : 1

                Rectangle {
                    x: 5
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20
                    height: 20
                    color: "transparent"
                    border.color: Theme.borderStrong
                    Text {
                        anchors.centerIn: parent
                        text: entry.index + 1
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                }
                Text {
                    x: 34
                    width: parent.width - 40
                    anchors.verticalCenter: parent.verticalCenter
                    text: entry.modelData.label
                    color: Theme.accent
                    opacity: entry.current ? 1 : 0.85
                    font.pixelSize: Theme.fontNormal
                    elide: Text.ElideRight
                }
                MouseArea {
                    id: entryMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: entry.modelData.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
                    onClicked: root.activate(entry.modelData.button)
                }
            }
        }
    }

    // -- right callout: keypad grid -----------------------------------------
    Rectangle {
        id: keypadCallout
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        visible: root.session !== null && root.session.keypad.length > 0
        width: keypadGrid.implicitWidth + 16
        height: keypadGrid.implicitHeight + 16
        color: "#1c1c1c"
        border.color: "#2e2e2e"

        Rectangle {
            width: 3
            height: parent.height
            color: Theme.accent
        }
        Grid {
            id: keypadGrid
            anchors.centerIn: parent
            columns: root.session && root.session.keypad.length ? root.session.keypad[0].length : 1
            spacing: 6
            Repeater {
                model: {
                    const cells = []
                    if (root.session)
                        for (const row of root.session.keypad)
                            for (const cell of row)
                                cells.push(cell)
                    return cells
                }
                KeyBadge {
                    required property var modelData
                    label: modelData.label
                    locked: modelData.locked
                    selected: modelData.button === root.selected
                    onClicked: root.activate(modelData.button)
                }
            }
        }
    }

    // -- artwork + hotspots ---------------------------------------------------
    Item {
        id: stage
        anchors.left: buttonCallout.right
        anchors.right: keypadCallout.visible ? keypadCallout.left : parent.right
        anchors.top: parent.top
        anchors.bottom: dots.top
        anchors.margins: 12

        Image {
            id: artwork
            anchors.fill: parent
            source: root.view ? root.view.image : ""
            fillMode: Image.PreserveAspectFit
            sourceSize.width: Math.max(1, width * Screen.devicePixelRatio)
            smooth: true
            mipmap: true
            asynchronous: true
        }

        Item {
            id: painted
            x: (artwork.width - artwork.paintedWidth) / 2
            y: (artwork.height - artwork.paintedHeight) / 2
            width: artwork.paintedWidth
            height: artwork.paintedHeight

            Repeater {
                model: root.view ? root.view.hotspots : []
                Rectangle {
                    id: spot
                    required property var modelData
                    readonly property bool current: modelData.button === root.selected
                    readonly property bool hovered: spotMouse.containsMouse && !modelData.locked
                    x: modelData.x * painted.width
                    y: modelData.y * painted.height
                    width: modelData.w * painted.width
                    height: modelData.h * painted.height
                    radius: modelData.radius * height
                    color: current ? Qt.rgba(0.95, 0.77, 0, 0.22) : hovered ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                    border.color: current ? Theme.accent : hovered ? Qt.rgba(0.95, 0.77, 0, 0.6) : "transparent"
                    border.width: 2
                    Behavior on color { ColorAnimation { duration: 100 } }

                    MouseArea {
                        id: spotMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: spot.modelData.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: root.activate(spot.modelData.button)
                    }
                }
            }
        }
    }

    // Connector from the selected keypad hotspot to the keypad callout.
    Rectangle {
        readonly property var spot: root.hotspotIn(root.view, root.selected)
        readonly property bool inKeypad: {
            if (!root.session)
                return false
            for (const row of root.session.keypad)
                for (const cell of row)
                    if (cell.button === root.selected)
                        return true
            return false
        }
        visible: spot !== null && inKeypad && keypadCallout.visible
        x: spot ? stage.x + painted.x + (spot.x + spot.w) * painted.width : 0
        y: spot ? stage.y + painted.y + (spot.y + spot.h / 2) * painted.height : 0
        width: Math.max(0, keypadCallout.x - x)
        height: 1
        color: Theme.accent
    }

    CarouselDots {
        id: dots
        anchors.horizontalCenter: stage.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        count: root.views.length
        current: root.viewIndex
        visible: count > 1
        onSelected: index => root.viewIndex = index
    }

    Text {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        visible: root.view !== null && root.views.length > 1
        text: root.view ? root.view.title.toUpperCase() + " VIEW" : ""
        color: Theme.textDim
        font.pixelSize: Theme.fontSmall
    }

    // Wireless devices stay registered while switched off.
    Rectangle {
        anchors.fill: parent
        visible: root.session !== null && !root.session.connected
        color: Qt.rgba(0, 0, 0, 0.65)
        Text {
            anchors.centerIn: parent
            text: "Device is offline"
            color: Theme.text
            font.pixelSize: Theme.fontHeader
        }
        MouseArea { anchors.fill: parent }
    }
}
