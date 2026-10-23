"""K621 read-modify-write tests with deterministic, non-user packet fixtures."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock, patch

from k621_rgb.hid_windows import Device, WindowsHID
from k621_rgb.k621 import LONG, SHORT, encode_static, select_pair, verify_static
from k621_rgb.protocol import LightingError
from k621_rgb.service import apply_once, inspect_devices


def path(collection, instance="8&device&0"):
    return (rf"\\?\hid#vid_258a&pid_0049&mi_01&col{collection:02x}#"
            rf"{instance}&{collection-1:04x}#{{4d1e55b2-f16f-11cf-88cb-001111000030}}")


def devices():
    return [Device(path(5), SHORT), Device(path(6), LONG)]


def packets():
    config = bytearray((i * 13 + 7) % 256 for i in range(1032))
    config[:8] = b"\x06\x83\xc6\x00\x00\x00\x00\x00"
    config[14:16] = config[78:80] = b"\x5a\xa5"
    palette = bytearray((i * 31 + 9) % 256 for i in range(1032))
    palette[:8] = b"\x06\x85\x00\x00\x00\x00\x00\x00"
    return bytes(config), bytes(palette)


def readback(colors, mode):
    config, palette = bytearray(mode), bytearray(colors)
    config[:8] = b"\x06\x83\xc6\x00\x00\x00\x00\x00"
    palette[:8] = b"\x06\x85\x00\x00\x00\x00\x00\x00"
    return bytes(config), bytes(palette)


class K621Tests(TestCase):
    def test_exact_collection_pair_is_ready_without_device_queries(self):
        hid = Mock()
        hid.enumerate.return_value = devices()
        self.assertTrue(inspect_devices(hid)["ready"])
        hid.apply_static.assert_not_called()
        self.assertEqual(select_pair(devices()).long.fingerprint, LONG)

    def test_wrong_revision_or_incomplete_or_ambiguous_pair_is_rejected(self):
        cases = [[], devices()[:1], devices()[1:], devices() * 2,
                 [devices()[0], Device(path(6), replace(LONG, version=257))],
                 [devices()[0], Device(path(6, "8&other&0"), LONG)]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(LightingError):
                select_pair(case)

    def test_real_backend_is_dispatched_once(self):
        hid = Mock()
        hid.enumerate.return_value = devices()
        apply_once("#123456", hid)
        hid.apply_static.assert_called_once_with(select_pair(devices()), "#123456")
        hid.send.assert_not_called()

    def test_rgb_and_static_fields_change_and_every_other_byte_is_preserved(self):
        config, palette = packets()
        for color in ("#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#123456", "#000000"):
            with self.subTest(color=color):
                colors, mode = encode_static(config, palette, color)
                self.assertEqual(colors[:8], bytes.fromhex("06 08 c8 00 40 00 00 00"))
                self.assertEqual(colors[29:32], bytes.fromhex(color[1:]))
                self.assertEqual(mode[:8], bytes.fromhex("06 03 c6 00 00 00 00 00"))
                self.assertEqual((mode[20], mode[21], mode[38], mode[39]),
                                 (0, 1, config[38] & 0xF0, (config[39] & 0xF0) | 9))
                self.assertTrue(all(colors[i] == palette[i] for i in range(8, 1032)
                                    if i not in (29, 30, 31)))
                self.assertTrue(all(mode[i] == config[i] for i in range(8, 1032)
                                    if i not in (20, 21, 38, 39)))
                verify_static(*readback(colors, mode), colors, mode)

    def test_malformed_responses_fail_before_programming(self):
        config, palette = packets()
        for c, p in ((config[:100], palette), (config, palette[:100]),
                     (b"\0" * 1032, palette), (config, b"\0" * 1032)):
            with self.subTest(c=c[:8], p=p[:8]), self.assertRaises(LightingError):
                encode_static(c, p, "#123456")

    def test_readback_mismatch_is_failure(self):
        config, palette = packets()
        colors, mode = encode_static(config, palette, "#123456")
        after, colors_after = readback(colors, mode)
        bad = bytearray(colors_after)
        bad[29] ^= 1
        with self.assertRaisesRegex(LightingError, "did not retain"):
            verify_static(after, bytes(bad), colors, mode)

    def native(self):
        hid = object.__new__(WindowsHID)
        hid.open = Mock(side_effect=[101, 102])
        hid.describe = Mock(side_effect=[SHORT, LONG])
        hid.kernel = Mock()
        hid.set_feature = Mock()
        return hid

    @patch("time.sleep")
    def test_native_only_programs_two_lighting_reports_and_closes_both_handles(self, sleep):
        config, palette = packets()
        colors, mode = encode_static(config, palette, "#123456")
        hid = self.native()
        hid.read_region = Mock(side_effect=[config, palette, *readback(colors, mode)])
        hid.apply_static(select_pair(devices()), "#123456")
        self.assertEqual([c.args for c in hid.set_feature.call_args_list], [(102, colors), (102, mode)])
        self.assertEqual([c.args for c in hid.kernel.CloseHandle.call_args_list], [(102,), (101,)])
        self.assertEqual([c.args[2] for c in hid.read_region.call_args_list], [0xC6, 0xC8, 0xC6, 0xC8])

    @patch("time.sleep")
    def test_native_partial_failure_closes_both_and_never_retries(self, sleep):
        hid = self.native()
        hid.read_region = Mock(side_effect=packets())
        hid.set_feature.side_effect = [None, LightingError("disconnected")]
        with self.assertRaisesRegex(LightingError, "disconnected"):
            hid.apply_static(select_pair(devices()), "#123456")
        self.assertEqual(hid.set_feature.call_count, 2)
        self.assertEqual(hid.kernel.CloseHandle.call_count, 2)

    def test_native_wrong_layout_sends_no_programming_reports(self):
        hid = self.native()
        hid.read_region = Mock(return_value=b"\0" * 1032)
        with self.assertRaises(LightingError):
            hid.apply_static(select_pair(devices()), "#123456")
        hid.set_feature.assert_not_called()
        self.assertEqual(hid.kernel.CloseHandle.call_count, 2)
