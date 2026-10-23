"""Offline investigation helper; never opens a device or runs vendor code."""
import argparse
import json
from pathlib import Path


def trace():
    for line in Path("research/captures/lighting-session.jsonl").read_text().splitlines():
        e = json.loads(line)
        p = e["message"].get("payload", {})
        k = p.get("kind", "")
        if k not in ("HidD_SetFeature", "HidD_GetFeature"):
            continue
        b = p["before"]
        print(e["time"][11:23], k[5:], len(b), bytes(b[:8]).hex(" "),
              b[29:32] if b[:3] == [6, 8, 200] else "")


def xrefs(needle):
    import pefile
    import capstone
    p = pefile.PE("research/vendor/k621/app/KeyboardDrv.exe")
    base = p.OPTIONAL_HEADER.ImageBase
    data = p.get_memory_mapped_image()
    address = int(needle, 16) if needle.startswith("0x") else base + data.index(needle.encode() + b"\0")
    print("Address", hex(address))
    dis = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    dis.detail = True
    dis.skipdata = True
    code = p.sections[0]
    hits = []
    for i in dis.disasm(code.get_data(), base + code.VirtualAddress):
        if not i.id:
            continue
        if any((op.type == capstone.x86.X86_OP_IMM and op.imm == address) or
               (op.type == capstone.x86.X86_OP_MEM and op.mem.disp == address)
               for op in i.operands):
            hits.append(i.address)
    for hit in hits:
        print("\nXREF", hex(hit))
        if len(hits) > 12:
            continue
        # Disassembly boundary is only reliable at the matched instruction.
        for i in dis.disasm(data[hit-base:hit-base+110], hit):
            print(hex(i.address), i.mnemonic, i.op_str)


def dump(start, length):
    import pefile
    import capstone
    p = pefile.PE("research/vendor/k621/app/KeyboardDrv.exe")
    base = p.OPTIONAL_HEADER.ImageBase
    data = p.get_memory_mapped_image()
    dis = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for i in dis.disasm(data[start-base:start-base+length], start):
        print(hex(i.address), i.mnemonic, i.op_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["trace", "xref", "dump"])
    parser.add_argument("argument", nargs="?")
    parser.add_argument("length", nargs="?", type=int, default=300)
    args = parser.parse_args()
    if args.action == "trace":
        trace()
    elif args.action == "xref":
        xrefs(args.argument)
    else:
        dump(int(args.argument, 16), args.length)
