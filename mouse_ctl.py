#!/usr/bin/env python3
"""
Omarchy Mouse Settings Backend Controller (mouse_ctl.py)
Hardened security implementation:
- Atomic file writes via temp-files + fsync + os.replace
- Symlink clobbering protection (refuses to follow symlinks)
- File locking via fcntl.flock to prevent race conditions
- Strict input validation & range clamping (finite numbers, allowlisted enums)
- Selective persistence & conditional hyprctl reload
"""

import argparse
import fcntl
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

INPUT_LUA_PATH = Path.home() / ".config" / "hypr" / "input.lua"
BINDINGS_LUA_PATH = Path.home() / ".config" / "hypr" / "bindings.lua"
LOCK_PATH = Path.home() / ".config" / "hypr" / ".mouse_ctl.lock"

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

ALLOWED_BUTTON_ACTIONS = {
    "side_back": {"default", "prev_workspace", "menu", "prev_window"},
    "side_forward": {"default", "next_workspace", "terminal", "next_window"},
    "middle_click": {"default", "close_window", "toggle_floating", "toggle_fullscreen"},
    "super_left": {"move_window", "disabled"},
    "super_right": {"resize_window", "disabled"},
    "super_wheel": {"workspace_scroll", "disabled"}
}

@contextmanager
def file_lock():
    """Acquires an exclusive lock across read-modify-write operations to prevent races."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOCK_PATH, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                except Exception:
                    pass
    except Exception:
        yield

def safe_atomic_write(target_path: Path, content: str) -> bool:
    """
    Safely writes content to target_path atomically on POSIX.
    - Prevents symlink attacks: if target_path is a symlink, unlinks the symlink itself
      so the target file is never clobbered.
    - Writes to a temporary file in the same directory, flushes, fsyncs, and os.replace().
    """
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.is_symlink():
            target_path.unlink()

        fd, tmp_path = tempfile.mkstemp(
            dir=str(target_path.parent),
            prefix=f"{target_path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(target_path))
            return True
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return False
    except Exception:
        return False

def validate_float(val, default: float, min_val: float, max_val: float) -> float:
    """Strictly coerces and clamps a float value, rejecting NaN and Infinities."""
    try:
        v = float(val)
        if not math.isfinite(v):
            return default
        return max(min_val, min(max_val, round(v, 2)))
    except (TypeError, ValueError, OverflowError):
        return default

def validate_int(val, default: int, min_val: int, max_val: int) -> int:
    """Strictly coerces and clamps an integer value."""
    try:
        v = int(val)
        return max(min_val, min(max_val, v))
    except (TypeError, ValueError, OverflowError):
        return default

def validate_bool(val, default: bool) -> bool:
    """Strictly parses boolean values."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    if isinstance(val, (int, float)):
        return bool(val)
    return default

def validate_accel_profile(val: str, default: str = "adaptive") -> str:
    """Strictly allowlists acceleration profile names."""
    if str(val) in ("flat", "adaptive", "custom"):
        return str(val)
    return default

def validate_button_mapping(button: str, action: str) -> str:
    """Validates button mapping actions against strict allowlist."""
    default = DEFAULT_BUTTON_MAPPINGS.get(button, "default")
    allowed = ALLOWED_BUTTON_ACTIONS.get(button, set())
    if str(action) in allowed:
        return str(action)
    return default

def run_cmd(cmd):
    """Run a shell command safely using list argv (never shell=True)."""
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
            name = str(m.get("name", "Unknown Mouse"))
            clean_mice.append({
                "name": name,
                "address": str(m.get("address", "")),
                "defaultSpeed": validate_float(m.get("defaultSpeed"), 0.0, -1.0, 1.0),
                "scrollFactor": validate_float(m.get("scrollFactor"), 1.0, 0.1, 10.0)
            })
        return clean_mice
    except Exception:
        return []

