"""Forwarding E2E test runner for Orchestra.

Invokes prototype/tests/test_e2e.py using the Python standard library,
forwarding command-line arguments and preserving the exit code.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "prototype" / "tests" / "test_e2e.py"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not TARGET.is_file():
        sys.stderr.write(f"Error: Target test runner not found at {TARGET}\n")
        return 1

    cmd = [sys.executable, str(TARGET), *argv]
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
