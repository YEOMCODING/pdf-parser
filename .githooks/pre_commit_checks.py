#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


CHECKS = ("lint", "build", "test")


def load_package(root: Path) -> Optional[dict]:
    package_file = root / "package.json"
    if not package_file.exists():
        return None

    try:
        return json.loads(package_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid package.json: {exc}") from exc


def run_checks(root: Path, runner=subprocess.run) -> int:
    try:
        package = load_package(root)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    if package is None:
        print("package.json not found; skipping npm lint/build/test checks.")
        return 0

    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        scripts = {}

    missing = [name for name in CHECKS if name not in scripts]
    if missing:
        print(
            "Missing required npm scripts: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    for name in CHECKS:
        print(f"Running npm run {name}")
        result = runner(["npm", "run", name], cwd=root)
        if result.returncode != 0:
            print(f"npm run {name} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode

    return 0


def main() -> int:
    return run_checks(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
