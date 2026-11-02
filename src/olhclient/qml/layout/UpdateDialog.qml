import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Check for, download and install a new release (see core/updater.py).
Popup {
    id: root
    property var updater
    readonly property string step: updater ? updater.state : "idle"

    visible: updater !== null && updater.dialogOpen
    modal: true
    closePolicy: Popup.NoAutoClose
    width: 420
    padding: 20
    background: Rectangle {
        color: Theme.panel
        border.color: Theme.accent
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            text: root.step === "installed" ? "UPDATE INSTALLED"
                : root.step === "error" ? "UPDATE FAILED" : "UPDATES"
            color: root.step === "error" ? Theme.danger : Theme.accent
            font.pixelSize: Theme.fontHeader
        }
        Text {
            Layout.fillWidth: true
            text: {
                if (!root.updater)
                    return ""
                const u = root.updater
                switch (root.step) {
                case "checking": return "Checking for updates…"
                case "available":
                    return "Version " + u.latestVersion + " is available (you have " + u.currentVersion + ")."
                        + (u.canInstall ? "" : "\nDownload it from the release page.")
                case "downloading": return "Downloading version " + u.latestVersion + "…"
                case "installing": return "Installing version " + u.latestVersion + "…"
                case "installed": return "Restart the client to use version " + u.latestVersion + "."
                default: return u.message
                }
            }
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.fontNormal
        }

        // Download progress; full width and pulsing while installing.
        Rectangle {
            visible: root.step === "downloading" || root.step === "installing"
            Layout.fillWidth: true
            implicitHeight: 6
            color: Theme.field
            Rectangle {
                width: root.step === "installing" ? parent.width
                     : parent.width * (root.updater ? root.updater.progress : 0)
                height: parent.height
                color: Theme.accent
                SequentialAnimation on opacity {
                    running: root.step === "installing"
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 600 }
                    NumberAnimation { to: 1; duration: 600 }
                }
            }
        }
        Text {
            visible: root.step === "downloading"
            text: root.updater ? root.updater.progressText : ""
            color: Theme.textDim
            font.pixelSize: Theme.fontSmall
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8

            AccentButton {
                visible: root.step === "available" && root.updater !== null && !root.updater.canInstall
                         || root.step === "error" && root.updater !== null && root.updater.updateAvailable
                text: "Release page"
                onClicked: Qt.openUrlExternally(root.updater.releaseUrl)
            }
            AccentButton {
                visible: root.step !== "installing"
                text: root.step === "checking" || root.step === "downloading" ? "Cancel"
                    : root.step === "available" || root.step === "installed" ? "Later" : "Close"
                onClicked: root.updater.cancel()
            }
            AccentButton {
                visible: root.step === "available" && root.updater !== null && root.updater.canInstall
                accent: true
                text: "Update"
                onClicked: root.updater.install()
            }
            AccentButton {
                visible: root.step === "installed"
                accent: true
                text: "Restart now"
                onClicked: root.updater.restart()
            }
        }
    }
}
