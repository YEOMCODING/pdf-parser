import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib import util
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
SPEC = util.spec_from_file_location(
    "pre_commit_checks",
    ROOT / ".githooks" / "pre_commit_checks.py",
)
pc = util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pc)


def write_package_json(root: Path, scripts: Dict[str, str]) -> None:
    (root / "package.json").write_text(
        json.dumps({"scripts": scripts}, indent=2),
        encoding="utf-8",
    )


class FakeRunner:
    def __init__(self, returncodes=None):
        self.returncodes = returncodes or {}
        self.calls = []

    def __call__(self, cmd, cwd):
        self.calls.append((cmd, cwd))
        script = cmd[-1]
        return subprocess.CompletedProcess(cmd, self.returncodes.get(script, 0))


class TestPreCommitChecks(unittest.TestCase):
    def test_skips_when_package_json_is_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(runner.calls, [])
            self.assertIn("package.json not found", stdout.getvalue())

    def test_fails_when_required_scripts_are_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package_json(root, {"lint": "eslint ."})
            runner = FakeRunner()
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 1)
            self.assertEqual(runner.calls, [])
            output = stderr.getvalue()
            self.assertIn("Missing required npm scripts", output)
            self.assertIn("build", output)
            self.assertIn("test", output)

    def test_runs_lint_build_and_test_in_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package_json(
                root,
                {"lint": "eslint .", "build": "next build", "test": "vitest"},
            )
            runner = FakeRunner()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(
                [call[0] for call in runner.calls],
                [
                    ["npm", "run", "lint"],
                    ["npm", "run", "build"],
                    ["npm", "run", "test"],
                ],
            )
            self.assertTrue(all(call[1] == root for call in runner.calls))

    def test_stops_on_first_failed_check(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package_json(
                root,
                {"lint": "eslint .", "build": "next build", "test": "vitest"},
            )
            runner = FakeRunner(returncodes={"build": 2})
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 2)
            self.assertEqual(
                [call[0] for call in runner.calls],
                [
                    ["npm", "run", "lint"],
                    ["npm", "run", "build"],
                ],
            )

    def test_invalid_package_json_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("{ invalid", encoding="utf-8")
            runner = FakeRunner()
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 1)
            self.assertEqual(runner.calls, [])
            self.assertIn("Invalid package.json", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
