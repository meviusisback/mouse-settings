#!/usr/bin/env python3
"""
Omarchy Mouse Settings Backend Controller (mouse_ctl.py)
Manages live Hyprland mouse/pointer options, button bindings, and persistent storage in:
- ~/.config/hypr/input.lua (Sensitivity, acceleration, scroll, focus)
- ~/.config/hypr/bindings.lua (Mouse button remaps and shortcuts)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

INPUT_LUA_PATH = Path.home() / ".config" / "hypr" / "input.lua"
BINDINGS_LUA_PATH = Path.home() / ".config" / "hypr" / "bindings.lua"

START_MARKER = "-- [[ OMARCHY_MOUSE_SETTINGS_START ]]"
END_MARKER = "-- [[ OMARCHY_MOUSE_SETTINGS_END ]]"

BINDINGS_START_MARKER = "-- [[ OMARCHY_MOUSE_BINDINGS_START ]]"
BINDINGS_END_MARKER = "-- [[ OMARCHY_MOUSE_BINDINGS_END ]]"

DEFAULT_BUTTON_MAPPINGS = {
    "side_back": "default",         # default (browser back), prev_workspace, menu, prev_window
    "side_forward": "default",      # default (browser forward), next_workspace, terminal, next_window
    "middle_click": "default",      # default (paste/tab), close_window, toggle_floating, toggle_fullscreen
    "super_left": "move_window",    # move_window, disabled
    "super_right": "resize_window", # resize_window, disabled
    "super_wheel": "workspace_scroll" # workspace_scroll, disabled
}

def run_cmd(cmd):
    """Run a shell command and return stdout string."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

def get_hypr_option(opt_name):
    """Query a single Hyprland option via hyprctl getoption -j."""
    code, out, _ = run_cmd(["hyprctl", "getoption", opt_name, "-j"])
    if code != 0 or not out:
        return None
    try:
        data = json.loads(out)
        if "float" in data:
            return data["float"]
        if "int" in data:
            return data["int"]
        if "bool" in data:
            return data["bool"]
        if "str" in data:
            val = data["str"]
            if val == "[[EMPTY]]":
                return ""
            return val
        return None
    except Exception:
        return None

def get_devices():
    """Retrieve connected mouse / pointer devices from hyprctl devices -j."""
    code, out, _ = run_cmd(["hyprctl", "devices", "-j"])
    if code != 0 or not out:
        return []
    try:
        data = json.loads(out)
        mice = data.get("mice", [])
        clean_mice = []
        for m in mice:
            name = m.get("name", "Unknown Mouse")
            clean_mice.append({
                "name": name,
                "address": m.get("address", ""),
                "defaultSpeed": m.get("defaultSpeed", 0.0),
                "scrollFactor": m.get("scrollFactor", 1.0)
            })
        return clean_mice
    except Exception:
        return []

def read_saved_button_mappings():
    """Read saved button mappings from ~/.config/hypr/bindings.lua."""
    mappings = dict(DEFAULT_BUTTON_MAPPINGS)
    if not BINDINGS_LUA_PATH.exists():
        return mappings

    try:
        content = BINDINGS_LUA_PATH.read_text(encoding="utf-8")
        if BINDINGS_START_MARKER in content and BINDINGS_END_MARKER in content:
            block = content.split(BINDINGS_START_MARKER)[1].split(BINDINGS_END_MARKER)[0]
            # Match metadata comments or bindings
            if 'o.bind("mouse:275", "Previous workspace"' in block:
                mappings["side_back"] = "prev_workspace"
            elif 'o.bind("mouse:275", "Omarchy menu"' in block:
                mappings["side_back"] = "menu"
            elif 'o.bind("mouse:275", "Previous window"' in block:
                mappings["side_back"] = "prev_window"

            if 'o.bind("mouse:276", "Next workspace"' in block:
                mappings["side_forward"] = "next_workspace"
            elif 'o.bind("mouse:276", "Terminal"' in block:
                mappings["side_forward"] = "terminal"
            elif 'o.bind("mouse:276", "Next window"' in block:
                mappings["side_forward"] = "next_window"

            if 'o.bind("mouse:274", "Close active window"' in block:
                mappings["middle_click"] = "close_window"
            elif 'o.bind("mouse:274", "Toggle floating"' in block:
                mappings["middle_click"] = "toggle_floating"
            elif 'o.bind("mouse:274", "Toggle fullscreen"' in block:
                mappings["middle_click"] = "toggle_fullscreen"

            if 'hl.unbind("SUPER + mouse:272")' in block:
                mappings["super_left"] = "disabled"
            if 'hl.unbind("SUPER + mouse:273")' in block:
                mappings["super_right"] = "disabled"
            if 'hl.unbind("SUPER + mouse_down")' in block:
                mappings["super_wheel"] = "disabled"
    except Exception:
        pass

    return mappings

