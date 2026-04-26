from __future__ import annotations

"""Compose command compatibility helpers.

Supports both:
1) `docker compose`
2) `docker-compose`
"""

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def detect_compose_command() -> list[str]:
    """Return the available compose command prefix."""
    candidates = [
        ["docker", "compose"],
        ["docker-compose"],
    ]
    for candidate in candidates:
        result = subprocess.run(
            [*candidate, "version"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    raise RuntimeError(
        "Docker Compose is not available. Install either 'docker compose' plugin or 'docker-compose'."
    )


def compose_cmd(compose_file: Path, args: list[str]) -> list[str]:
    """Build a compose command with selected file and arguments."""
    base = detect_compose_command()
    return [*base, "-f", str(compose_file), *args]

