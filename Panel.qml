import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "ess.pi-usage"
  ipcTarget: "ess.pi-usage"
  manageIpc: false

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color surface: Color.popups.background
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function todayDate() {
    var now = new Date()
    return now.getFullYear() + "-"
      + String(now.getMonth() + 1).padStart(2, "0") + "-"
      + String(now.getDate()).padStart(2, "0")
  }

  function dayName(date) {
    var parsed = new Date(String(date || "") + "T00:00:00")
    if (isNaN(parsed.getTime())) return String(date || "")
    return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][parsed.getDay()]
  }

  readonly property var models: backend.modelRows()
  readonly property real weekPeak: backend.weekPeak()

  PiBackend {
    id: backend
    settings: root.settings
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { backend.refresh(true); return "ok" }
  }

  // Bar chip: Pi Agent logo with green/red/neutral status colors.
  readonly property color okGreen: "#9ece6a"

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) {
    backend.refresh(false)
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "π"
    active: backend.outOfTokens
    foreground: backend.hasTokens ? root.okGreen : (bar ? bar.foreground : Color.foreground)
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) backend.refresh(true)
      else root.toggle()
    }

    // Status dot: green = healthy, red = over budget / exhausted, grey = idle
    Rectangle {
      id: statusDot
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(6)
      height: Style.space(6)
      radius: width / 2
      color: backend.hasTokens ? root.okGreen : (backend.ready && backend.outOfTokens ? root.urgent : root.foreground)
      opacity: backend.ready ? 1 : 0.4
    }

    // Timeline meter under chip
    // like the OpenCode widget. Full green = funded, drains to red.
    Rectangle {
      id: chipTrack
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.leftMargin: 7
      anchors.rightMargin: 7
      anchors.bottomMargin: 5
      height: 3
      radius: 1.5
      color: root.track
      visible: backend.balance.available === true

      Rectangle {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        height: parent.height
        radius: parent.radius
        width: parent.width * backend.balanceFraction
        color: backend.outOfTokens ? root.urgent : root.okGreen
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) { if (t === "r" || t === "R") backend.refresh(true) }

      Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height

        Column {
          id: column
          width: parent.width
          spacing: Style.space(12)

          PanelHero {
            width: parent.width
            title: "Pi"
            meta: heroMeta()
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          // ---------- Token budget: used vs. available ----------
          Column {
            visible: backend.balance.available === true
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader {
              width: parent.width
              text: "BUDGET"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Item {
              width: parent.width
              implicitHeight: Math.max(balanceLabel.implicitHeight, balanceValue.implicitHeight)

              Text {
                id: balanceLabel
                text: budgetLabel()
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
                anchors.left: parent.left
                anchors.right: balanceValue.left
                anchors.rightMargin: Style.spacing.sm
                anchors.verticalCenter: parent.verticalCenter
              }

              Text {
                id: balanceValue
                textFormat: Text.PlainText
                text: backend.balanceText
                color: backend.outOfTokens ? root.urgent : root.okGreen
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
              }
            }

            Text {
              width: parent.width
              text: budgetDetail()
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            // Budget timeline meter, like the OpenCode widget: drains as
            // tokens are spent. Free-tier model = full meter, always.
            Rectangle {
              visible: budgetMeterVisible()
              width: parent.width
              height: 6
              radius: 3
              color: root.track

              Rectangle {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height
                radius: parent.radius
                width: parent.width * backend.balanceFraction
                color: backend.outOfTokens ? root.urgent : root.okGreen
              }
            }

            Text {
              visible: !budgetMeterVisible()
              width: parent.width
              text: "No token budget found — top up OpenRouter to fill the meter"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }

          Text {
            visible: backend.balance.available !== true
            width: parent.width
            text: balanceHelp()
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          // ---------- Totals: today / 7d / all-time ----------
          PanelSeparator { foreground: root.foreground }

          Column {
            width: parent.width
            spacing: Style.space(8)

            PanelSectionHeader {
              width: parent.width
              text: "TOKENS"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Row {
              width: parent.width
              spacing: Style.spacing.md
              Repeater {
                model: [
                  { label: "Today", value: backend.todayTotalTokens },
                  { label: "7 days", value: weekTotal() },
                  { label: "All-time", value: allTimeTotal() }
                ]
                Item {
                  required property var modelData
                  width: (parent.width - Style.spacing.md * 2) / 3
                  implicitHeight: totalLabel.implicitHeight + totalValue.implicitHeight + 4
                  Text {
                    id: totalLabel
                    anchors.top: parent.top
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData.label
                    color: root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }
                  Text {
                    id: totalValue
                    anchors.top: totalLabel.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: backend.formatTokenCount(modelData.value)
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }
                }
              }
            }

            Text {
              width: parent.width
              text: backend.totalPrompts + " prompts · " + backend.totalSessions + " sessions · " + backend.activeDays + " days"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              horizontalAlignment: Text.AlignHCenter
            }
            Text {
              visible: !backend.ready
              width: parent.width
              text: "Run Pi once — sessions land in ~/.pi/agent/sessions/*.jsonl"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.WordWrap
            }
          }

          // ---------- By day ----------
          PanelSeparator { visible: backend.recentDays.length > 0; foreground: root.foreground }

          PanelSectionHeader {
            visible: backend.recentDays.length > 0
            width: parent.width
            text: "TOKENS BY DAY"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Column {
            visible: backend.recentDays.length > 0
            width: parent.width
            spacing: Style.spacing.sm

            // Straight ruler line at top
            Rectangle {
              width: parent.width
              height: Style.space(2)
              color: root.track
              radius: 1
            }

            // Sparkline chart (OpenCode style)
            Canvas {
              id: spark
              visible: backend.recentDays.length > 0
              width: parent.width
              height: Style.space(72)
              antialiasing: true
              property var values: backend.recentDays.map(function(day) { return Number(day.messageCount || 0) })
              property int peak: Math.max(1, Math.max.apply(null, (backend.recentDays || []).map(function(d) { return Number(d.messageCount || 0) })))
              onValuesChanged: requestPaint()
              onPeakChanged: requestPaint()
              onWidthChanged: requestPaint()
              onHeightChanged: requestPaint()
              onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                var vals = values || []
                var n = vals.length
                if (n === 0) return
                var top = Math.max(1, spark.peak)
                var pad = Style.space(8)
                var base = height - Style.space(4)
                function px(i) { return n === 1 ? width / 2 : pad + i * (width - 2 * pad) / (n - 1) }
                function py(v) { return base - Style.space(4) - (v / top) * (base - 2 * pad) }
                ctx.beginPath()
                ctx.moveTo(px(0), py(vals[0]))
                for (var i = 1; i < n; i++) {
                  var mx = (px(i - 1) + px(i)) / 2
                  var my = (py(vals[i - 1]) + py(vals[i])) / 2
                  ctx.quadraticCurveTo(px(i - 1), py(vals[i - 1]), mx, my)
                }
                ctx.lineTo(px(n - 1), py(vals[n - 1]))
                var fill = ctx.createLinearGradient(0, 0, 0, base)
                var fc = root.foreground
                fill.addColorStop(0, Qt.rgba(fc.r, fc.g, fc.b, 0.30))
                fill.addColorStop(1, Qt.rgba(fc.r, fc.g, fc.b, 0.0))
                ctx.save()
                ctx.lineTo(px(n - 1), base)
                ctx.lineTo(px(0), base)
                ctx.closePath()
                ctx.fillStyle = fill
                ctx.fill()
                ctx.restore()
                ctx.beginPath()
                ctx.moveTo(px(0), py(vals[0]))
                for (var j = 1; j < n; j++) {
                  var nx = (px(j - 1) + px(j)) / 2
                  var ny = (py(vals[j - 1]) + py(vals[j])) / 2
                  ctx.quadraticCurveTo(px(j - 1), py(vals[j - 1]), nx, ny)
                }
                ctx.lineTo(px(n - 1), py(vals[n - 1]))
                ctx.lineWidth = 2
                ctx.strokeStyle = Qt.rgba(fc.r, fc.g, fc.b, 1)
                ctx.stroke()
                var peakIdx = 0
                for (var k = 1; k < n; k++) if (vals[k] > vals[peakIdx]) peakIdx = k
                for (var m = 0; m < n; m++) {
                  ctx.beginPath()
                  if (m === peakIdx && spark.peak > 0) {
                    ctx.arc(px(m), py(vals[m]), 4, 0, 2 * Math.PI)
                    ctx.fillStyle = Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 1)
                  } else {
                    ctx.arc(px(m), py(vals[m]), 2.5, 0, 2 * Math.PI)
                    ctx.fillStyle = Qt.rgba(fc.r, fc.g, fc.b, 0.85)
                  }
                  ctx.fill()
                }
              }
            }

            // Meter bar (OpenCode style)
            Rectangle {
              visible: backend.recentDays.length > 0
              width: parent.width
              height: Style.space(6)
              radius: height / 2
              color: root.track
            }

            Row {
              visible: backend.recentDays.length > 0
              width: parent.width
              spacing: Style.spacing.md
              Repeater {
                model: backend.recentDays
                delegate: Column {
                  required property var modelData
                  required property int index
                  property bool isToday: String(modelData.date || "") === root.todayDate()
                  width: (parent.width - Style.spacing.md * (backend.recentDays.length - 1)) / backend.recentDays.length
                  spacing: Style.space(2)
                  Text {
                    width: parent.width
                    text: isToday ? "Today" : root.dayName(modelData.date)
                    color: isToday ? root.foreground : root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: isToday
                    horizontalAlignment: Text.AlignHCenter
                  }
                  Text {
                    width: parent.width
                    text: backend.formatTokenCount(Number(modelData.messageCount || 0))
                    color: root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    horizontalAlignment: Text.AlignHCenter
                  }
                }
              }
            }
          }

          // ---------- By model ----------
          PanelSeparator { visible: root.models.length > 0; foreground: root.foreground }

          Column {
            visible: root.models.length > 0
            width: parent.width
            spacing: Style.spacing.md

            PanelSectionHeader {
              width: parent.width
              text: "TOKENS BY MODEL"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            Repeater {
              model: root.models
              Item {
                required property var modelData
                property real share: modelData.total / Math.max(1, root.models.length > 0 ? root.models[0].total : 1)

                width: parent.width
                implicitHeight: modelName.implicitHeight + Style.spacing.lg

                Rectangle {
                  anchors.fill: parent
                  radius: Style.cornerRadius
                  color: root.alpha(root.foreground, 0.05)
                }
                Rectangle {
                  anchors.left: parent.left
                  anchors.top: parent.top
                  anchors.bottom: parent.bottom
                  width: parent.width * root.clamp(share, 0, 1)
                  radius: Style.cornerRadius
                  color: root.alpha(root.foreground, 0.14)
                }
                Text {
                  id: modelName
                  text: (modelData.active ? "● " : "") + modelData.name
                  color: modelData.active ? root.okGreen : root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: modelData.active === true
                  elide: Text.ElideRight
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(8)
                  anchors.right: modelTokens.left
                  anchors.rightMargin: Style.space(8)
                  anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                  id: modelTokens
                  text: backend.formatTokenCount(modelData.total)
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(8)
                  anchors.verticalCenter: parent.verticalCenter
                }
                MouseArea {
                  anchors.fill: parent
                  onClicked: modelData.expanded = !modelData.expanded
                }
              }
            }

            Text {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: "R refresh · right-click refresh · click model to expand"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }

            Text {
              width: parent.width
              text: cacheLegend()
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }
        }
      }
    }
  }

  function heroMeta() {
    var active = ""
    if (backend.activeModel !== "")
      active = backend.friendlyModelName(backend.activeModel) + " em uso"
    if (backend.balance.available === true)
      return (active !== "" ? active + " · " : "") + backend.balanceText
    if (backend.ready) return active !== "" ? active : "Local transcripts"
    return "No sessions yet"
  }

  function budgetLabel() {
    var model = String(backend.balance.model || "")
    if (model !== "") return backend.friendlyModelName(model)
    return "Token budget"
  }

  function budgetDetail() {
    var b = backend.balance
    if (backend.freeUnlimited)
      return "Free-tier model · unlimited tokens · "
        + backend.formatTokenCount(backend.todayTotalTokens) + " used today"
    if (String(b.tokenMode || "") === "converted")
      return backend.formatTokenCount(Number(b.usedTokens || 0)) + " used of "
        + backend.formatTokenCount(Number(b.budgetTokens || 0))
        + " · ~$" + Number(b.pricePer1M || 0).toFixed(2) + "/1M tokens"
    return "$" + Number(b.used || 0).toFixed(2)
      + " used of $" + Number(b.total || 0).toFixed(2)
  }

  function budgetMeterVisible() {
    if (backend.freeUnlimited) return true
    if (String(backend.balance.tokenMode || "") === "converted")
      return Number(backend.balance.budgetTokens || 0) > 0
    return Number(backend.balance.total || 0) > 0
  }

  function balanceHelp() {
    var err = backend.balance.error || ""
    if (err === "no-key") return "No OpenRouter key found in ~/.pi/agent/auth.json — chip stays neutral"
    if (err !== "") return "Balance check failed (" + err + ") — using last known state"
    return ""
  }

  function weekTotal() {
    var total = 0
    for (var i = 0; i < backend.recentDays.length; i++)
      total += Number(backend.recentDays[i].messageCount || 0)
    return total
  }

  function allTimeTotal() {
    var total = 0
    var rows = root.models
    for (var i = 0; i < rows.length; i++) total += Number(rows[i].total || 0)
    return total
  }

  function cacheLegend() {
    if (root.models.length === 0) return ""
    var top = root.models[0]
    return "Top: " + top.name + " — in " + backend.formatTokenCount(top.input)
      + " · out " + backend.formatTokenCount(top.output)
      + " · cache read " + backend.formatTokenCount(top.cacheRead)
      + " · cache write " + backend.formatTokenCount(top.cacheWrite)
  }
}
