#!/usr/bin/env python3
"""Freeze evaluation packets outside source bundles; never run a model or install skills.

Actor packets contain prompts and explicitly selected inputs, not judge checks.
Directory separation is not a sandbox: a host adapter must restrict what the actor
can see. Use stable trusted snapshots, including an inspected execution-only skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from skill_lib import inventory, is_link_like, lint_skill
from summarize_evals import (canonical_digest, load_json, nonempty, read_regular_bytes,
                             require, validate_provenance, validate_suite, verify_fixture_files)

MAX_PACKETS = 200
MAX_EXPORT_BYTES = 256 * 1024 * 1024
MAX_READ_BYTES = 10 * 1024 * 1024


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def packet_manifest(root: Path) -> dict[str, str]:
    """Hash every file/type, including ignored additions; exclude only this manifest."""
    entries: dict[str, str] = {}
    total = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative == ".packet-manifest.json":
            continue
        info = path.lstat()
        require(not is_link_like(info), f"Packet links/reparse points are not allowed: {relative}")
        require(len(entries) < 8000, "Packet contains too many entries.")
        if stat.S_ISDIR(info.st_mode):
            entries[relative] = "directory"
        else:
            require(stat.S_ISREG(info.st_mode), f"Packet contains a special file: {relative}")
            total += info.st_size
            require(total <= MAX_EXPORT_BYTES, "Packet exceeds byte budget.")
            entries[relative] = hashlib.sha256(read_regular_bytes(path, MAX_READ_BYTES)).hexdigest()
    return entries


def prepare(suite_path: Path, bindings_path: Path, output: Path) -> dict[str, Any]:
    suite = load_json(suite_path)
    cases = validate_suite(suite)
    for case in cases.values():
        require(not case.get("fixture") or bool(case.get("input_files")), "Legacy fixture setup needs explicit input_files; do not silently omit inputs.")
    reserved = {"suite.json", "observations.json", "index.json", "request.json", "skill", ".packet-manifest.json"}
    require(not any(name.split("/")[0] in reserved for name in suite.get("fixtures", {})), "Fixture path collides with packet or judge metadata.")
    verify_fixture_files(suite, suite_path.parent)
    bindings = load_json(bindings_path)
    require(type(bindings.get("schema_version")) is int and bindings["schema_version"] == 1, "Bindings schema_version must be 1.")
    conditions = bindings.get("conditions")
    require(isinstance(conditions, dict) and set(conditions) == set(suite["conditions"]), "Bindings must identify exactly the suite conditions.")
    slots = len(cases) * len(conditions) * suite["repetitions"]
    require(slots <= MAX_PACKETS, f"Limit the experiment to {MAX_PACKETS} packets.")
    environment = bindings.get("environment")
    require(isinstance(environment, dict), "Bindings need environment.")
    for key in ("model", "host", "tools", "permissions", "budget"):
        require(nonempty(environment.get(key)), f"environment.{key} is required.")
    output = Path(os.path.abspath(output.expanduser()))
    require(not output.exists() and not output.is_symlink(), "Output must not already exist.")
    require(output.parent.is_dir(), "Output parent must exist.")
    forbidden = [Path(__file__).resolve().parent.parent]
    frozen: dict[str, tuple[str | None, dict[str, bytes]]] = {}
    provenance: dict[str, Any] = {}
    fixture_bytes = {name: read_regular_bytes(suite_path.parent / name, MAX_READ_BYTES)
                     for name in suite.get("fixtures", {})}
    for name, info in conditions.items():
        require(isinstance(info, dict) and "skill_dir" in info, f"{name} needs skill_dir (null for baseline without a skill).")
        if info["skill_dir"] is None:
            require(name == "baseline", "Only baseline may omit a skill.")
            directory, contents, digest = None, {}, "no_skill"
        else:
            require(nonempty(info["skill_dir"]), "skill_dir must be a nonempty path.")
            root = (bindings_path.parent / info["skill_dir"]).absolute()
            require(lint_skill(root)["errors"] == 0, f"Resolve structural errors before freezing {name}.")
            files, issues, _ = inventory(root)
            require(not any(x["level"] == "error" for x in issues), "Source inventory failed.")
            forbidden.append(root.resolve())
            contents = {p.relative_to(root).as_posix(): read_regular_bytes(p, MAX_READ_BYTES) for p in files}
            directory = root.name
            digest = canonical_digest({p: hashlib.sha256(b).hexdigest() for p, b in contents.items()})
        frozen[name] = (directory, contents)
        provenance[name] = {key: environment[key] for key in ("model", "host", "tools", "permissions", "budget")}
        provenance[name].update(skill_sha256=digest, fixtures_sha256=canonical_digest(suite.get("fixtures", {})))
        context = bindings.get("execution_context")
        if context is not None:
            require(isinstance(context, dict), "execution_context must be an object.")
            provenance[name]["execution_context"] = dict(context, builder_model=info.get("builder_model", ""))
    require(not any(output.resolve().is_relative_to(root) for root in forbidden), "Keep packets outside target and installed skill directories.")
    records = {"schema_version": 1, "suite_id": suite["suite_id"],
               "metadata": {"model": environment["model"], "host": environment["host"],
                            "skill_version": "per-condition hashes in provenance", "run_context": "Prepared only; replace with actual session context before recording results.", "evidence_kind": ""},
               "provenance": {"suite_sha256": canonical_digest(suite), "conditions": provenance}, "observations": []}
    # Validate identity contracts now without inventing an observed assertion.
    validate_provenance(suite, dict(records, observations=[{}]))
    estimated = sum(len(b) for b in fixture_bytes.values()) + len(json.dumps(suite).encode("utf-8"))
    estimated += sum(len(c["prompt"].encode("utf-8")) for c in cases.values()) * len(conditions) * suite["repetitions"]
    for _, content in frozen.values():
        estimated += sum(len(b) for b in content.values()) * len(cases) * suite["repetitions"]
    estimated += sum(sum(len(fixture_bytes[x]) for x in c.get("input_files", [])) for c in cases.values()) * len(conditions) * suite["repetitions"]
    require(estimated <= MAX_EXPORT_BYTES, "Experiment snapshots exceed the 256 MiB export budget.")
    slots_list = [(c, name, r) for c in cases.values() for name in conditions for r in range(1, suite["repetitions"] + 1)]
    secrets.SystemRandom().shuffle(slots_list)
    index = []
    output.mkdir(exist_ok=False)
    try:
        for case, condition, repetition in slots_list:
            run_id = secrets.token_hex(12)
            actor = output / "actors" / run_id
            actor.mkdir(parents=True)
            directory, content = frozen[condition]
            for relative, data in content.items():
                destination = actor / "skill" / directory / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            selected = case.get("input_files", [])
            for relative in selected:
                destination = actor / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(fixture_bytes[relative])
            request = {"schema_version": 1, "run_id": run_id, "prompt": case["prompt"],
                       "activation": "implicit" if case["kind"] == "trigger" else "explicit",
                       "skill_directory": f"skill/{directory}" if directory else None, "input_files": selected}
            write_json(actor / "request.json", request)
            manifest = packet_manifest(actor)
            write_json(actor / ".packet-manifest.json", manifest)
            index.append({"packet_sha256": canonical_digest(manifest), "run_id": run_id, "case_id": case["id"], "condition": condition, "repetition": repetition,
                          "request_sha256": canonical_digest(request), "packet": f"actors/{run_id}"})
        judge = output / "judge"
        write_json(judge / "suite.json", suite)
        write_json(judge / "observations.json", records)
        write_json(judge / "index.json", {"schema_version": 1, "suite_sha256": canonical_digest(suite), "runs": index,
                                          "warning": "Keep this mapping, rubrics and fixtures away from actors. Blinding is procedural, not an access-control boundary."})
        for relative, data in fixture_bytes.items():
            path = judge / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    except BaseException:
        shutil.rmtree(output)
        raise
    return {"output": str(output), "packets": slots, "observations": 0,
            "status": "prepared_not_run", "runtime_validation": "not_run",
            "limitations": "No installation or model call. Inspect target skills for embedded test answers. Adapter isolation and actual host selection remain to be verified."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("bindings", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.suite, args.bindings, args.output), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"Cannot prepare evaluation: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
