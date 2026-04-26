from __future__ import annotations

import subprocess


def test_infra_smoke_script_syntax() -> None:
    subprocess.run(
        ["bash", "-n", "scripts/infra_smoke_test.sh"],
        check=True,
        text=True,
        capture_output=True,
    )

