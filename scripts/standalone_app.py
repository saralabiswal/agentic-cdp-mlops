#!/usr/bin/env python3
from __future__ import annotations

"""One-command launcher for standalone synthetic CDP simulation app."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch standalone synthetic CDP simulation app.")
    parser.add_argument("--host", default="127.0.0.1", help="UI/API host bind.")
    parser.add_argument("--port", type=int, default=8080, help="UI/API port bind.")
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip initial synthetic bootstrap run and start server only.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=101,
        help="Seed for synthetic bootstrap execution.",
    )
    return parser.parse_args()


def _bootstrap(seed: int) -> None:
    cmd = [
        sys.executable,
        "ui/adapter/build_view_model.py",
        "--runtime-mode",
        "execute_backend",
        "--execution-mode",
        "synthetic_only",
        "--seed",
        str(seed),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    if not args.skip_bootstrap:
        print("Bootstrapping standalone synthetic data ...")
        _bootstrap(seed=args.seed)
    print(f"Starting live server at http://{args.host}:{args.port}/ui/experience/")
    cmd = [
        sys.executable,
        "scripts/ui_live_server.py",
        "--host",
        str(args.host),
        "--port",
        str(args.port),
    ]
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
