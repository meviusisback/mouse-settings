import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "meviusisback.mouse-settings"
  ipcTarget: "meviusisback.mouse-settings"
  manageIpc: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color accent: Color.accent

  property var status: ({
    devices: [],
    primaryDevice: "Standard Mouse",
    sensitivity: 0.0,
    accel_profile: "adaptive",
    is_flat: false,
    follow_mouse: 1,
    natural_scroll: false,
    left_handed: false,
    scroll_factor: 1.0,
    mouse_refocus: true
  })

  property string activeTab: "motion" // "motion" | "scrolling" | "shortcuts"
  property bool isSaving: false
  property string lastActionNote: ""

  function scriptPath() {
    return Qt.resolvedUrl("mouse_ctl.py").toString().replace(/^file:\/\//, "")
  }

  function fetchStatus() {
    if (!statusProc.running) statusProc.running = true
  }

  function applySettings(newValues) {
    var updated = {}
    for (var k in root.status) updated[k] = root.status[k]
    for (var n in newValues) updated[n] = newValues[n]
    root.status = updated
    root.isSaving = true
    applyProc.command = ["python3", root.scriptPath(), "apply", "--json-data", JSON.stringify(newValues)]
    applyProc.running = true
  }

  function toggleAccelMode() {
    toggleAccelProc.running = true
  }

  function toggleNaturalScroll() {
    toggleScrollProc.running = true
  }

  function resetDefaults() {
    resetProc.running = true
  }

  function openConfigEditor() {
    configEditorProc.running = true
  }

  // Periodic poll & initial query
  Timer {
    interval: 3000
    running: true
    repeat: true
    onTriggered: root.fetchStatus()
  }

  IpcHandler {
    enabled: true
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function toggleAccel(): void { root.toggleAccelMode() }
  }

  // Processes for background commands
  Process {
    id: statusProc
    running: true
    command: ["python3", root.scriptPath(), "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var output = text || ""
        try {
          var data = JSON.parse(output)
          root.status = data
        } catch (e) {
          // ignore transient parse error
        }
      }
    }
  }

  Process {
    id: applyProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.isSaving = false
        root.lastActionNote = "Saved"
        clearNoteTimer.restart()
      }
    }
  }

  Process {
    id: toggleAccelProc
    command: ["python3", root.scriptPath(), "toggle-accel"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.fetchStatus()
    }
  }

  Process {
    id: toggleScrollProc
    command: ["python3", root.scriptPath(), "toggle-natural-scroll"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.fetchStatus()
    }
  }

  Process {
    id: resetProc
    command: ["python3", root.scriptPath(), "reset-defaults"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.fetchStatus()
    }
  }

  Process {
    id: configEditorProc
    command: ["omarchy-launch-config-editor", Quickshell.env("HOME") + "/.config/hypr/input.lua"]
  }

  Timer {
    id: clearNoteTimer
    interval: 2000
    onTriggered: root.lastActionNote = ""
  }

  // Top Bar Icon Button
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍽"
    tooltipText: Model.getTooltipText(root.status)
    active: root.status && root.status.accel_profile === "flat"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) {
        root.toggleAccelMode()
      } else {
        root.toggle()
      }
    }
  }

  // Popup Settings Panel
  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.opened
    contentWidth: Style.space(350)
    contentHeight: Style.space(480)

    ColumnLayout {
      anchors.fill: parent
      spacing: Style.spacing.md

      // Header Row
      RowLayout {
        Layout.fillWidth: true
        spacing: Style.spacing.sm

        Text {
          text: "󰍽"
          color: root.accent
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
        }

        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2

          Text {
            text: "Mouse & Pointer"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            font.bold: true
          }

          Text {
            text: Model.formatDeviceName(root.status.primaryDevice)
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
            Layout.fillWidth: true
          }
        }

        // Open config file in text editor
        BorderSurface {
          implicitWidth: Style.space(30)
          implicitHeight: Style.space(30)
          radius: Style.cornerRadius
          color: editHover.hovered ? Style.normalFillFor(root.foreground, root.accent) : "transparent"
          borderSpec: Border.controlSpec("normal", root.foreground, root.accent)

          Text {
            anchors.centerIn: parent
            text: "󰒓"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          MouseArea {
            id: editHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.openConfigEditor()
          }
        }
      }

      // Tab Navigation (Motion, Scrolling, Shortcuts)
      BorderSurface {
        Layout.fillWidth: true
        implicitHeight: Style.space(36)
        radius: Style.cornerRadius
        color: Style.normalFillFor(root.foreground, root.accent)

        RowLayout {
          anchors.fill: parent
          spacing: 2

          // Tab 1: Motion
          BorderSurface {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Style.cornerRadius
            color: root.activeTab === "motion" ? Style.selectedFillFor(root.foreground, root.accent) : "transparent"

            RowLayout {
              anchors.centerIn: parent
              spacing: Style.spacing.xs

              Text {
                text: "󰍽"
                color: root.activeTab === "motion" ? Color.accent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }
              Text {
                text: "Motion"
                color: root.activeTab === "motion" ? root.foreground : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: root.activeTab === "motion"
              }
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.activeTab = "motion"
            }
          }

          // Tab 2: Scrolling
          BorderSurface {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Style.cornerRadius
            color: root.activeTab === "scrolling" ? Style.selectedFillFor(root.foreground, root.accent) : "transparent"

            RowLayout {
              anchors.centerIn: parent
              spacing: Style.spacing.xs

              Text {
                text: "󱕒"
                color: root.activeTab === "scrolling" ? Color.accent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }
              Text {
                text: "Scrolling"
                color: root.activeTab === "scrolling" ? root.foreground : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: root.activeTab === "scrolling"
              }
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.activeTab = "scrolling"
            }
          }

          // Tab 3: Shortcuts
          BorderSurface {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Style.cornerRadius
            color: root.activeTab === "shortcuts" ? Style.selectedFillFor(root.foreground, root.accent) : "transparent"

            RowLayout {
              anchors.centerIn: parent
              spacing: Style.spacing.xs

              Text {
                text: "󰒋"
                color: root.activeTab === "shortcuts" ? Color.accent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }
              Text {
                text: "Shortcuts"
                color: root.activeTab === "shortcuts" ? root.foreground : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: root.activeTab === "shortcuts"
              }
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.activeTab = "shortcuts"
            }
          }
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
      }

      // Tab Content Area
      Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        // TAB 1: MOTION & SPEED
        ColumnLayout {
          anchors.fill: parent
          visible: root.activeTab === "motion"
          spacing: Style.spacing.md

          // Cursor Speed Section
          ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.xs

            RowLayout {
              Layout.fillWidth: true
              Text {
                text: "Cursor Speed"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
              }
              Item { Layout.fillWidth: true }
              Text {
                text: Model.formatSpeed(root.status.sensitivity)
                color: Color.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.spacing.sm

              Text {
                text: "🐢"
                font.pixelSize: Style.font.body
              }

              PanelSlider {
                Layout.fillWidth: true
                bar: root.bar
                minimum: -1.0
                maximum: 1.0
                step: 0.05
                value: root.status.sensitivity
                onReleased: function(v) {
                  root.applySettings({ sensitivity: Math.round(v * 100) / 100 })
                }
              }

              Text {
                text: "🚀"
                font.pixelSize: Style.font.body
              }
            }
          }

          // Acceleration / Precision Style
          ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.xs

            Text {
              text: "Pointer Movement Style"
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.subtitle
              font.bold: true
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.spacing.sm

              // Card: Flat / Raw 1:1
              BorderSurface {
                Layout.fillWidth: true
                implicitHeight: Style.space(64)
                radius: Style.cornerRadius
                color: root.status.accel_profile === "flat" ? Style.selectedFillFor(root.foreground, root.accent) : Style.normalFillFor(root.foreground, root.accent)
                borderSpec: Border.controlSpec(root.status.accel_profile === "flat" ? "selected" : "normal", root.foreground, root.accent)

                ColumnLayout {
                  anchors.centerIn: parent
                  spacing: 2

                  RowLayout {
                    spacing: 4
                    Text { text: "󰓅"; color: root.status.accel_profile === "flat" ? Color.accent : root.foreground; font.family: root.fontFamily }
                    Text { text: "Precision (1:1)"; color: root.foreground; font.bold: true; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
                  }
                  Text { text: "Gaming & Design"; color: root.dim; font.pixelSize: Style.space(9); font.family: root.fontFamily }
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.applySettings({ accel_profile: "flat" })
                }
              }

              // Card: Adaptive
              BorderSurface {
                Layout.fillWidth: true
                implicitHeight: Style.space(64)
                radius: Style.cornerRadius
                color: root.status.accel_profile !== "flat" ? Style.selectedFillFor(root.foreground, root.accent) : Style.normalFillFor(root.foreground, root.accent)
                borderSpec: Border.controlSpec(root.status.accel_profile !== "flat" ? "selected" : "normal", root.foreground, root.accent)

                ColumnLayout {
                  anchors.centerIn: parent
                  spacing: 2

                  RowLayout {
                    spacing: 4
                    Text { text: "📈"; font.pixelSize: Style.font.caption }
                    Text { text: "Dynamic"; color: root.foreground; font.bold: true; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
                  }
                  Text { text: "Adaptive Speed"; color: root.dim; font.pixelSize: Style.space(9); font.family: root.fontFamily }
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.applySettings({ accel_profile: "adaptive" })
                }
              }
            }
          }

          // Left Handed Mode
          Toggle {
            Layout.fillWidth: true
            label: "Left-Handed Mode"
            description: "Swap primary and secondary mouse buttons"
            checked: root.status.left_handed
            onClicked: root.applySettings({ left_handed: !root.status.left_handed })
          }

          Item { Layout.fillHeight: true }
        }

        // TAB 2: SCROLLING & BEHAVIOR
        ColumnLayout {
          anchors.fill: parent
          visible: root.activeTab === "scrolling"
          spacing: Style.spacing.md

          // Natural Scrolling Toggle
          Toggle {
            Layout.fillWidth: true
            label: "Natural (Mobile) Scrolling"
            description: "Wheel down scrolls content down (touchpad/macOS style)"
            checked: root.status.natural_scroll
            onClicked: root.applySettings({ natural_scroll: !root.status.natural_scroll })
          }

          // Scroll Speed Slider
          ColumnLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.xs

            RowLayout {
              Layout.fillWidth: true
              Text {
                text: "Scroll Speed Multiplier"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
              }
              Item { Layout.fillWidth: true }
              Text {
                text: Model.formatScrollSpeed(root.status.scroll_factor)
                color: Color.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.spacing.sm

              Text { text: "🐌"; font.pixelSize: Style.font.body }

              PanelSlider {
                Layout.fillWidth: true
                bar: root.bar
                minimum: 0.2
                maximum: 3.0
                step: 0.1
                value: root.status.scroll_factor
                onReleased: function(v) {
                  root.applySettings({ scroll_factor: Math.round(v * 10) / 10 })
                }
              }

              Text { text: "⚡"; font.pixelSize: Style.font.body }
            }
          }

          // Focus Follows Mouse Toggle
          Toggle {
            Layout.fillWidth: true
            label: "Focus Follows Cursor"
            description: "Moving mouse over a window immediately activates it"
            checked: root.status.follow_mouse > 0
            onClicked: root.applySettings({ follow_mouse: root.status.follow_mouse > 0 ? 0 : 1 })
          }

          // Auto-refocus on close
          Toggle {
            Layout.fillWidth: true
            label: "Auto-Refocus on App Close"
            description: "Refocus window under cursor when an app closes"
            checked: root.status.mouse_refocus
            onClicked: root.applySettings({ mouse_refocus: !root.status.mouse_refocus })
          }

          Item { Layout.fillHeight: true }
        }

        // TAB 3: SHORTCUTS & INTERACTIVE TEST
        ColumnLayout {
          anchors.fill: parent
          visible: root.activeTab === "shortcuts"
          spacing: Style.spacing.sm

          Text {
            text: "Mouse Gestures & Shortcuts"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }

          // Visual Shortcuts List
          BorderSurface {
            Layout.fillWidth: true
            implicitHeight: Style.space(120)
            radius: Style.cornerRadius
            color: Style.normalFillFor(root.foreground, root.accent)
            padding: Style.spacing.sm

            ColumnLayout {
              anchors.fill: parent
              spacing: Style.spacing.xs

              RowLayout {
                spacing: Style.spacing.xs
                Text { text: "󰆿 Super + Left Drag:"; color: Color.accent; font.family: root.fontFamily; font.bold: true; font.pixelSize: Style.font.caption }
                Text { text: "Move window"; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
              }
              RowLayout {
                spacing: Style.spacing.xs
                Text { text: "󰆿 Super + Right Drag:"; color: Color.accent; font.family: root.fontFamily; font.bold: true; font.pixelSize: Style.font.caption }
                Text { text: "Resize window"; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
              }
              RowLayout {
                spacing: Style.spacing.xs
                Text { text: "󰆿 Super + Wheel:"; color: Color.accent; font.family: root.fontFamily; font.bold: true; font.pixelSize: Style.font.caption }
                Text { text: "Switch workspaces"; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
              }
              RowLayout {
                spacing: Style.spacing.xs
                Text { text: "󰆿 Side Buttons (4/5):"; color: Color.accent; font.family: root.fontFamily; font.bold: true; font.pixelSize: Style.font.caption }
                Text { text: "Back / Forward in apps"; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
              }
            }
          }

          // Interactive Testing Box
          BorderSurface {
            id: testBox
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Style.cornerRadius
            color: testArea.containsMouse ? Style.selectedFillFor(root.foreground, root.accent) : Style.normalFillFor(root.foreground, root.accent)
            borderSpec: Border.controlSpec(testArea.containsMouse ? "hover-cursor" : "normal", root.foreground, root.accent)

            property string testMsg: "Click or scroll here to test"
            property int clickCount: 0

            ColumnLayout {
              anchors.centerIn: parent
              spacing: 4

              Text {
                text: "󰛤 Interactive Testing Zone"
                color: Color.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
              }

              Text {
                text: testBox.testMsg
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                anchors.horizontalCenter: parent.horizontalCenter
              }
            }

            MouseArea {
              id: testArea
              anchors.fill: parent
              hoverEnabled: true
              acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
              cursorShape: Qt.PointingHandCursor

              onClicked: function(mouse) {
                testBox.clickCount += 1
                var bName = "Left Click"
                if (mouse.button === Qt.RightButton) bName = "Right Click"
                else if (mouse.button === Qt.MiddleButton) bName = "Middle Click"
                testBox.testMsg = bName + " detected! (#" + testBox.clickCount + ")"
              }

              onWheel: function(wheel) {
                var dir = wheel.angleDelta.y > 0 ? "Up" : "Down"
                testBox.testMsg = "Scrolled " + dir + " (Delta: " + wheel.angleDelta.y + ")"
              }
            }
          }
        }
      }

      PanelSeparator {
        Layout.fillWidth: true
      }

      // Footer Row: Reset & Live Status
      RowLayout {
        Layout.fillWidth: true
        spacing: Style.spacing.sm

        BorderSurface {
          implicitHeight: Style.space(28)
          implicitWidth: Style.space(120)
          radius: Style.cornerRadius
          color: resetHover.hovered ? Style.selectedFillFor(root.foreground, root.urgent) : "transparent"
          borderSpec: Border.controlSpec("normal", root.foreground, root.accent)

          RowLayout {
            anchors.centerIn: parent
            spacing: 4

            Text { text: "󰁯"; color: resetHover.hovered ? root.urgent : root.foreground; font.family: root.fontFamily }
            Text { text: "Reset Defaults"; color: resetHover.hovered ? root.urgent : root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
          }

          MouseArea {
            id: resetHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.resetDefaults()
          }
        }

        Item { Layout.fillWidth: true }

        Text {
          text: root.isSaving ? "Saving…" : (root.lastActionNote ? "✓ " + root.lastActionNote : "Live in Hyprland")
          color: root.isSaving ? Color.accent : root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}