def read_saved_input_settings():
    """Reads settings previously saved in the marker block of input.lua."""
    settings = {}
    if not INPUT_LUA_PATH.exists():
        return settings
    try:
        content = INPUT_LUA_PATH.read_text(encoding="utf-8")
        if START_MARKER in content and END_MARKER in content:
            block = content.split(START_MARKER)[1].split(END_MARKER)[0]
            sens_match = re.search(r"sensitivity\s*=\s*([-+]?[0-9]*\.?[0-9]+)", block)
            if sens_match:
                settings["sensitivity"] = validate_float(sens_match.group(1), 0.0, -1.0, 1.0)
            accel_match = re.search(r'accel_profile\s*=\s*"([^"]+)"', block)
            if accel_match:
                settings["accel_profile"] = validate_accel_profile(accel_match.group(1))
            follow_match = re.search(r"follow_mouse\s*=\s*([0-9]+)", block)
            if follow_match:
                settings["follow_mouse"] = validate_int(follow_match.group(1), 1, 0, 3)
            natural_match = re.search(r"natural_scroll\s*=\s*(true|false)", block)
            if natural_match:
                settings["natural_scroll"] = (natural_match.group(1) == "true")
            left_match = re.search(r"left_handed\s*=\s*(true|false)", block)
            if left_match:
                settings["left_handed"] = (left_match.group(1) == "true")
            scroll_match = re.search(r"scroll_factor\s*=\s*([-+]?[0-9]*\.?[0-9]+)", block)
            if scroll_match:
                settings["scroll_factor"] = validate_float(scroll_match.group(1), 1.0, 0.1, 8.0)
            refocus_match = re.search(r"mouse_refocus\s*=\s*(true|false)", block)
            if refocus_match:
                settings["mouse_refocus"] = (refocus_match.group(1) == "true")
    except Exception:
        pass
    return settings

def read_saved_button_mappings():
    """Read saved button mappings from ~/.config/hypr/bindings.lua."""
    mappings = dict(DEFAULT_BUTTON_MAPPINGS)
    if not BINDINGS_LUA_PATH.exists():
        return mappings

    try:
        content = BINDINGS_LUA_PATH.read_text(encoding="utf-8")
        if BINDINGS_START_MARKER in content and BINDINGS_END_MARKER in content:
            block = content.split(BINDINGS_START_MARKER)[1].split(BINDINGS_END_MARKER)[0]
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
    """Get full sanitized state of mouse configuration and button mappings."""
    saved_input = read_saved_input_settings()

    # Prioritize values from the saved plugin block if present, else query hyprctl
    sensitivity = saved_input.get("sensitivity", get_hypr_option("input:sensitivity"))
    sensitivity = validate_float(sensitivity, 0.0, -1.0, 1.0)

    accel_profile = saved_input.get("accel_profile", get_hypr_option("input:accel_profile"))
    accel_profile = validate_accel_profile(accel_profile, "adaptive")

    follow_mouse = saved_input.get("follow_mouse", get_hypr_option("input:follow_mouse"))
    follow_mouse = validate_int(follow_mouse, 1, 0, 3)

    natural_scroll = saved_input.get("natural_scroll", get_hypr_option("input:natural_scroll"))
    natural_scroll = validate_bool(natural_scroll, False)

    left_handed = saved_input.get("left_handed", get_hypr_option("input:left_handed"))
    left_handed = validate_bool(left_handed, False)

    scroll_factor = saved_input.get("scroll_factor", get_hypr_option("input:scroll_factor"))
    scroll_factor = validate_float(scroll_factor, 1.0, 0.1, 8.0)

    mouse_refocus = saved_input.get("mouse_refocus", get_hypr_option("input:mouse_refocus"))
    mouse_refocus = validate_bool(mouse_refocus, True)

    devices = get_devices()
    button_mappings = read_saved_button_mappings()

    return {
        "devices": devices,
        "primaryDevice": devices[0]["name"] if devices else "Standard Mouse",
        "sensitivity": sensitivity,
        "accel_profile": accel_profile,
        "is_flat": (accel_profile == "flat"),
        "follow_mouse": follow_mouse,
        "natural_scroll": natural_scroll,
        "left_handed": left_handed,
        "scroll_factor": scroll_factor,
        "mouse_refocus": mouse_refocus,
        "button_mappings": button_mappings
    }

