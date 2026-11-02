import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// The macros page: OpenLinkHub's macros on the left, the actions of the selected one on
// the right. Edits a local draft; Save sends it to OpenLinkHub.
RowLayout {
    id: root
    property var library
    readonly property var current: library ? library.current : null
    spacing: Theme.gap

    property int draftRepeat: 0
    property int draftRepeatDelay: 0
    // bumped on every change of the draft list, which bindings cannot see otherwise
    property int revision: 0

    readonly property var actions: { revision; return draftActions() }
    readonly property bool dirty: current !== null && (current.gaps || draftRepeat !== current.repeat
        || draftRepeatDelay !== current.repeatDelay || actions.map(signature).join(";") !== current.actions.map(signature).join(";"))
    readonly property string problem: library && current ? library.validate(actions) : ""

    // the action being added
    property int newType: 3
    property int newCommand: 0
    property int newDelay: 50
    property string newText: ""
    property int newX: 0
    property int newY: 0
    property bool newAbsolute: false
    property var keyOptions: []
    readonly property var shownKeys: {
        const filter = keyFilter.text.trim().toLowerCase()
        return filter ? keyOptions.filter(o => o.text.toLowerCase().includes(filter)) : keyOptions
    }

    // action types: 1 media, 3 keyboard, 5 delay, 6 text, 9 mouse, 20 mouse position
    function isKey(type) { return type === 1 || type === 3 || type === 9 }
    function repeats(type) { return type === 6 || type === 20 }

    function copy(a) {
        return { type: a.type, command: a.command, delay: a.delay, text: a.text, hold: a.hold, repeat: a.repeat,
                 repeatDelay: a.repeatDelay, posX: a.posX, posY: a.posY, absolute: a.absolute }
    }
    function signature(a) {
        return [a.type, a.command, a.delay, a.text, a.hold, a.repeat, a.repeatDelay, a.posX, a.posY, a.absolute].join("|")
    }
    function draftActions() {
        const result = []
        for (let i = 0; i < draft.count; ++i)
            result.push(copy(draft.get(i)))
        return result
    }
    function indexIn(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value)
                return i
        return -1
    }

    function revert() {
        draft.clear()
        if (current) {
            for (const action of current.actions)
                draft.append(copy(action))
            draftRepeat = current.repeat
            draftRepeatDelay = current.repeatDelay
        }
        revision++
    }
    function setField(row, role, value) {
        draft.setProperty(row, role, value)
        revision++
    }
    function moveAction(row, to) {
        draft.move(row, to, 1)
        revision++
    }
    function removeAction(row) {
        draft.remove(row)
        revision++
    }
    function refreshKeys() {
        keyOptions = library && isKey(newType) ? library.keyOptions(newType) : []
    }
    readonly property bool canAdd: current !== null && (isKey(newType) ? newCommand !== 0
        : newType === 5 ? newDelay > 0 : newType === 6 ? newText !== "" : true)
    function addAction() {
        draft.append({ type: newType, command: isKey(newType) ? newCommand : 0, delay: newType === 5 ? newDelay : 0,
                       text: newType === 6 ? newText : "", hold: false, repeat: 0, repeatDelay: 0,
                       posX: newType === 20 ? newX : 0, posY: newType === 20 ? newY : 0,
                       absolute: newType === 20 && newAbsolute })
        revision++
        actionList.positionViewAtEnd()
    }

    onCurrentChanged: revert()
    onNewTypeChanged: { newCommand = 0; refreshKeys() }
    Component.onCompleted: {
        refreshKeys()
        if (library)
            library.reload()
    }

    ListModel { id: draft }

    Connections {
        target: root.library
        function onNamesChanged() { root.refreshKeys() }
    }

    // -- macro list ------------------------------------------------------------
    Panel {
        id: listPanel
        Layout.preferredWidth: 310
        Layout.maximumWidth: 310
        Layout.fillHeight: true
        title: "Macros"
        icon: Qt.resolvedUrl("../icons/macro.svg")
        highlighted: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            ListView {
                id: macroList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.library ? root.library.macros : []
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    id: macroRow
                    required property var modelData
                    readonly property bool current: root.current !== null && root.current.id === modelData.id
                    width: ListView.view.width
                    height: 40
                    color: current ? Theme.header : rowMouse.containsMouse ? Theme.hover : "transparent"

                    Rectangle {
                        width: 3
                        height: parent.height
                        color: Theme.accent
                        visible: macroRow.current
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        x: 16
                        width: parent.width - countLabel.width - 32
                        text: macroRow.modelData.name
                        color: macroRow.current ? Theme.accent : Theme.text
                        font.pixelSize: Theme.fontNormal
                        elide: Text.ElideRight
                    }
                    Text {
                        id: countLabel
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        text: macroRow.modelData.count + (macroRow.modelData.count === 1 ? " action" : " actions")
                        color: Theme.textDim
                        font.pixelSize: Theme.fontSmall
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.library.currentId = macroRow.modelData.id
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.margins: 16
                visible: root.library !== null && root.library.loaded && macroList.count === 0
                text: "No macros yet. Create one, add its actions, then assign it to a button with Key remapping."
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 10
                spacing: 6
                Item { Layout.fillWidth: true }
                AccentButton {
                    text: "New"
                    enabled: root.library !== null && !root.library.busy
                    onClicked: newPopup.open()
                }
                AccentButton {
                    text: "Delete…"
                    enabled: root.current !== null && !root.library.busy
                    onClicked: deletePopup.open()
                }
            }
        }
    }

    Popup {
        id: newPopup
        parent: listPanel
        y: listPanel.height - height - 50
        width: listPanel.width
        padding: 14
        modal: true
        focus: true
        onOpened: { nameField.text = ""; nameField.forceActiveFocus() }
        background: Rectangle { color: Theme.panel; border.color: Theme.accent }

        readonly property string problem: root.library && nameField.text ? root.library.nameProblem(nameField.text) : ""

        function create() {
            if (!nameField.text || problem)
                return
            root.library.create(nameField.text)
            close()
        }

        contentItem: ColumnLayout {
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "New macro"
                color: Theme.text
                font.pixelSize: Theme.fontNormal
            }
            DarkTextField {
                id: nameField
                Layout.fillWidth: true
                placeholderText: "Name (letters and numbers)"
                onAccepted: newPopup.create()
            }
            Text {
                Layout.fillWidth: true
                visible: newPopup.problem !== ""
                text: newPopup.problem
                color: Theme.danger
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AccentButton { text: "Cancel"; onClicked: newPopup.close() }
                AccentButton {
                    accent: true
                    text: "Create"
                    enabled: nameField.text !== "" && newPopup.problem === ""
                    onClicked: newPopup.create()
                }
            }
        }
    }

    Popup {
        id: deletePopup
        parent: listPanel
        y: listPanel.height - height - 50
        width: listPanel.width
        padding: 14
        modal: true
        background: Rectangle { color: Theme.panel; border.color: Theme.danger }

        contentItem: ColumnLayout {
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: root.current ? "Delete macro " + root.current.name + "? Buttons that run it will do nothing." : ""
                color: Theme.text
                font.pixelSize: Theme.fontNormal
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                AccentButton { text: "Cancel"; onClicked: deletePopup.close() }
                AccentButton {
                    text: "Delete"
                    onClicked: {
                        root.library.deleteMacro(root.current.id)
                        deletePopup.close()
                    }
                }
            }
        }
    }

    // -- editor ----------------------------------------------------------------
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: Theme.panelAlt

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            EditorHeader {
                Layout.fillWidth: true
                icon: Qt.resolvedUrl("../icons/macro.svg")
                title: root.current ? "MACRO   ·   " + root.current.name : "NO MACRO SELECTED"
                AccentButton {
                    text: "Revert"
                    enabled: root.dirty && !root.library.busy
                    onClicked: root.revert()
                }
                AccentButton {
                    accent: true
                    text: root.library && root.library.busy ? "Saving…" : "Save"
                    enabled: root.dirty && root.problem === "" && !root.library.busy
                    onClicked: root.library.save(root.current.id, root.draftRepeat, root.draftRepeatDelay, root.actions)
                }
            }

            // playback settings of the whole macro
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.topMargin: 12
                enabled: root.current !== null
                spacing: 12

                DarkSwitch {
                    text: "Loop until pressed again"
                    checked: root.draftRepeat < 0
                    onToggled: root.draftRepeat = checked ? -1 : 1
                }
                Item { implicitWidth: 12 }
                Text {
                    text: "Play"
                    color: root.draftRepeat < 0 ? Theme.textMuted : Theme.text
                    font.pixelSize: Theme.fontNormal
                }
                DarkSpinBox {
                    Layout.preferredWidth: 100
                    enabled: root.draftRepeat >= 0
                    from: 1
                    to: 1000
                    value: Math.max(1, root.draftRepeat)
                    onValueModified: root.draftRepeat = value
                }
                Text {
                    text: "times, pause"
                    color: Theme.text
                    font.pixelSize: Theme.fontNormal
                }
                DarkSpinBox {
                    Layout.preferredWidth: 110
                    from: 0
                    to: 60000
                    value: root.draftRepeatDelay
                    onValueModified: root.draftRepeatDelay = value
                }
                Text {
                    Layout.fillWidth: true
                    text: "ms between plays"
                    color: Theme.text
                    font.pixelSize: Theme.fontNormal
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.topMargin: 6
                text: "Not every device driver uses these playback settings."
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.topMargin: 6
                visible: root.current !== null && root.current.gaps
                text: "Some actions of this macro never play: its action list has a gap. Save to close it."
                color: Theme.danger
                font.pixelSize: Theme.fontSmall
                wrapMode: Text.Wrap
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 12
                implicitHeight: 1
                color: Theme.border
            }

            // actions, in the order they play
            ListView {
                id: actionList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: draft
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: actionRow
                    required property int index
                    required property var model
                    width: ListView.view.width
                    height: root.repeats(actionRow.model.type) ? 80 : 44
                    color: index % 2 ? Theme.panelAlt : "#202020"

                    RowLayout {
                        id: mainRow
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 18
                        anchors.rightMargin: 14
                        height: 44
                        spacing: 10

                        Text {
                            Layout.preferredWidth: 22
                            text: actionRow.index + 1
                            color: Theme.textDim
                            font.pixelSize: Theme.fontNormal
                        }
                        Text {
                            Layout.preferredWidth: 110
                            text: root.library ? root.library.stepTitle(actionRow.model.type) : ""
                            color: Theme.accent
                            font.pixelSize: Theme.fontNormal
                        }

                        // keyboard, mouse and media keys
                        Text {
                            Layout.fillWidth: true
                            visible: root.isKey(actionRow.model.type)
                            text: root.library ? root.library.keyName(actionRow.model.type, actionRow.model.command) : ""
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                            elide: Text.ElideRight
                        }
                        DarkSwitch {
                            visible: root.isKey(actionRow.model.type)
                            text: "Hold"
                            checked: actionRow.model.hold
                            onToggled: root.setField(actionRow.index, "hold", checked)
                        }

                        // delay
                        DarkSpinBox {
                            Layout.preferredWidth: 110
                            visible: actionRow.model.type === 5
                            from: 1
                            to: 65535
                            value: actionRow.model.delay
                            onValueModified: root.setField(actionRow.index, "delay", value)
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: actionRow.model.type === 5
                            text: "ms"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontNormal
                        }

                        // text
                        DarkTextField {
                            Layout.fillWidth: true
                            visible: actionRow.model.type === 6
                            text: actionRow.model.text
                            onTextEdited: root.setField(actionRow.index, "text", text)
                        }

                        // mouse position
                        Text {
                            visible: actionRow.model.type === 20
                            text: "X"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontNormal
                        }
                        DarkSpinBox {
                            Layout.preferredWidth: 96
                            visible: actionRow.model.type === 20
                            from: 0
                            to: 16384
                            value: actionRow.model.posX
                            onValueModified: root.setField(actionRow.index, "posX", value)
                        }
                        Text {
                            visible: actionRow.model.type === 20
                            text: "Y"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontNormal
                        }
                        DarkSpinBox {
                            Layout.preferredWidth: 96
                            visible: actionRow.model.type === 20
                            from: 0
                            to: 16384
                            value: actionRow.model.posY
                            onValueModified: root.setField(actionRow.index, "posY", value)
                        }
                        DarkSwitch {
                            Layout.fillWidth: true
                            visible: actionRow.model.type === 20
                            text: "Absolute"
                            checked: actionRow.model.absolute
                            onToggled: root.setField(actionRow.index, "absolute", checked)
                        }

                        AccentButton {
                            implicitWidth: 30
                            leftPadding: 0
                            rightPadding: 0
                            text: "▲"
                            enabled: actionRow.index > 0
                            onClicked: root.moveAction(actionRow.index, actionRow.index - 1)
                        }
                        AccentButton {
                            implicitWidth: 30
                            leftPadding: 0
                            rightPadding: 0
                            text: "▼"
                            enabled: actionRow.index < draft.count - 1
                            onClicked: root.moveAction(actionRow.index, actionRow.index + 1)
                        }
                        AccentButton {
                            implicitWidth: 30
                            leftPadding: 0
                            rightPadding: 0
                            text: "✕"
                            onClicked: root.removeAction(actionRow.index)
                        }
                    }

                    // repeat, for text and mouse position
                    RowLayout {
                        anchors.top: mainRow.bottom
                        anchors.left: parent.left
                        anchors.leftMargin: 18 + 22 + 110 + 20
                        visible: root.repeats(actionRow.model.type)
                        spacing: 10
                        Text {
                            text: "Repeat"
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                        DarkSpinBox {
                            Layout.preferredWidth: 90
                            from: 0
                            to: 100
                            value: actionRow.model.repeat
                            onValueModified: root.setField(actionRow.index, "repeat", value)
                        }
                        Text {
                            text: "times,"
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                        DarkSpinBox {
                            Layout.preferredWidth: 110
                            from: 0
                            to: 10000
                            value: actionRow.model.repeatDelay
                            onValueModified: root.setField(actionRow.index, "repeatDelay", value)
                        }
                        Text {
                            text: "ms apart"
                            color: Theme.text
                            font.pixelSize: Theme.fontNormal
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    visible: root.current !== null && draft.count === 0
                    text: "No actions yet. Add them below."
                    color: Theme.textDim
                    font.pixelSize: Theme.fontNormal
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 18
                Layout.rightMargin: 18
                Layout.bottomMargin: 6
                visible: root.problem !== ""
                text: root.problem
                color: Theme.danger
                font.pixelSize: Theme.fontNormal
                wrapMode: Text.Wrap
            }

            // add an action at the end
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 52
                color: Theme.panel
                enabled: root.current !== null

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 14
                    spacing: 10

                    Text {
                        text: "Add"
                        color: Theme.text
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkComboBox {
                        Layout.preferredWidth: 150
                        model: root.library ? root.library.stepTypes : []
                        currentIndex: root.indexIn(model, root.newType)
                        onActivated: index => root.newType = model[index].value
                    }

                    DarkTextField {
                        id: keyFilter
                        Layout.preferredWidth: 120
                        visible: root.isKey(root.newType)
                        placeholderText: "Search key…"
                    }
                    DarkComboBox {
                        Layout.fillWidth: true
                        visible: root.isKey(root.newType)
                        model: root.shownKeys
                        currentIndex: root.indexIn(root.shownKeys, root.newCommand)
                        displayText: !root.keyOptions.length ? "Loading…" : currentIndex < 0 ? "Choose a key" : currentText
                        onActivated: index => root.newCommand = root.shownKeys[index].value
                    }

                    DarkSpinBox {
                        Layout.preferredWidth: 110
                        visible: root.newType === 5
                        from: 1
                        to: 65535
                        value: root.newDelay
                        onValueModified: root.newDelay = value
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: root.newType === 5
                        text: "ms"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontNormal
                    }

                    DarkTextField {
                        Layout.fillWidth: true
                        visible: root.newType === 6
                        placeholderText: "Text to type"
                        text: root.newText
                        onTextEdited: root.newText = text
                    }

                    Text {
                        visible: root.newType === 20
                        text: "X"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkSpinBox {
                        Layout.preferredWidth: 96
                        visible: root.newType === 20
                        from: 0
                        to: 16384
                        value: root.newX
                        onValueModified: root.newX = value
                    }
                    Text {
                        visible: root.newType === 20
                        text: "Y"
                        color: Theme.textDim
                        font.pixelSize: Theme.fontNormal
                    }
                    DarkSpinBox {
                        Layout.preferredWidth: 96
                        visible: root.newType === 20
                        from: 0
                        to: 16384
                        value: root.newY
                        onValueModified: root.newY = value
                    }
                    DarkSwitch {
                        Layout.fillWidth: true
                        visible: root.newType === 20
                        text: "Absolute"
                        checked: root.newAbsolute
                        onToggled: root.newAbsolute = checked
                    }

                    AccentButton {
                        accent: true
                        text: "Add action"
                        enabled: root.canAdd
                        onClicked: root.addAction()
                    }
                }
            }
        }
    }
}
