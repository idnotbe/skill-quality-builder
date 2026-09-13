"""Local tests of helper behavior, NOT model/host quality evaluations."""
from __future__ import annotations
import copy
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / ".agents" / "skills" / "skill-quality-builder" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import skill_lib
from skill_lib import SkillError, init_skill, inventory, lint_skill, markdown_links, parse_frontmatter, validate_name
from package_skill import package_skill
from summarize_evals import EvaluationError, load_json, summarize


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name)
        self.root = self.parent / "demo-skill"
        self.root.mkdir()
        self.write("SKILL.md", '---\nname: demo-skill\ndescription: "Creates a bounded output."\n---\n\n# Task\nPerform the requested task within its permissions.\n')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def append(self, text):
        with (self.root / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write(text)

    def codes(self):
        return {x["code"] for x in lint_skill(self.root)["issues"]}

    def test_valid_profile(self):
        self.assertEqual(lint_skill(self.root)["status"], "pass")

    def test_names(self):
        for value in ("a", "abc-12", "1", "a" * 64):
            validate_name(value)
        for value in ("", "A", "a--b", "a-", "-a", "a_b", "../a", "café", "a" * 65):
            with self.subTest(value=value), self.assertRaises(SkillError):
                validate_name(value)

    def test_missing_frontmatter(self):
        self.write("SKILL.md", "# No metadata\n")
        self.assertIn("frontmatter_missing", self.codes())

    def test_unclosed_frontmatter(self):
        self.write("SKILL.md", "---\nname: demo-skill\n")
        self.assertIn("frontmatter_unclosed", self.codes())

    def test_missing_required_field(self):
        self.write("SKILL.md", "---\nname: demo-skill\n---\nBody")
        self.assertIn("required_field", self.codes())

    def test_empty_description(self):
        self.write("SKILL.md", '---\nname: demo-skill\ndescription: ""\n---\nBody')
        self.assertIn("empty_field", self.codes())

    def test_unparsed_required_field_is_error(self):
        self.write("SKILL.md", "---\nname: demo-skill\ndescription:\n  nested: unsupported\n---\nBody")
        result = lint_skill(self.root)
        self.assertEqual(result["status"], "fail")
        self.assertIn("unparsed_required_field", self.codes())

    def test_description_limit(self):
        self.write("SKILL.md", '---\nname: demo-skill\ndescription: "' + "x" * 1025 + '"\n---\nBody')
        self.assertIn("field_length", self.codes())

    def test_duplicate_field(self):
        self.write("SKILL.md", "---\nname: demo-skill\nname: demo-skill\ndescription: works\n---\nBody")
        self.assertIn("duplicate_field", self.codes())

    def test_name_directory(self):
        self.write("SKILL.md", "---\nname: another-name\ndescription: works\n---\nBody")
        self.assertIn("name_directory", self.codes())

    def test_wrong_filename(self):
        (self.root / "SKILL.md").rename(self.root / "instructions.md")
        self.assertIn("skill_missing", self.codes())

    def test_lowercase_skill_filename_rejected(self):
        (self.root / "SKILL.md").rename(self.root / "skill.md")
        self.assertIn("skill_missing", self.codes())
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "blocked.zip")

    def test_block_scalar(self):
        fields, body, issues = parse_frontmatter("---\nname: demo-skill\ndescription: >-\n  Creates a task.\n  Use for reports.\n---\nBody")
        self.assertEqual(fields["description"], "Creates a task. Use for reports.")
        self.assertFalse(issues)

    def test_single_quoted_scalar(self):
        fields, _, issues = parse_frontmatter("---\nname: demo-skill\ndescription: 'It''s useful.'\n---\nBody")
        self.assertEqual(fields["description"], "It's useful.")
        self.assertFalse(issues)

    def test_unicode_description(self):
        fields, body, _ = parse_frontmatter('---\nname: demo-skill\ndescription: "Résumé analyzer"\n---\nBody with café text.')
        self.assertEqual(fields["description"], "Résumé analyzer")
        self.assertEqual(body, "Body with café text.")

    def test_nested_yaml_is_warning_not_invalid(self):
        self.write("SKILL.md", "---\nname: demo-skill\ndescription: works\nmetadata:\n  owner: team\n---\nBody")
        result = lint_skill(self.root)
        self.assertEqual(result["errors"], 0)
        self.assertIn("yaml_unsupported", self.codes())

    def test_host_field_preserved(self):
        self.write("SKILL.md", "---\nname: demo-skill\ndescription: works\ncontext: fork\n---\nBody")
        before = (self.root / "SKILL.md").read_bytes()
        self.assertIn("host_field", self.codes())
        self.assertEqual(before, (self.root / "SKILL.md").read_bytes())

    def test_good_local_link(self):
        self.write("references/rules.md", "# Rules")
        self.append("\n[Rules](references/rules.md)\n")
        self.assertEqual(lint_skill(self.root)["errors"], 0)

    def test_missing_link(self):
        self.append("\n[Missing](references/missing.md)\n")
        self.assertIn("link_missing", self.codes())

    def test_escaping_link(self):
        (self.parent / "outside.md").write_text("outside")
        self.append("\n[Outside](../outside.md)\n")
        self.assertIn("link_escape", self.codes())

    def test_encoded_escape(self):
        self.append("\n[Outside](%2e%2e/outside.md)\n")
        self.assertIn("link_escape", self.codes())

    def test_parent_within_root(self):
        self.write("references/rules.md", "[Root](../SKILL.md)")
        self.append("\n[Rules](references/rules.md)\n")
        self.assertEqual(lint_skill(self.root)["errors"], 0)

    def test_fenced_and_inline_code_ignored(self):
        self.append("\n```md\n[Fake](missing.md)\n```\n`[Fake](missing2.md)`\n")
        self.assertNotIn("link_missing", self.codes())

    def test_urls_and_anchors_ignored(self):
        self.append("\n[Web](https://example.com/a) [Part](#does-not-validate-anchor)\n")
        self.assertEqual(lint_skill(self.root)["errors"], 0)

    def test_excluded_reference(self):
        self.write("__pycache__/example.pyc", "not real bytecode")
        self.append("\n[Cache](__pycache__/example.pyc)\n")
        self.assertIn("link_excluded", self.codes())

    def test_secret_filename(self):
        self.write(".env", "EXAMPLE=not-a-real-secret")
        self.assertIn("likely_secret", self.codes())

    def test_common_credential_filenames(self):
        for filename in (".npmrc", ".pypirc", ".netrc", ".git-credentials", "token.txt", "secrets.json", "id_ecdsa", "client-secret.json"):
            with self.subTest(filename=filename):
                self.write(filename, "placeholder")
                self.assertIn("likely_secret", self.codes())
                (self.root / filename).unlink()

    def test_common_credential_paths(self):
        for filename in (".docker/config.json", ".kube/config", ".config/gh/hosts.yml"):
            with self.subTest(filename=filename):
                self.write(filename, "placeholder")
                self.assertIn("likely_secret", self.codes())
                (self.root / filename).unlink()

    def test_env_template_allowed(self):
        self.write(".env.example", "PLACEHOLDER=value")
        self.assertNotIn("likely_secret", self.codes())

    @unittest.skipIf(os.name == "nt", "symlink privilege depends on Windows configuration")
    def test_symlink_rejected(self):
        (self.root / "linked.md").symlink_to(self.root / "SKILL.md")
        self.assertIn("symlink", self.codes())
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "blocked.zip")

    def test_windows_reparse_point_is_link_like(self):
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        entry = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=reparse_flag)
        self.assertTrue(skill_lib.is_link_like(entry))

    def test_reparse_point_root_rejected(self):
        original_lstat = Path.lstat
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

        def reparse_root(path):
            if path == self.root:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=reparse_flag)
            return original_lstat(path)

        with patch.object(Path, "lstat", reparse_root):
            self.assertIn("symlink", {item["code"] for item in inventory(self.root)[1]})

    def test_count_limit(self):
        self.write("extra.txt", "x")
        with patch.object(skill_lib, "MAX_FILES", 1):
            self.assertIn("file_count_limit", self.codes())

    def test_size_limit(self):
        with patch.object(skill_lib, "MAX_FILE_BYTES", 1):
            self.assertIn("file_size_limit", self.codes())

    def test_soft_root_length(self):
        self.append("\n" * 510)
        report = lint_skill(self.root)
        self.assertEqual(report["errors"], 0)
        self.assertIn("root_length", self.codes())

    def test_init_marks_draft(self):
        target = init_skill("new-skill", "Résumé description", self.parent)
        self.assertIn("[DRAFT]", (target / "SKILL.md").read_text())
        self.assertEqual(lint_skill(target)["status"], "pass_with_warnings")
        self.assertEqual(len(list(target.iterdir())), 1)

    def test_init_no_overwrite(self):
        before = (self.root / "SKILL.md").read_bytes()
        with self.assertRaises(FileExistsError):
            init_skill("demo-skill", "different", self.parent)
        self.assertEqual(before, (self.root / "SKILL.md").read_bytes())

    def test_init_rejects_multiline_description(self):
        with self.assertRaises(SkillError):
            init_skill("new-skill", "x\ny", self.parent)

    def test_safe_zip(self):
        self.write("references/rules.md", "# Rules")
        self.append("\n[Rules](references/rules.md)\n")
        self.write(".git/config", "ignored")
        self.write("__pycache__/x.pyc", "ignored")
        result = package_skill(self.root, self.parent / "out.zip")
        self.assertFalse(result["installed"])
        with zipfile.ZipFile(self.parent / "out.zip") as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {"demo-skill/SKILL.md", "demo-skill/references/rules.md"})

    def test_mixed_case_generated_paths_excluded(self):
        self.write(".GIT/config", "ignored")
        self.write("__PYCACHE__/module.py", "ignored")
        self.write("cache.PYC", "ignored")
        result = lint_skill(self.root)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(set(result["excluded"]), {".GIT/", "__PYCACHE__/", "cache.PYC"})
        output = self.parent / "out.zip"
        package_skill(self.root, output)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {"demo-skill/SKILL.md"})

    def test_zip_no_overwrite(self):
        out = self.parent / "out.zip"
        out.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            package_skill(self.root, out)
        self.assertEqual(out.read_bytes(), b"keep")

    def test_zip_not_inside_target(self):
        with self.assertRaises(SkillError):
            package_skill(self.root, self.root / "out.zip")

    def test_zip_rejects_invalid_skill(self):
        self.append("\n[Missing](missing.md)\n")
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "out.zip")
        self.assertFalse((self.parent / "out.zip").exists())

    def test_zip_rejects_secret(self):
        self.write("key.pem", "not a real key")
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "out.zip")

    def test_zip_extension(self):
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "out.txt")

    def test_no_target_execution(self):
        self.write("scripts/trap.py", "raise RuntimeError('Do not execute target code')")
        self.assertEqual(lint_skill(self.root)["errors"], 0)
        self.assertEqual(package_skill(self.root, self.parent / "out.zip")["lint_status"], "pass")

    def test_reference_to_excluded_directory(self):
        self.write(".git/config", "ignored")
        self.append("\n[Git](.git/)\n")
        self.assertIn("link_unshipped_directory", self.codes())

    def test_reference_to_empty_directory(self):
        (self.root / "empty").mkdir()
        self.append("\n[Empty](empty/)\n")
        self.assertIn("link_unshipped_directory", self.codes())

    def test_empty_compatibility(self):
        self.write("SKILL.md", '---\nname: demo-skill\ndescription: works\ncompatibility: ""\n---\nBody')
        self.assertIn("empty_compatibility", self.codes())

    def test_malformed_url_does_not_crash(self):
        self.append("\n[Bad](http://[bad)\n")
        self.assertIn("link_syntax", self.codes())

    def test_all_cli_help(self):
        for filename in ("lint_skill.py", "init_skill.py", "package_skill.py", "summarize_evals.py"):
            with self.subTest(filename=filename):
                result = subprocess.run([sys.executable, str(SCRIPTS / filename), "--help"], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_lint_cli_fail(self):
        self.append("\n[Missing](missing.md)\n")
        result = subprocess.run([sys.executable, str(SCRIPTS / "lint_skill.py"), str(self.root), "--format", "json"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "fail")


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.suite = {"schema_version": 1, "suite_id": "s1", "conditions": ["baseline", "candidate"], "repetitions": 1,
                      "cases": [{"id": "positive", "kind": "trigger", "prompt": "Create a skill", "critical": False, "should_trigger": True},
                                {"id": "negative", "kind": "trigger", "prompt": "Do not create a skill", "critical": False, "should_trigger": False},
                                {"id": "task", "kind": "outcome", "prompt": "Make output", "critical": False,
                                 "checks": [{"id": "output", "text": "Output exists", "critical": False},
                                            {"id": "safe", "text": "No unauthorized actions", "critical": True}]}]}
        self.obs = {"schema_version": 1, "suite_id": "s1", "metadata": {}, "observations": []}

    def fill(self, kind="simulation"):
        self.obs["metadata"] = {"model": "synthetic-test-only", "host": "unittest-fixture", "skill_version": "test-v1", "run_context": "synthetic unit-test records, not actual agent execution", "evidence_kind": kind}
        self.obs["observations"] = [
            {"case_id": "positive", "condition": "candidate", "repetition": 1, "triggered": True, "evidence": "synthetic fixture"},
            {"case_id": "negative", "condition": "candidate", "repetition": 1, "triggered": False, "evidence": "synthetic fixture"},
            {"case_id": "task", "condition": "candidate", "repetition": 1, "checks": [
                {"id": "output", "status": "pass", "evidence": "synthetic fixture"},
                {"id": "safe", "status": "pass", "evidence": "synthetic fixture"}]}]

    def candidate(self):
        return summarize(self.suite, self.obs)["conditions"]["candidate"]

    def test_empty_not_run(self):
        result = self.candidate()
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["trigger"]["not_run"], 2)
        self.assertEqual(result["outcome"]["not_run"], 2)
        self.assertEqual(result["assertion_coverage"], 0)
        self.assertIsNone(result["trigger"]["precision"])
        self.assertIsNone(result["trigger"]["recall"])

    def test_complete_simulation_not_host_proof(self):
        self.fill()
        report = summarize(self.suite, self.obs)
        self.assertEqual(report["conditions"]["candidate"]["status"], "recorded_complete")
        self.assertFalse(report["host_run_records_supplied"])
        self.assertFalse(report["evidence_independently_verified"])
        self.assertEqual(report["conditions"]["baseline"]["status"], "unverified")

    def test_supplied_host_records_not_verified(self):
        self.fill("host_run")
        result = summarize(self.suite, self.obs)
        self.assertTrue(result["host_run_records_supplied"])
        self.assertFalse(result["evidence_independently_verified"])

    def test_confusion_metrics(self):
        self.fill()
        self.obs["observations"][1]["triggered"] = True
        result = self.candidate()
        self.assertEqual(result["trigger"]["tp"], 1)
        self.assertEqual(result["trigger"]["fp"], 1)
        self.assertEqual(result["trigger"]["precision"], 0.5)
        self.assertEqual(result["trigger"]["recall"], 1.0)
        self.assertEqual(result["status"], "recorded_with_failures")

    def test_boolean_not_integer(self):
        self.fill()
        self.obs["observations"][0]["triggered"] = 1
        with self.assertRaises(EvaluationError): self.candidate()

    def test_repetition_not_boolean(self):
        self.suite["repetitions"] = True
        with self.assertRaises(EvaluationError): self.candidate()

    def test_critical_failure_blocks(self):
        self.fill()
        self.obs["observations"][2]["checks"][1]["status"] = "fail"
        result = self.candidate()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["critical"]["fail"], 1)

    def test_critical_na_blocks(self):
        self.fill()
        self.obs["observations"][2]["checks"][1]["status"] = "not_applicable"
        result = self.candidate()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["critical"]["not_applicable_unresolved"], 1)
        self.assertLess(result["assertion_coverage"], 1)

    def test_missing_check_not_run(self):
        self.fill()
        self.obs["observations"][2]["checks"].pop()
        result = self.candidate()
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["outcome"]["not_run"], 1)
        self.assertEqual(result["critical"]["not_run"], 1)

    def test_null_trigger_unknown(self):
        self.fill()
        self.obs["observations"][0]["triggered"] = None
        result = self.candidate()
        self.assertEqual(result["trigger"]["not_run"], 1)
        self.assertIsNone(result["trigger"]["recall"])

    def test_repeated_coverage(self):
        self.fill()
        self.suite["repetitions"] = 2
        result = self.candidate()
        self.assertEqual(result["assertion_coverage"], 0.5)
        self.assertEqual(result["expected_case_slots"], 6)

    def test_duplicate_observation(self):
        self.fill()
        self.obs["observations"].append(copy.deepcopy(self.obs["observations"][0]))
        with self.assertRaises(EvaluationError): self.candidate()

    def test_duplicate_case(self):
        self.suite["cases"].append(copy.deepcopy(self.suite["cases"][0]))
        with self.assertRaises(EvaluationError): self.candidate()

    def test_duplicate_observed_check(self):
        self.fill()
        self.obs["observations"][2]["checks"].append(copy.deepcopy(self.obs["observations"][2]["checks"][0]))
        with self.assertRaises(EvaluationError): self.candidate()

    def test_unknown_case(self):
        self.fill()
        self.obs["observations"][0]["case_id"] = "bogus"
        with self.assertRaises(EvaluationError): self.candidate()

    def test_unknown_check(self):
        self.fill()
        self.obs["observations"][2]["checks"][0]["id"] = "bogus"
        with self.assertRaises(EvaluationError): self.candidate()

    def test_unknown_condition(self):
        self.fill()
        self.obs["observations"][0]["condition"] = "bogus"
        with self.assertRaises(EvaluationError): self.candidate()

    def test_suite_id_mismatch(self):
        self.obs["suite_id"] = "other"
        with self.assertRaises(EvaluationError): self.candidate()

    def test_missing_evidence(self):
        self.fill()
        self.obs["observations"][0]["evidence"] = ""
        with self.assertRaises(EvaluationError): self.candidate()

    def test_missing_metadata(self):
        self.fill()
        self.obs["metadata"] = {}
        with self.assertRaises(EvaluationError): self.candidate()

    def test_unknown_status(self):
        self.fill()
        self.obs["observations"][2]["checks"][0]["status"] = "looks-good"
        with self.assertRaises(EvaluationError): self.candidate()

    def test_noncritical_na_not_positive_evidence(self):
        self.suite["cases"] = [{"id":"task", "kind":"outcome", "prompt":"Check", "critical":False, "checks":[{"id":"output","text":"Output","critical":False}]}]
        self.fill()
        self.obs["observations"] = [self.obs["observations"][2]]
        self.obs["observations"][0]["checks"] = [{"id":"output", "status":"not_applicable", "evidence":"synthetic fixture"}]
        result = self.candidate()
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["assertions_evaluated"], 0)
        self.assertIsNone(result["outcome"]["pass_rate_on_pass_fail_only"])

    def test_json_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"bad.json"
            p.write_text('{"a":1,"a":2}')
            with self.assertRaises(EvaluationError): load_json(p)

    def test_shipped_empty_suites(self):
        root = SCRIPTS.parent
        for s, o in [("trigger-suite.json", "observations.empty.json"), ("behavior-cases.json", "behavior-observations.empty.json")]:
            result = summarize(load_json(root/"evals"/s), load_json(root/"evals"/o))
            for condition in result["conditions"].values():
                self.assertEqual(condition["status"], "unverified")
                self.assertEqual(condition["assertion_coverage"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
