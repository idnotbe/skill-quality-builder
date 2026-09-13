#!/usr/bin/env python3
"""Create only a minimal DRAFT skill; never overwrite. No install, network, or model call."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from skill_lib import init_skill


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--output-parent", type=Path, required=True, help="Explicit workspace directory")
    args = parser.parse_args()
    try:
        path = init_skill(args.name, args.description, args.output_parent)
    except (OSError, ValueError) as exc:
        print(f"Cannot initialize: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"created": str(path), "state": "draft", "validation": "not_run", "installed": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
