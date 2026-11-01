import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Settings of a Slipstream USB receiver, after iCUE's Device Settings page: the
// receiver and its paired devices as cards on the left, its settings on the right.
Rectangle {
    id: root
    property var receiver
    property var backend
    color: Theme.panelAlt

    function indexIn(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value)
                return i
        return -1
    }

    // Artwork of a paired device, if the client knows that device.
    function thumbnailOf(serial) {
        const devices = backend ? backend.devices : null
        if (!devices || devices.count === 0)
            return ""
        const row = devices.indexOf("serial", serial)
        return row >= 0 ? devices.get(row).thumbnail : ""
    }

    component DeviceCard: Rectangle {
        id: card
        property alias title: cardTitle.text
        property alias image: cardImage.source
        property bool current: false
        property bool clickable: false
        signal clicked()

        width: parent ? parent.width : 200
        height: 112
        color: current ? Theme.hover : cardMouse.containsMouse && clickable ? "#2c2c2c" : Theme.panelAlt
        border.color: current ? Theme.borderStrong : Theme.border

        Image {
            id: cardImage
            anchors.horizontalCenter: parent.horizontalCenter
            y: 12
            width: parent.width - 40
            height: 62
            sourceSize: Qt.size(220, 124)
            fillMode: Image.PreserveAspectFit
        }
        Image {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 8
            visible: !card.current
            source: "../icons/wireless.svg"
            sourceSize: Qt.size(16, 16)
            opacity: 0.7
        }
        Text {
            id: cardTitle
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            width: parent.width - 16
            horizontalAlignment: Text.AlignHCenter
            color: card.current ? Theme.text : Theme.textDim
            font.pixelSize: Theme.fontNormal
            elide: Text.ElideMiddle
        }
        MouseArea {
            id: cardMouse
            anchors.fill: parent
            hoverEnabled: true
            enabled: card.clickable
            cursorShape: Qt.PointingHandCursor
            onClicked: card.clicked()
        }
    }

    component InfoTip: Rectangle {
        id: tip
        property string text
        implicitWidth: 18
        implicitHeight: 18
        radius: 9
        color: tipMouse.containsMouse ? Theme.text : Theme.textDim

        Text {
            anchors.centerIn: parent
            text: "i"
            color: Theme.panelAlt
            font.pixelSize: Theme.fontSmall
            font.bold: true
        }
        MouseArea {
            id: tipMouse
            anchors.fill: parent
            hoverEnabled: true
        }
        ToolTip {
            visible: tipMouse.containsMouse
            delay: 300
            width: 320
            contentItem: Text {
                text: tip.text
                color: Theme.text
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.WordWrap
            }
            background: Rectangle {
                color: "#202020"
                border.color: Theme.borderStrong
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // -- device cards ------------------------------------------------------
        Rectangle {
            Layout.preferredWidth: 230
            Layout.fillHeight: true
            color: Theme.panel

            Flickable {
                anchors.fill: parent
                anchors.margins: 14
                contentHeight: cards.implicitHeight
                clip: true

                Column {
                    id: cards
                    width: parent.width
                    spacing: 10

                    Text {
                        text: "RECEIVER"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                    DeviceCard {
                        title: root.receiver ? root.receiver.product : ""
                        image: "../images/slipstream.svg"
                        current: true
                    }
                    Text {
                        topPadding: 6
                        text: "PAIRED DEVICES"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                    Repeater {
                        model: root.receiver ? root.receiver.pairedDevices : []
                        DeviceCard {
                            required property var modelData
                            readonly property string thumbnail: root.thumbnailOf(modelData.serial)
                            title: modelData.product
                            image: thumbnail
                            clickable: thumbnail !== ""
                            onClicked: root.backend.selectDevice(modelData.serial)
                        }
                    }
                    Text {
                        visible: !root.receiver || root.receiver.pairedDevices.length === 0
                        width: parent.width
                        text: "No device is paired with this receiver."
                        color: Theme.textMuted
                        font.pixelSize: Theme.fontSmall
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // -- settings ----------------------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            EditorHeader {
                Layout.fillWidth: true
                title: "DEVICE SETTINGS"
                icon: "../icons/settings.svg"
                Text {
                    text: !root.receiver ? "" : root.receiver.busy ? "Applying…" : "Changes apply immediately"
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSmall
                }
            }

            ColumnLayout {
                Layout.margins: 24
                Layout.maximumWidth: 640
                spacing: 16

                RowLayout {
                    spacing: 18
                    Column {
                        Layout.preferredWidth: 240
                        spacing: 4
                        Text {
                            text: "Firmware"
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                        Text {
                            text: root.receiver && root.receiver.firmware ? "v. " + root.receiver.firmware : "Unknown"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSmall
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: Theme.border
                }

                RowLayout {
                    spacing: 18
                    Text {
                        Layout.preferredWidth: 240
                        text: "USB Receiver Polling Rate"
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkComboBox {
                        id: pollingRate
                        Layout.preferredWidth: 220
                        visible: root.receiver !== null && root.receiver.pollingRates.length > 0
                        enabled: root.receiver !== null && !root.receiver.busy
                        model: root.receiver ? root.receiver.pollingRates : []
                        currentIndex: root.receiver ? root.indexIn(model, root.receiver.pollingRate) : -1
                        displayText: currentIndex < 0 ? "Not set" : currentText
                        onActivated: index => root.receiver.setPollingRate(model[index].value)
                    }
                    Text {
                        Layout.preferredWidth: 220
                        visible: !pollingRate.visible
                        text: "Not adjustable"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontNormal
                    }
                    InfoTip {
                        text: "How often the receiver reports to the computer. It applies to every device "
                            + "paired with this receiver. The receiver may restart when it changes, so its "
                            + "devices can disconnect for a few seconds."
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
