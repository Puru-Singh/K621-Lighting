"""Windows HID enumeration and feature transport using ctypes, without drivers.

Enumeration opens metadata handles with zero desired access and never sends
feature/output reports. No serial numbers are collected. Write handles are
opened only after protocol verification, inside the bounded apply subprocess.
"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import asdict, dataclass
import os
import re

from .protocol import Fingerprint, LightingError


class GUID(C.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD),
                ("Data4", C.c_ubyte * 8)]


class INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", W.DWORD), ("Reserved", C.c_size_t)]


class ATTRIBUTES(C.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", W.USHORT),
                ("ProductID", W.USHORT), ("VersionNumber", W.USHORT)]


class CAPS(C.Structure):
    _fields_ = [("Usage", W.USHORT), ("UsagePage", W.USHORT),
                ("InputReportByteLength", W.USHORT), ("OutputReportByteLength", W.USHORT),
                ("FeatureReportByteLength", W.USHORT), ("Reserved", W.USHORT * 17),
                ("NumberLinkCollectionNodes", W.USHORT),
                ("NumberInputButtonCaps", W.USHORT), ("NumberInputValueCaps", W.USHORT),
                ("NumberInputDataIndices", W.USHORT), ("NumberOutputButtonCaps", W.USHORT),
                ("NumberOutputValueCaps", W.USHORT), ("NumberOutputDataIndices", W.USHORT),
                ("NumberFeatureButtonCaps", W.USHORT), ("NumberFeatureValueCaps", W.USHORT),
                ("NumberFeatureDataIndices", W.USHORT)]


@dataclass(frozen=True)
class Device:
    path: str
    fingerprint: Fingerprint | None
    error: str = ""

    def diagnostic(self, include_path=False):
        result = {"descriptor": asdict(self.fingerprint) if self.fingerprint else None,
                  "error": self.error}
        if include_path:
            result["path"] = self.path
        return result


class WindowsHID:
    def __init__(self):
        if os.name != "nt":
            raise LightingError("This utility requires Windows and a USB-connected keyboard.")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.setup = C.WinDLL("setupapi", use_last_error=True)
        self.hid = C.WinDLL("hid", use_last_error=True)
        self.invalid = C.c_void_p(-1).value
        self._bind(self.kernel, "CreateFileW", W.HANDLE,
                   [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE])
        self._bind(self.kernel, "CloseHandle", W.BOOL, [W.HANDLE])
        self._bind(self.hid, "HidD_GetHidGuid", None, [C.POINTER(GUID)])
        self._bind(self.setup, "SetupDiGetClassDevsW", W.HANDLE,
                   [C.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD])
        self._bind(self.setup, "SetupDiEnumDeviceInterfaces", W.BOOL,
                   [W.HANDLE, W.LPVOID, C.POINTER(GUID), W.DWORD, C.POINTER(INTERFACE_DATA)])
        self._bind(self.setup, "SetupDiGetDeviceInterfaceDetailW", W.BOOL,
                   [W.HANDLE, C.POINTER(INTERFACE_DATA), W.LPVOID, W.DWORD,
                    C.POINTER(W.DWORD), W.LPVOID])
        self._bind(self.setup, "SetupDiDestroyDeviceInfoList", W.BOOL, [W.HANDLE])
        self._bind(self.hid, "HidD_GetAttributes", W.BOOLEAN, [W.HANDLE, C.POINTER(ATTRIBUTES)])
        for name in ("HidD_GetManufacturerString", "HidD_GetProductString", "HidD_SetFeature", "HidD_GetFeature"):
            self._bind(self.hid, name, W.BOOLEAN, [W.HANDLE, W.LPVOID, W.ULONG])
        self._bind(self.hid, "HidD_GetPreparsedData", W.BOOLEAN,
                   [W.HANDLE, C.POINTER(W.LPVOID)])
        self._bind(self.hid, "HidD_FreePreparsedData", W.BOOLEAN, [W.LPVOID])
        self._bind(self.hid, "HidP_GetCaps", W.LONG, [W.LPVOID, C.POINTER(CAPS)])

    @staticmethod
    def _bind(dll, name, restype, argtypes):
        func = getattr(dll, name)
        func.restype, func.argtypes = restype, argtypes

    def open(self, path, write=False):
        handle = self.kernel.CreateFileW(path, 0xC0000000 if write else 0, 3, None, 3, 0, None)
        if handle == self.invalid:
            raise LightingError(f"Cannot open keyboard interface: {C.WinError(C.get_last_error())}")
        return handle

    def describe(self, handle, path):
        attrs = ATTRIBUTES()
        attrs.Size = C.sizeof(attrs)
        if not self.hid.HidD_GetAttributes(handle, C.byref(attrs)):
            raise LightingError(f"Cannot read HID attributes: {C.WinError(C.get_last_error())}")
        strings = []
        for name in ("HidD_GetManufacturerString", "HidD_GetProductString"):
            buffer = C.create_unicode_buffer(256)
            strings.append(buffer.value if getattr(self.hid, name)(handle, buffer, C.sizeof(buffer)) else "")
        preparsed = W.LPVOID()
        if not self.hid.HidD_GetPreparsedData(handle, C.byref(preparsed)):
            raise LightingError("Cannot read keyboard report capabilities.")
        caps = CAPS()
        try:
            if self.hid.HidP_GetCaps(preparsed, C.byref(caps)) != 0x00110000:
                raise LightingError("Windows rejected the keyboard's HID capabilities.")
        finally:
            self.hid.HidD_FreePreparsedData(preparsed)
        interface = re.search(r"&mi_([0-9a-f]{2})", path, re.I)
        return Fingerprint(attrs.VendorID, attrs.ProductID, attrs.VersionNumber,
                           int(interface[1], 16) if interface else -1,
                           *strings, caps.UsagePage, caps.Usage,
                           caps.InputReportByteLength, caps.OutputReportByteLength,
                           caps.FeatureReportByteLength)

    def enumerate(self):
        guid = GUID()
        self.hid.HidD_GetHidGuid(C.byref(guid))
        info = self.setup.SetupDiGetClassDevsW(C.byref(guid), None, None, 0x12)
        if info == self.invalid:
            raise LightingError("Windows could not enumerate HID interfaces.")
        devices = []
        try:
            index = 0
            while True:
                interface = INTERFACE_DATA()
                interface.cbSize = C.sizeof(interface)
                if not self.setup.SetupDiEnumDeviceInterfaces(info, None, C.byref(guid), index,
                                                              C.byref(interface)):
                    if C.get_last_error() == 259:
                        break
                    raise LightingError(f"HID enumeration failed: {C.WinError(C.get_last_error())}")
                index += 1
                size = W.DWORD()
                self.setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(interface), None, 0,
                                                            C.byref(size), None)
                if not 6 <= size.value <= 65536:
                    raise LightingError("Windows returned an invalid HID interface detail size.")
                detail = C.create_string_buffer(size.value)
                C.cast(detail, C.POINTER(W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
                if not self.setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(interface), detail,
                                                                   size, None, None):
                    raise LightingError("Cannot read HID interface path.")
                path = C.wstring_at(C.addressof(detail) + 4)
                # Limit metadata queries to the family under investigation.
                if "vid_258a&pid_0049" not in path.lower():
                    continue
                handle = None
                try:
                    handle = self.open(path)
                    devices.append(Device(path, self.describe(handle, path)))
                except LightingError as exc:
                    devices.append(Device(path, None, str(exc)))
                finally:
                    if handle is not None:
                        self.kernel.CloseHandle(handle)
        finally:
            self.setup.SetupDiDestroyDeviceInfoList(info)
        return devices

    def send(self, path, expected, packets):
        """Called only after built-in profile selection. No retries or reads of keys."""
        import time
        handle = self.open(path, write=True)
        try:
            if self.describe(handle, path) != expected:
                raise LightingError("Keyboard identity changed; no lighting commands were sent.")
            for packet, delay_ms in packets:
                buffer = C.create_string_buffer(packet, len(packet))
                if not self.hid.HidD_SetFeature(handle, buffer, len(packet)):
                    raise LightingError(
                        f"Lighting transfer failed; keyboard state may be partial: "
                        f"{C.WinError(C.get_last_error())}. No automatic retry."
                    )
                if delay_ms:
                    time.sleep(delay_ms / 1000)
        finally:
            self.kernel.CloseHandle(handle)

    def set_feature(self, handle, packet):
        buffer = C.create_string_buffer(packet, len(packet))
        if not self.hid.HidD_SetFeature(handle, buffer, len(packet)):
            raise LightingError(f"Keyboard transfer failed: {C.WinError(C.get_last_error())}. No automatic retry.")

    def read_region(self, short_handle, long_handle, address):
        import time
        # Vendor's read helpers: 83/C6 config, 85/variable memory page.
        if address not in (0xC6, 0xC8):
            raise LightingError("Unsupported lighting read address.")
        opcode = 0x83 if address == 0xC6 else 0x85
        self.set_feature(short_handle, bytes([5, opcode, address, 0, 0, 0, 0]))
        time.sleep(0.04)
        buffer = C.create_string_buffer(1032)
        buffer[0] = b"\x06"
        if not self.hid.HidD_GetFeature(long_handle, buffer, 1032):
            raise LightingError(f"Cannot read keyboard settings: {C.WinError(C.get_last_error())}")
        return bytes(buffer)

    def apply_static(self, pair, color):
        import time
        from .k621 import encode_static, verify_static
        handles = []
        try:
            for device in (pair.short, pair.long):
                handle = self.open(device.path, write=True)
                handles.append(handle)
                if self.describe(handle, device.path) != device.fingerprint:
                    raise LightingError("Keyboard identity changed; reconnect and refresh.")
            short, long = handles
            config = self.read_region(short, long, 0xC6)
            palette = self.read_region(short, long, 0xC8)
            colors, mode = encode_static(config, palette, color)
            # No keymap (04/D8), macro (05), or other palette (09/CC,D0) writes.
            self.set_feature(long, colors)
            time.sleep(0.07)
            self.set_feature(long, mode)
            time.sleep(0.1)
            verify_static(self.read_region(short, long, 0xC6),
                          self.read_region(short, long, 0xC8), colors, mode)
        finally:
            for handle in reversed(handles):
                self.kernel.CloseHandle(handle)
