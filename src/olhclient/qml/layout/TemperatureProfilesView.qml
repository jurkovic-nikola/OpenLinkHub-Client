import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

RowLayout {
    id: root
    objectName: "temperatureForm"
    required property var backend
    property var options: ({})
    property var profiles: []
    property string selected: ""
    property var detail: null
    property bool graphMode: true
    property bool modeUnknown: false
    property string pendingSelection: ""
    function navigate(name) {
        if (name === selected && detail) return
        if (detail && (pump.dirty || fans.dirty || Object.keys(rangeChanges).length)) {
            pendingSelection = name
            discard.open()
        } else select(name)
    }
    readonly property bool preset: ["Normal", "Performance", "Quiet"].includes(selected)
    property var rangeChanges: ({})
    function select(name) {
        selected = name
        detail = null
        rangeChanges = {}
        if (name) backend.selectTemperatureProfile(name)
    }
    property bool loadFailed: false
    readonly property int sensor: sensors.currentIndex >= 0 ? Number(sensors.currentValue) : -1
    readonly property string selector: ({
        3: "hwmonDeviceId", 4: "probeData", 6: "hwmon-probeData",
        8: "gpuIndex", 9: "probeData"
    })[sensor] || ""
    spacing: Theme.gap
    Component.onCompleted: backend.loadTemperatureForm()
    Connections {
        target: root.backend
        function onTemperatureFormLoaded(form) {
            root.options = form.options
            root.modeUnknown = form.graphMode == null
            root.graphMode = form.graphMode !== false
            root.profiles = form.profiles
            root.loadFailed = false
        }
        function onTemperatureFormFailed() { root.loadFailed = true }
        function onTemperatureCreated(name) {
            root.profiles = Array.from(new Set(root.profiles.concat([name]))).sort(
                (a, b) => a.localeCompare(b))
            profileName.clear()
            root.select(name)
        }
        function onTemperatureSelected(name, data) {
            if (name !== root.selected) return
            root.detail = data
            pump.load(data.points ? data.points["0"] : [])
            fans.load(data.points ? data.points["1"] : [])
        }
        function onTemperatureSaved(name, kind) {
            if (name !== root.selected) return
            if (kind === 0) pump.dirty = false
            else if (kind === 1) fans.dirty = false
            else root.select(name)
        }
        function onTemperatureDeleted(name) {
            root.profiles = root.profiles.filter(p => p !== name)
            if (name === root.selected) root.select("")
        }
    }

    function create() {
        let payload = {profile: profileName.text, sensor: sensor, static: fixed.checked,
                       zeroRpm: zero.checked, linear: false}
        let value = hardware.currentValue
        if (sensor === 3) payload.hwmonDeviceId = value
        if (sensor === 4 || sensor === 9) {
            let parts = value.split(";")
            payload.deviceId = parts[0]
            payload.channelId = Number(parts[1])
        }
        if (sensor === 6) {
            let parts = value.split(";")
            payload.hwmonDeviceId = parts[0]
            payload.temperatureInputId = parts[1]
            payload.hwmonDevice = parts[2]
        }
        if (sensor === 7) payload.externalExecutable = binaryPath.text
        if (sensor === 8) payload.gpuIndex = Number(value)
        backend.createTemperatureProfile(payload)
    }

    Panel {
        title: "Profiles"
        highlighted: true
        Layout.preferredWidth: 310
        Layout.maximumWidth: 310
        Layout.fillHeight: true
        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.profiles
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    id: profileRow
                    required property string modelData
                    readonly property bool current: modelData === root.selected
                    objectName: "profileRow_" + modelData
                    width: ListView.view.width
                    height: 40
                    enabled: root.backend && !root.backend.temperatureSaving
                    color: current ? Theme.header : rowMouse.containsMouse ? Theme.hover : "transparent"
                    Rectangle {
                        width: 3
                        height: parent.height
                        color: Theme.accent
                        visible: profileRow.current
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        x: 16
                        width: parent.width - 32
                        text: profileRow.modelData
                        color: profileRow.current ? Theme.accent : Theme.text
                        font.pixelSize: Theme.fontNormal
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.navigate(profileRow.modelData)
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 10
                spacing: 6
                Item { Layout.fillWidth: true }
                AccentButton {
                    text: "New"
                    enabled: root.backend && !root.backend.temperatureSaving
                    onClicked: root.navigate("")
                }
                AccentButton {
                    text: "Delete…"
                    enabled: !!root.detail && !root.preset && root.backend && !root.backend.temperatureSaving
                    onClicked: confirmDelete.open()
                }
            }
        }
    }
    Panel {
        visible: !root.selected
        title: "Create temperature profile"
        highlighted: true
        Layout.fillWidth: true
        Layout.fillHeight: true
        ColumnLayout {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.margins: 18
            spacing: 10
            enabled: root.backend && !root.backend.temperatureSaving
            Text { text: "Profile name"; color: Theme.text }
            DarkTextField {
                id: profileName
                objectName: "profileName"
                Layout.preferredWidth: 320
                placeholderText: "At least 3 letters or digits"
                validator: RegularExpressionValidator { regularExpression: /[A-Za-z0-9]{3,}/ }
            }
            Text { text: "Temperature sensor"; color: Theme.text }
            DarkComboBox {
                id: sensors
                Layout.preferredWidth: 320
                model: root.options.sensor || []
            }
            DarkComboBox {
                id: hardware
                Layout.preferredWidth: 320
                visible: root.selector !== ""
                model: root.options[root.selector] || []
                displayText: currentIndex < 0 ? "No matching hardware available" : currentText
            }
            DarkTextField {
                id: binaryPath
                visible: root.sensor === 7
                Layout.preferredWidth: 320
                placeholderText: "Path to binary on the OpenLinkHub server"
            }
            DarkSwitch { id: fixed; text: "Static speed" }
            DarkSwitch { id: zero; text: "Zero RPM" }
            AccentButton {
                text: "Create profile"
                enabled: profileName.acceptableInput && root.sensor >= 0
                         && (!root.selector || hardware.currentIndex >= 0)
                         && (root.sensor !== 7 || binaryPath.text.trim().length > 0)
                onClicked: root.create()
            }
            AccentButton {
                visible: root.loadFailed
                text: "Retry loading profiles"
                onClicked: {
                    root.loadFailed = false
                    root.backend.loadTemperatureForm()
                }
            }
        }
    }
    Panel {
        visible: !!root.selected
        title: root.selected
        highlighted: true
        Layout.fillWidth: true
        Layout.fillHeight: true
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            enabled: root.backend && !root.backend.temperatureSaving
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: root.detail ? ((root.options.sensor || []).find(s => Number(s.value) === root.detail.sensor)?.text || "Sensor")
                        + " - Zero RPM " + (root.detail.zeroRpm ? "enabled" : "disabled") : ""
                    color: Theme.text
                }
                DarkSwitch {
                    visible: root.modeUnknown && !root.preset
                    text: "Graph mode"
                    checked: root.graphMode
                    enabled: !pump.dirty && !fans.dirty && !Object.keys(root.rangeChanges).length
                    onToggled: root.graphMode = checked
                }
                Item { Layout.fillWidth: true }
            }
            Text {
                visible: root.graphMode && !root.preset && !!root.detail
                text: "Click to add a point, drag to adjust, or right-click to remove."
                color: Theme.textDim
            }
            RowLayout {
                visible: root.graphMode && !root.preset && !!root.detail
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 18
                TemperatureCurve {
                    id: pump
                    title: "Pump speed"
                    maximum: root.detail && root.detail.sensor === 2 ? 60 : 100
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    onSaveRequested: points => root.backend.saveTemperatureCurve(root.selected, 0, points)
                }
                TemperatureCurve {
                    id: fans
                    title: "Fan speed"
                    maximum: pump.maximum
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    onSaveRequested: points => root.backend.saveTemperatureCurve(root.selected, 1, points)
                }
            }
            ListView {
                Layout.fillHeight: true
                Layout.fillWidth: true
                visible: (!root.graphMode || root.preset) && !!root.detail
                clip: true
                spacing: 4
                model: visible ? root.detail.profiles : []
                delegate: RowLayout {
                    id: band
                    required property var modelData
                    function changed() {
                        const changes = Object.assign({}, root.rangeChanges)
                        changes[modelData.id] = {fans: fanSpeed.value, pump: pumpSpeed.value}
                        root.rangeChanges = changes
                    }
                    Text { text: band.modelData.min + " – " + band.modelData.max + " °C"; color: Theme.text; Layout.preferredWidth: 125 }
                    Text { text: "Fan %"; color: Theme.text }
                    DarkSpinBox {
                        id: fanSpeed
                        from: 0; to: 100; value: band.modelData.fans
                        enabled: !root.preset && !root.detail.linear
                        onValueModified: band.changed()
                    }
                    Text { text: "Pump %"; color: Theme.text }
                    DarkSpinBox {
                        id: pumpSpeed
                        from: 20; to: 100; value: band.modelData.pump
                        enabled: fanSpeed.enabled
                        onValueModified: band.changed()
                    }
                }
            }
            AccentButton {
                visible: !root.graphMode && !root.preset && !!root.detail && !root.detail.linear
                text: "Save ranges"
                enabled: Object.keys(root.rangeChanges).length > 0
                onClicked: root.backend.saveTemperatureRanges(root.selected, root.rangeChanges)
            }
        }
    }
    ConfirmationDialog {
        id: discard
        title: "Unsaved changes"
        message: "Discard your changes to " + root.selected + "?"
        confirmText: "Discard"
        destructive: true
        onAccepted: root.select(root.pendingSelection)
    }
    ConfirmationDialog {
        id: confirmDelete
        title: "Delete profile"
        message: "Delete temperature profile " + root.selected + "?"
        confirmText: "Delete"
        destructive: true
        onAccepted: root.backend.deleteTemperatureProfile(root.selected)
    }
}
