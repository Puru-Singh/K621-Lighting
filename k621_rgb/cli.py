import argparse
import json
from pathlib import Path
import sys

from .protocol import LightingError


def main(argv=None):
    parser = argparse.ArgumentParser(description="K621 static color utility (USB, Windows).")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--diagnose", action="store_true", help="Read descriptors; never send lighting commands")
    action.add_argument("--apply", metavar="#RRGGBB", help="Apply once through a bounded worker")
    # Used by the parent process only. This still enforces the built-in protocol gate.
    action.add_argument("--worker-apply", metavar="#RRGGBB", help=argparse.SUPPRESS)
    parser.add_argument("--include-paths", action="store_true", help="Include machine-specific HID paths in diagnostics")
    parser.add_argument("--output", type=Path, help="Write JSON result to a file (useful for the windowed executable)")
    args = parser.parse_args(argv)
    if not (args.diagnose or args.apply or args.worker_apply):
        from .gui import run
        run()
        return 0
    code = 0
    try:
        from .service import apply_once, inspect_devices, run_bounded
        if args.diagnose:
            payload = inspect_devices(include_paths=args.include_paths)
        elif args.worker_apply:
            apply_once(args.worker_apply)
            payload = {"ok": True, "status": f"Static color {args.worker_apply.upper()} applied and settings read back successfully."}
        else:
            payload = run_bounded("--worker-apply", args.apply)
    except (LightingError, OSError) as exc:
        payload, code = {"ok": False, "error": str(exc)}, 1
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        try:
            args.output.write_text(text, encoding="utf-8")
        except OSError as exc:
            if sys.stderr:
                print(f"Cannot save result: {exc}", file=sys.stderr)
            return 1
    if sys.stdout:
        print(text, end="")
    return code
