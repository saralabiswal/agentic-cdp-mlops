#!/usr/bin/env python3
from __future__ import annotations

"""Run a one-command smoke test for standalone UI/API simulation flow."""

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test standalone UI/API flow.")
    parser.add_argument("--host", default="127.0.0.1", help="Server bind host.")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Server port. Use 0 to auto-select a free local port.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Max seconds to wait for server health.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip standalone bootstrap step for faster smoke checks.",
    )
    parser.add_argument(
        "--use-case-id",
        default="UC-NBA-RET-001",
        help="Use-case ID for simulation session checks.",
    )
    parser.add_argument(
        "--scenario-id",
        default="nba_high_risk_save",
        help="Scenario preset for deterministic simulation check.",
    )
    parser.add_argument(
        "--runtime-mode",
        default="synthetic_only",
        choices=["default", "synthetic_only"],
        help="Execution runtime mode for simulation session.",
    )
    parser.add_argument(
        "--infra-profile",
        default="local",
        choices=["local", "oss"],
        help="Infrastructure profile for simulation session.",
    )
    parser.add_argument("--seed", type=int, default=101, help="Deterministic seed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    port = args.port if args.port > 0 else _pick_free_port(args.host)
    log_path = Path(tempfile.gettempdir()) / f"cdp-standalone-smoke-{int(time.time())}.log"

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "standalone_app.py"),
        "--host",
        args.host,
        "--port",
        str(port),
    ]
    if args.skip_bootstrap:
        cmd.append("--skip-bootstrap")

    print(f"Starting standalone app on http://{args.host}:{port} (log: {log_path})")
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    try:
        health = _wait_for_health(
            host=args.host,
            port=port,
            timeout_seconds=max(1, args.timeout_seconds),
            process=process,
            log_path=log_path,
        )
        base = f"http://{args.host}:{port}"
        oss_payload = _request_json(f"{base}/api/oss-inventory")
        create_payload = _request_json(
            f"{base}/api/simulation/session",
            method="POST",
            payload={
                "use_case_id": args.use_case_id,
                "infra_profile": args.infra_profile,
                "seed": int(args.seed),
                "runtime_mode": args.runtime_mode,
                "scenario_id": args.scenario_id,
                "failure_injection": [],
            },
        )

        session_id = str(create_payload.get("session_id", "")).strip()
        if not session_id:
            raise RuntimeError("Simulation create response missing session_id.")

        state0 = _request_json(f"{base}/api/simulation/session/{session_id}")
        run_next = _request_json(
            f"{base}/api/simulation/session/{session_id}/run-next",
            method="POST",
            payload={},
        )
        run_all = _request_json(
            f"{base}/api/simulation/session/{session_id}/run-all",
            method="POST",
            payload={},
        )
        reset = _request_json(
            f"{base}/api/simulation/session/{session_id}/reset",
            method="POST",
            payload={},
        )

        _validate_stage_progress(state0=state0, run_next=run_next, run_all=run_all, reset=reset)

        component_count = 0
        if isinstance(oss_payload.get("components"), list):
            component_count = len(oss_payload["components"])

        summary = {
            "health_status": health.get("status"),
            "host": args.host,
            "port": port,
            "oss_component_count": component_count,
            "session_id": session_id,
            "state0_stage_cursor": state0.get("stage_cursor"),
            "run_next_stage_cursor": run_next.get("stage_cursor"),
            "run_next_run_status": run_next.get("run_status"),
            "run_all_stage_cursor": run_all.get("stage_cursor"),
            "run_all_stage_total": run_all.get("stage_total"),
            "reset_stage_cursor": reset.get("stage_cursor"),
        }
        print("SMOKE_OK")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print("SMOKE_FAIL")
        print(str(exc))
        print(f"log_path={log_path}")
        tail = _tail(log_path, limit=60)
        if tail:
            print("--- standalone log tail ---")
            print(tail)
        return 1
    finally:
        _stop_process(process)


def _pick_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def _wait_for_health(
    *,
    host: str,
    port: int,
    timeout_seconds: int,
    process: subprocess.Popen[str],
    log_path: Path,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://{host}:{port}/api/health"
    last_error: str | None = None
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            tail = _tail(log_path, limit=60)
            raise RuntimeError(
                f"Standalone process exited early with code {exit_code}. "
                f"Log tail:\n{tail}"
            )
        try:
            payload = _request_json(url)
            if payload.get("status") == "ok":
                return payload
            last_error = f"Unexpected health payload: {payload}"
        except Exception as exc:  # pragma: no cover - transient retries.
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(
        f"Timed out waiting for healthy server on {url}. "
        f"Last error: {last_error or 'none'}"
    )


def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body: bytes | None = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib_request.Request(url=url, method=method, data=body, headers=headers)
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} returned non-JSON body: {text[:300]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{method} {url} returned non-object JSON payload.")
    return parsed


def _validate_stage_progress(
    *,
    state0: dict[str, Any],
    run_next: dict[str, Any],
    run_all: dict[str, Any],
    reset: dict[str, Any],
) -> None:
    state0_cursor = _to_int(state0.get("stage_cursor"))
    run_next_cursor = _to_int(run_next.get("stage_cursor"))
    run_all_cursor = _to_int(run_all.get("stage_cursor"))
    run_all_total = _to_int(run_all.get("stage_total"))
    reset_cursor = _to_int(reset.get("stage_cursor"))

    if state0_cursor != 0:
        raise RuntimeError(f"Expected initial stage_cursor=0, got {state0_cursor}")
    if run_next_cursor < 1:
        raise RuntimeError(f"Expected run-next stage_cursor>=1, got {run_next_cursor}")
    if run_all_total < 1:
        raise RuntimeError(f"Expected run-all stage_total>=1, got {run_all_total}")
    if run_all_cursor != run_all_total:
        raise RuntimeError(
            f"Expected run-all stage_cursor==stage_total, got cursor={run_all_cursor}, total={run_all_total}"
        )
    if reset_cursor != 0:
        raise RuntimeError(f"Expected reset stage_cursor=0, got {reset_cursor}")


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _tail(path: Path, *, limit: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""
    return "\n".join(lines[-limit:])


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())

