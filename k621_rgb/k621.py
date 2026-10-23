"""Original K621-RGB protocol recovered from KeyboardDrv 1.6.6.

No vendor binaries or captured configuration templates are needed at runtime.
Each application reads the current palette/config, changes only the static
lighting fields, and writes those two regions back. Keymap/macro commands and
the vendor app's extra CC/D0 palette writes are deliberately absent.
See docs/PROTOCOL.md for disassembly and on-device evidence.
"""
from dataclasses import dataclass
import re

from .protocol import Fingerprint, LightingError, parse_color


LONG = Fingerprint(0x258A, 0x0049, 0x0100, 1, "BY Tech", "Gaming Keyboard",
                   0xFF00, 1, 0, 0, 1032)
SHORT = Fingerprint(0x258A, 0x0049, 0x0100, 1, "BY Tech", "Gaming Keyboard",
                    0xFF00, 1, 0, 0, 6)
NAME = "Redragon K621-RGB HORUS"


@dataclass(frozen=True)
class Pair:
    short: object
    long: object


def physical_id(path):
    """Collections differ only in &colXX and their final collection instance."""
    parts = path.lower().split("#")
    if len(parts) != 4 or "&mi_01" not in parts[1] or "&col" not in parts[1]:
        raise LightingError("Unexpected K621 HID path; reconnect the USB cable.")
    return re.sub(r"&col[0-9a-f]+", "", parts[1]), parts[2].rsplit("&", 1)[0]


def select_pair(devices):
    longs = [d for d in devices if d.fingerprint == LONG]
    shorts = [d for d in devices if d.fingerprint == SHORT]
    if len(longs) > 1 or len(shorts) > 1:
        raise LightingError("Multiple compatible keyboards found. Connect only one K621 and refresh.")
    if len(longs) != 1 or len(shorts) != 1:
        if not devices:
            raise LightingError("Keyboard not found. Connect your K621 with USB and select wired mode.")
        errors = [d.error for d in devices if d.error]
        if errors:
            raise LightingError("Cannot access the K621: " + errors[0])
        raise LightingError("The connected device does not match the original K621-RGB USB interfaces.")
    if physical_id(longs[0].path) != physical_id(shorts[0].path):
        raise LightingError("Keyboard collections belong to different devices; reconnect only one K621.")
    return Pair(shorts[0], longs[0])


def validate_config(packet):
    if (len(packet) != 1032 or packet[:4] != b"\x06\x83\xc6\x00"
            or packet[14:16] != b"\x5a\xa5" or packet[78:80] != b"\x5a\xa5"):
        raise LightingError("Unexpected keyboard configuration response; no settings were programmed.")


def validate_palette(packet):
    if len(packet) != 1032 or packet[:2] != b"\x06\x85":
        raise LightingError("Unexpected keyboard palette response; no settings were programmed.")


def encode_static(config, palette, color):
    """Preserve every non-lighting byte from the device, including other modes."""
    rgb = bytes(parse_color(color))
    validate_config(config)
    validate_palette(palette)
    colors = bytearray(palette)
    colors[:8] = b"\x06\x08\xc8\x00\x40\x00\x00\x00"
    colors[29:32] = rgb  # Fixed_on's first of seven RGB slots.
    mode = bytearray(config)
    mode[:8] = b"\x06\x03\xc6\x00\x00\x00\x00\x00"
    # Recovered from 411040: ordinary hardware effect, hardware ID 1,
    # first effect's color/random nibble 0, brightness nibble 9 (maximum).
    # Keep profile selection, direction bits, speed, and every other field.
    mode[20] = 0
    mode[21] = 1
    mode[38] &= 0xF0
    mode[39] = (mode[39] & 0xF0) | 9
    return bytes(colors), bytes(mode)


def verify_static(config_after, palette_after, colors, mode):
    validate_config(config_after)
    validate_palette(palette_after)
    if config_after[8:] != mode[8:] or palette_after[8:] != colors[8:]:
        raise LightingError(
            "The keyboard did not retain the requested lighting settings. "
            "Close other keyboard/RGB utilities, reconnect USB, and try again. No automatic retry."
        )