def get_current_status():
    """Get full state of mouse configuration and button mappings."""
    sensitivity = get_hypr_option("input:sensitivity")
    if sensitivity is None:
        sensitivity = 0.0

    accel_profile = get_hypr_option("input:accel_profile")
    if not accel_profile or accel_profile == "[[EMPTY]]":
        accel_profile = "adaptive"

    follow_mouse = get_hypr_option("input:follow_mouse")
    if follow_mouse is None:
        follow_mouse = 1

    natural_scroll = get_hypr_option("input:natural_scroll")
    if natural_scroll is None:
        natural_scroll = False

    left_handed = get_hypr_option("input:left_handed")
    if left_handed is None:
        left_handed = False

    scroll_factor = get_hypr_option("input:scroll_factor")
    if scroll_factor is None or scroll_factor <= 0:
        scroll_factor = 1.0

    mouse_refocus = get_hypr_option("input:mouse_refocus")
    if mouse_refocus is None:
        mouse_refocus = True

    devices = get_devices()
    button_mappings = read_saved_button_mappings()

    return {
        "devices": devices,
        "primaryDevice": devices[0]["name"] if devices else "Standard Mouse",
        "sensitivity": round(float(sensitivity), 2),
        "accel_profile": accel_profile,
        "is_flat": (accel_profile == "flat"),
        "follow_mouse": int(follow_mouse),
        "natural_scroll": bool(natural_scroll),
        "left_handed": bool(left_handed),
        "scroll_factor": round(float(scroll_factor), 2),
        "mouse_refocus": bool(mouse_refocus),
        "button_mappings": button_mappings
    }

def apply_hypr_eval(settings):
    """Apply settings live in Hyprland using hyprctl eval."""
    sensitivity = float(settings.get("sensitivity", 0.0))
    accel = settings.get("accel_profile", "adaptive")
    accel_lua = f'"{accel}"' if accel in ("flat", "adaptive", "custom") else '""'
    follow_mouse = int(settings.get("follow_mouse", 1))
    natural_scroll = "true" if settings.get("natural_scroll") else "false"
    left_handed = "true" if settings.get("left_handed") else "false"
    scroll_factor = float(settings.get("scroll_factor", 1.0))
    mouse_refocus = "true" if settings.get("mouse_refocus", True) else "false"

    lua_cmd = (
        f"hl.config({{ input = {{ "
        f"sensitivity = {sensitivity:.2f}, "
        f"accel_profile = {accel_lua}, "
        f"follow_mouse = {follow_mouse}, "
        f"natural_scroll = {natural_scroll}, "
        f"left_handed = {left_handed}, "
        f"scroll_factor = {scroll_factor:.2f}, "
        f"mouse_refocus = {mouse_refocus} "
        f"}} }})"
    )

    code, out, err = run_cmd(["hyprctl", "eval", lua_cmd])
    return code == 0

