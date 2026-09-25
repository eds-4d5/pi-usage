import QtQuick
import Quickshell
import Quickshell.Io

// Runs scripts/pi-usage.py and exposes the parsed record.
// Keeps the last good result if the backend emits malformed JSON.
Item {
  id: root
  visible: false

  property var settings: ({})
  property var record: ({})
  property int dataRevision: 0
  property string errorText: ""
  property bool pendingRefresh: false

  readonly property string scriptPath: Qt.resolvedUrl("scripts/pi-usage.py").toString().replace("file://", "")
  readonly property int refreshIntervalSec: Math.max(30, Number(settings && settings.refreshIntervalSec !== undefined ? settings.refreshIntervalSec : 300))

  readonly property int todayTotalTokens: Number(record.todayTotalTokens || 0)
  readonly property int totalPrompts: Number(record.totalPrompts || 0)
  readonly property int totalSessions: Number(record.totalSessions || 0)
  readonly property int activeDays: Number(record.activeDays || 0)
  readonly property var recentDays: Array.isArray(record.recentDays) ? record.recentDays : []
  readonly property var modelUsage: (record.modelUsage && typeof record.modelUsage === "object") ? record.modelUsage : {}
  readonly property bool ready: record.ready === true
  readonly property var balance: (record.balance && typeof record.balance === "object") ? record.balance : ({available: false})
  readonly property string tokenMode: String(balance.tokenMode || "")
  readonly property bool freeUnlimited: balance.available === true && tokenMode === "free-unlimited"
  // Green chip: tokens available to use. Red chip: exhausted.
  // Unknown (no key / offline / unpriced model): neutral bar color.
  readonly property bool hasTokens: {
    if (balance.available !== true) return false
    if (freeUnlimited) return true
    if (tokenMode === "converted") return Number(balance.remainingTokens) > 0
    return Number(balance.remaining) > 0
  }
  readonly property bool outOfTokens: {
    if (balance.available !== true) return false
    if (freeUnlimited) return false
    if (tokenMode === "converted")
      return Number(balance.budgetTokens) > 0 && Number(balance.remainingTokens) <= 0
    return Number(balance.remaining) <= 0
  }
  readonly property string balanceText: {
    if (balance.available !== true) return ""
    if (freeUnlimited) return "∞ free"
    if (tokenMode === "converted") return formatTokenCount(Number(balance.remainingTokens)) + " left"
    return "$" + Number(balance.remaining).toFixed(2) + " left"
  }
  // 1.0 = full budget, 0.0 = exhausted (or unknown ceiling).
  readonly property real balanceFraction: {
    if (balance.available !== true) return 0
    if (freeUnlimited) return 1
    var t, r
    if (tokenMode === "converted") {
      t = Number(balance.budgetTokens || 0)
      r = Number(balance.remainingTokens || 0)
    } else {
      t = Number(balance.total || 0)
      r = Number(balance.remaining || 0)
    }
    if (!(t > 0)) return 0
    var f = r / t
    if (!isFinite(f)) return 0
    return Math.max(0, Math.min(1, f))
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh(false)
  }

  Process {
    id: proc
    running: false
    command: ["python3", root.scriptPath]

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyOutput(text)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.trim() !== "") console.warn("pi-usage", text.trim().slice(0, 500))
    }
    onExited: {
      if (root.pendingRefresh) {
        root.pendingRefresh = false
        root.refresh(false)
      }
    }
  }

  function refresh(force) {
    if (proc.running) {
      pendingRefresh = true
      return
    }
    proc.running = true
  }

  function applyOutput(text) {
    try {
      var parsed = JSON.parse(text)
      if (parsed && parsed.id === "pi") {
        record = parsed
        errorText = ""
        dataRevision++
      } else {
        errorText = "Unexpected backend output"
      }
    } catch (e) {
      console.warn("pi-usage", "Ignoring malformed backend output:", String(e).slice(0, 200))
      errorText = "Backend parse error"
    }
  }

  function formatTokenCount(n) {
    if (n === undefined || n === null) return "0"
    n = Number(n)
    if (!isFinite(n)) return "0"
    if (n >= 1e9) return (n / 1e9).toFixed(1) + "B"
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M"
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K"
    return String(Math.round(n))
  }

  function friendlyModelName(id) {
    if (!id) return "Unknown"
    var name = String(id).replace(/^pi-/, "")
    var parts = name.split("-")
    var words = []
    var version = []
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i]
      if (part === "") continue
      if (/^\d/.test(part)) { version.push(part); continue }
      if (version.length > 0) { words.push(version.join(".")); version = [] }
      words.push(part.charAt(0).toUpperCase() + part.slice(1))
    }
    if (version.length > 0) words.push(version.join("."))
    return words.length > 0 ? words.join(" ") : "Unknown"
  }

  readonly property string activeModel: String(record.activeModel || "")

  function modelRows() {
    var rows = []
    for (var id in modelUsage) {
      var b = modelUsage[id] || {}
      var input = Number(b.inputTokens || 0)
      var output = Number(b.outputTokens || 0)
      var cacheRead = Number(b.cacheReadInputTokens || 0)
      var cacheWrite = Number(b.cacheCreationInputTokens || 0)
      rows.push({
        id: id,
        name: friendlyModelName(id),
        total: input + output + cacheRead + cacheWrite,
        input: input, output: output,
        cacheRead: cacheRead, cacheWrite: cacheWrite,
        active: id === root.activeModel
      })
    }
    rows.sort(function(a, b) { return b.total - a.total })
    return rows
  }

  function weekPeak() {
    var peak = 0
    for (var i = 0; i < recentDays.length; i++)
      peak = Math.max(peak, Number(recentDays[i].messageCount || 0))
    return Math.max(1, peak)
  }
}
