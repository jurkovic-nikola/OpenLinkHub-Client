import QtQuick
import QtQuick.Layouts
import "../theme"
import "../components"

ColumnLayout {
    id: curve
    required property string title
    required property int maximum
    property var points: []
    property bool dirty: false
    signal saveRequested(var points)

    function load(values) {
        points = (values || []).map(p => ({x: p.x, y: p.y})).sort((a,b) => a.x - b.x)
        dirty = false
    }

    Text { text: curve.title + " (%)"; color: Theme.text; font.bold: true }
    Canvas {
        id: plot
        objectName: curve.title + " plot"
        Layout.fillWidth: true
        Layout.fillHeight: true
        readonly property real plotLeft: 40
        readonly property real plotTop: 12
        readonly property real w: Math.max(1, width - plotLeft - 18)
        readonly property real h: Math.max(1, height - plotTop - 46)
        function px(x) { return plotLeft + w * Math.min(x, curve.maximum) / curve.maximum }
        function py(y) { return plotTop + h * (1 - y / 100) }
        Connections {
            target: curve
            function onPointsChanged() { plot.requestPaint() }
            function onMaximumChanged() { plot.requestPaint() }
        }
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0,0,width,height)
            ctx.font = "11px sans-serif"
            ctx.fillStyle = "#bbbbbb"
            ctx.strokeStyle = "#474747"
            ctx.lineWidth = 1
            for (let y = 0; y <= 100; y += 10) {
                ctx.textAlign = "right"
                ctx.fillText(y + "%", plotLeft - 5, py(y) + 4)
                ctx.beginPath(); ctx.moveTo(plotLeft, py(y)); ctx.lineTo(plotLeft+w, py(y)); ctx.stroke()
            }
            const step = w < 380 && curve.maximum === 100 ? 20 : 10
            ctx.textAlign = "center"
            for (let x = 0; x <= curve.maximum; x += step) {
                ctx.fillText(x, px(x), plotTop+h+16)
                ctx.beginPath(); ctx.moveTo(px(x), plotTop); ctx.lineTo(px(x), plotTop+h); ctx.stroke()
            }
            ctx.fillText("Temperature (°C)", plotLeft+w/2, height-5)
            ctx.strokeStyle = "#42a5f5"
            ctx.fillStyle = "#42a5f5"
            ctx.lineWidth = 2
            ctx.beginPath()
            curve.points.forEach((p,i) => {
                if (i === 0) ctx.moveTo(px(p.x), py(p.y))
                else ctx.lineTo(px(p.x), py(p.y))
            })
            ctx.stroke()
            for (const p of curve.points) {
                ctx.beginPath(); ctx.arc(px(p.x), py(p.y), 4, 0, Math.PI*2); ctx.fill()
            }
        }
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            property var dragging: null
            function movePoint(x,y) {
                dragging.x = Math.round(Math.max(0,Math.min(1,(x-plot.plotLeft)/plot.w))*curve.maximum)
                dragging.y = Math.round(Math.max(0,Math.min(1,1-(y-plot.plotTop)/plot.h))*100)
                curve.points = curve.points.slice().sort((a,b) => a.x-b.x)
                curve.dirty = true
            }
            onPressed: mouse => {
                const near = curve.points.find(p => Math.hypot(plot.px(p.x)-mouse.x, plot.py(p.y)-mouse.y) <= 9)
                if (mouse.button === Qt.RightButton) {
                    if (near && curve.points.length > 2) {
                        curve.points = curve.points.filter(p => p !== near)
                        curve.dirty = true
                    }
                } else if (near) {
                    dragging = near
                } else if (mouse.x >= plot.plotLeft && mouse.x <= plot.plotLeft+plot.w &&
                           mouse.y >= plot.plotTop && mouse.y <= plot.plotTop+plot.h) {
                    dragging = {}
                    curve.points = curve.points.concat([dragging])
                    movePoint(mouse.x, mouse.y)
                }
            }
            onPositionChanged: mouse => { if (pressed && dragging) movePoint(mouse.x, mouse.y) }
            onReleased: dragging = null
            onCanceled: dragging = null
        }
    }
    AccentButton {
        objectName: curve.title + " save"
        text: "Save " + curve.title.toLowerCase()
        accent: curve.dirty
        enabled: curve.dirty && curve.points.length >= 2
        onClicked: curve.saveRequested(curve.points)
    }
}
