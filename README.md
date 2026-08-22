# Omarchy Mouse & Pointer Settings (`meviusisback.mouse-settings`)

A graphical mouse and pointer configuration tool for [Omarchy Linux](https://omarchy.org).

## ✨ Features

- **Top Bar Integration**: Clean mouse icon (`󰍽`) with rich tooltip status.
- **Left-Click Popup**: Opens the graphical settings panel.
- **Right-Click Fast Toggle**: Instantly toggles between Precision Mode (Flat 1:1) and Dynamic Acceleration on the fly with desktop notifications.
- **Pointer Motion & Speed**:
  - Intuitive slider (🐢 Slow ────●──── 🚀 Fast) with live multiplier.
  - Visual selector for **Precision (Raw 1:1)** vs **Dynamic (Adaptive)**.
  - Left-handed mode toggle (swaps primary and secondary buttons).
- **Scrolling & Behavior**:
  - Natural (Mobile-style) vs Traditional scrolling.
  - Scroll speed multiplier slider (up to 8.0x).
  - Focus follows cursor toggle.
  - Auto-refocus on window close toggle.
- **Mouse Button Mapping**:
  - Remap Side Button 1 (Back / 275), Side Button 2 (Forward / 276), and Middle Click (Wheel / 274).
  - Toggle window management gestures (Super + Left Drag, Super + Right Drag, Super + Wheel).
- **Interactive Testing Zone**: Live canvas to test clicks, double-clicks, and scroll wheel responsiveness immediately.
- **Live & Persistent**: Changes take effect immediately in Hyprland without restarts and safely persist to `~/.config/hypr/input.lua` and `~/.config/hypr/bindings.lua`.

## 📦 Installation

To install directly in Omarchy:

```bash
omarchy plugin add https://github.com/meviusisback/mouse-settings --enable
```

Or manually clone into `~/.config/omarchy/plugins/meviusisback.mouse-settings`.

## 🔒 Security & Architecture

This plugin follows strict security and reliability standards:
- **Atomic File Writes**: Configurations are written to temporary files and moved into place via atomic `os.replace` with `fsync`, eliminating partial-write corruption risks.
- **Race Condition Prevention**: Uses `fcntl.flock` file locking during read-modify-write operations to prevent concurrent conflicts.
- **Symlink Protection**: Refuses to follow symlinks when writing to configuration files.
- **Scoped Persistence**: Writes only inside clearly delimited marker blocks (`-- [[ OMARCHY_MOUSE_SETTINGS_START ]]` and `-- [[ OMARCHY_MOUSE_BINDINGS_START ]]`), leaving user configs and comments outside these blocks untouched.
- **Strict Input Sanitization**: All numeric, boolean, and enum parameters are validated, bounded, and sanitized before evaluation in Hyprland.

## 📜 License

MIT License
