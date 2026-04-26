from __future__ import annotations

import json
from pathlib import Path

import scripts.generate_oss_inventory as generator


def test_generate_oss_inventory_outputs_files(tmp_path: Path, monkeypatch) -> None:
    req_main = tmp_path / "requirements.txt"
    req_ml = tmp_path / "requirements-ml.txt"
    req_main.write_text("PyYAML==6.0.2\npytest==8.3.5\n", encoding="utf-8")
    req_ml.write_text("numpy>=1.26.0\n", encoding="utf-8")

    out_json = tmp_path / "OSS_INVENTORY.json"
    out_md = tmp_path / "OSS_LICENSE_SUMMARY.md"

    monkeypatch.setattr(generator, "REQ_FILES", [req_main, req_ml])
    monkeypatch.setattr(generator, "OUTPUT_JSON", out_json)
    monkeypatch.setattr(generator, "OUTPUT_MD", out_md)

    status = generator.main()
    assert status == 0
    assert out_json.exists()
    assert out_md.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "generated_at_utc" in payload
    assert isinstance(payload.get("components"), list)
    assert len(payload["components"]) >= 3