def apply_hypr_eval(settings) -> bool:
    """Apply settings live in Hyprland using hyprctl eval with sanitized parameters."""
    sensitivity = validate_float(settings.get("sensitivity"), 0.0, -1.0, 1.0)
    accel = validate_accel_profile(settings.get("accel_profile", "adaptive"))
    accel_lua = f'"{accel}"' if accel in ("flat", "adaptive", "custom") else '""'
    follow_mouse = validate_int(settings.get("follow_mouse"), 1, 0, 3)
    natural_scroll = "true" if validate_bool(settings.get("natural_scroll"), False) else "false"
    left_handed = "true" if validate_bool(settings.get("left_handed"), False) else "false"
    scroll_factor = validate_float(settings.get("scroll_factor"), 1.0, 0.1, 8.0)
    mouse_refocus = "true" if validate_bool(settings.get("mouse_refocus"), True) else "false"

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

def persist_to_input_lua(settings) -> bool:
    """
    Safely updates or appends settings inside ~/.config/hypr/input.lua using atomic write.
    Returns True if file content changed, False otherwise.
    """
    if not INPUT_LUA_PATH.exists():
        original_content = "-- User input overrides\n"
    else:
        try:
            original_content = INPUT_LUA_PATH.read_text(encoding="utf-8")
        except Exception:
            original_content = ""

    sensitivity = validate_float(settings.get("sensitivity"), 0.0, -1.0, 1.0)
    accel = validate_accel_profile(settings.get("accel_profile", "adaptive"))
    accel_lua = f'"{accel}"' if accel in ("flat", "adaptive", "custom") else '""'
    follow_mouse = validate_int(settings.get("follow_mouse"), 1, 0, 3)
    natural_scroll = "true" if validate_bool(settings.get("natural_scroll"), False) else "false"
    left_handed = "true" if validate_bool(settings.get("left_handed"), False) else "false"
    scroll_factor = validate_float(settings.get("scroll_factor"), 1.0, 0.1, 8.0)
    mouse_refocus = "true" if validate_bool(settings.get("mouse_refocus"), True) else "false"

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

    if updated_content == original_content:
        return False  # No change

    return safe_atomic_write(INPUT_LUA_PATH, updated_content)

def persist_to_bindings_lua(mappings) -> bool:
    """
    Safely updates button mappings in ~/.config/hypr/bindings.lua using atomic write.
    Returns True if file content changed, False otherwise.
    """
    if not BINDINGS_LUA_PATH.exists():
        original_content = "-- User keybinding overrides\n"
    else:
        try:
            original_content = BINDINGS_LUA_PATH.read_text(encoding="utf-8")
        except Exception:
            original_content = ""

    lines = []
    lines.append(BINDINGS_START_MARKER)

    # Side Back (275)
    sb = validate_button_mapping("side_back", mappings.get("side_back", "default"))
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
    sf = validate_button_mapping("side_forward", mappings.get("side_forward", "default"))
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
    mc = validate_button_mapping("middle_click", mappings.get("middle_click", "default"))
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
    sl = validate_button_mapping("super_left", mappings.get("super_left", "move_window"))
    if sl == "disabled":
        lines.append('hl.unbind("SUPER + mouse:272")')

    # Super + Right Drag (273)
    sr = validate_button_mapping("super_right", mappings.get("super_right", "resize_window"))
    if sr == "disabled":
        lines.append('hl.unbind("SUPER + mouse:273")')

    # Super + Wheel
    sw = validate_button_mapping("super_wheel", mappings.get("super_wheel", "workspace_scroll"))
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

    if updated_content == original_content:
        return False  # No change

    return safe_atomic_write(BINDINGS_LUA_PATH, updated_content)

