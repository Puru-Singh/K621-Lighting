# Native Windows app validation

## Version 1.0.1 update

- Last applied colors replaces presets. Up to 12 unique colors persist newest
  first and are recorded only after successful Apply. Existing saved colors
  migrate; choosing/editing a color does not add it to history.
- Added eight history checks covering migration, empty history, repeat ordering,
  capacity, JSON roundtrip, malformed entries, and invalid input. All 51 native
  checks pass in both the build and the upgraded installed app. UI self-tests
  additionally confirm draft color edits do not modify history.
- Refresh uses zero button padding with centered, bounded glyph content. Dark
  and light renders were checked; the complete refresh arrow is visible.
- The 1.0.1 installer upgraded the existing installation successfully and its
  version registration was verified. The preferences file remained unchanged
  during installation. MSIX validation and Python/C# packet parity passed again.
- No lighting protocol changes or additional hardware writes were needed for
  this UI/preferences update. Original hardware verification follows below.

## Completed

- C# build: .NET SDK 10.0.402, zero compile warnings/errors.
- Native protocol self-tests: 43 passing checks across RGB parsing, six colors,
  full preservation of unrelated bytes, readback mismatch detection, exact HID
  pairing, ambiguous/incomplete/cross-device/wrong-revision rejection, and native
  Windows HID structure sizes.
- Cross-language parity: SHA-256 comparisons confirm C# produces byte-for-byte
  identical C6/C8 write packets to the physically verified Python encoder for
  red, green, blue, white, mixed color, and off.
- Native UI self-test: connected Apply is enabled; invalid hex disables it;
  selecting a valid color restores it. The test does not program a keyboard.
- Dark and light client areas rendered and visually inspected at 444×760 DIPs.
  Both use Fluent control styling, correct text contrast, readable fields, a
  full-width accent Apply button, and an unclipped footer. Smaller window heights
  scroll. Controls have keyboard navigation and accessible names.
- Neither UI construction, preview rendering, nor native metadata diagnostics
  sends lighting updates. Native diagnostics reported the same disconnected
  state as the Python app during the initial UI build.

## Packaging

The generated setup is a per-user Inno installer with a Start menu shortcut,
Installed apps registration, stable upgrade ID, silent install support, and
normal uninstall. The bundled .NET runtime removes any prerequisite download
for users. MakeAppx validates the MSIX schema and package contents during build.
The unsigned MSIX requires Store identity/signing for public Store distribution.

The per-user installer completed with exit code 0. The installed executable at
`%LOCALAPPDATA%\Programs\K621Lighting\K621Lighting.exe` passed all 43 native
protocol checks. Its Start menu shortcut and HKCU Installed apps/uninstall
registration were checked: display name K621 Lighting, version 1.0.0. The
installed diagnostic ran successfully and reported the keyboard disconnected.

The initial build checks took place while USB was disconnected. After the user
reconnected the keyboard, the installed native app detected the correct device,
applied lavender `#A78BFA`, and successfully verified its C6/C8 readback. Independent
Python snapshots before/after found only C8 RGB offsets 29–31 changed: the entire
C6 configuration, CC/D0 color tables, and D8 key-assignment page were unchanged.
The original `#BB1C00` color was then restored through the installed native app,
again with successful device readback. Native hardware verification is complete.

MakeAppx created and validated the unsigned MSIX successfully. The Inno installer
supports per-user silent installation and does not launch the UI during a silent
install. Its normal uninstall registration is present; uninstall was not run
because the requested app is left installed for use. No Store or winget public
submission was made, and no package signing certificate was silently trusted.
