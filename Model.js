// Helper functions for formatting labels, tooltip texts, and settings conversions.

function formatSpeed(sensitivity) {
  var s = numberOr(sensitivity, 0)
  if (Math.abs(s) < 0.05) return "Standard (1.0x)"
  if (s > 0) return "Fast (" + (1.0 + s).toFixed(2) + "x)"
  return "Slow (" + (1.0 + s).toFixed(2) + "x)"
}

// Coercion helpers: the panel merges every polled status payload onto its defaults so a
// missing or mistyped field can never reach a typed QML property as `undefined`.
// Number() accepts "" / [] / whitespace as 0, so only real numbers and non-empty numeric
// strings are accepted here — everything else falls back to the declared default.
function numberOr(value, fallback) {
  if (typeof value === "number") return isFinite(value) ? value : fallback
  if (typeof value === "string" && value.trim() !== "") {
    var n = Number(value)
    return isFinite(n) ? n : fallback
  }
  return fallback
}

function boolOr(value, fallback) {
  if (value === true || value === false) return value
  if (value === 1 || value === 0) return value === 1
  if (value === "true" || value === "1") return true
  if (value === "false" || value === "0") return false
  return fallback
}

// Own enumerable keys only. A `for (var k in obj)` loop also walks inherited enumerable
// keys, so if anything else in the shell has polluted Object.prototype the merge would start
// adopting keys the widget never declared — the exact door this allowlist exists to close.
function ownKeys(obj) {
  var keys = []
  for (var k in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, k)) keys.push(k)
  }
  return keys
}

// Copy a button_mappings payload onto the declared defaults, keeping only keys the widget
// knows and only non-empty string values. Always returns a fresh object.
function normalizeMappings(mappings, defaults) {
  var keys = ownKeys(defaults)
  var out = {}
  for (var i = 0; i < keys.length; i++) out[keys[i]] = defaults[keys[i]]
  if (!mappings || typeof mappings !== "object" || Array.isArray(mappings)) return out
  for (var j = 0; j < keys.length; j++) {
    var v = mappings[keys[j]]
    if (typeof v === "string" && v !== "") out[keys[j]] = v
  }
  return out
}

function formatScrollSpeed(factor) {
  var f = Number(factor) || 1.0
  if (Math.abs(f - 1.0) < 0.05) return "Normal (1.0x)"
  return f.toFixed(2) + "x"
}

function formatDeviceName(rawName) {
  if (!rawName) return "Standard Mouse"
  var name = String(rawName).replace(/-/g, " ").replace(/_/g, " ")
  return name.replace(/\b\w/g, function(l) { return l.toUpperCase() })
}

function sideBackOptions() {
  return [
    { value: "default", label: "Browser Bck (Default)" },
    { value: "prev_workspace", label: "Prev Workspace" },
    { value: "menu", label: "Omarchy Menu" },
    { value: "prev_window", label: "Focus Prev Window" }
  ]
}

function sideForwardOptions() {
  return [
    { value: "default", label: "Browser Fwd (Default)" },
    { value: "next_workspace", label: "Next Workspace" },
    { value: "terminal", label: "Launch Terminal" },
    { value: "next_window", label: "Focus Next Window" }
  ]
}

function middleClickOptions() {
  return [
    { value: "default", label: "Standard (Paste / Tab)" },
    { value: "close_window", label: "Close Active Window" },
    { value: "toggle_floating", label: "Toggle Floating" },
    { value: "toggle_fullscreen", label: "Toggle Fullscreen" }
  ]
}

function simulateButtons() {
  return [
    { value: "left", label: "L" },
    { value: "right", label: "R" },
    { value: "middle", label: "M" },
    { value: "side_back", label: "S1" },
    { value: "side_forward", label: "S2" }
  ]
}

function formatBattery(battery, withModel) {
  if (!battery || battery.percent === undefined || battery.percent === null) return ""
  var s = " · 🔋 " + Math.round(Number(battery.percent)) + "%"
  if (withModel && battery.model) s += " (" + battery.model + ")"
  return s
}

function getOptionLabel(options, val) {
  for (var i = 0; i < options.length; i++) {
    if (options[i].value === val) return options[i].label
  }
  return options[0] ? options[0].label : ""
}

function getTooltipText(status) {
  if (!status) return "Mouse Settings"
  var dev = formatDeviceName(status.primaryDevice || "Mouse")
  var mode = status.accel_profile === "flat" ? "Precision (1:1)" : "Dynamic"
  var spd = formatSpeed(status.sensitivity)
  return dev + " · " + mode + " · " + spd + formatBattery(status.battery, true)
}
