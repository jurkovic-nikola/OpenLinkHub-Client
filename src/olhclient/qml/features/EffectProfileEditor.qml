import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Settings of the current effect (OpenLinkHub's RGB profile): colours, speed and the
// rest of OpenLinkHub's RGB editor. Edited as a draft and saved together.
ColumnLayout {
    id: root
    property var profile
    property string note: ""

    property var draft: ({})
    property string saved: "{}"  // the profile's values as JSON, to compare the draft with
    readonly property bool dirty: JSON.stringify(draft) !== saved
    readonly property var colors: draft.colors || []
    readonly property var temperatures: draft.temperatures || []
    readonly property var stops: draft.gradient || []
    readonly property var sortedStops: stops.slice().sort((a, b) => a.position - b.position)
    readonly property int labelWidth: 170

    function revert() {
        saved = JSON.stringify(profile ? profile.values : {})
        draft = JSON.parse(saved)
    }

    function set(key, value) {
        const copy = Object.assign({}, draft)
        copy[key] = value
        draft = copy
    }

    function setAt(key, i, value) {
        const list = draft[key].slice()
        list[i] = value
        set(key, list)
    }

    function setStop(i, field, value) {
        const list = stops.map(s => Object.assign({}, s))
        list[i][field] = value
        set("gradient", list)
    }

    function addStop() {
        set("gradient", stops.concat([{color: "#00ffff", position: 0.5, brightness: 1}]))
    }

    function removeStop(i) {
        const list = stops.slice()
        list.splice(i, 1)
        set("gradient", list)
    }

    // a gradient colour as the LEDs show it
    function shade(stop) {
        const c = Qt.color(stop.color)
        return Qt.rgba(c.r * stop.brightness, c.g * stop.brightness, c.b * stop.brightness, 1)
    }

    visible: profile !== null && profile !== undefined && profile.available
    spacing: 12
    onProfileChanged: revert()
    Connections {
        target: root.profile
        function onChanged() { root.revert() }
    }

    ColorPicker {
        id: picker
        anchors.centerIn: Overlay.overlay
    }

    Text {
        text: root.profile ? root.profile.effectTitle.toUpperCase() : ""
        color: Theme.textDim
        font.pixelSize: Theme.fontSmall
        font.bold: true
    }

    // -- colours --------------------------------------------------------------
    Repeater {
        model: root.profile ? root.profile.colorNames : []
        RowLayout {
            id: colorRow
            required property int index
            required property string modelData
            readonly property string draftColor: root.colors[index] !== undefined ? root.colors[index] : "#000000"
            spacing: 12
            Text {
                Layout.preferredWidth: root.labelWidth
                text: colorRow.modelData + " colour"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            ColorSwatch {
                color: colorRow.draftColor
                onClicked: picker.pick(colorRow.draftColor, c => root.setAt("colors", colorRow.index, c))
            }
            Text {
                Layout.preferredWidth: 70
                text: colorRow.draftColor
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
                font.family: "monospace"
            }
            DarkSpinBox {
                visible: root.profile.hasTemperatures
                from: 0
                to: 105
                value: root.temperatures[colorRow.index] !== undefined ? root.temperatures[colorRow.index] : 0
                onValueModified: root.setAt("temperatures", colorRow.index, value)
            }
            Text {
                visible: root.profile.hasTemperatures
                text: "°C"
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
            }
        }
    }

    // -- probe temperature range ---------------------------------------------
    Repeater {
        model: root.profile && root.profile.hasTempRange
               ? [{key: "minTemp", text: "Minimum temperature"}, {key: "maxTemp", text: "Maximum temperature"}] : []
        RowLayout {
            id: rangeRow
            required property var modelData
            spacing: 12
            Text {
                Layout.preferredWidth: root.labelWidth
                text: rangeRow.modelData.text
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            DarkSpinBox {
                from: 0
                to: 100
                value: root.draft[rangeRow.modelData.key] || 0
                onValueModified: root.set(rangeRow.modelData.key, value)
            }
            Text { text: "°C"; color: Theme.textDim; font.pixelSize: Theme.fontNormal }
        }
    }

    // -- speed ----------------------------------------------------------------
    RowLayout {
        visible: root.profile !== null && root.profile.hasSpeed
        spacing: 12
        Text {
            Layout.preferredWidth: root.labelWidth
            text: "Speed"
            color: Theme.text
            font.pixelSize: Theme.fontNormal
        }
        Text { text: "Fast"; color: Theme.textDim; font.pixelSize: Theme.fontSmall }
        DarkSlider {
            id: speedSlider
            Layout.preferredWidth: 200
            from: 1
            to: root.profile ? root.profile.speedMax : 10
            stepSize: root.profile ? root.profile.speedStep : 0.1
            value: root.draft.speed || 1
            onMoved: root.set("speed", Math.round(value * 10) / 10)
        }
        Text { text: "Slow"; color: Theme.textDim; font.pixelSize: Theme.fontSmall }
        Text {
            text: (root.draft.speed || 1).toString()
            color: Theme.accent
            font.pixelSize: Theme.fontNormal
        }
    }

    // -- Slipstream options ---------------------------------------------------
    RowLayout {
        visible: root.profile !== null && root.profile.hasDirection
        spacing: 12
        Text {
            Layout.preferredWidth: root.labelWidth
            text: "Direction (Slipstream only)"
            color: Theme.text
            font.pixelSize: Theme.fontNormal
        }
        DarkComboBox {
            Layout.preferredWidth: 200
            model: root.profile ? root.profile.directions : []
            currentIndex: {
                for (let i = 0; i < model.length; ++i)
                    if (model[i].value === root.draft.direction)
                        return i
                return -1
            }
            onActivated: index => root.set("direction", model[index].value)
        }
    }
    RowLayout {
        visible: root.profile !== null && root.profile.hasAlternate
        spacing: 12
        Text {
            Layout.preferredWidth: root.labelWidth
            text: "Alternate colours (Slipstream only)"
            color: Theme.text
            font.pixelSize: Theme.fontNormal
            wrapMode: Text.Wrap
        }
        DarkSwitch {
            checked: root.draft.alternate === true
            onToggled: root.set("alternate", checked)
        }
    }

    // -- gradient -------------------------------------------------------------
    ColumnLayout {
        visible: root.profile !== null && root.profile.hasGradient
        spacing: 10

        Rectangle {
            id: bar
            Layout.preferredWidth: 420
            Layout.preferredHeight: 24
            color: root.sortedStops.length ? root.shade(root.sortedStops[0]) : "black"
            border.color: Theme.borderStrong
            Repeater {
                model: root.sortedStops
                Rectangle {
                    id: segment
                    required property int index
                    required property var modelData
                    readonly property var next: root.sortedStops[index + 1] || modelData
                    x: modelData.position * bar.width
                    width: (index + 1 < root.sortedStops.length ? next.position : 1) * bar.width - x
                    height: bar.height
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: root.shade(segment.modelData) }
                        GradientStop { position: 1; color: root.shade(segment.next) }
                    }
                }
            }
        }

        Repeater {
            model: root.stops.length
            RowLayout {
                id: stopRow
                required property int index
                readonly property var stop: root.stops[index] || {color: "#000000", position: 0, brightness: 1}
                spacing: 10
                ColorSwatch {
                    color: stopRow.stop.color
                    onClicked: picker.pick(stopRow.stop.color, c => root.setStop(stopRow.index, "color", c))
                }
                Text {
                    Layout.preferredWidth: 70
                    text: stopRow.stop.color
                    color: Theme.textDim
                    font.pixelSize: Theme.fontNormal
                    font.family: "monospace"
                }
                Text { text: "Position"; color: Theme.text; font.pixelSize: Theme.fontNormal }
                DarkSpinBox {
                    from: 0
                    to: 100
                    value: Math.round(stopRow.stop.position * 100)
                    onValueModified: root.setStop(stopRow.index, "position", value / 100)
                }
                Text { text: "%"; color: Theme.textDim; font.pixelSize: Theme.fontNormal }
                Text { text: "Brightness"; color: Theme.text; font.pixelSize: Theme.fontNormal }
                DarkSpinBox {
                    from: 0
                    to: 100
                    value: Math.round(stopRow.stop.brightness * 100)
                    onValueModified: root.setStop(stopRow.index, "brightness", value / 100)
                }
                Text { text: "%"; color: Theme.textDim; font.pixelSize: Theme.fontNormal }
                AccentButton {
                    text: "Remove"
                    enabled: root.stops.length > 2
                    onClicked: root.removeStop(stopRow.index)
                }
            }
        }
        AccentButton {
            text: "Add colour"
            onClicked: root.addStop()
        }
    }

    RowLayout {
        Layout.topMargin: 4
        spacing: 10
        AccentButton {
            text: "Revert"
            enabled: root.dirty
            onClicked: root.revert()
        }
        AccentButton {
            accent: true
            text: root.profile && root.profile.saving ? "Saving…" : "Save effect"
            enabled: root.dirty && !(root.profile && root.profile.saving)
            onClicked: root.profile.save(root.draft)
        }
    }
    Text {
        Layout.fillWidth: true
        Layout.maximumWidth: 460
        visible: text !== ""
        text: root.note
        wrapMode: Text.Wrap
        color: Theme.textMuted
        font.pixelSize: Theme.fontSmall
    }
}
