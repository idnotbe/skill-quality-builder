"""Deterministic regressions for the September 2026 audit; not host/model tests."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(os.environ.get("SKILL_TEST_SCRIPTS", str(
    Path(__file__).resolve().parents[1] / ".agents/skills/skill-quality-builder/scripts")))
sys.path.insert(0, str(SCRIPTS))
import skill_lib
from skill_lib import SkillError, init_skill, lint_skill, parse_frontmatter
from package_skill import package_skill
from summarize_evals import EvaluationError, load_json


def manifest(root: Path) -> dict[str, str]:
    """Include directories and all files, including ignored additions."""
    return {p.relative_to(root).as_posix(): "directory" if p.is_dir() else
            hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*")}


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name)
        self.root = self.parent / "demo-skill"
        self.root.mkdir()
        self.skill('"Create a bounded output."')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path: str, text: str) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def skill(self, description: str):
        self.write("SKILL.md", f"---\nname: demo-skill\ndescription: {description}\n---\n# Task\nUse the supplied input.\n")

    def append(self, text: str):
        with (self.root / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("\n" + text + "\n")

    def codes(self, **kwargs):
        return {i["code"] for i in lint_skill(self.root, **kwargs)["issues"]}

    def test_comments_cannot_supply_or_change_required_scalar_type(self):
        for raw in ("# no description", "null # absent", "true # bool", "false # bool",
                    "123 # number", "-1.5 # number", "1e3 # number", "0x12 # number", "~ # absent"):
            with self.subTest(raw=raw):
                self.skill(raw)
                self.assertGreater(lint_skill(self.root)["errors"], 0)
                target = self.parent / "blocked.zip"
                with self.assertRaises(SkillError):
                    package_skill(self.root, target)
                self.assertFalse(target.exists())

    def test_valid_scalars_with_comments_and_literal_hashes(self):
        cases = [("A useful task # editorial", "A useful task"),
                 ("John's report # note", "John's report"),
                 ('"Keep # literal" # note', "Keep # literal"),
                 ("'It''s # literal' # note", "It's # literal"),
                 ('"Escaped \\\" # literal" # note', 'Escaped " # literal'),
                 ("report#fragment", "report#fragment"),
                 ('"true" # string', "true")]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.skill(raw)
                fields, _, _ = parse_frontmatter((self.root / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(fields["description"], expected)
                self.assertEqual(lint_skill(self.root)["errors"], 0)

    def test_block_scalar_comment_is_supported(self):
        self.skill(">- # a folded scalar\n  Useful description.\n  More context.")
        fields, _, _ = parse_frontmatter((self.root / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(fields["description"], "Useful description. More context.")
        self.assertEqual(lint_skill(self.root)["errors"], 0)

    def test_malformed_quoted_tail_remains_invalid(self):
        for raw in ('"Good" garbage # note', "'Good' garbage # note", '"Unclosed # note'):
            with self.subTest(raw=raw):
                self.skill(raw)
                self.assertGreater(lint_skill(self.root)["errors"], 0)

    def test_init_rejects_unsupported_separators_before_any_creation(self):
        for char in ("\u0085", "\u2028", "\u2029", "\n", "\r", "\x00", "\ud800"):
            with self.subTest(char=repr(char)):
                parent = self.parent / "must-not-exist"
                with self.assertRaises(SkillError):
                    init_skill("new-skill", "Create" + char + "reports", parent)
                self.assertFalse(parent.exists())

    def test_accepted_init_descriptions_round_trip(self):
        for index, description in enumerate(("한국어 요약", "Résumé and 日本語", 'Use "quotes" # hash',
                                            "It's valid", "한" * 1024, "Review 👩‍💻 outputs")):
            with self.subTest(description=description[:25]):
                target = init_skill(f"new-{index}", description, self.parent)
                fields, _, _ = parse_frontmatter((target / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(fields["description"], description)
                self.assertEqual(lint_skill(target)["errors"], 0)

    def test_unrelated_web_link_does_not_hide_orphan(self):
        self.write("references/critical.md", "# Critical requirement\n")
        self.append("[Background](https://example.invalid)")
        self.assertIn("undiscoverable_references", self.codes())

    def test_transitive_links_and_cycles_are_reachable(self):
        self.write("references/a.md", "[B](b.md)")
        self.write("references/b.md", "[A](a.md)")
        self.append("[A](references/a.md)")
        self.assertNotIn("undiscoverable_references", self.codes())

    def test_unreachable_cycle_still_warns(self):
        self.write("references/a.md", "[B](b.md)")
        self.write("references/b.md", "[A](a.md)")
        self.assertIn("undiscoverable_references", self.codes())

    def test_code_and_directory_links_do_not_reach_every_file(self):
        self.write("references/a.md", "# Rules")
        self.append("[Directory](references/)\n```md\n[A](references/a.md)\n```")
        self.assertIn("undiscoverable_references", self.codes())

    def test_reference_exemption_is_explicit_and_exact(self):
        self.write("references/test-data.md", "# Intentionally unlinked test material")
        self.assertNotIn("undiscoverable_references", self.codes(reference_exemptions=("references/test-data.md",)))
        self.assertIn("invalid_reference_exemption", self.codes(reference_exemptions=("references/*.md",)))

    def test_read_only_cli_preserves_full_manifest_without_B(self):
        for file in SCRIPTS.glob("*.py"):
            self.write("scripts/" + file.name, file.read_text(encoding="utf-8"))
        before = manifest(self.root)
        env = os.environ.copy()
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env.pop("PYTHONPYCACHEPREFIX", None)
        result = subprocess.run([sys.executable, str(self.root / "scripts/lint_skill.py"), str(self.root), "--format", "json"],
                                capture_output=True, text=True, timeout=10, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, manifest(self.root))

    def test_portable_names_on_any_os(self):
        for name in ("CON.txt", "NUL", "Lpt9.txt", "COM¹.txt", "folder/AUX.json", "bad:name", "name.", "name "):
            with self.subTest(name=name):
                self.assertTrue(skill_lib.portable_path_issues(["demo-skill/" + name]))
        self.assertFalse(skill_lib.portable_path_issues(["demo-skill/references/한국어.md", "demo-skill/COM10.txt"]))

    def test_case_and_normalization_collisions_include_directories(self):
        for names in (("Rules.md", "rules.md"), ("Refs/a.md", "refs/b.md"), ("café.md", "cafe\u0301.md")):
            with self.subTest(names=names):
                codes = {i["code"] for i in skill_lib.portable_path_issues(list(names))}
                self.assertIn("portable_collision", codes)

    @unittest.skipIf(os.name == "nt", "Cannot create the deliberately incompatible fixture on Windows")
    def test_packaging_rejects_incompatible_names_native_is_explicit(self):
        for name in ("CON.txt", "Rules.md", "rules.md"):
            self.write(name, "fixture")
        with self.assertRaises(SkillError):
            package_skill(self.root, self.parent / "portable.zip")
        self.assertFalse((self.parent / "portable.zip").exists())
        report = package_skill(self.root, self.parent / "native.zip", portability="native")
        self.assertEqual(report["portability"], "native")

    def test_portable_package_extracts_with_identical_content(self):
        self.write("references/rules.md", "# Rules\n한국어 text\n")
        self.append("[Rules](references/rules.md)")
        package_skill(self.root, self.parent / "out.zip")
        with zipfile.ZipFile(self.parent / "out.zip") as archive:
            self.assertIsNone(archive.testzip())
            archive.extractall(self.parent / "extracted")
        self.assertEqual(manifest(self.root), manifest(self.parent / "extracted/demo-skill"))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO only")
    def test_evaluation_fifo_returns_input_error_without_blocking(self):
        pipe = self.parent / "pipe.json"
        os.mkfifo(pipe)
        other = self.parent / "empty.json"
        other.write_text("{}", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "summarize_evals.py"), str(pipe), str(other)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("regular", result.stderr.lower())

    def test_evaluation_directory_is_not_json_input(self):
        with self.assertRaises(EvaluationError):
            load_json(self.root)

    def test_regular_json_and_duplicate_keys(self):
        path = self.parent / "input.json"
        path.write_text('{"description":"한국어"}', encoding="utf-8")
        self.assertEqual(load_json(path)["description"], "한국어")
        path.write_text('{"a":1,"a":2}', encoding="utf-8")
        with self.assertRaises(EvaluationError):
            load_json(path)


if __name__ == "__main__":
    unittest.main()