def persist_to_input_lua(settings):
    """Safely update or append settings inside ~/.config/hypr/input.lua."""
    INPUT_LUA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not INPUT_LUA_PATH.exists():
        original_content = "-- User input overrides\n"
    else:
        original_content = INPUT_LUA_PATH.read_text(encoding="utf-8")

    sensitivity = float(settings.get("sensitivity", 0.0))
    accel = settings.get("accel_profile", "adaptive")
    accel_lua = f'"{accel}"' if accel in ("flat", "adaptive", "custom") else '""'
    follow_mouse = int(settings.get("follow_mouse", 1))
    natural_scroll = "true" if settings.get("natural_scroll") else "false"
    left_handed = "true" if settings.get("left_handed") else "false"
    scroll_factor = float(settings.get("scroll_factor", 1.0))
    mouse_refocus = "true" if settings.get("mouse_refocus", True) else "false"

    new_block = (
        f"{START_MARKER}\n"
        f"hl.config({{\n"
        f"  input = {{\n"
        f"    sensitivity = {sensitivity:.2f},\n"
        f"    accel_profile = {accel_lua},\n"
        f"    follow_mouse = {follow_mouse},\n"
        f"    natural_scroll = {natural_scroll},\n"
        f"    left_handed = {left_handed},\n"
        f"    scroll_factor = {scroll_factor:.2f},\n"
        f"    mouse_refocus = {mouse_refocus},\n"
        f"  }},\n"
        f"}})\n"
        f"{END_MARKER}"
    )

    if START_MARKER in original_content and END_MARKER in original_content:
        pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
        updated_content = pattern.sub(new_block, original_content)
    else:
        updated_content = original_content.rstrip() + "\n\n" + new_block + "\n"

    INPUT_LUA_PATH.write_text(updated_content, encoding="utf-8")
    return ""

def persist_to_bindings_lua(mappings):
    """Safely update button mappings in ~/.config/hypr/bindings.lua."""
    BINDINGS_LUA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BINDINGS_LUA_PATH.exists():
        original_content = "-- User keybinding overrides\n"
    else:
        original_content = BINDINGS_LUA_PATH.read_text(encoding="utf-8")

    lines = []
    lines.append(BINDINGS_START_MARKER)

    # Side Back (275)
    sb = mappings.get("side_back", "default")
    if sb == "prev_workspace":
        lines.append('hl.unbind("mouse:275")')
        lines.append('o.bind("mouse:275", "Previous workspace", hl.dsp.focus({ workspace = "e-1" }), { mouse = true })')
    elif sb == "menu":
        lines.append('hl.unbind("mouse:275")')
        lines.append('o.bind("mouse:275", "Omarchy menu", "omarchy-menu toggle root", { mouse = true })')
    elif sb == "prev_window":
        lines.append('hl.unbind("mouse:275")')
        lines.append('o.bind("mouse:275", "Previous window", hl.dsp.focus({ direction = "l" }), { mouse = true })')

    # Side Forward (276)
    sf = mappings.get("side_forward", "default")
    if sf == "next_workspace":
        lines.append('hl.unbind("mouse:276")')
        lines.append('o.bind("mouse:276", "Next workspace", hl.dsp.focus({ workspace = "e+1" }), { mouse = true })')
    elif sf == "terminal":
        lines.append('hl.unbind("mouse:276")')
        lines.append('o.bind("mouse:276", "Terminal", { launch = "ghostty" }, { mouse = true })')
    elif sf == "next_window":
        lines.append('hl.unbind("mouse:276")')
        lines.append('o.bind("mouse:276", "Next window", hl.dsp.focus({ direction = "r" }), { mouse = true })')

    # Middle Click (274)
    mc = mappings.get("middle_click", "default")
    if mc == "close_window":
        lines.append('hl.unbind("mouse:274")')
        lines.append('o.bind("mouse:274", "Close active window", hl.dsp.window.kill(), { mouse = true })')
    elif mc == "toggle_floating":
        lines.append('hl.unbind("mouse:274")')
        lines.append('o.bind("mouse:274", "Toggle floating", hl.dsp.window.toggle_floating(), { mouse = true })')
    elif mc == "toggle_fullscreen":
        lines.append('hl.unbind("mouse:274")')
        lines.append('o.bind("mouse:274", "Toggle fullscreen", hl.dsp.window.fullscreen(), { mouse = true })')

    # Super + Left Drag (272)
    sl = mappings.get("super_left", "move_window")
    if sl == "disabled":
        lines.append('hl.unbind("SUPER + mouse:272")')

    # Super + Right Drag (273)
    sr = mappings.get("super_right", "resize_window")
    if sr == "disabled":
        lines.append('hl.unbind("SUPER + mouse:273")')

    # Super + Wheel
    sw = mappings.get("super_wheel", "workspace_scroll")
    if sw == "disabled":
        lines.append('hl.unbind("SUPER + mouse_down")')
        lines.append('hl.unbind("SUPER + mouse_up")')

    lines.append(BINDINGS_END_MARKER)

    new_block = "\n".join(lines)

    if BINDINGS_START_MARKER in original_content and BINDINGS_END_MARKER in original_content:
        pattern = re.compile(re.escape(BINDINGS_START_MARKER) + r".*?" + re.escape(BINDINGS_END_MARKER), re.DOTALL)
        updated_content = pattern.sub(new_block, original_content)
    else:
        updated_content = original_content.rstrip() + "\n\n" + new_block + "\n"

    BINDINGS_LUA_PATH.write_text(updated_content, encoding="utf-8")
    run_cmd(["hyprctl", "reload"])
    _, err_out, _ = run_cmd(["hyprctl", "configerrors"])
    return err_out

