from __future__ import annotations

import subprocess
import sys


def test_demo_script_syntax() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/demo_nba_oss.py", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "--compact" in result.stdout
