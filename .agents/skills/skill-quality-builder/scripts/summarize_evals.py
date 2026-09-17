#!/usr/bin/env python3
"""Aggregate supplied observations, not execute evaluations or certify their truth.

Stdlib only, no model calls. Missing observations remain not_run. Exit 0 for valid
input (including failed/unverified results); exit 2 for invalid input. Inspect the
JSON result rather than treating process success as evaluation success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

STATUSES = {"pass", "fail", "not_run", "not_applicable"}
EVIDENCE_KINDS = {"host_run", "manual_artifact_review", "simulation"}
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_SLOTS = 100000
MAX_FIXTURE_FILES = 2000
MAX_FIXTURE_TOTAL_BYTES = 100 * 1024 * 1024
DIMENSIONS = {"completion", "correctness", "judgment", "usefulness", "safety", "format", "unspecified"}
EXECUTION_FIELDS = ("executor_model", "host_version", "effort", "thinking_mode", "output_budget", "instruction_stack_sha256", "profile_sha256")


class EvaluationError(ValueError):
    """Invalid evaluation schema or contradictory identifiers."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def read_regular_bytes(path: Path, limit: int) -> bytes:
    """Bounded read without blocking on a POSIX FIFO; inspect stable snapshots only."""
    entry = path.stat()
    require(stat.S_ISREG(entry.st_mode), "Input must be a regular file.")
    require(entry.st_size <= limit, f"Input exceeds the {limit}-byte limit.")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "Input must be a regular file.")
        payload = stream.read(limit + 1)
    require(len(payload) <= limit, f"Input exceeds the {limit}-byte limit.")
    return payload


def load_json(path: Path) -> dict[str, Any]:
    # Reject duplicate JSON keys rather than silently retaining the last value.
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON property: {key}")
            result[key] = value
        return result
    payload = read_regular_bytes(path, MAX_JSON_BYTES)
    value = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs)
    require(isinstance(value, dict), "Top-level JSON must be an object.")
    return value


