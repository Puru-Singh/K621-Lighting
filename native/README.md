# K621 Lighting — native Windows 11 app

K621 Lighting 1.0.2 is a C#/.NET 10 WPF desktop app using Microsoft's built-in
Windows 11 Fluent theme. It has native light/dark/system themes, system accent
colors, rounded cards, keyboard preview, RGB sliders, hex entry, color history,
and a single Apply action. It is not an Electron app or a recolored Tkinter app.
The last 12 successfully applied colors appear newest first; reapplying a color
moves it to the front without duplicates. Editing or choosing a history color
only changes the preview until Apply succeeds. History persists across launches;
upgrading from 1.0 imports the previously remembered color.

## Install and run

Run `artifacts/release/K621Lighting-1.0.2-Setup-x64.exe`. Installation is per-user;
it adds **K621 Lighting** to Start and Windows Settings → Apps → Installed apps.
It supports normal uninstall and future upgrades. No Python, separate .NET
installation, vendor utility, service, startup task, or custom USB driver is needed.

Connect an original K621-RGB HORUS with USB in wired mode. Choose a recent color,
drag the RGB sliders, or type `#RRGGBB`; click **Apply to keyboard**. The keyboard
settings are read back to confirm success. Opening the app never applies a color.
`#000000` turns off the main backlight; hardware indicators are firmware controlled.

The portable ZIP is also available; keep all files together. The runtime is bundled
so the app works without a system-wide .NET install. The application itself does
not access the network.

## Preferences and keyboard safety

Preferences are stored in `%LOCALAPPDATA%\K621Lighting\settings.json`. On first
run, a valid color is imported from the old Python utility's settings if present.
Theme changes save appearance preferences; an edited color is saved only after
a successful Apply. There is no continuous device polling or background daemon.

The C# backend preserves the verified Python protocol: exact collection pairing,
configuration signatures, live read-modify-write of only the C8 RGB bytes and C6
static mode fields, and complete readback verification. Keymap/macro regions are
not programmed. A separate worker has a 15-second timeout and no retries; a
named mutex prevents two native app instances programming the device concurrently.

## Build

Requirements: .NET 10 Windows SDK/runtime packs, Windows SDK MakeAppx, and Inno
Setup 6.7.3. This workspace uses project-local SDK/compiler tools under ignored
`.tools/`. No development tools are included in the installer.

```powershell
.\tools\build-native.ps1
python tools\verify-native-protocol.py
```

The build creates the self-contained app, runs protocol and UI self-tests, builds
the per-user installer, validates an unsigned MSIX, creates a portable ZIP, and
generates SHA-256 checksums. Parameters allow different SDK/compiler paths.

## Microsoft Store and winget

These are distribution channels, separate from the UI framework. MSIX packaging
is already generated; the installer also supports winget's normal Inno switches.
The app has **not** been publicly submitted or listed in either channel.

- **Store:** reserve an app in your Partner Center developer account. Replace the
  local Name/Publisher/PublisherDisplayName in `packaging/AppxManifest.xml` with
  the assigned Store identity, rebuild, run certification checks, and submit the
  MSIX with screenshots, description, privacy information, and support details.
  The package uses `runFullTrust` because USB HID access uses normal desktop APIs.
  The Microsoft Store signs accepted packages; the generated unsigned MSIX is a
  publishing artifact and is not a double-click installer for this PC.
- **winget:** host the exact setup EXE at a stable public HTTPS release URL. Run
  `tools/New-WingetManifest.ps1 -InstallerUrl <actual-HTTPS-download-URL>` to
  generate a manifest with the real installer hash. Validate using `winget validate`
  and test the hosted installer before submitting to the winget community repo.
  The package ID and license can be changed before the first public release.

The normal setup EXE is usable immediately without a Store account, package
certificate trust changes, or enabling Developer Mode. Store publication, code
signing identity, and public hosting are not fabricated by the build scripts.
