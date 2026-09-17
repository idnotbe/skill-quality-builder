#!/usr/bin/env python3
"""Run one prepared packet through an explicitly authorized, trusted host adapter.

Dry-run by default. No built-in API client, login, installer or shell expansion.
A fresh process/cwd is not an OS sandbox; the adapter must enforce host permissions,
isolate sessions and keep judge files and credentials out of the actor's context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from prepare_evals import packet_manifest, write_json
from summarize_evals import canonical_digest, fixture_path, load_json, nonempty, require, sha256_string

MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def stop_process(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run(packet: Path, output: Path, argv: list[str], *, execute: bool = False,
        timeout: float = 300, expected_packet_sha: str | None = None, max_output_bytes: int = MAX_OUTPUT_BYTES) -> dict[str, Any]:
    packet = packet.resolve()
    request = load_json(packet / "request.json")
    require(type(request.get("schema_version")) is int and request["schema_version"] == 1 and nonempty(request.get("run_id")) and nonempty(request.get("prompt")), "Invalid packet request.")
    require(request.get("activation") in {"implicit", "explicit"}, "Unknown activation mode.")
    inputs = request.get("input_files")
    require(isinstance(inputs, list) and all(fixture_path(x) for x in inputs), "Invalid input file paths.")
    skill = request.get("skill_directory")
    require(skill is None or fixture_path(skill), "Invalid skill directory.")
    for relative in inputs + ([skill] if skill else []):
        path = (packet / relative).resolve()
        require(path.is_relative_to(packet) and path.exists(), "Packet references missing or outside content.")
    manifest = load_json(packet / ".packet-manifest.json")
    require(manifest == packet_manifest(packet), "Packet changed after preparation; prepare and bind a new experiment.")
    digest = canonical_digest(manifest)
    if execute or expected_packet_sha is not None:
        require(sha256_string(expected_packet_sha) and digest == expected_packet_sha,
                "Supply the expected packet SHA-256 from the separate judge index before execution.")
    require(isinstance(argv, list) and bool(argv) and all(nonempty(x) and "\x00" not in x for x in argv), "Provide trusted adapter argv after --.")
    require(Path(argv[0]).is_absolute() and Path(argv[0]).is_file(), "Adapter executable must be an absolute existing file path.")
    require(Path(argv[0]).suffix.lower() not in {".bat", ".cmd"}, "Use a direct executable, not a shell batch file.")
    require(type(timeout) in (int, float) and 0 < timeout <= 3600, "Timeout must be in (0, 3600] seconds.")
    require(type(max_output_bytes) is int and 0 < max_output_bytes <= MAX_OUTPUT_BYTES, "Invalid output limit.")
    output = Path(os.path.abspath(output.expanduser()))
    require(not output.exists() and not output.is_symlink() and output.parent.is_dir(), "Output must be new with an existing parent.")
    require(not output.resolve().is_relative_to(packet), "Keep observations outside the actor packet.")
    require(not output.resolve().is_relative_to(Path(__file__).resolve().parent.parent), "Keep logs outside the installed skill.")
    result = {"schema_version": 1, "run_id": request["run_id"], "request_sha256": canonical_digest(request),
              "packet_sha256": digest, "adapter_argv_sha256": canonical_digest(argv), "status": "not_run", "graded": False,
              "evidence_independently_verified": False,
              "limitations": "Adapter transport evidence only; does not prove real host selection, model identity, sandboxing, or task quality."}
    if not execute:
        return result
    output.mkdir(exist_ok=False)
    start = time.monotonic()
    status = "completed"
    with (packet / "request.json").open("rb") as stdin, (output / "stdout.bin").open("xb") as stdout, (output / "stderr.bin").open("xb") as stderr:
        try:
            process = subprocess.Popen(argv, cwd=packet, stdin=stdin, stdout=stdout, stderr=stderr,
                                       shell=False, start_new_session=os.name != "nt")
        except OSError as exc:
            result.update(status="launch_error", error=str(exc), duration_seconds=time.monotonic() - start)
            write_json(output / "result.json", result)
            return result
        try:
            while process.poll() is None:
                if sum((output / p).stat().st_size for p in ("stdout.bin", "stderr.bin")) > max_output_bytes:
                    status = "output_limit"
                    stop_process(process)
                    break
                if time.monotonic() - start > timeout:
                    status = "timeout"
                    stop_process(process)
                    break
                time.sleep(0.02)
        finally:
            if process.poll() is None:
                stop_process(process)
    result.update(status=status, exit_code=process.returncode, duration_seconds=time.monotonic() - start)
    if sum((output / p).stat().st_size for p in ("stdout.bin", "stderr.bin")) > max_output_bytes:
        result["status"] = "output_limit"
    if result["status"] == "completed" and process.returncode:
        result["status"] = "adapter_error"
    if result["status"] == "completed":
        try:
            response = load_json(output / "stdout.bin")
            require(isinstance(response.get("output"), str), "Adapter response needs output text (empty is allowed).")
            require(isinstance(response.get("events"), list) and all(isinstance(x, dict) for x in response["events"]), "Adapter response needs an events list of objects.")
            result["response"] = response
            result["response_sha256"] = canonical_digest(response)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            result.update(status="invalid_response", error=str(exc))
    # Bound retained logs too; the polling limit is not a hard disk quota.
    for name in ("stdout.bin", "stderr.bin"):
        path = output / name
        with path.open("r+b") as stream:
            stream.truncate(min(path.stat().st_size, max_output_bytes))
    write_json(output / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-packet-sha", help="SHA-256 from judge/index.json; required for execution")
    parser.add_argument("--timeout", type=float, default=300)
    # Split adapter args explicitly; never load commands from an untrusted suite.
    arguments = sys.argv[1:]
    split = arguments.index("--") if "--" in arguments else len(arguments)
    args = parser.parse_args(arguments[:split])
    argv = arguments[split + 1:]
    try:
        result = run(args.packet, args.output, argv, execute=args.execute, timeout=args.timeout, expected_packet_sha=args.expected_packet_sha)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"Cannot run packet: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"not_run", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
