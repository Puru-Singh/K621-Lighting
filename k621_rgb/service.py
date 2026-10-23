"""Device selection and a single lighting transaction; UI-independent."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .hid_windows import WindowsHID
from .protocol import LightingError, parse_color, protocol_for
from .k621 import LONG, NAME, select_pair


def select_target(devices):
    candidates = []
    for device in devices:
        if device.fingerprint is not None:
            try:
                protocol = protocol_for(device.fingerprint)
            except LightingError:
                continue
            candidates.append((device, protocol))
    if len(candidates) > 1:
        raise LightingError("Multiple compatible keyboards found. Connect only one K621 and try again.")
    if not candidates:
        if not devices:
            raise LightingError("No K621 candidate found. Connect the USB cable and select wired mode.")
        errors = [device.error for device in devices if device.error]
        if errors and all(device.fingerprint is None for device in devices):
            raise LightingError("Cannot inspect the keyboard: " + errors[0])
        raise LightingError(
            "Keyboard detected. Lighting is locked until this K621's lighting-only "
            "commands are verified. See docs/CAPTURE.md."
        )
    # An unreadable second device could be another matching target. Do not guess.
    if any(device.fingerprint is None for device in devices):
        raise LightingError("A keyboard interface could not be identified. Reconnect and refresh.")
    return candidates[0]


def apply_once(color, hid=None):
    parse_color(color)
    hid = hid or WindowsHID()
    devices = hid.enumerate()
    if any(d.fingerprint == LONG for d in devices):
        hid.apply_static(select_pair(devices), color)
        return
    device, protocol = select_target(devices)
    packets = protocol.encode(color)
    hid.send(device.path, device.fingerprint, packets)


def inspect_devices(hid=None, include_paths=False):
    hid = hid or WindowsHID()
    devices = hid.enumerate()
    try:
        select_pair(devices)
        ready, status = True, f"Connected: {NAME}. Choose a color and click Apply."
    except LightingError as exc:
        ready, status = False, str(exc)
    return {"ready": ready, "status": status,
            "interfaces": [device.diagnostic(include_paths) for device in devices]}


def command(*args):
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "app.py"), *args]


def run_bounded(*args, timeout=15):
    """Kill a stalled HID worker instead of leaving a blocked background thread."""
    # A windowed PyInstaller executable has no sys.stdout, even with redirected
    # handles. An explicit temporary JSON file works in both source/frozen modes.
    with tempfile.TemporaryDirectory(prefix="k621-worker-") as directory:
        output = Path(directory) / "result.json"
        try:
            result = subprocess.run(command(*args, "--output", str(output)), capture_output=True,
                                    timeout=timeout,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise LightingError(
                "Keyboard operation timed out and the worker was stopped. "
                "If applying, the keyboard state may be partial. No automatic retry."
            ) from None
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            raise LightingError("The keyboard worker failed. Run the diagnostic command for details.") from None
    if result.returncode:
        raise LightingError(payload.get("error", "Keyboard operation failed."))
    return payload


@dataclass
class Settings:
    path: Path

    @classmethod
    def default(cls):
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return cls(root / "K621StaticColor" / "settings.json")

    def load(self):
        try:
            color = json.loads(self.path.read_text(encoding="utf-8"))["color"]
            parse_color(color)
            return color.upper()
        except (OSError, ValueError, KeyError, TypeError, LightingError):
            return "#4A90E2"

    def save(self, color):
        parse_color(color)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"color": color.upper()}) + "\n", encoding="utf-8")
        temporary.replace(self.path)
