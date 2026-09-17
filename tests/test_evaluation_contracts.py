"""Test record binding and shared checks, not the truth of model observations."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import shutil
from unittest.mock import patch
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/skill-quality-builder/scripts"
sys.path.insert(0, str(SCRIPTS))
import summarize_evals
from skill_lib import lint_skill
from summarize_evals import (EvaluationError, canonical_digest, load_json, summarize,
                             validate_suite, verify_fixture_files)


class EvaluationContracts(unittest.TestCase):
    def setUp(self):
        self.suite = {"schema_version": 1, "suite_id": "contract-test", "conditions": ["baseline", "candidate"],
                      "repetitions": 1, "require_provenance": True, "fixtures": {},
                      "common_checks": [{"id": "contract", "text": "Exact output shape", "critical": True}],
                      "cases": [{"id": cid, "kind": "outcome", "prompt": cid, "critical": False, "checks": []}
                                for cid in ("normal", "empty", "adversarial")]}
        self.obs = {"schema_version": 1, "suite_id": "contract-test", "metadata": {
            "model": "synthetic", "host": "unittest", "skill_version": "fixture",
            "run_context": "synthetic records; no agent execution", "evidence_kind": "simulation"},
            "observations": [{"case_id": cid, "condition": condition, "repetition": 1,
                              "checks": [{"id": "contract", "status": "pass", "evidence": "synthetic record"}]}
                             for condition in self.suite["conditions"] for cid in ("normal", "empty", "adversarial")]}
        self.bind()

    def bind(self):
        environment = {"model": "synthetic", "host": "unittest", "tools": "none",
                       "permissions": "no external actions", "budget": "fixed synthetic budget",
                       "fixtures_sha256": canonical_digest(self.suite["fixtures"])}
        self.obs["provenance"] = {"suite_sha256": canonical_digest(self.suite), "conditions": {
            "baseline": dict(environment, skill_sha256="no_skill"),
            "candidate": dict(environment, skill_sha256="a" * 64)}}

    def test_shared_constraints_expand_into_every_outcome_without_mutation(self):
        before = copy.deepcopy(self.suite)
        report = summarize(self.suite, self.obs)
        self.assertEqual(self.suite, before)
        self.assertEqual(report["conditions"]["candidate"]["assertions_expected"], 3)
        self.assertEqual(report["provenance_status"], "declared_identities_match")
        self.assertFalse(report["evidence_independently_verified"])
        self.assertFalse(report["host_run_records_supplied"])

    def test_missing_shared_check_remains_not_run(self):
        self.obs["observations"][-1]["checks"] = []
        result = summarize(self.suite, self.obs)["conditions"]["candidate"]
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["critical"]["not_run"], 1)

    def test_empty_result_cannot_bypass_contract(self):
        self.obs["observations"][4]["checks"][0]["status"] = "fail"
        self.assertEqual(summarize(self.suite, self.obs)["conditions"]["candidate"]["status"], "blocked")

    def test_common_and_local_duplicate_rejected(self):
        self.suite["cases"][0]["checks"] = copy.deepcopy(self.suite["common_checks"])
        with self.assertRaises(EvaluationError):
            validate_suite(self.suite)

    def test_malformed_common_check_rejected_even_without_outcomes(self):
        self.suite["cases"] = [{"id": "trigger", "kind": "trigger", "prompt": "request", "should_trigger": True, "critical": False}]
        self.suite["common_checks"] = [{"id": "bad"}]
        with self.assertRaises(EvaluationError):
            validate_suite(self.suite)

    def test_empty_observations_do_not_require_fabricated_provenance(self):
        self.obs["observations"] = []
        self.obs.pop("provenance")
        report = summarize(self.suite, self.obs)
        self.assertEqual(report["provenance_status"], "not_run")
        self.assertTrue(all(c["status"] == "unverified" for c in report["conditions"].values()))

    def test_missing_binding_rejected_for_required_suite(self):
        self.obs.pop("provenance")
        with self.assertRaises(EvaluationError):
            summarize(self.suite, self.obs)

    def test_legacy_unbound_records_stay_explicitly_unbound(self):
        self.suite.pop("require_provenance")
        self.obs.pop("provenance")
        self.assertEqual(summarize(self.suite, self.obs)["provenance_status"], "unbound")

    def test_suite_change_invalidates_old_records(self):
        self.suite["cases"][0]["prompt"] = "changed input"
        with self.assertRaises(EvaluationError):
            summarize(self.suite, self.obs)

    def test_different_environments_rejected(self):
        for field in ("model", "host", "tools", "permissions", "budget"):
            with self.subTest(field=field):
                self.bind()
                self.obs["provenance"]["conditions"]["candidate"][field] = "different"
                with self.assertRaises(EvaluationError):
                    summarize(self.suite, self.obs)

    def test_condition_identities_required(self):
        for identity in ("main", "", "no_skill", "xyz", "a" * 63):
            with self.subTest(identity=identity):
                self.bind()
                self.obs["provenance"]["conditions"]["candidate"]["skill_sha256"] = identity
                with self.assertRaises(EvaluationError):
                    summarize(self.suite, self.obs)

    def test_unknown_or_missing_condition_rejected(self):
        self.obs["provenance"]["conditions"]["other"] = self.obs["provenance"]["conditions"].pop("baseline")
        with self.assertRaises(EvaluationError):
            summarize(self.suite, self.obs)

    def test_fixture_manifest_change_invalidates_condition_binding(self):
        self.obs["provenance"]["conditions"]["candidate"]["fixtures_sha256"] = "b" * 64
        with self.assertRaises(EvaluationError):
            summarize(self.suite, self.obs)

    def test_fixture_paths_must_be_contained_and_hashed(self):
        for path, value in (("../x", "a" * 64), ("/x", "a" * 64), ("a\\b", "a" * 64), ("a", "main")):
            with self.subTest(path=path):
                self.suite["fixtures"] = {path: value}
                with self.assertRaises(EvaluationError):
                    validate_suite(self.suite)

    def test_actual_fixture_bytes_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.txt"
            fixture.write_bytes(b"fixed input")
            suite = dict(self.suite, fixtures={"input.txt": hashlib.sha256(fixture.read_bytes()).hexdigest()})
            verify_fixture_files(suite, root)
            fixture.write_bytes(b"different input")
            with self.assertRaises(EvaluationError):
                verify_fixture_files(suite, root)

    def test_shipped_manifests_and_empty_reports(self):
        evals = SCRIPTS.parent / "evals"
        for file in evals.glob("*.json"):
            data = load_json(file)
            if "cases" not in data:
                continue
            with self.subTest(suite=file.name):
                validate_suite(data)
                verify_fixture_files(data, evals)
                empty = {"schema_version": 1, "suite_id": data["suite_id"], "metadata": {}, "observations": []}
                report = summarize(data, empty)
                self.assertTrue(all(c["status"] == "unverified" for c in report["conditions"].values()))

    def test_fixture_sources_are_not_auto_discoverable_skills(self):
        fixtures = SCRIPTS.parent / "evals/fixtures"
        self.assertFalse(list(fixtures.rglob("SKILL.md")))
        with tempfile.TemporaryDirectory() as directory:
            for source in fixtures.iterdir():
                if not source.is_dir() or not (source / "SKILL.fixture.md").is_file():
                    continue
                target = Path(directory) / source.name
                shutil.copytree(source, target)
                (target / "SKILL.fixture.md").rename(target / "SKILL.md")
                self.assertEqual(lint_skill(target)["errors"], 0, source.name)

    def test_fixture_size_and_count_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input").write_bytes(b"fixed input")
            suite = dict(self.suite, fixtures={"input": hashlib.sha256(b"fixed input").hexdigest()})
            with patch.object(summarize_evals, "MAX_FIXTURE_TOTAL_BYTES", 1), self.assertRaises(EvaluationError):
                verify_fixture_files(suite, root)
            with patch.object(summarize_evals, "MAX_FIXTURE_FILES", 0), self.assertRaises(EvaluationError):
                validate_suite(suite)

    def test_template_checks_apply_to_normal_empty_and_adversarial(self):
        suite = load_json(SCRIPTS.parent / "assets/evaluation-suite.template.json")
        cases = validate_suite(suite)
        for case in cases.values():
            if case["kind"] == "outcome":
                ids = {check["id"] for check in case["checks"]}
                self.assertTrue({"global-output-contract", "trust-boundary"} <= ids)


if __name__ == "__main__":
    unittest.main()
