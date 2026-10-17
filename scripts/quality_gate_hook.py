"""Automated Quality Gate Hook & CLI Reviewer for Antigravity (Ruff, Mypy, Pylance/Pyright, TSC)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parent.parent


def _find_node_executable() -> str | None:
    """Locate a Node.js executable on PATH or inside the local virtualenv's nodejs_wheel."""
    system_node = shutil.which("node")
    if system_node is not None:
        return system_node

    venv_root = Path(sys.executable).resolve().parent.parent
    candidates = [
        venv_root / "Lib" / "site-packages" / "nodejs_wheel" / "node.exe",
        venv_root / "Lib" / "site-packages" / "nodejs_wheel" / "bin" / "node.exe",
        *venv_root.glob("lib/python*/site-packages/nodejs_wheel/bin/node"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _run_step(label: str, cmd: list[str]) -> tuple[bool, str]:
    """Run a single verification command and return (passed, diagnostic_output)."""
    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True, ""

    combined = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    return False, f"[{label}] FAILED (exit {completed.returncode}):\n{combined}"


def run_all_checks(*, include_pytest: bool = False) -> tuple[bool, list[str]]:
    """Execute Ruff, Mypy, BasedPyright (Pylance), Frontend TSC, and optionally Pytest.

    Args:
        include_pytest: When True, also runs the full pytest suite.

    Returns:
        Tuple of (all_passed, list_of_failure_reports).
    """
    python_exe = sys.executable
    steps: list[tuple[str, list[str]]] = [
        ("Ruff Linter", [python_exe, "-m", "ruff", "check", "src", "tests", "scripts"]),
        ("Mypy Strict", [python_exe, "-m", "mypy", "src", "tests", "scripts"]),
        (
            "Pylance / BasedPyright Strict",
            [python_exe, "-m", "basedpyright", "src", "tests", "scripts"],
        ),
    ]

    tsc_script = REPO_ROOT / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
    tsconfig = REPO_ROOT / "frontend" / "tsconfig.json"
    node_exe = _find_node_executable()
    if tsc_script.is_file() and tsconfig.is_file() and node_exe is not None:
        steps.append(
            (
                "TypeScript / Vite Compiler (tsc)",
                [node_exe, str(tsc_script), "-p", str(tsconfig), "--noEmit"],
            )
        )

    if include_pytest:
        steps.append(("Pytest Suite", [python_exe, "-m", "pytest", "-q"]))

    failures: list[str] = []
    for label, cmd in steps:
        passed, report = _run_step(label, cmd)
        if not passed:
            failures.append(report)

    return len(failures) == 0, failures


def _handle_stop_hook() -> int:
    """Handle Antigravity Stop lifecycle hook stdin/stdout JSON contract."""
    raw_stdin = sys.stdin.read().strip()
    termination_reason = "NO_TOOL_CALL"
    if raw_stdin:
        try:
            payload: object = json.loads(raw_stdin)
            if isinstance(payload, dict):
                typed_payload = cast("dict[str, object]", payload)
                reason_val = typed_payload.get("terminationReason")
                if isinstance(reason_val, str):
                    termination_reason = reason_val
        except json.JSONDecodeError:
            termination_reason = "NO_TOOL_CALL"

    if termination_reason != "NO_TOOL_CALL":
        sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        return 0

    passed, failures = run_all_checks(include_pytest=False)
    if passed:
        sys.stdout.write(json.dumps({"decision": "allow"}) + "\n")
        return 0

    reason_msg = (
        "Automatic Quality Gate detected IDE/static analysis errors in generated files. "
        "You MUST fix all errors below before finishing your turn:\n\n" + "\n\n".join(failures)
    )
    sys.stdout.write(
        json.dumps(
            {
                "decision": "continue",
                "reason": reason_msg,
            }
        )
        + "\n"
    )
    return 0


def main() -> int:
    """Entrypoint supporting both CLI mode (--cli) and Antigravity Stop hook mode."""
    parser = argparse.ArgumentParser(
        description="Run full IDE & static analysis quality gate (Ruff, Mypy, Pylance, TSC)."
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in human-readable CLI mode (including pytest) instead of Hook JSON mode.",
    )
    args = parser.parse_args()

    if not args.cli:
        return _handle_stop_hook()

    passed, failures = run_all_checks(include_pytest=True)
    if passed:
        sys.stdout.write(
            "QUALITY GATE PASSED: Ruff, Mypy, Pylance (BasedPyright), TypeScript (tsc), and Pytest "
            "all succeeded with 0 errors.\n"
        )
        return 0

    sys.stderr.write("QUALITY GATE FAILED:\n\n" + "\n\n".join(failures) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
