"""Only reviewed, device-specific lighting protocols belong in this module.

There is deliberately no external profile loader or raw-packet CLI. USB IDs
are shared by incompatible keyboards and do not prove protocol compatibility.
"""
from dataclasses import dataclass
import re


class LightingError(Exception):
    """An actionable error safe to display to the user."""


def parse_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise LightingError("Enter a color as #RRGGBB, for example #4A90E2.")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


@dataclass(frozen=True)
class Fingerprint:
    vendor_id: int
    product_id: int
    version: int
    interface: int
    manufacturer: str
    product: str
    usage_page: int
    usage: int
    input_length: int
    output_length: int
    feature_length: int


@dataclass(frozen=True)
class FeatureReport:
    """A captured lighting-only report; first byte includes the report ID.

    rgb_offsets may contain multiple RGB triples for an all-keys frame.
    Any future protocol with checksums needs its own reviewed encoder.
    """
    template: bytes
    rgb_offsets: tuple[tuple[int, int, int], ...] = ()
    delay_after_ms: int = 0

    def encode(self, rgb: tuple[int, int, int]) -> bytes:
        if not self.template or not 0 <= self.delay_after_ms <= 500:
            raise LightingError("Invalid built-in lighting report.")
        packet = bytearray(self.template)
        used = set()
        for offsets in self.rgb_offsets:
            if len(offsets) != 3:
                raise LightingError("Invalid built-in RGB mapping.")
            for offset, channel in zip(offsets, rgb):
                if not 0 < offset < len(packet) or offset in used:
                    raise LightingError("Invalid built-in RGB offset.")
                used.add(offset)
                packet[offset] = channel
        return bytes(packet)


@dataclass(frozen=True)
class LightingProtocol:
    name: str
    fingerprint: Fingerprint
    evidence: str
    reports: tuple[FeatureReport, ...]

    def encode(self, color: str) -> tuple[tuple[bytes, int], ...]:
        rgb = parse_color(color)
        if not self.evidence or not 1 <= len(self.reports) <= 32:
            raise LightingError("Lighting protocol has no reviewed capture evidence.")
        if not any(report.rgb_offsets for report in self.reports):
            raise LightingError("Lighting protocol has no color mapping.")
        result = tuple((report.encode(rgb), report.delay_after_ms) for report in self.reports)
        if any(len(packet) != self.fingerprint.feature_length for packet, _ in result):
            raise LightingError("Lighting report length does not match the verified interface.")
        return result


# Intentionally empty until captures from this exact K621 establish lighting-only
# reports. Never populate this from a K617/K629 example or a shared VID/PID.
VERIFIED_PROTOCOLS: tuple[LightingProtocol, ...] = ()


def protocol_for(fingerprint: Fingerprint) -> LightingProtocol:
    matches = [p for p in VERIFIED_PROTOCOLS if p.fingerprint == fingerprint]
    if len(matches) != 1:
        raise LightingError(
            "Lighting is locked: this K621's lighting commands have not been verified. "
            "Collect the vendor-app captures described in docs/CAPTURE.md first."
        )
    return matches[0]