def canonical_digest(value: Any) -> str:
    """SHA-256 of canonical UTF-8 JSON; formatting is not part of suite identity."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_string(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def fixture_path(value: Any) -> bool:
    return (nonempty(value) and not any(ord(c) < 32 for c in value) and "\\" not in value and ":" not in value
            and not value.startswith("/") and all(part not in ("", ".", "..") for part in value.split("/")))


def verify_fixture_files(suite: dict[str, Any], directory: Path) -> None:
    """Verify declared fixed input bytes without executing them; stable snapshots only."""
    root = directory.resolve()
    total = 0
    fixtures = suite.get("fixtures", {})
    require(len(fixtures) <= MAX_FIXTURE_FILES, "Too many fixture files.")
    for relative, expected in fixtures.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), f"Fixture escapes the suite directory: {relative}")
        content = read_regular_bytes(path, min(MAX_JSON_BYTES, MAX_FIXTURE_TOTAL_BYTES - total))
        total += len(content)
        require(hashlib.sha256(content).hexdigest() == expected, f"Fixture digest mismatch: {relative}")


def validate_provenance(suite: dict[str, Any], observations: dict[str, Any]) -> str:
    """Check declared identities, not whether the supplied observations are true."""
    if not observations["observations"]:
        return "not_run"
    binding = observations.get("provenance")
    if binding is None and not suite.get("require_provenance", False):
        return "unbound"
    require(isinstance(binding, dict), "Nonempty observations require a provenance object.")
    require(binding.get("suite_sha256") == canonical_digest(suite), "Suite digest mismatch.")
    by_condition = binding.get("conditions")
    require(isinstance(by_condition, dict) and set(by_condition) == set(suite["conditions"]),
            "Provenance must identify exactly the declared conditions.")
    expected_fixtures = canonical_digest(suite.get("fixtures", {}))
    contexts = []
    environment_keys = ("model", "host", "tools", "permissions", "budget")
    environments = []
    for condition in suite["conditions"]:
        info = by_condition[condition]
        require(isinstance(info, dict), f"Invalid provenance for {condition}.")
        identity = info.get("skill_sha256")
        require(sha256_string(identity) or (condition == "baseline" and identity == "no_skill"),
                f"{condition} needs a skill SHA-256; only baseline may use no_skill.")
        require(info.get("fixtures_sha256") == expected_fixtures, f"Fixture manifest digest mismatch: {condition}")
        for key in environment_keys:
            require(nonempty(info.get(key)), f"Provenance {condition}.{key} must be nonempty.")
        require(info["model"] == observations["metadata"]["model"] and info["host"] == observations["metadata"]["host"],
                f"Global model/host metadata disagrees with {condition}.")
        environments.append(tuple(info[key] for key in environment_keys))
        context = info.get("execution_context")
        if suite.get("require_execution_context", False) or context is not None:
            require(isinstance(context, dict), f"{condition} needs execution_context.")
            for key in EXECUTION_FIELDS:
                require(nonempty(context.get(key)), f"{condition}.execution_context.{key} is required.")
            require(context["executor_model"] == info["model"], "Executor model disagrees with condition model.")
            for key in ("instruction_stack_sha256", "profile_sha256"):
                require(sha256_string(context[key]), f"{condition}.{key} must be a SHA-256 digest.")
            require(nonempty(context.get("builder_model")), f"{condition} needs builder_model (or none for a human/no-skill baseline).")
            contexts.append(tuple(context[key] for key in EXECUTION_FIELDS))
    require(not contexts or len(contexts) == len(suite["conditions"]), "Do not mix bound and unbound execution contexts.")
    require(not contexts or all(item == contexts[0] for item in contexts),
            "Executor settings differ: compare skill candidates within matched model/host/effort cohorts.")
    require(all(env == environments[0] for env in environments), "Baseline/candidate environment mismatch.")
    return "declared_identities_match"


def validate_suite(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(isinstance(suite, dict), "Suite must be an object.")
    require(type(suite.get("schema_version")) is int and suite["schema_version"] == 1, "Suite schema_version must be integer 1.")
    require(nonempty(suite.get("suite_id")), "suite_id must be a nonempty string.")
    require(type(suite.get("require_provenance", False)) is bool, "require_provenance must be Boolean.")
    require(type(suite.get("require_execution_context", False)) is bool, "require_execution_context must be Boolean.")
    require(not suite.get("require_execution_context") or suite.get("require_provenance"), "Execution context requires provenance.")
    fixtures = suite.get("fixtures", {})
    require(isinstance(fixtures, dict), "fixtures must be a path-to-SHA256 object.")
    require(len(fixtures) <= MAX_FIXTURE_FILES, "Too many fixture files.")
    require(all(fixture_path(path) and sha256_string(digest) for path, digest in fixtures.items()),
            "Fixture paths must be contained relative paths and digests lowercase SHA-256.")
    common = suite.get("common_checks", [])
    require(isinstance(common, list), "common_checks must be a list.")
    # Validate even when a suite has no outcome cases; do not silently ignore malformed checks.
    common_ids = set()
    for check in common:
        require(isinstance(check, dict) and nonempty(check.get("id")) and nonempty(check.get("text"))
                and type(check.get("critical")) is bool, "Invalid common check.")
        require(check["id"] not in common_ids, "Duplicate common check id.")
        require(isinstance(check.get("dimension", "unspecified"), str) and check.get("dimension", "unspecified") in DIMENSIONS, "Unknown common check dimension.")
        common_ids.add(check["id"])
    conditions = suite.get("conditions")
    require(isinstance(conditions, list) and len(conditions) > 0, "conditions must be a nonempty list.")
    require(all(nonempty(x) for x in conditions), "Every condition must be a nonempty string.")
    require(len(set(conditions)) == len(conditions), "Duplicate conditions.")
    reps = suite.get("repetitions")
    require(positive_int(reps), "repetitions must be a positive integer, not a Boolean.")
    cases = suite.get("cases")
    require(isinstance(cases, list) and len(cases) > 0, "cases must be nonempty.")
    case_map: dict[str, dict[str, Any]] = {}
    units = 0
    for case in cases:
        require(isinstance(case, dict), "Each case must be an object.")
        case = dict(case)  # Expand checks without mutating the caller's suite or its digest.
        cid = case.get("id")
        require(nonempty(cid), "Each case needs a nonempty id.")
        require(cid not in case_map, f"Duplicate case id: {cid}")
        require(nonempty(case.get("prompt")), f"Case {cid} needs a prompt.")
        require(type(case.get("critical")) is bool, f"Case {cid} critical must be Boolean.")
        require(case.get("evaluation_role", "regression") in ("regression", "capability"), f"Unknown evaluation_role for {cid}.")
        inputs = case.get("input_files", [])
        require(isinstance(inputs, list) and all(isinstance(x, str) and x in fixtures for x in inputs),
                f"{cid}.input_files must select declared fixture paths, never judge-only answers.")
        require(len(set(inputs)) == len(inputs), f"Duplicate input_files in {cid}.")
        kind = case.get("kind")
        require(kind in ("trigger", "outcome"), f"Unknown kind for {cid}.")
        if kind == "trigger":
            require(type(case.get("should_trigger")) is bool, f"Case {cid} should_trigger must be Boolean.")
            units += 1
        else:
            checks = case.get("checks")
            require(isinstance(checks, list), f"Outcome {cid} needs a checks list.")
            checks = list(common) + checks
            require(len(checks) > 0, f"Outcome {cid} needs checks.")
            case["checks"] = checks
            ids: set[str] = set()
            for check in checks:
                require(isinstance(check, dict), f"Invalid check in {cid}.")
                check_id = check.get("id")
                require(nonempty(check_id), f"Check in {cid} needs an id.")
                require(check_id not in ids, f"Duplicate check id in {cid}: {check_id}")
                require(nonempty(check.get("text")), f"Check {cid}/{check_id} needs text.")
                require(type(check.get("critical")) is bool, f"Check {cid}/{check_id} critical must be Boolean.")
                require(isinstance(check.get("dimension", "unspecified"), str) and check.get("dimension", "unspecified") in DIMENSIONS, f"Unknown dimension: {cid}/{check_id}")
                ids.add(check_id)
            units += len(checks)
        case_map[cid] = case
    require(units * len(conditions) * reps <= MAX_SLOTS, f"Evaluation exceeds {MAX_SLOTS} expected assertion slots.")
    return case_map


def summarize(suite: dict[str, Any], observation_file: dict[str, Any]) -> dict[str, Any]:
    case_map = validate_suite(suite)
    require(isinstance(observation_file, dict), "Observation file must be an object.")
    require(type(observation_file.get("schema_version")) is int and observation_file["schema_version"] == 1, "Observations schema_version must be integer 1.")
    require(observation_file.get("suite_id") == suite["suite_id"], "suite_id mismatch.")
    rows = observation_file.get("observations")
    require(isinstance(rows, list), "observations must be a list.")
    metadata = observation_file.get("metadata")
    require(isinstance(metadata, dict), "metadata must be an object.")
    if rows:
        for key in ("model", "host", "skill_version", "run_context"):
            require(nonempty(metadata.get(key)), f"Nonempty observations require metadata.{key}.")
        require(metadata.get("evidence_kind") in EVIDENCE_KINDS, "Unknown or missing metadata.evidence_kind.")
    provenance_status = validate_provenance(suite, observation_file)
    conditions = suite["conditions"]
    reps = suite["repetitions"]
    indexed: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in rows:
        require(isinstance(row, dict), "Each observation must be an object.")
        cid = row.get("case_id")
        require(isinstance(cid, str) and cid in case_map, f"Unknown case_id: {cid}")
        condition = row.get("condition")
        require(isinstance(condition, str) and condition in conditions, f"Unknown condition: {condition}")
        rep = row.get("repetition")
        require(positive_int(rep) and rep <= reps, "repetition is outside the suite range.")
        key = (cid, condition, rep)
        require(key not in indexed, f"Duplicate observation: {key}")
        case = case_map[cid]
        if case["kind"] == "trigger":
            require("triggered" in row and (row["triggered"] is None or type(row["triggered"]) is bool), f"{cid}.triggered must be true, false, or null.")
            if row["triggered"] is not None:
                require(nonempty(row.get("evidence")), f"{cid} needs an evidence reference.")
        else:
            checks = row.get("checks")
            require(isinstance(checks, list), f"{cid} observations need a checks list.")
            allowed = {x["id"] for x in case["checks"]}
            seen: set[str] = set()
            for check in checks:
                require(isinstance(check, dict), f"{cid} contains a non-object check.")
                check_id = check.get("id")
                require(isinstance(check_id, str) and check_id in allowed, f"Unknown check id in {cid}: {check_id}")
                require(check_id not in seen, f"Duplicate observed check in {cid}: {check_id}")
                status = check.get("status")
                require(isinstance(status, str) and status in STATUSES, f"Unknown status in {cid}/{check_id}.")
                if status != "not_run":
                    require(nonempty(check.get("evidence")), f"{cid}/{check_id}: pass/fail/N/A requires evidence.")
                seen.add(check_id)
        indexed[key] = row
    result_conditions: dict[str, Any] = {}
    for condition in conditions:
        confusion = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        outcome_counts = {k: 0 for k in ("pass", "fail", "not_run", "not_applicable")}
        trigger_expected = 0
        trigger_observed = 0
        expected_checks = 0
        supplied_rows = 0
        critical_fail = 0
        critical_na = 0
        critical_missing = 0
        details: list[dict[str, Any]] = []
        for cid, case in case_map.items():
            for rep in range(1, reps + 1):
                row = indexed.get((cid, condition, rep))
                supplied_rows += int(row is not None)
                detail: dict[str, Any] = {"case_id": cid, "repetition": rep, "kind": case["kind"], "evaluation_role": case.get("evaluation_role", "regression"), "split": case.get("split", "unspecified")}
                if case["kind"] == "trigger":
                    trigger_expected += 1
                    triggered = row.get("triggered") if row else None
                    if triggered is None:
                        detail["status"] = "not_run"
                        if case["critical"]:
                            critical_missing += 1
                    else:
                        trigger_observed += 1
                        expected = case["should_trigger"]
                        label = "tp" if expected and triggered else "fn" if expected else "fp" if triggered else "tn"
                        confusion[label] += 1
                        detail["classification"] = label
                        detail["status"] = "pass" if expected == triggered else "fail"
                        if detail["status"] == "fail" and case["critical"]:
                            critical_fail += 1
                        detail["evidence"] = row["evidence"]
                else:
                    seen_checks = {x["id"]: x for x in row["checks"]} if row else {}
                    detailed_checks = []
                    for check in case["checks"]:
                        expected_checks += 1
                        observed = seen_checks.get(check["id"])
                        status = observed["status"] if observed else "not_run"
                        outcome_counts[status] += 1
                        critical = case["critical"] or check["critical"]
                        if critical:
                            critical_fail += int(status == "fail")
                            critical_na += int(status == "not_applicable")
                            critical_missing += int(status == "not_run")
                        detailed_checks.append({"id": check["id"], "dimension": check.get("dimension", "unspecified"), "critical": critical, "status": status, "evidence": observed.get("evidence", "") if observed else ""})
                    detail["checks"] = detailed_checks
                details.append(detail)
        trigger_missing = trigger_expected - trigger_observed
        evaluated_checks = outcome_counts["pass"] + outcome_counts["fail"]
        units_expected = trigger_expected + expected_checks
        units_evaluated = trigger_observed + evaluated_checks
        any_failure = confusion["fp"] + confusion["fn"] + outcome_counts["fail"] > 0
        incomplete = trigger_missing + outcome_counts["not_run"] > 0
        if critical_fail or critical_na:
            status = "blocked"
        elif incomplete or units_evaluated == 0:
            status = "unverified"
        elif any_failure:
            status = "recorded_with_failures"
        else:
            status = "recorded_complete"
        denominator_precision = confusion["tp"] + confusion["fp"]
        denominator_recall = confusion["tp"] + confusion["fn"]
        result_conditions[condition] = {
            "status": status,
            "expected_case_slots": len(case_map) * reps,
            "supplied_case_records": supplied_rows,
            "assertion_coverage": units_evaluated / units_expected if units_expected else None,
            "assertions_expected": units_expected,
            "assertions_evaluated": units_evaluated,
            "trigger": {**confusion, "expected": trigger_expected, "observed": trigger_observed, "not_run": trigger_missing,
                        "coverage": trigger_observed / trigger_expected if trigger_expected else None,
                        "precision": confusion["tp"] / denominator_precision if denominator_precision else None,
                        "recall": confusion["tp"] / denominator_recall if denominator_recall else None},
            "outcome": {**outcome_counts, "expected_checks": expected_checks,
                        "pass_rate_on_pass_fail_only": outcome_counts["pass"] / evaluated_checks if evaluated_checks else None},
            "critical": {"fail": critical_fail, "not_applicable_unresolved": critical_na, "not_run": critical_missing},
            "details": details,
        }
    for condition in result_conditions.values():
        dimensions: dict[str, dict[str, int]] = {}
        roles: dict[str, dict[str, int]] = {}
        for case in condition["details"]:
            if case["kind"] != "outcome":
                continue
            for check in case["checks"]:
                for grouped, name in ((dimensions, check["dimension"]), (roles, case["evaluation_role"])):
                    grouped.setdefault(name, {s: 0 for s in sorted(STATUSES)})[check["status"]] += 1
        condition["by_dimension"] = dimensions
        condition["by_evaluation_role"] = roles
    kind = metadata.get("evidence_kind") if rows else None
    return {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "metadata": metadata,
        "evidence_kind": kind,
        "host_run_records_supplied": bool(rows) and kind == "host_run",
        "evidence_independently_verified": False,
        "provenance_status": provenance_status,
        "suite_sha256": canonical_digest(suite),
        "fixtures_sha256": canonical_digest(suite.get("fixtures", {})),
        "conditions": result_conditions,
        "paired_comparisons": paired_comparisons(result_conditions),
        "notes": [
            "The tool aggregates records only. It does not run a model, verify evidence, or approve a release.",
            "Empty or missing records remain not_run. N/A is never positive evidence; critical N/A blocks validation.",
            "recorded_complete describes supplied records, not proven host performance. Simulation is not a host test.",
            "Coverage counts observed trigger decisions and pass/fail outcome checks, excluding N/A.",
            "Exit code 0 means the input was valid, not that the evaluated skill passed.",
        ],
    }


def paired_comparisons(conditions: dict[str, Any]) -> dict[str, Any]:
    """Descriptive matched assertions, not independent trials or statistical proof."""
    if "baseline" not in conditions:
        return {}
    def flatten(condition: dict[str, Any]) -> dict[tuple[Any, ...], dict[str, Any]]:
        result = {}
        for case in condition["details"]:
            checks = case.get("checks", [{"id": "trigger", "status": case.get("status"), "dimension": "trigger", "critical": False}])
            for check in checks:
                result[(case["case_id"], case["repetition"], check["id"])] = dict(check, evaluation_role=case["evaluation_role"])
        return result
    baseline = flatten(conditions["baseline"])
    comparisons = {}
    for name, condition in conditions.items():
        if name == "baseline":
            continue
        counts = {key: 0 for key in ("improved", "regressed", "both_pass", "both_fail", "not_comparable")}
        by_dimension: dict[str, dict[str, int]] = {}
        for slot, current in flatten(condition).items():
            old = baseline[slot]
            a, b = old["status"], current["status"]
            label = ("not_comparable" if a not in {"pass", "fail"} or b not in {"pass", "fail"}
                     else "improved" if (a, b) == ("fail", "pass")
                     else "regressed" if (a, b) == ("pass", "fail")
                     else "both_pass" if b == "pass" else "both_fail")
            counts[label] += 1
            by_dimension.setdefault(current["dimension"], {k: 0 for k in counts})[label] += 1
        comparisons[name] = {**counts, "by_dimension": by_dimension,
                             "release_recommendation": "not_computed",
                             "interpretation": "Paired assertion counts only; no causal, independent-sample, or model-quality claim. Inspect critical blockers, coverage and cohort identity."}
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    try:
        suite = load_json(args.suite)
        validate_suite(suite)
        verify_fixture_files(suite, args.suite.parent)
        report = summarize(suite, load_json(args.observations))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"Invalid evaluation input: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
