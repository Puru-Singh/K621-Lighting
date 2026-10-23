# Original K621-RGB lighting protocol — v0.2.0

The standalone backend is implemented in `k621_rgb/k621.py`. It contains no vendor
code, DLL, firmware image, captured user configuration, or externally loaded
packet template. Native HID transport uses the Windows API through ctypes.

## Hardware provenance

User-confirmed underside label: K621-RGB / HORUS. HID descriptors on this PC:
VID `258A`, PID `0049`, revision `0100`, manufacturer `BY Tech`, product
`Gaming Keyboard`; interface 1, usage page `FF00`, usage `0001`, with separate
feature-report collections of lengths 6 and 1032. Both collections must match
and belong to the same physical HID instance. Read-only descriptor details are
in `research/device-diagnostics.json`. These generic descriptors are not a claim
of support for other models; the configuration signatures are also checked.

Installer SHA-256 provenance:

- Original 1.6.6 / 2021-11-06:
  `50a7f73a942a6e2df862345a0b92a64441f73f01f351063f2fd1a9224c02646a`.
  Its `Cfg.ini` targets `258A:0049` and its app is `KeyboardDrv.exe`.
- PRO 2.0 / 2023-12-01:
  `726e992fba4a80d70f18ba9d80547bf5f0ec4d5853a182536ad6f9a52cbcaff5`.
  Its configuration targets wired `258A:010C`, wireless `3554:FA09`; not run.

Both installers were extracted with innoextract. No firmware updater was run.

## Recovery and evidence

Local Frida hooks recorded only the original app's HID feature-report calls,
without capturing keyboard input or installing a driver. Red, green, blue,
mixed RGB, and repeated mixed RGB buffers were compared. The user confirmed the
vendor application's physical color changes and normal typing.

The vendor's manual Apply button sends key assignments as well as lighting.
Its live RGB-edit path omits those assignment writes. Offline x86 disassembly
then established the read-modify-write behavior and layout:

| Original address | Recovered behavior |
| --- | --- |
| `411040` | Lighting flags, hardware effect ID, per-effect color flags, brightness/speed nibbles |
| `411190` | Reads current config, builds lighting updates; keymap branch is separate |
| `4467E0` / `446870` | HID wrappers prepend report ID, increasing supplied length by one |
| `446A80` / `446B20` | Config write/read: `03/C6` and `83/C6` |
| `446E50` | Lighting table write `08/C8`; 21 reserved bytes before the first color |
| `446FE0` | Page read `85/<address>`; 1024-byte page body |

An isolated vendor process also confirmed its parsed layout constants and mode
hardware IDs, with non-read feature writes blocked during inspection.

Native reads of C6, C8, CC, D0, and D8 were compared against the last vendor
writes: all 1024-byte bodies matched exactly. The utility therefore preserves
live device data instead of replaying defaults. Initial vendor initialization
had changed many fields; subsequent live RGB updates preserved the config body.

## Standalone transaction

Lengths include the report ID byte. Match both collections, open both, and
recheck descriptors. Setup/read calls below do not program the regions.

1. Short collection: `05 83 C6 00 00 00 00`; wait 40 ms. GetFeature report 6,
   length 1032, on the long collection. Require header `06 83 C6 00` and
   `5A A5` signatures at zero-based offsets 14 and 78.
2. Short collection: `05 85 C8 00 00 00 00`; wait 40 ms. GetFeature report 6,
   length 1032. Require response prefix `06 85`.
3. Copy live C8; set header `06 08 C8 00 40 00 00 00`; replace only bytes
   29–31 with requested RGB. SetFeature on the long collection.
4. Wait 70 ms. Copy live C6; set header `06 03 C6 00 00 00 00 00`. Set
   byte 20 to 0 (ordinary effect), byte 21 to 1 (Fixed_on), clear the low
   nibble of byte 38 (single-color selection), and set byte 39's low nibble
   to 9 (brightness). Preserve high nibbles and every other body byte.
   SetFeature on the long collection.
5. Wait 100 ms. Read C6/C8 again; bodies must exactly match the expected write
   bodies or the operation reports failure. Close both handles.

This path does not program `04/D8` key assignments, macro opcode `05`, or other
lighting tables `09/CC,D0`. No retries or firmware operations; the worker has
a 15-second process timeout. The 7-byte short API buffer is deliberate: the
original wrapper prepends the report ID and adds one to its 6-byte payload.
This exact buffer was exercised successfully in native reads on this device.

## On-device results

With the vendor app closed, standalone green returned success and both page
readbacks matched. Independent before/after snapshots found only C8 offsets
29, 30, 31 changed; C6, CC, D0, and the full D8 key-assignment page were unchanged
for that transition. Further checks are recorded in `VALIDATION.md`.

## References

- [Official K621 download page](https://redragonshop.com/blogs/product-download/horus-tkl-k621)
- [OpenRGB K621 misidentification report](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/2679)
- [innoextract](https://constexpr.org/innoextract/)
