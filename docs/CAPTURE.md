# Reproducing the local K621 investigation

The original non-PRO package was extracted with innoextract, without running its
installer or firmware updater. The PRO package was inspected offline only.
Raw packages and captures stay under ignored `research/vendor` and
`research/captures` directories; do not commit configuration dumps.

## Capture path used

USBPcap/Wireshark were not installed. Instead, development-only Frida hooks
recorded `HidD_SetFeature` and `HidD_GetFeature` calls in the matching vendor app.
This records the application buffers and return values, not USB wire framing.
The logger filters handles by the K621-family USB IDs. It does not intercept
keyboard input, hook other applications, or install a capture driver.

With Frida installed in the development environment, start logging before the app
is launched, or attach to its PID if it is already visible:

```powershell
.\.venv\Scripts\python.exe tools\capture_vendor.py research\vendor\k621\app\KeyboardDrv.exe research\captures\session.jsonl
# Alternatively add: --attach <vendor-app-PID>
```

For desktop automation the extracted app was launched visibly via Computer Use
and the logger attached afterward. Attaching may require elevation depending on
the app's process permissions. Do not run `Update.exe` in either extracted package.

In the original app, select **Light → Fixed_on**, uncheck **RGB** (multicolor),
and keep brightness fixed. Apply red, green, blue, a mixed color such as
`#123456`, and then the identical mixed color again. Record action boundaries and
ensure every Apply has completed before the next. Confirm physical color changes
and normal typing separately: a successful API return does not verify the LEDs.
Close the vendor app to detach the logger.

Generate a sanitized summary without exporting the configuration blocks:

```powershell
python tools\analyze_capture.py research\captures\session.jsonl --output research\capture-summary.json
```

## Protocol recovery completed for v0.2.0

Read-modify-write recovery and native on-device verification are documented in
`PROTOCOL.md`. The current backend replaces only C8 color bytes and C6 lighting
fields, with exact readback verification. No raw capture template is replayed.

## Historical investigation checklist

1. Decode the lighting-mode/configuration report and distinguish fields for the
   active profile from other profiles, key assignments, macros, and reserved data.
2. Establish a minimal lighting transaction from the observed calls, including
   any read-modify-write behavior needed to preserve unrelated settings. Do not
   replay a captured user's full configuration as a universal template.
3. Resolve the short-report length discrepancy: descriptor length 6, vendor API
   calls with buffers of 7 bytes (and 8/9 bytes for version queries). API-call
   logging alone does not establish what bytes reach the USB wire. Use a narrowly
   filtered USBPcap capture if necessary; capture only this keyboard's control
   transfers and exclude keyboard-input traffic.
4. Add the reviewed encoder and complete interface matching to the built-in
   protocol registry; no external JSON profile can unlock writes.
5. Verify primary colors, white, mixed color, normal typing, existing macros/key
   assignments, and persistence after app exit, reconnect, power cycle, and
   switching to wireless. Record each outcome; do not infer persistence.

Raw captures can include current profiles and key assignments. Keep them local;
share only reviewed and sanitized fixtures with clear hardware provenance.
