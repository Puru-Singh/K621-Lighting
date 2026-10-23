"""Read layout constants from an isolated vendor process; block programming calls."""
from pathlib import Path
import frida
import json
import time

exe = Path('research/vendor/k621/app/KeyboardDrv.exe').resolve()
device = frida.get_local_device()
pid = device.spawn([str(exe)], cwd=str(exe.parent))
session = None
try:
    session = device.attach(pid)
    script = session.create_script(r'''
Process.attachModuleObserver({ onAdded(module) {
  if (module.name.toLowerCase() !== 'hid.dll') return;
  const addr = module.getExportByName('HidD_SetFeature');
  const original = new NativeFunction(addr, 'uchar', ['pointer', 'pointer', 'uint']);
  Interceptor.replace(addr, new NativeCallback((h, b, n) => {
    if (n < 3) return 0;
    const id=b.readU8(), op=b.add(1).readU8(), address=b.add(2).readU8();
    if (id===5 && ((op & 0x80) || (op===5 && address===0x81))) return original(h,b,n);
    send({blocked: true, prefix: Array.from(new Uint8Array(b.readByteArray(Math.min(n,8))))});
    return 0;
  }, 'uchar', ['pointer', 'pointer', 'uint']));
}});
rpc.exports = { layout() {
  const base=Process.getModuleByName('KeyboardDrv.exe').base;
  const read=(va,n)=>Array.from(new Uint8Array(base.add(va-0x400000).readByteArray(n)));
  return {base:base.toString(), globals:read(0x5d8450,0x50),
          modes:read(0x5d7378,21*60), selected:read(0x5d70ac,4)};
}};
''')
    script.on('message', lambda message, data: print(message, flush=True))
    script.load()
    device.resume(pid)
    time.sleep(2)
    layout = script.exports_sync.layout()
    Path('research/captures/vendor-layout.json').write_text(json.dumps(layout), encoding='utf-8')
    print('Layout constants:',layout['globals'])
    print('Mode hardware IDs:',[layout['modes'][i*60] for i in range(21)])
finally:
    if session:
        session.detach()
    device.kill(pid)
