"""Record HID feature calls from the extracted K621 app, without a USB driver.

Development-only: requires frida. No key-input hooks or raw USB traffic capture.
Raw captures may contain device configuration; keep them local and ignored.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import threading


HOOK = r"""
const handles = new Map();
const kernel = Process.getModuleByName('kernel32.dll');
Interceptor.attach(kernel.getExportByName('CreateFileW'), {
  onEnter(args) { this.path = args[0].readUtf16String(); },
  onLeave(result) {
    if (this.path && this.path.toLowerCase().includes('vid_258a&pid_0049')) {
      handles.set(result.toString(), this.path);
      send({kind: 'open', handle: result.toString(), path: this.path});
    }
  }
});
let hooked = false;
function hook(module) {
  if (hooked || module.name.toLowerCase() !== 'hid.dll') return;
  hooked = true;
  const attributes = new NativeFunction(module.getExportByName('HidD_GetAttributes'), 'uchar', ['pointer', 'pointer']);
  for (const name of ['HidD_SetFeature', 'HidD_GetFeature']) {
    Interceptor.attach(module.getExportByName(name), {
      onEnter(args) {
        this.handle = args[0].toString();
        this.buffer = args[1];
        this.length = args[2].toUInt32();
        if (!handles.has(this.handle)) {
          const attrs = Memory.alloc(12); attrs.writeU32(12);
          if (attributes(args[0], attrs) && attrs.add(4).readU16() === 0x258a && attrs.add(6).readU16() === 0x0049) {
            handles.set(this.handle, 'existing K621-family handle');
          }
        }
        this.enabled = handles.has(this.handle) && this.length > 0 && this.length <= 4096;
        if (this.enabled) {
          this.before = Array.from(new Uint8Array(this.buffer.readByteArray(this.length)));
        }
      },
      onLeave(result) {
        if (this.enabled) {
          send({kind: name, handle: this.handle, length: this.length,
                ok: !result.isNull(), before: this.before,
                after: Array.from(new Uint8Array(this.buffer.readByteArray(this.length)))});
        }
      }
    });
  }
  send({kind: 'ready', message: 'Feature report hooks active; no keyboard-input hooks.'});
}
Process.attachModuleObserver({ onAdded: hook });
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--attach", type=int, help="Attach to an already running vendor-app PID")
    args = parser.parse_args()
    import frida
    executable = args.exe.resolve(strict=True)
    if executable.name.lower() != "keyboarddrv.exe":
        parser.error("Only the reviewed non-PRO KeyboardDrv.exe entry point is allowed; never Update.exe.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    with args.output.open("a", encoding="utf-8", buffering=1) as output:
        def record(message, data):
            event = {"time": datetime.now(timezone.utc).isoformat(), "message": message}
            with lock:
                output.write(json.dumps(event) + "\n")
            if message.get("type") == "error":
                print(message, flush=True)

        device = frida.get_local_device()
        pid = args.attach or device.spawn([str(executable)], cwd=str(executable.parent))
        session = None
        try:
            session = device.attach(pid)
            script = session.create_script(HOOK)
            script.on("message", record)
            script.load()
            if not args.attach:
                device.resume(pid)
            print(f"Recording vendor HID feature calls from PID {pid} to {args.output}", flush=True)
            print("Close the vendor app or press Ctrl+C to stop. Never run its firmware updater.", flush=True)
            stopped = threading.Event()
            session.on("detached", lambda *_: stopped.set())
            stopped.wait()
        except KeyboardInterrupt:
            pass
        finally:
            if session:
                session.detach()
            if not args.attach:
                try:
                    device.kill(pid)
                except frida.ProcessNotFoundError:
                    pass


if __name__ == "__main__":
    main()
