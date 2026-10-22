#!/usr/bin/env python3
"""Regression guard for the widget <-> CLI status contract.

The bar widget polls `mouse_ctl.py status` every 3 s and merges the payload onto the
defaults declared in `Panel.qml` (`readonly property var defaultStatus`). When commit
b96e6d3 dropped the `sensitivity` key from `get_current_status()`, the cursor speed
slider's `value: root.status.sensitivity` received `undefined` and the shell logged

    Panel.qml[509:17]: Unable to assign [undefined] to double

on every single poll: ~600 journal lines per half hour. The QML side now degrades to its
defaults, and this test fails if a key the widget declares disappears from the payload,
or if a field the widget uses in a numeric/bool binding comes back with the wrong type.

Run: python3 -m unittest discover -s tests -v
"""

import json
import pathlib
import re
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
PANEL = REPO / "Panel.qml"
CLI = REPO / "mouse_ctl.py"

# Fields the widget binds to a typed property: `value:` is a double, `checked:`/`active:`
# is a bool. A wrong type here is exactly what spams the journal.
NUMERIC_FIELDS = ("sensitivity", "scroll_factor", "follow_mouse")
BOOL_FIELDS = ("is_flat", "natural_scroll", "left_handed", "mouse_refocus", "middle_drag_scroll")

# Nested keys of the button_mappings object the widget reads (Model.js option lists).
BUTTON_MAPPING_KEYS = (
    "side_back",
    "side_forward",
    "middle_click",
    "super_left",
    "super_right",
    "super_wheel",
)


def panel_default_status_keys():
    """Top-level keys of the widget's defaultStatus object literal."""
    text = PANEL.read_text(encoding="utf-8")
    match = re.search(
        r"readonly\s+property\s+var\s+defaultStatus\s*:\s*\(\{(.*?)\n  \}\)",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("could not locate defaultStatus in Panel.qml")
    keys = re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:", match.group(1), re.MULTILINE)
    if not keys:
        raise AssertionError("defaultStatus parsed as empty")
    return keys


def cli_status_payload():
    result = subprocess.run(
        [sys.executable, str(CLI), "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"`status` exited {result.returncode}: {result.stderr.strip()}")
    return json.loads(result.stdout)


class StatusContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = panel_default_status_keys()
        cls.payload = cli_status_payload()

    def test_default_status_parsed(self):
        # Guard the guard: a broken regex would make every other assertion vacuous.
        self.assertIn("sensitivity", self.keys)
        self.assertIn("button_mappings", self.keys)
        self.assertGreaterEqual(len(self.keys), 12)

    def test_payload_has_every_widget_key(self):
        missing = [k for k in self.keys if k not in self.payload]
        self.assertEqual([], missing, f"status payload lost keys the widget reads: {missing}")

    def test_numeric_fields_are_numbers(self):
        for field in NUMERIC_FIELDS:
            value = self.payload.get(field)
            self.assertIsInstance(value, (int, float), f"{field} is not numeric: {value!r}")
            self.assertFalse(isinstance(value, bool), f"{field} came back as a bool")

    def test_bool_fields_are_bools(self):
        for field in BOOL_FIELDS:
            value = self.payload.get(field)
            self.assertIsInstance(value, bool, f"{field} is not a bool: {value!r}")

    def test_button_mappings_complete(self):
        mappings = self.payload.get("button_mappings")
        self.assertIsInstance(mappings, dict)
        for key in BUTTON_MAPPING_KEYS:
            self.assertIn(key, mappings, f"button_mappings lost {key}")

    def test_json_parses_like_the_widget(self):
        # QML's JSON.parse rejects bare NaN/Infinity, which Python's json.load accepts.
        raw = subprocess.run(
            [sys.executable, str(CLI), "status"], capture_output=True, text=True, check=True
        ).stdout
        self.assertNotRegex(raw, r"\b(NaN|Infinity|-Infinity)\b")


if __name__ == "__main__":
    unittest.main()