def notify_user(title, message, icon="input-mouse"):
    """Send desktop notification via notify-send."""
    run_cmd(["notify-send", "-a", "Omarchy", "-i", icon, title, message])

def main():
    parser = argparse.ArgumentParser(description="Omarchy Mouse Control Helper")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Get JSON status of mouse settings")

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply and persist settings")
    apply_parser.add_argument("--json-data", type=str, help="JSON string with settings")

    # quick toggle accel
    subparsers.add_parser("toggle-accel", help="Toggle precision (flat) vs desktop (adaptive) acceleration")

    # quick toggle natural scroll
    subparsers.add_parser("toggle-natural-scroll", help="Toggle natural scroll direction")

    # reset
    subparsers.add_parser("reset-defaults", help="Reset mouse settings to default")

    args = parser.parse_args()

    if args.command == "status" or not args.command:
        state = get_current_status()
        print(json.dumps(state, indent=2))
        return

    if args.command == "toggle-accel":
        current = get_current_status()
        new_profile = "adaptive" if current["accel_profile"] == "flat" else "flat"
        current["accel_profile"] = new_profile
        current["is_flat"] = (new_profile == "flat")
        apply_hypr_eval(current)
        persist_to_input_lua(current)
        label = "Precision (Raw 1:1)" if new_profile == "flat" else "Desktop (Dynamic)"
        notify_user("Mouse Acceleration", f"Switched to {label}")
        print(json.dumps({"success": True, "accel_profile": new_profile, "label": label}))
        return

    if args.command == "toggle-natural-scroll":
        current = get_current_status()
        new_val = not current["natural_scroll"]
        current["natural_scroll"] = new_val
        apply_hypr_eval(current)
        persist_to_input_lua(current)
        label = "Natural (Mobile)" if new_val else "Traditional (Classic PC)"
        notify_user("Mouse Scrolling", f"Scroll direction set to {label}")
        print(json.dumps({"success": True, "natural_scroll": new_val, "label": label}))
        return

    if args.command == "reset-defaults":
        defaults = {
            "sensitivity": 0.0,
            "accel_profile": "adaptive",
            "follow_mouse": 1,
            "natural_scroll": False,
            "left_handed": False,
            "scroll_factor": 1.0,
            "mouse_refocus": True,
        }
        apply_hypr_eval(defaults)
        persist_to_input_lua(defaults)
        persist_to_bindings_lua(DEFAULT_BUTTON_MAPPINGS)
        notify_user("Mouse Settings", "Reset to Omarchy defaults")
        print(json.dumps({"success": True, "status": get_current_status()}))
        return

    if args.command == "apply":
        current = get_current_status()
        if args.json_data:
            try:
                payload = json.loads(args.json_data)
                current.update(payload)
                if "button_mappings" in payload:
                    current["button_mappings"] = payload["button_mappings"]
            except Exception as e:
                print(json.dumps({"error": f"Invalid JSON: {e}"}))
                sys.exit(1)

        apply_hypr_eval(current)
        persist_to_input_lua(current)
        err = persist_to_bindings_lua(current.get("button_mappings", {}))
        print(json.dumps({"success": True, "error": err, "status": get_current_status()}))
        return

if __name__ == "__main__":
    main()
