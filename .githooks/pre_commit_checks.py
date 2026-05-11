#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


CHECKS = (
    ("ruff check", ["-m", "ruff", "check", "."]),
    ("pytest", ["-m", "pytest"]),
)


def run_checks(root: Path, runner=subprocess.run) -> int:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        print("pyproject.toml not found; skipping Python lint/test checks.")
        return 0

    python = python_executable(root)
    for label, command in CHECKS:
        print(f"Running {label}")
        result = runner([python, *command], cwd=root)
        if result.returncode != 0:
            print(f"{label} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode

    return 0


def python_executable(root: Path) -> str:
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> int:
    return run_checks(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
