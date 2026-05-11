import io
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


def write_pyproject(root: Path, content: str = "[project]\nname = \"demo\"\n") -> None:
    (root / "pyproject.toml").write_text(content, encoding="utf-8")


class FakeRunner:
    def __init__(self, returncodes: Dict[str, int] | None = None):
        self.returncodes = returncodes or {}
        self.calls = []

    def __call__(self, cmd, cwd):
        self.calls.append((cmd, cwd))
        key = " ".join(cmd)
        return subprocess.CompletedProcess(cmd, self.returncodes.get(key, 0))


class TestPreCommitChecks(unittest.TestCase):
    def test_skips_when_pyproject_is_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(runner.calls, [])
            self.assertIn("pyproject.toml not found", stdout.getvalue())

    def test_runs_python_checks_in_order(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pyproject(root)
            runner = FakeRunner()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(
                [call[0] for call in runner.calls],
                [
                    [sys.executable, "-m", "ruff", "check", "."],
                    [sys.executable, "-m", "pytest"],
                ],
            )
            self.assertTrue(all(call[1] == root for call in runner.calls))

    def test_prefers_local_venv_python(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pyproject(root)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("", encoding="utf-8")
            runner = FakeRunner()

            result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 0)
            self.assertEqual(runner.calls[0][0][0], str(venv_python))

    def test_stops_on_first_failed_check(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pyproject(root)
            runner = FakeRunner(returncodes={f"{sys.executable} -m ruff check .": 2})
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = pc.run_checks(root, runner=runner)

            self.assertEqual(result, 2)
            self.assertEqual(
                [call[0] for call in runner.calls],
                [[sys.executable, "-m", "ruff", "check", "."]],
            )
            self.assertIn("ruff check failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
