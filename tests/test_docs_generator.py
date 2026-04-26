from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_generate_tech_docs_script(tmp_path: Path) -> None:
    output_path = tmp_path / "TECHNICAL_ARCHITECTURE.md"
    cmd = [
        sys.executable,
        "docs/generate_tech_docs.py",
        "--output",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, text=True, capture_output=True)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "Technical Architecture (Auto-Generated)" in content
    assert "stack/orchestrator.py" in content
    assert "Stage 1: Data Sources" in content

