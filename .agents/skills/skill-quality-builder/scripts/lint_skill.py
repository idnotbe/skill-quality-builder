#!/usr/bin/env python3
"""Read-only limited structural checks; 0=no errors, 1=checks fail, 2=input/IO error."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
if __name__ == "__main__":
    sys.dont_write_bytecode = True

from skill_lib import lint_skill


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path, help="Skill directory, relative to caller cwd or absolute")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--portability", choices=("portable", "native"), default="portable")
    parser.add_argument("--reference-exempt", action="append", default=[], help="Exact references/*.md path excluded from reachability warnings; record the reason in the review")
    args = parser.parse_args()
    try:
        report = lint_skill(args.skill_dir, portability=args.portability, reference_exemptions=tuple(args.reference_exempt))
    except (OSError, ValueError) as exc:
        print(f"Input/IO error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']}: {report['errors']} errors, {report['warnings']} warnings")
        for item in report["issues"]:
            print(f"{item['level'].upper()} {item['code']} {item.get('path', '')}: {item['message']}")
        print(report["limitations"])
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
