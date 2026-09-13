#!/usr/bin/env python3
"""Aggregate supplied observations, not execute evaluations or certify their truth.

Stdlib only, no model calls. Missing observations remain not_run. Exit 0 for valid
input (including failed/unverified results); exit 2 for invalid input. Inspect the
JSON result rather than treating process success as evaluation success.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

STATUSES = {"pass", "fail", "not_run", "not_applicable"}
EVIDENCE_KINDS = {"host_run", "manual_artifact_review", "simulation"}
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_SLOTS = 100000


class EvaluationError(ValueError):
    """Invalid evaluation schema or contradictory identifiers."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvaluationError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def load_json(path: Path) -> dict[str, Any]:
    require(path.stat().st_size <= MAX_JSON_BYTES, "JSON input exceeds the 10 MiB limit.")
    # Reject duplicate JSON keys rather than silently retaining the last value.
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON property: {key}")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    require(isinstance(value, dict), "Top-level JSON must be an object.")
    return value


def validate_suite(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(isinstance(suite, dict), "Suite must be an object.")
    require(type(suite.get("schema_version")) is int and suite["schema_version"] == 1, "Suite schema_version must be integer 1.")
    require(nonempty(suite.get("suite_id")), "suite_id must be a nonempty string.")
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
        cid = case.get("id")
        require(nonempty(cid), "Each case needs a nonempty id.")
        require(cid not in case_map, f"Duplicate case id: {cid}")
        require(nonempty(case.get("prompt")), f"Case {cid} needs a prompt.")
        require(type(case.get("critical")) is bool, f"Case {cid} critical must be Boolean.")
        kind = case.get("kind")
        require(kind in ("trigger", "outcome"), f"Unknown kind for {cid}.")
        if kind == "trigger":
            require(type(case.get("should_trigger")) is bool, f"Case {cid} should_trigger must be Boolean.")
            units += 1
        else:
            checks = case.get("checks")
            require(isinstance(checks, list) and len(checks) > 0, f"Outcome {cid} needs checks.")
            ids: set[str] = set()
            for check in checks:
                require(isinstance(check, dict), f"Invalid check in {cid}.")
                check_id = check.get("id")
                require(nonempty(check_id), f"Check in {cid} needs an id.")
                require(check_id not in ids, f"Duplicate check id in {cid}: {check_id}")
                require(nonempty(check.get("text")), f"Check {cid}/{check_id} needs text.")
                require(type(check.get("critical")) is bool, f"Check {cid}/{check_id} critical must be Boolean.")
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
                detail: dict[str, Any] = {"case_id": cid, "repetition": rep, "kind": case["kind"]}
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
                        detailed_checks.append({"id": check["id"], "critical": critical, "status": status, "evidence": observed.get("evidence", "") if observed else ""})
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
    kind = metadata.get("evidence_kind") if rows else None
    return {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "metadata": metadata,
        "evidence_kind": kind,
        "host_run_records_supplied": bool(rows) and kind == "host_run",
        "evidence_independently_verified": False,
        "conditions": result_conditions,
        "notes": [
            "The tool aggregates records only. It does not run a model, verify evidence, or approve a release.",
            "Empty or missing records remain not_run. N/A is never positive evidence; critical N/A blocks validation.",
            "recorded_complete describes supplied records, not proven host performance. Simulation is not a host test.",
            "Coverage counts observed trigger decisions and pass/fail outcome checks, excluding N/A.",
            "Exit code 0 means the input was valid, not that the evaluated skill passed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    try:
        report = summarize(load_json(args.suite), load_json(args.observations))
    except (OSError, ValueError, TypeError) as exc:
        print(f"Invalid evaluation input: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
