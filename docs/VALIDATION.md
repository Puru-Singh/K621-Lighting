# Validation — v0.2.0, 2026-10-23

## Automated/source checks

- 23 passing tests cover color input, deterministic synthetic fixtures, exact
  collection pairing, wrong revision, incomplete/cross-device/ambiguous pairs,
  malformed responses, readback mismatches, preservation of every unrelated body
  byte, native handle cleanup, and stopping after a partial transfer failure.
- Actual backend tests assert exactly two programming reports: `08/C8` and
  `03/C6`. Keymap/macro/other palette programming is absent.
- Generic template tests use synthetic fixtures only; the K621 backend reads
  current device pages and does not use those templates.

## Hardware checks

- Original K621-RGB collections enumerated without administrator access.
- Vendor-app red/green/blue: physical changes and normal typing confirmed by user.
- Native read helpers recovered from the app read C6/C8/CC/D0/D8. Every body
  matched the last vendor write, establishing the readback layout.
- Standalone `--apply #00FF00`, with vendor app closed: transfer and exact C6/C8
  readback succeeded. Independent snapshots showed only the three C8 RGB bytes
  changed; C6, CC, D0, and the full D8 assignment page were unchanged.
- Red, blue, white, mixed `#123456`, and green applications each passed exact
  device readback. The final state was left green. A final independent snapshot
  again found only RGB offsets 29–31 changed relative to the original snapshot.
- Rebuilt windowed EXE diagnostics reported ready and its green Apply exited 0.
  A hidden source-GUI hardware smoke exercised enabled Apply, bounded worker,
  live HID write/readback, successful status, and saving the selected color to
  temporary settings. No desktop control was used for these checks.
- One research snapshot immediately after rapid color changes could not enumerate
  the long collection. A subsequent normal diagnostic and research snapshot both
  succeeded. The application reports a missing interface and offers Refresh;
  it never guesses a collection or retries a programming transaction.

## Limits

Readback verifies lighting settings; it does not optically measure LEDs.
Persistence after USB reconnect, full power cycle, and switching to wireless must
be physically checked; no autostart task or service is installed. Hardware status
indicator LEDs may have firmware-controlled colors. This backend supports the
original K621-RGB; it does not claim support for PRO or unrelated keyboards.

No firmware updater, PRO utility, USB capture driver, or resident service was
installed or run. Raw local captures/snapshots remain ignored by Git.
