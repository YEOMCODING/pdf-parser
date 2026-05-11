#!/usr/bin/env bash
set -u

mode="${1:-pre}"
input_file="$(mktemp "${TMPDIR:-/tmp}/codex-tdd-guard.XXXXXX")"
trap 'rm -f "$input_file"' EXIT

cat > "$input_file"

exec python3 - "$mode" "$input_file" <<'PY'
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


MODE = sys.argv[1] if len(sys.argv) > 1 else "pre"
INPUT_FILE = Path(sys.argv[2]) if len(sys.argv) > 2 else None
NOW = int(time.time())

CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}

TEST_CONFIG_NAMES = {
    "jest.config.js",
    "jest.config.ts",
    "playwright.config.js",
    "playwright.config.ts",
    "pytest.ini",
    "vitest.config.js",
    "vitest.config.ts",
}

TEST_COMMAND_PATTERNS = [
    re.compile(r"(^|[;&|\s])python3?\s+-m\s+pytest(\s|$)"),
    re.compile(r"(^|[;&|\s])pytest(\s|$)"),
    re.compile(r"(^|[;&|\s])npm\s+(run\s+)?test(:[A-Za-z0-9_-]+)?(\s|$)"),
    re.compile(r"(^|[;&|\s])pnpm\s+(run\s+)?test(:[A-Za-z0-9_-]+)?(\s|$)"),
    re.compile(r"(^|[;&|\s])yarn\s+(run\s+)?test(:[A-Za-z0-9_-]+)?(\s|$)"),
    re.compile(r"(^|[;&|\s])(vitest|jest)(\s|$)"),
    re.compile(r"(^|[;&|\s])go\s+test(\s|$)"),
    re.compile(r"(^|[;&|\s])cargo\s+test(\s|$)"),
]

SHELL_WRITE_PATTERNS = [
    (
        re.compile(r"(^|[;&|\s])(?:cat|printf|echo)\b[\s\S]*[^<]>{1,2}\s*[^&|;\s]+"),
        "shell redirection file write",
    ),
    (re.compile(r"(^|[;&|\s])tee\s+(-a\s+)?[^&|;\s]+"), "tee file write"),
    (re.compile(r"(^|[;&|\s])sed\s+[^&|;]*\s-i(\s|$)"), "sed -i in-place edit"),
    (re.compile(r"(^|[;&|\s])perl\s+[^&|;]*\s-pi"), "perl -pi in-place edit"),
    (
        re.compile(r"(^|[;&|\s])python3?\s+-c\s+[\s\S]*(open\(|write_text|write_bytes|shutil\.copy|os\.remove)"),
        "python inline file write",
    ),
    (
        re.compile(r"(^|[;&|\s])python3?\s+-\s+[\s\S]*(open\(|write_text|write_bytes|shutil\.copy|os\.remove)"),
        "python heredoc file write",
    ),
    (
        re.compile(r"(^|[;&|\s])node\s+-e\s+[\s\S]*(writeFile|appendFile|rmSync|renameSync)"),
        "node inline file write",
    ),
    (re.compile(r"(^|[;&|\s])apply_patch(\s|$)"), "apply_patch through Bash"),
    (re.compile(r"(^|[;&|\s])(touch|cp|mv|rm)\s+"), "direct filesystem mutation"),
]


def repo_root() -> Path:
    env_root = os.environ.get("TDD_GUARD_ROOT")
    if env_root:
        return Path(env_root).resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except Exception:
        pass

    return Path.cwd().resolve()


ROOT = repo_root()
STATE_FILE = Path(
    os.environ.get("TDD_GUARD_STATE_FILE", ROOT / ".codex" / "tdd-guard" / "state.json")
)