def notify_user(title, message, icon="input-mouse"):
    """Send desktop notification via notify-send using fixed compile-time strings."""
    run_cmd(["notify-send", "-a", "Omarchy", "-i", icon, str(title), str(message)])

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

    with file_lock():
        if args.command == "toggle-accel":
            current = get_current_status()
            new_profile = "adaptive" if current["accel_profile"] == "flat" else "flat"
            current["accel_profile"] = new_profile
            current["is_flat"] = (new_profile == "flat")
            eval_ok = apply_hypr_eval(current)
            persist_to_input_lua(current)
            label = "Precision (Raw 1:1)" if new_profile == "flat" else "Desktop (Dynamic)"
            notify_user("Mouse Acceleration", f"Switched to {label}")
            print(json.dumps({"success": eval_ok, "accel_profile": new_profile, "label": label}))
            return

        if args.command == "toggle-natural-scroll":
            current = get_current_status()
            new_val = not current["natural_scroll"]
            current["natural_scroll"] = new_val
            eval_ok = apply_hypr_eval(current)
            persist_to_input_lua(current)
            label = "Natural (Mobile)" if new_val else "Traditional (Classic PC)"
            notify_user("Mouse Scrolling", f"Scroll direction set to {label}")
            print(json.dumps({"success": eval_ok, "natural_scroll": new_val, "label": label}))
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
            eval_ok = apply_hypr_eval(defaults)
            input_changed = persist_to_input_lua(defaults)
            bindings_changed = persist_to_bindings_lua(DEFAULT_BUTTON_MAPPINGS)
            if bindings_changed or input_changed:
                run_cmd(["hyprctl", "reload"])
            notify_user("Mouse Settings", "Reset to Omarchy defaults")
            print(json.dumps({"success": eval_ok, "status": get_current_status()}))
            return

        if args.command == "apply":
            current = get_current_status()
            has_input_change = False
            has_bindings_change = False

            if args.json_data:
                try:
                    payload = json.loads(args.json_data)
                    if not isinstance(payload, dict):
                        print(json.dumps({"success": False, "error": "Payload must be a JSON object"}))
                        return

                    # Selective field update with strict validation
                    if "sensitivity" in payload:
                        current["sensitivity"] = validate_float(payload["sensitivity"], current["sensitivity"], -1.0, 1.0)
                        has_input_change = True
                    if "accel_profile" in payload:
                        current["accel_profile"] = validate_accel_profile(payload["accel_profile"], current["accel_profile"])
                        current["is_flat"] = (current["accel_profile"] == "flat")
                        has_input_change = True
                    if "follow_mouse" in payload:
                        current["follow_mouse"] = validate_int(payload["follow_mouse"], current["follow_mouse"], 0, 3)
                        has_input_change = True
                    if "natural_scroll" in payload:
                        current["natural_scroll"] = validate_bool(payload["natural_scroll"], current["natural_scroll"])
                        has_input_change = True
                    if "left_handed" in payload:
                        current["left_handed"] = validate_bool(payload["left_handed"], current["left_handed"])
                        has_input_change = True
                    if "scroll_factor" in payload:
                        current["scroll_factor"] = validate_float(payload["scroll_factor"], current["scroll_factor"], 0.1, 8.0)
                        has_input_change = True
                    if "mouse_refocus" in payload:
                        current["mouse_refocus"] = validate_bool(payload["mouse_refocus"], current["mouse_refocus"])
                        has_input_change = True

                    if "button_mappings" in payload and isinstance(payload["button_mappings"], dict):
                        for btn, act in payload["button_mappings"].items():
                            if btn in ALLOWED_BUTTON_ACTIONS:
                                current["button_mappings"][btn] = validate_button_mapping(btn, act)
                        has_bindings_change = True

                except Exception as e:
                    print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
                    return

            eval_ok = True
            if has_input_change:
                eval_ok = apply_hypr_eval(current)
                persist_to_input_lua(current)

            if has_bindings_change:
                bindings_changed = persist_to_bindings_lua(current.get("button_mappings", {}))
                if bindings_changed:
                    run_cmd(["hyprctl", "reload"])

            _, err_out, _ = run_cmd(["hyprctl", "configerrors"])
            print(json.dumps({
                "success": eval_ok and not err_out,
                "error": err_out if err_out else None,
                "status": get_current_status()
            }))
            return

if __name__ == "__main__":
    main()
