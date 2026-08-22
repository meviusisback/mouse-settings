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
  // Clean up common Linux device string artifacts
  var name = String(rawName).replace(/-/g, " ").replace(/_/g, " ")
  return name.replace(/\b\w/g, function(l) { return l.toUpperCase() })
}

function followMouseOptions() {
  return [
    { value: 1, title: "Cursor Hover Focus", desc: "Focus windows as the cursor moves over them (Omarchy default)" },
    { value: 2, title: "Hover & Click Focus", desc: "Focus follows cursor but click always raises the window" },
    { value: 0, title: "Click to Focus Only", desc: "You must click a window to focus it (Classic style)" },
    { value: 3, title: "Separate Keyboard Focus", desc: "Keyboard and mouse focus operate independently" }
  ]
}

function getFollowMouseTitle(val) {
  var opts = followMouseOptions()
  for (var i = 0; i < opts.length; i++) {
    if (opts[i].value === val) return opts[i].title
  }
  return "Cursor Hover Focus"
}

function getTooltipText(status) {
  if (!status) return "Mouse Settings"
  var dev = formatDeviceName(status.primaryDevice || "Mouse")
  var mode = status.accel_profile === "flat" ? "Precision (1:1)" : "Dynamic"
  var spd = formatSpeed(status.sensitivity)
  return dev + " · " + mode + " · " + spd
}
