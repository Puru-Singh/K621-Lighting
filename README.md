# K621 Static Color

**New: native Windows 11 app.** See [native/README.md](native/README.md) for
K621 Lighting 1.0.1, its Fluent interface, installer, MSIX package, and winget
publishing tools. The Python utility below remains as the original verified
implementation and protocol reference.

Portable Windows utility for a Redragon K621-RGB HORUS over USB.

**Version 0.2.0 enables Apply for the original K621-RGB over USB.** The backend
reads the keyboard's current settings, changes the static color and lighting
mode, writes two lighting reports, and verifies them by reading them back.
It does not use the vendor app or write key assignments/macros. See
[protocol findings](docs/PROTOCOL.md).

## Run

Extract the entire `K621StaticColor-portable.zip`, then open
`K621StaticColor/K621StaticColor.exe`. Keep `_internal` next to the EXE. No Python,
installer, administrator privileges, or background service is needed for the app.

Close old v0.1.0 windows and run this version; the title and footer say 0.2.0.
Connect the keyboard by USB in wired mode, choose a color, and click **Apply to
keyboard**. You can then close the app. Static lighting uses maximum brightness;
`#000000` turns the main backlight off. Hardware status indicators may remain lit.

The color picker and `#RRGGBB` input update the preview only. Refresh reads device
metadata. Save diagnostics exports descriptor information without serial numbers
or machine-specific device paths. Apply sends one transaction and remembers
the color only after successful transfer and readback.
Opening the utility never automatically applies a color. Settings are stored at
`%LOCALAPPDATA%\K621StaticColor\settings.json` after a successful application.

## Source and diagnostics

Python 3.14 with Tkinter was used for this build; source runtime imports are all
from the standard library. From the project directory:

```powershell
python app.py
python app.py --diagnose
python app.py --diagnose --output diagnostics.json
python app.py --apply '#123456'
python -m unittest discover -s tests -v
```

`--apply` applies a color and returns a JSON success/error result.
`--diagnose --include-paths` optionally adds local HID paths; these can contain
machine-specific identifiers. A windowed EXE has no console: use `--output` when
running diagnostics from that executable and wait for it to finish, for example:

```powershell
Start-Process -FilePath '.\dist\K621StaticColor\K621StaticColor.exe' -ArgumentList '--diagnose --output diagnostics.json' -Wait -WindowStyle Hidden
```

## Build

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\tools\build.ps1
```

The script runs the tests, builds `dist/K621StaticColor/K621StaticColor.exe`, and
creates `dist/K621StaticColor-portable.zip`. It deliberately uses an unpacked
portable folder so each bounded HID worker can be stopped directly on timeout.
The GUI and command-line apply path limit a worker to 15 seconds, never retry
automatically, and release device handles when a transfer finishes or fails.

## Hardware scope

Only the original K621-RGB is under investigation. The supplied PRO package has
a different wired product ID and must not be used for this keyboard. OpenRGB
integration, wireless writes, firmware changes, per-key editing, animations,
autostart, and resident services are outside this version. USB reconnect, power
cycle, and wireless-mode retention have not been physically tested; reapply over
USB if needed. The app verifies the two HID collections and firmware configuration
layout before programming. Other keyboards sharing VID/PID are not supported.
