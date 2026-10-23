"""Synthetic fixtures verify plumbing, never stand in for hardware captures."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from k621_rgb.hid_windows import Device, WindowsHID
from k621_rgb.protocol import (FeatureReport, Fingerprint, LightingError,
                               LightingProtocol, parse_color)
from k621_rgb.service import Settings, apply_once, inspect_devices, run_bounded, select_target


FP = Fingerprint(0x258A, 0x0049, 0x0100, 1, "SYNTHETIC", "TEST ONLY",
                 0xFF00, 1, 0, 0, 8)
REPORT = FeatureReport(bytes([6, 8, 11, 22, 33, 44, 55, 66]), ((2, 3, 4),), 1)
PROTOCOL = LightingProtocol("synthetic test protocol", FP, "tests only; no hardware evidence", (REPORT,))


class FakeHID:
    def __init__(self, devices=None, error=None):
        self.devices = devices if devices is not None else [Device("fake", FP)]
        self.error = error
        self.sent = []

    def enumerate(self):
        return self.devices

    def send(self, *args):
        self.sent.append(args)
        if self.error:
            raise self.error


class CoreTests(unittest.TestCase):
    def test_color_parsing(self):
        self.assertEqual(parse_color("#aB10Ff"), (171, 16, 255))
        self.assertEqual(parse_color("#000000"), (0, 0, 0))
        for value in ("", "fff", "#FFF", "#1234567", " #123456", "#GG0000", None):
            with self.subTest(value=value), self.assertRaises(LightingError):
                parse_color(value)

    def test_encoder_preserves_unrelated_bytes_and_template(self):
        for color, rgb in (("#FF0000", (255, 0, 0)), ("#00FF00", (0, 255, 0)),
                           ("#0000FF", (0, 0, 255)), ("#123456", (18, 52, 86))):
            packet, delay = PROTOCOL.encode(color)[0]
            self.assertEqual(packet, bytes([6, 8, *rgb, 44, 55, 66]))
            self.assertEqual(delay, 1)
        self.assertEqual(REPORT.template, bytes([6, 8, 11, 22, 33, 44, 55, 66]))

    def test_invalid_builtin_protocol_fails_before_transport(self):
        bad = [replace(PROTOCOL, evidence=""), replace(PROTOCOL, reports=()),
               replace(PROTOCOL, fingerprint=replace(FP, feature_length=7)),
               replace(PROTOCOL, reports=(replace(REPORT, rgb_offsets=((0, 2, 3),)),)),
               replace(PROTOCOL, reports=(replace(REPORT, rgb_offsets=((2, 2, 3),)),)),
               replace(PROTOCOL, reports=(replace(REPORT, delay_after_ms=501),))]
        for protocol in bad:
            with self.subTest(protocol=protocol), self.assertRaises(LightingError):
                protocol.encode("#123456")

    def test_shipping_gate_blocks_even_matching_usb_ids(self):
        hid = FakeHID()
        with self.assertRaisesRegex(LightingError, "locked"):
            apply_once("#123456", hid)
        self.assertEqual(hid.sent, [])

    def test_invalid_input_does_not_enumerate(self):
        hid = FakeHID()
        with patch.object(hid, "enumerate") as enumerate_devices:
            with self.assertRaises(LightingError):
                apply_once("#GG0000", hid)
            enumerate_devices.assert_not_called()

    def test_missing_and_unreadable_devices(self):
        for devices, message in (([], "No K621"), ([Device("fake", None, "access denied")], "access denied")):
            with self.subTest(devices=devices), self.assertRaisesRegex(LightingError, message):
                select_target(devices)

    @patch("k621_rgb.protocol.VERIFIED_PROTOCOLS", (PROTOCOL,))
    def test_selection_rejects_ambiguity_and_descriptor_mismatch(self):
        with self.assertRaisesRegex(LightingError, "Multiple"):
            select_target([Device("a", FP), Device("b", FP)])
        with self.assertRaisesRegex(LightingError, "could not be identified"):
            select_target([Device("a", FP), Device("b", None, "denied")])
        for field, value in (("product", "Other"), ("interface", 0), ("feature_length", 382),
                             ("version", 257), ("usage_page", 1)):
            with self.subTest(field=field), self.assertRaisesRegex(LightingError, "locked"):
                select_target([Device("a", replace(FP, **{field: value}))])

    @patch("k621_rgb.protocol.VERIFIED_PROTOCOLS", (PROTOCOL,))
    def test_apply_sends_exactly_one_transaction(self):
        hid = FakeHID()
        apply_once("#123456", hid)
        self.assertEqual(hid.sent, [("fake", FP, PROTOCOL.encode("#123456"))])

    @patch("k621_rgb.protocol.VERIFIED_PROTOCOLS", (PROTOCOL,))
    def test_transport_failure_does_not_retry(self):
        hid = FakeHID(error=LightingError("disconnected mid-transfer"))
        with self.assertRaisesRegex(LightingError, "disconnected"):
            apply_once("#123456", hid)
        self.assertEqual(len(hid.sent), 1)

    def test_diagnostics_redact_paths_and_never_write(self):
        hid = FakeHID()
        result = inspect_devices(hid)
        self.assertNotIn("fake", json.dumps(result))
        self.assertEqual(hid.sent, [])
        self.assertEqual(inspect_devices(hid, True)["interfaces"][0]["path"], "fake")

    def test_settings_load_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(Path(directory) / "sub" / "settings.json")
            self.assertEqual(settings.load(), "#4A90E2")
            settings.save("#aabbcc")
            self.assertEqual(settings.load(), "#AABBCC")
            settings.path.write_text('{"color":null}', encoding="utf-8")
            self.assertEqual(settings.load(), "#4A90E2")

    def test_timeout_reports_no_retry(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("fake", 15)) as call:
            with self.assertRaisesRegex(LightingError, "No automatic retry"):
                run_bounded("--worker-apply", "#123456")
            self.assertEqual(call.call_count, 1)

    def test_native_transport_closes_handle_after_mid_transaction_error(self):
        from unittest.mock import Mock
        native = object.__new__(WindowsHID)
        native.open = Mock(return_value=123)
        native.describe = Mock(return_value=FP)
        native.kernel = Mock()
        native.hid = Mock()
        native.hid.HidD_SetFeature.side_effect = [True, False]
        with self.assertRaisesRegex(LightingError, "partial"):
            native.send("fake", FP, ((b"\x06\x01", 0), (b"\x06\x02", 0), (b"\x06\x03", 0)))
        self.assertEqual(native.hid.HidD_SetFeature.call_count, 2)
        native.kernel.CloseHandle.assert_called_once_with(123)

    def test_native_transport_rechecks_identity(self):
        from unittest.mock import Mock
        native = object.__new__(WindowsHID)
        native.open = Mock(return_value=123)
        native.describe = Mock(return_value=replace(FP, version=999))
        native.kernel, native.hid = Mock(), Mock()
        with self.assertRaisesRegex(LightingError, "identity changed"):
            native.send("fake", FP, ((b"\x06\x01", 0),))
        native.hid.HidD_SetFeature.assert_not_called()
        native.kernel.CloseHandle.assert_called_once_with(123)


if __name__ == "__main__":
    unittest.main()
