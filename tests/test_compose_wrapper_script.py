from __future__ import annotations

import subprocess


def test_compose_wrapper_script_syntax() -> None:
    subprocess.run(
        ["bash", "-n", "scripts/compose.sh"],
        check=True,
        text=True,
        capture_output=True,
    )

