"""Exercise Git checkout conversion without weakening exact-byte fixture hashes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVALS = Path(".agents/skills/skill-quality-builder/evals")


@unittest.skipUnless(shutil.which("git"), "Git is required for checkout conversion coverage")
class FixtureCheckoutTests(unittest.TestCase):
    def test_hashed_fixtures_survive_autocrlf_checkout(self):
        expected: dict[str, str] = {}
        for name in ("trigger-suite.json", "behavior-cases.json", "child-skill-cases.json"):
            suite = json.loads((ROOT / EVALS / name).read_text(encoding="utf-8"))
            for path, digest in suite["fixtures"].items():
                if path in expected:
                    self.assertEqual(expected[path], digest)
                expected[path] = digest
        self.assertTrue(expected)
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            source, checkout = scratch / "source", scratch / "checkout"
            source.mkdir()
            checkout.mkdir()
            shutil.copyfile(ROOT / ".gitattributes", source / ".gitattributes")
            for path, digest in expected.items():
                relative = EVALS / path
                data = (ROOT / relative).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            env = os.environ.copy()
            env["GIT_CONFIG_NOSYSTEM"] = "1"
            env["GIT_CONFIG_GLOBAL"] = os.devnull
            for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
                env.pop(key, None)

            def git(*arguments: str) -> None:
                result = subprocess.run(["git", *arguments], cwd=source, env=env,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)

            git("init", "-q")
            git("config", "core.autocrlf", "true")
            git("config", "core.eol", "crlf")
            git("add", "--", ".gitattributes", EVALS.as_posix())
            git("checkout-index", "--all", "--prefix=" + checkout.as_posix() + "/")
            for path, digest in expected.items():
                with self.subTest(fixture=path):
                    actual = (checkout / EVALS / path).read_bytes()
                    self.assertEqual(hashlib.sha256(actual).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
