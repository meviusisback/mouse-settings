// Helper functions for formatting labels, tooltip texts, and settings conversions.

function formatSpeed(sensitivity) {
  var s = Number(sensitivity) || 0
  if (Math.abs(s) < 0.05) return "Standard (1.0x)"
  if (s > 0) return "Fast (" + (1.0 + s).toFixed(2) + "x)"
  return "Slow (" + (1.0 + s).toFixed(2) + "x)"
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
