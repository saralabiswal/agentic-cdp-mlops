from __future__ import annotations

"""Runtime helpers for advanced model backends and artifact persistence."""

import hashlib
import importlib
import json
import random
from pathlib import Path
from typing import Any


def optional_import(module_name: str) -> tuple[Any | None, str | None]:
    """Try importing optional dependency and return (module, error)."""
    try:
        module = importlib.import_module(module_name)
        return module, None
    except Exception as exc:  # pragma: no cover - depends on environment packages.
        return None, f"{module_name}: {exc}"


def deterministic_holdout_mask(
    rows: list[dict[str, Any]],
    *,
    seed: int,
    holdout_ratio: float = 0.2,
) -> list[bool]:
    """Create deterministic train/holdout assignment by hashed row payload."""
    threshold = int(max(0.0, min(1.0, holdout_ratio)) * 100)
    mask: list[bool] = []
    for idx, row in enumerate(rows):
        payload = json.dumps(row, sort_keys=True, separators=(",", ":"))
        token = f"{seed}:{idx}:{payload}".encode("utf-8")
        bucket = int(hashlib.sha256(token).hexdigest()[:8], 16) % 100
        mask.append(bucket < threshold)
    return mask


def write_json(path: Path, payload: dict[str, Any]) -> str:
    """Write JSON file and return POSIX path string."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return str(path.as_posix())


def set_reproducible_seed(seed: int) -> None:
    """Seed Python-level RNG for deterministic fallback behavior."""
    random.seed(seed)
