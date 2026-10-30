import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme"
import "components"
import "layout"

ApplicationWindow {
    id: window
    required property var backend
    property string defaultUsername: ""

    readonly property var session: backend.session
    property string featureId: ""
    readonly property var feature: {
        if (!session)
            return null
        for (const f of session.features)
            if (f.id === featureId)
                return f
        return session.features.length ? session.features[0] : null
    }

    // Feature panels are (re)created together with their controller so a panel
    // never sees the controller of another feature.
    function loadFeature() {
        if (!session || !feature) {
            listLoader.source = ""
            editorLoader.source = ""
            return
        }
        const props = { session: session, controller: session.controller(feature.id) }
        listLoader.setSource(feature.listQml, props)
        editorLoader.setSource(feature.editorQml, props)
    }
    onFeatureChanged: loadFeature()

    width: 1320
    height: 840
    minimumWidth: 1120
    minimumHeight: 700
    visible: true
    title: session ? session.product + " — OpenLinkHub" : "OpenLinkHub"
    color: Theme.window

    header: TopBar { backend: window.backend }
    footer: StatusBar { backend: window.backend }

    Connections {
        target: window.backend
        function onNotify(text, isError) { toast.show(text, isError) }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap
        spacing: Theme.gap
        enabled: window.session !== null

        // -- left column ---------------------------------------------------
        ColumnLayout {
            Layout.preferredWidth: 310
            Layout.maximumWidth: 310
            Layout.fillHeight: true
            spacing: Theme.gap

            ProfilesPanel {
                Layout.fillWidth: true
                session: window.session
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: window.feature ? window.feature.title : "Actions"
                icon: window.feature ? Qt.resolvedUrl("icons/" + window.feature.id + ".svg") : ""
                highlighted: true

                Loader {
                    id: listLoader
                    anchors.fill: parent
                }
            }

            LibraryPanel {
                Layout.fillWidth: true
                features: window.session ? window.session.features : []
                currentId: window.feature ? window.feature.id : ""
                onActivated: id => window.featureId = id
            }
        }

        // -- right column --------------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            DevicesStrip {
                Layout.fillWidth: true
                backend: window.backend
            }

            DeviceView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 300
                Layout.preferredHeight: 420
                session: window.session
                onButtonActivated: window.featureId = "key_remap"
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 280
                Layout.preferredHeight: 330
                color: Theme.panelAlt

                Loader {
                    id: editorLoader
                    anchors.fill: parent
                }
            }
        }
    }

    // -- empty / error states ------------------------------------------------
    Rectangle {
        anchors.fill: parent
        visible: window.session === null && !window.backend.authRequired
        color: Qt.rgba(0.08, 0.08, 0.08, 0.92)
        Column {
            anchors.centerIn: parent
            spacing: 10
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: !window.backend.connected ? "Cannot reach OpenLinkHub"
                    : window.backend.devices.count === 0 ? "No supported mouse found" : "Loading device…"
                color: Theme.text
                font.pixelSize: Theme.fontHeader + 3
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: window.backend.connected ? "Connect a mouse; the list refreshes automatically."
                    : window.backend.status + "\nRetrying every few seconds."
                horizontalAlignment: Text.AlignHCenter
                color: Theme.textDim
                font.pixelSize: Theme.fontNormal
            }
        }
    }

    LoginDialog {
        anchors.centerIn: parent
        visible: window.backend.authRequired
        username: window.defaultUsername
        onLogin: (user, password) => window.backend.login(user, password)
    }

    Toast {
        id: toast
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 18
    }
}
