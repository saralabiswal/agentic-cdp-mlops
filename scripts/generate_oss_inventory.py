#!/usr/bin/env python3
from __future__ import annotations

"""Generate OSS component + license inventory artifacts for demo transparency."""

import json
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "docs" / "OSS_INVENTORY.json"
OUTPUT_MD = ROOT / "docs" / "OSS_LICENSE_SUMMARY.md"

REQ_FILES = [
    ROOT / "requirements.txt",
    ROOT / "requirements-ml.txt",
]

CORE_COMPONENTS: list[dict[str, str]] = [
    {"component": "UI", "technology": "Static HTML/CSS/JavaScript", "license": "Custom project code", "source": "repo"},
    {"component": "API Server", "technology": "Python http.server", "license": "PSF", "source": "stdlib"},
    {"component": "Orchestration", "technology": "Python orchestrator", "license": "Custom project code", "source": "repo"},
    {"component": "Event Streaming", "technology": "Apache Kafka", "license": "Apache-2.0", "source": "optional_oss_profile"},
    {"component": "Curated Store", "technology": "PostgreSQL", "license": "PostgreSQL License", "source": "optional_oss_profile"},
    {"component": "Object Storage", "technology": "MinIO", "license": "AGPL-3.0", "source": "optional_oss_profile"},
    {"component": "Identity Resolution", "technology": "Splink adapter", "license": "MIT", "source": "optional_product_integration"},
    {"component": "Feature Store", "technology": "Feast adapter", "license": "Apache-2.0", "source": "optional_product_integration"},
    {"component": "Model Tracking", "technology": "MLflow adapter", "license": "Apache-2.0", "source": "optional_product_integration"},
    {"component": "Workflow Orchestration", "technology": "Airflow DAG adapter", "license": "Apache-2.0", "source": "optional_product_integration"},
    {"component": "Identity and Access", "technology": "Keycloak OIDC adapter", "license": "Apache-2.0", "source": "optional_product_integration"},
    {"component": "Observability", "technology": "Prometheus + Grafana adapter", "license": "Apache-2.0 + AGPL-3.0", "source": "optional_product_integration"},
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_requirement_name(line: str) -> str | None:
    token = line.strip()
    if not token or token.startswith("#"):
        return None
    # Strip markers/comments and extract leading package token.
    token = token.split(";", 1)[0].strip()
    token = token.split("#", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)", token)
    if not match:
        return None
    return match.group(1)


def _load_requirement_packages() -> list[str]:
    packages: list[str] = []
    for path in REQ_FILES:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            name = _parse_requirement_name(raw_line)
            if not name:
                continue
            packages.append(name)
    return sorted(set(packages), key=lambda row: row.lower())


def _resolve_installed_license(package_name: str) -> str:
    try:
        meta = metadata.metadata(package_name)
    except metadata.PackageNotFoundError:
        return "unknown (not installed)"
    except Exception:
        return "unknown"
    license_value = str(meta.get("License", "")).strip()
    if license_value:
        return license_value
    classifiers = meta.get_all("Classifier", [])
    if classifiers:
        for row in classifiers:
            text = str(row)
            if text.startswith("License ::"):
                return text.replace("License ::", "").strip()
    return "unknown"


def _build_dependency_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for pkg in _load_requirement_packages():
        rows.append(
            {
                "component": "Python Dependency",
                "technology": pkg,
                "license": _resolve_installed_license(pkg),
                "source": "requirements",
            }
        )
    return rows


def _write_json(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(payload: dict[str, Any]) -> None:
    rows = payload.get("components", [])
    lines = [
        "# OSS License Summary",
        "",
        f"Generated at (UTC): `{payload.get('generated_at_utc', 'unknown')}`",
        "",
        "| Component | Technology | License | Source |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("component", "")),
                    str(row.get("technology", "")),
                    str(row.get("license", "")),
                    str(row.get("source", "")),
                ]
            )
            + " |"
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _relativize(path: Path) -> str:
    """Return repo-relative path when possible, else absolute path."""
    try:
        return str(path.relative_to(ROOT).as_posix())
    except ValueError:
        return str(path.as_posix())


def main() -> int:
    rows = CORE_COMPONENTS + _build_dependency_rows()
    payload = {
        "generated_at_utc": _utc_now(),
        "generator": "scripts/generate_oss_inventory.py",
        "source_files": [_relativize(path) for path in REQ_FILES if path.exists()],
        "components": rows,
    }
    _write_json(payload)
    _write_markdown(payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "components": len(rows),
                "json_output": _relativize(OUTPUT_JSON),
                "markdown_output": _relativize(OUTPUT_MD),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
