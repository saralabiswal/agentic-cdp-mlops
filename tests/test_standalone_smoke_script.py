from __future__ import annotations

import subprocess
import sys


def test_standalone_smoke_script_help() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/standalone_smoke_test.py", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "Smoke test standalone UI/API flow." in completed.stdout
    assert "--skip-bootstrap" in completed.stdout

