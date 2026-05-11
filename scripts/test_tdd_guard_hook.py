import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".codex" / "hooks" / "tdd-guard.sh"


def patch_event(path: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                f"*** Update File: {path}\n"
                "@@\n"
                "+changed\n"
                "*** End Patch\n"
            )
        },
    }


class TddGuardHookTest(unittest.TestCase):
    def run_guard(self, mode: str, event: dict, tmp: Path, extra_env=None):
        env = os.environ.copy()
        env["TDD_GUARD_ROOT"] = str(tmp)
        env["TDD_GUARD_STATE_FILE"] = str(tmp / "state.json")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(SCRIPT), mode],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            env=env,
            cwd=tmp,
        )

    def test_allows_test_file_patch(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard("pre", patch_event("scripts/test_app.py"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocks_production_patch_without_red_test(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard("pre", patch_event("scripts/app.py"), tmp)

        self.assertEqual(result.returncode, 2)
        self.assertIn("production edit blocked", result.stderr)

    def test_stop_failed_validation_continues_codex(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            self.run_guard("post", patch_event("scripts/test_app.py"), tmp)
            self.run_guard(
                "post",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python3 -m pytest scripts/test_app.py"},
                    "tool_response": {"exitCode": 1},
                },
                tmp,
            )
            self.run_guard("post", patch_event("scripts/app.py"), tmp)

            result = self.run_guard(
                "stop",
                {"hook_event_name": "Stop"},
                tmp,
                extra_env={"TDD_GUARD_TEST_COMMAND": "false"},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["decision"], "block")
        self.assertIn("final test command failed", output["reason"])

    def test_allows_production_patch_after_failing_test_run(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            self.run_guard("post", patch_event("scripts/test_app.py"), tmp)
            self.run_guard(
                "post",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python3 -m pytest scripts/test_app.py"},
                    "tool_response": {"exitCode": 1},
                },
                tmp,
            )

            result = self.run_guard("pre", patch_event("scripts/app.py"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocks_bash_file_mutation(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(
                "pre",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "printf 'x' > scripts/app.py"},
                },
                tmp,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Bash file mutation is blocked", result.stderr)

    def test_blocks_apply_patch_through_bash(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(
                "pre",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "apply_patch <<'PATCH'\n*** Begin Patch\n*** End Patch\nPATCH"},
                },
                tmp,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("apply_patch through Bash", result.stderr)

    def test_passing_test_closes_red_cycle(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            self.run_guard("post", patch_event("scripts/test_app.py"), tmp)
            self.run_guard(
                "post",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python3 -m pytest scripts/test_app.py"},
                    "tool_response": {"exitCode": 1},
                },
                tmp,
            )
            self.run_guard("post", patch_event("scripts/app.py"), tmp)
            self.run_guard(
                "post",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python3 -m pytest scripts/test_app.py"},
                    "tool_response": {"exitCode": 0},
                },
                tmp,
            )

            result = self.run_guard("pre", patch_event("scripts/other.py"), tmp)

        self.assertEqual(result.returncode, 2)
        self.assertIn("production edit blocked", result.stderr)


if __name__ == "__main__":
    unittest.main()
