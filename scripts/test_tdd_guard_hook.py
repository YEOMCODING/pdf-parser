import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".codex" / "hooks" / "tdd-guard.sh"
HOOK_CONFIG = ROOT / ".codex" / "hooks.json"


def patch_event(path: str, *, action: str = "Update") -> dict:
    return {
        "tool_name": "apply_patch",
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                f"*** {action} File: {path}\n"
                "@@\n"
                "+changed\n"
                "*** End Patch\n"
            )
        },
    }


def denial_reason(result: subprocess.CompletedProcess) -> str:
    output = json.loads(result.stdout)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PreToolUse"
    assert hook_output["permissionDecision"] == "deny"
    return hook_output["permissionDecisionReason"]


class TddGuardHookTest(unittest.TestCase):
    def test_hook_config_runs_pretooluse_for_apply_patch_only(self):
        config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(set(config["hooks"]), {"PreToolUse"})
        groups = config["hooks"]["PreToolUse"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["matcher"], "^apply_patch$")

    def run_guard(self, event: dict, tmp: Path):
        return subprocess.run(
            ["bash", str(SCRIPT), "pre"],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            cwd=tmp,
        )

    def test_allows_test_file_patch(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(patch_event("src/lib/parser.test.ts"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_blocks_typescript_implementation_without_test_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(patch_event("src/lib/parser.ts"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("parser", denial_reason(result))

    def test_allows_typescript_implementation_with_sibling_test_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            (tmp / "src/lib").mkdir(parents=True)
            (tmp / "src/lib/parser.test.ts").write_text("", encoding="utf-8")

            result = self.run_guard(patch_event("src/lib/parser.ts"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_allows_typescript_implementation_with_parent_tests_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            (tmp / "src/__tests__").mkdir(parents=True)
            (tmp / "src/__tests__/parser.spec.ts").write_text("", encoding="utf-8")

            result = self.run_guard(patch_event("src/lib/parser.ts"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_blocks_python_implementation_without_test_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(patch_event("scripts/execute.py"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("execute", denial_reason(result))

    def test_allows_python_implementation_with_sibling_test_file(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            (tmp / "scripts").mkdir()
            (tmp / "scripts/test_execute.py").write_text("", encoding="utf-8")

            result = self.run_guard(patch_event("scripts/execute.py"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_allows_framework_entry_files_without_companion_test(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(patch_event("src/app/page.tsx"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_ignores_deleted_implementation_files(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            result = self.run_guard(patch_event("src/lib/parser.ts", action="Delete"), tmp)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
