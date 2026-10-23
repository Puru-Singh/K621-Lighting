"""Development: read known K621 configuration regions, never program them.

Read selectors are derived from KeyboardDrv.exe helpers 446B20 (83/C6),
446D70 (84/D8), and 446FE0 (85/variable address). The only SetFeature
commands here have the read bit set; no persistent-write opcodes are used.
Raw snapshots are private development evidence under ignored captures/.
"""
import ctypes as C
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from k621_rgb.hid_windows import WindowsHID
from k621_rgb.protocol import LightingError


def read_regions():
    hid = WindowsHID()
    hid._bind(hid.hid, 'HidD_GetFeature', C.c_ubyte, [C.c_void_p, C.c_void_p, C.c_ulong])
    devices = hid.enumerate()
    def target(length):
        matches = [d for d in devices if d.fingerprint and
                   (d.fingerprint.vendor_id, d.fingerprint.product_id, d.fingerprint.version,
                    d.fingerprint.interface, d.fingerprint.manufacturer, d.fingerprint.product,
                    d.fingerprint.usage_page, d.fingerprint.usage, d.fingerprint.feature_length) ==
                   (0x258a, 0x49, 0x100, 1, 'BY Tech', 'Gaming Keyboard', 0xff00, 1, length)]
        if len(matches) != 1:
            raise LightingError(f'Expected exactly one verified collection with feature length {length}')
        return matches[0]
    short, long = target(6), target(1032)
    handles = []
    result = {}
    try:
        for d in (short, long):
            h = hid.open(d.path, write=True)
            handles.append(h)
            if hid.describe(h, d.path) != d.fingerprint:
                raise LightingError('Device identity changed')
        for opcode, address in ((0x83, 0xc6), (0x85, 0xc8), (0x85, 0xcc), (0x85, 0xd0), (0x84, 0xd8)):
            request = bytes([5, opcode, address, 0, 0, 0, 0])
            buffer = C.create_string_buffer(request, len(request))
            if not hid.hid.HidD_SetFeature(handles[0], buffer, len(request)):
                raise LightingError(f'Read selector failed: {C.WinError(C.get_last_error())}')
            time.sleep(0.04)
            response = C.create_string_buffer(1032)
            response[0] = b'\x06'
            if not hid.hid.HidD_GetFeature(handles[1], response, 1032):
                raise LightingError(f'Read response failed: {C.WinError(C.get_last_error())}')
            packet = bytes(response)
            result[f'{address:02x}'] = list(packet)
            print(hex(address), packet[:12].hex(' '), 'nonzero', sum(b != 0 for b in packet), flush=True)
            time.sleep(0.06)
    finally:
        for h in handles:
            hid.kernel.CloseHandle(h)
    return result


if __name__ == '__main__':
    output = Path(sys.argv[1])
    result = read_regions()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result), encoding='utf-8')
