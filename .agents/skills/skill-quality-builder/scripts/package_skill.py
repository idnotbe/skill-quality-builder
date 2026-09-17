#!/usr/bin/env python3
"""Create a checked ZIP, never overwrite or install. Use only a stable trusted snapshot."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any
if __name__ == "__main__":
    sys.dont_write_bytecode = True

from skill_lib import SkillError, inside, inventory, lint_skill


def package_skill(root: Path, output: Path, *, portability: str = "portable") -> dict[str, Any]:
    root = Path(os.path.abspath(root.expanduser()))
    output = output.expanduser().resolve()
    if inside(output, root.resolve()):
        raise SkillError("ZIP output must be outside the skill directory.")
    if output.suffix.lower() != ".zip":
        raise SkillError("Output must have a .zip extension.")
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    if not output.parent.is_dir():
        raise SkillError("Output parent must already exist.")
    report = lint_skill(root, portability=portability)
    if report["errors"]:
        codes = ", ".join(sorted({i["code"] for i in report["issues"] if i["level"] == "error"}))
        raise SkillError(f"Structural errors block packaging: {codes}")
    files, issues, excluded = inventory(root)
    if any(i["level"] == "error" for i in issues):
        raise SkillError("Source inventory changed or failed checks.")
    created = False
    try:
        # Exclusive mode avoids overwriting an existing path even after prechecks.
        with output.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for path in files:
                    if path.is_symlink():
                        raise SkillError("Symlink appeared after inspection; stop.")
                    archive.write(path, (Path(root.name) / path.relative_to(root)).as_posix())
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {"output": str(output), "file_count": len(files), "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "lint_status": report["status"], "warnings": [i for i in report["issues"] if i["level"] == "warning"], "excluded": excluded, "installed": False, "runtime_validation": "not_run", "portability": portability}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--portability", choices=("portable", "native"), default="portable", help="portable rejects incompatible archive names; native is an explicit host-only opt-out")
    args = parser.parse_args()
    try:
        result = package_skill(args.skill_dir, args.output, portability=args.portability)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Packaging refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
