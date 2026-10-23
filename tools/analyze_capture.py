"""Summarize local feature captures without exporting raw configuration data."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def analyze(path):
    groups = defaultdict(list)
    failures = []
    for line in path.read_text(encoding="utf-8").splitlines():
        message = json.loads(line)["message"]
        if message.get("type") == "error":
            failures.append("Instrumentation error; inspect the local raw capture.")
        event = message.get("payload", {})
        if event.get("kind") not in ("HidD_GetFeature", "HidD_SetFeature"):
            continue
        if not event.get("ok"):
            failures.append(f"Failed {event['kind']} call")
        packet = event["before"] if event["kind"] == "HidD_SetFeature" else event["after"]
        groups[(event["kind"], len(packet), tuple(packet[:5]))].append(packet)
    summary = []
    for (kind, length, header), packets in groups.items():
        changed = [i for i in range(length) if len({p[i] for p in packets}) > 1]
        summary.append({"call": kind, "length": length, "header_prefix_hex": bytes(header).hex(" "),
                        "count": len(packets), "varying_offsets": changed,
                        "observed_rgb_at_29_31": list(dict.fromkeys(
                            tuple(p[29:32]) for p in packets
                        )) if header[:3] == (6, 8, 200) else None})
    return {"source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source": "Local K621 vendor-app HID API trace; not a USB wire capture",
            "replayable": False, "errors": failures, "groups": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(analyze(args.capture), indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
