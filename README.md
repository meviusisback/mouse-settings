# Omarchy Mouse & Pointer Settings (`meviusisback.mouse-settings`)

A graphical mouse and pointer configuration tool for [Omarchy Linux](https://omarchy.org).

![Mouse & Pointer Plugin](preview.png)

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
  - Scroll speed multiplier slider.
  - Focus follows cursor toggle.
  - Auto-refocus on window close toggle.
- **Interactive Testing Zone**: Live canvas to test clicks, double-clicks, and scroll wheel responsiveness immediately.
- **Live & Persistent**: Changes take effect immediately in Hyprland without restarts and safely persist to `~/.config/hypr/input.lua`.

## 📦 Installation

To install directly in Omarchy:

```bash
omarchy plugin add https://github.com/meviusisback/mouse-settings --enable
```

Or manually clone into `~/.config/omarchy/plugins/meviusisback.mouse-settings`.

## 📜 License

MIT License