def load_event() -> dict:
    if INPUT_FILE is None:
        return {}
    raw = INPUT_FILE.read_text(encoding="utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def default_state() -> dict:
    return {
        "schema_version": 1,
        "last_test_change_at": 0,
        "last_test_command": "",
        "last_test_status": "unknown",
        "last_red_at": 0,
        "last_green_at": 0,
        "red_valid": False,
        "implementation_started_at": 0,
        "changed_test_files": [],
        "changed_production_files": [],
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        return default_state()
    try:
        loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_state()

    state = default_state()
    if isinstance(loaded, dict):
        state.update(loaded)
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def tool_name(event: dict) -> str:
    value = event.get("tool_name") or event.get("toolName") or ""
    return str(value)


def tool_input(event: dict):
    return event.get("tool_input", event.get("toolInput", {}))


def tool_command(event: dict) -> str:
    value = tool_input(event)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("command", "cmd", "patch", "input"):
            found = value.get(key)
            if isinstance(found, str):
                return found
    return ""


def normalize_path(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    value = value.removeprefix("a/").removeprefix("b/")
    return value.lstrip("./")


def changed_files_from_patch(patch: str) -> list[str]:
    files = []
    for line in patch.splitlines():
        for prefix in (
            "*** Add File: ",
            "*** Update File: ",
            "*** Delete File: ",
            "*** Move to: ",
        ):
            if line.startswith(prefix):
                path = normalize_path(line[len(prefix) :])
                if path and path not in files:
                    files.append(path)
    return files


def is_test_file(path: str) -> bool:
    path = normalize_path(path)
    lower = path.lower()
    name = Path(lower).name
    parts = set(Path(lower).parts)

    if name in TEST_CONFIG_NAMES:
        return True
    if {"test", "tests", "__tests__", "spec", "specs"} & parts:
        return True
    if name.startswith("test_") and Path(name).suffix == ".py":
        return True
    if name.endswith("_test.py"):
        return True
    if re.search(r"(\.|-)(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$", name):
        return True
    if lower.endswith(".feature"):
        return True
    return False


def is_guard_state(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized.startswith(".codex/tdd-guard/")


def is_production_file(path: str) -> bool:
    normalized = normalize_path(path)
    if not normalized or is_guard_state(normalized) or is_test_file(normalized):
        return False
    return Path(normalized).suffix.lower() in CODE_EXTENSIONS


def is_test_command(command: str) -> bool:
    normalized = " ".join(command.strip().split())
    return any(pattern.search(normalized) for pattern in TEST_COMMAND_PATTERNS)


def block_pre(reason: str) -> int:
    print(reason, file=sys.stderr)
    return 2


def block_stop(reason: str) -> int:
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": reason,
                "systemMessage": reason,
            },
            ensure_ascii=False,
        )
    )
    return 0


def system_message(message: str) -> int:
    print(json.dumps({"systemMessage": message}, ensure_ascii=False))
    return 0


def pre_apply_patch(event: dict) -> int:
    patch = tool_command(event)
    files = changed_files_from_patch(patch)

    if any(is_guard_state(path) for path in files):
        return block_pre("TDD Guard: runtime state files under .codex/tdd-guard/ cannot be edited manually.")

    production_files = [path for path in files if is_production_file(path)]
    if not production_files:
        return 0

    state = load_state()
    if state.get("red_valid"):
        return 0

    return block_pre(
        "TDD Guard: production edit blocked before a red test. "
        "Add or update a test, run it and confirm it fails, then make the implementation change. "
        f"Blocked files: {', '.join(production_files)}"
    )


def pre_bash(event: dict) -> int:
    command = tool_command(event)
    if not command.strip():
        return 0

    normalized = " ".join(command.split())
    if is_test_command(normalized):
        return 0

    for pattern, label in SHELL_WRITE_PATTERNS:
        if pattern.search(normalized):
            return block_pre(
                "TDD Guard: Bash file mutation is blocked; use apply_patch so the TDD hook can inspect the edit. "
                f"Detected: {label}"
            )

    if ".codex/tdd-guard/" in normalized:
        return block_pre("TDD Guard: runtime state files under .codex/tdd-guard/ cannot be edited manually.")

    return 0


def remember_patch(event: dict) -> int:
    patch = tool_command(event)
    files = changed_files_from_patch(patch)
    if not files:
        return 0

    state = load_state()
    test_files = [path for path in files if is_test_file(path)]
    production_files = [path for path in files if is_production_file(path)]

    if test_files:
        state["last_test_change_at"] = NOW
        state["changed_test_files"] = sorted(set(state.get("changed_test_files", []) + test_files))
        state["red_valid"] = False
        state["last_test_status"] = "test_changed"

    if production_files:
        state["implementation_started_at"] = NOW
        state["changed_production_files"] = sorted(
            set(state.get("changed_production_files", []) + production_files)
        )

    save_state(state)
    return 0


def find_exit_code(value) -> int | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {"exitcode", "exit_code", "returncode", "status"}:
                try:
                    return int(nested)
                except (TypeError, ValueError):
                    pass
        for nested in value.values():
            found = find_exit_code(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = find_exit_code(nested)
            if found is not None:
                return found
    elif isinstance(value, str):
        match = re.search(r"(?:exit(?:ed)?(?:\s+with)?\s+code|returncode)\s*[:=]?\s*(-?\d+)", value, re.I)
        if match:
            return int(match.group(1))
    return None


def remember_test_result(event: dict) -> int:
    command = tool_command(event)
    if not is_test_command(command):
        return 0

    state = load_state()
    response = event.get("tool_response", event.get("toolResponse", {}))
    exit_code = find_exit_code(response)
    state["last_test_command"] = command

    if exit_code is None:
        state["last_test_status"] = "unknown"
    elif exit_code == 0:
        state["last_test_status"] = "green"
        state["last_green_at"] = NOW
        state["red_valid"] = False
        state["implementation_started_at"] = 0
    else:
        state["last_test_status"] = "red"
        state["last_red_at"] = NOW
        state["red_valid"] = True

    save_state(state)
    return 0


def configured_test_command() -> str:
    explicit = os.environ.get("TDD_GUARD_TEST_COMMAND", "").strip()
    if explicit:
        return explicit

    package_json = ROOT / "package.json"
    if package_json.exists():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = package.get("scripts", {})
            if isinstance(scripts, dict) and "test" in scripts:
                return "npm test"
        except Exception:
            pass

    if shutil.which("pytest"):
        return "pytest"

    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "python3 -m pytest"
    except Exception:
        pass

    return ""


def run_stop_validation() -> int:
    state = load_state()
    if not state.get("implementation_started_at"):
        return 0

    command = configured_test_command()
    if not command:
        message = (
            "TDD Guard: implementation changed, but no test command was detected. "
            "Set TDD_GUARD_TEST_COMMAND to enforce Stop validation."
        )
        if os.environ.get("TDD_GUARD_STRICT_STOP") == "1":
            return block_stop(message)
        return system_message(message)

    result = subprocess.run(command, cwd=ROOT, shell=True)
    state["last_test_command"] = command
    if result.returncode == 0:
        state["last_test_status"] = "green"
        state["last_green_at"] = NOW
        state["red_valid"] = False
        state["implementation_started_at"] = 0
        save_state(state)
        return 0

    state["last_test_status"] = "red"
    state["last_red_at"] = NOW
    state["red_valid"] = True
    save_state(state)
    return block_stop(
        f"TDD Guard: final test command failed ({command}). Fix the implementation until tests pass."
    )


def main() -> int:
    event = load_event()
    name = tool_name(event)

    if MODE == "pre":
        if name == "apply_patch":
            return pre_apply_patch(event)
        if name == "Bash":
            return pre_bash(event)
        return 0

    if MODE == "post":
        if name == "apply_patch":
            return remember_patch(event)
        if name == "Bash":
            return remember_test_result(event)
        return 0

    if MODE == "stop":
        return run_stop_validation()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
