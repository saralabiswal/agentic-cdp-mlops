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


def test_generate_user_guide_pdf_with_screenshots(tmp_path: Path) -> None:
    output_path = tmp_path / "USER_GUIDE.pdf"
    cmd = [
        sys.executable,
        "docs/generate_user_guide_pdf.py",
        "--output",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, text=True, capture_output=True)

    guide = Path("docs/USER_GUIDE.md").read_text(encoding="utf-8")
    assert "## 2. Current App Navigation" in guide
    assert "## 4. Visual Walkthrough" in guide
    assert "assets/user-guide/00-about.png" in guide
    assert "assets/user-guide/01-ai-decision-portfolio.png" in guide
    assert "assets/user-guide/05-simulation-flow.png" in guide
    assert "assets/user-guide/08-technical-model-evidence.png" in guide
    assert Path("docs/assets/user-guide/00-about.png").exists()
    assert Path("docs/assets/user-guide/01-ai-decision-portfolio.png").exists()
    assert Path("docs/assets/user-guide/05-simulation-flow.png").exists()
    assert Path("docs/assets/user-guide/08-technical-model-evidence.png").exists()
    assert output_path.exists()
    assert output_path.stat().st_size > 100_000
