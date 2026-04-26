from __future__ import annotations

import subprocess


def test_ci_refresh_status_docs_script_syntax() -> None:
    subprocess.run(
        ["bash", "-n", "scripts/ci_refresh_status_docs.sh"],
        check=True,
        text=True,
        capture_output=True,
    )

