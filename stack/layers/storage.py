from __future__ import annotations

"""Stage 3: Raw Storage + Curated Warehouse.

This layer writes:
- raw append-only event logs
- curated record sets aligned to the active use case

Curated JSON and JSONL outputs are both produced so downstream steps can use
either document-style reads or line-oriented bulk loading.
"""

import json
from pathlib import Path
from typing import Any

from stack.layers.ingestion_event_bus import LocalEventBus


def build_raw_and_curated_storage(
    use_case_id: str, bus: LocalEventBus, output_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Materialize raw and curated datasets and return curated rows + artifact paths."""
    raw_dir = output_dir / "storage" / "raw"
    curated_dir = output_dir / "storage" / "curated"
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    raw_events = bus.all_events()
    raw_file = raw_dir / "events.jsonl"
    with raw_file.open("w", encoding="utf-8") as f:
        for event in raw_events:
            f.write(json.dumps(event) + "\n")

    curated_rows = _build_curated_rows(use_case_id=use_case_id, bus=bus)
    curated_file = curated_dir / "records.json"
    with curated_file.open("w", encoding="utf-8") as f:
        json.dump(curated_rows, f, indent=2)

    curated_jsonl_file = curated_dir / "records.jsonl"
    with curated_jsonl_file.open("w", encoding="utf-8") as f:
        for row in curated_rows:
            f.write(json.dumps(row) + "\n")

    return curated_rows, {
        "raw_events": str(raw_file),
        "curated_records": str(curated_file),
        "curated_records_jsonl": str(curated_jsonl_file),
    }


def _build_curated_rows(use_case_id: str, bus: LocalEventBus) -> list[dict[str, Any]]:
    """Dispatch curation strategy based on use-case contract."""
    if use_case_id == "UC-NBA-RET-001":
        return _curate_nba(bus)
    if use_case_id == "UC-CHURN-RET-002":
        return _curate_churn(bus)
    if use_case_id == "UC-MMM-PLN-003":
        return _table_payload(bus, suffix="media_spend")
    if use_case_id == "UC-INCR-MKT-004":
        return _table_payload(bus, suffix="campaign_experiments")
    raise ValueError(f"Unsupported use_case_id '{use_case_id}'")


def _table_payload(bus: LocalEventBus, suffix: str) -> list[dict[str, Any]]:
    """Read payloads from the topic matching the given table suffix."""
    topic = _find_topic_with_suffix(bus=bus, suffix=suffix)
    return [event["payload"] for event in bus.topics.get(topic, [])]


def _curate_nba(bus: LocalEventBus) -> list[dict[str, Any]]:
    """Join NBA source entities into one curated customer-centric rowset."""
    customers = _index_by_key(_table_payload(bus, suffix="crm_customers"), "customer_id")
    behavior = _index_by_key(_table_payload(bus, suffix="behavior_signals"), "customer_id")
    contact = _index_by_key(_table_payload(bus, suffix="contact_history"), "customer_id")

    curated: list[dict[str, Any]] = []
    for customer_id, profile in customers.items():
        curated.append(
            {
                "customer_id": customer_id,
                **profile,
                **behavior[customer_id],
                **contact[customer_id],
            }
        )
    return curated


def _curate_churn(bus: LocalEventBus) -> list[dict[str, Any]]:
    """Join churn source entities into one curated customer-centric rowset."""
    customers = _index_by_key(_table_payload(bus, suffix="crm_customers"), "customer_id")
    usage = _index_by_key(_table_payload(bus, suffix="usage_signals"), "customer_id")
    support = _index_by_key(_table_payload(bus, suffix="support_events"), "customer_id")

    curated: list[dict[str, Any]] = []
    for customer_id, profile in customers.items():
        curated.append(
            {
                "customer_id": customer_id,
                **profile,
                **usage[customer_id],
                **support[customer_id],
            }
        )
    return curated


def _find_topic_with_suffix(bus: LocalEventBus, suffix: str) -> str:
    """Locate topic by table suffix using the canonical naming convention."""
    for topic in bus.topics:
        # Supports both:
        # 1) local topic: raw.<use_case_slug>.<table>.v1
        # 2) OSS run-scoped topic: raw.<use_case_slug>.<table>.v1.<run_id>
        parts = topic.split(".")
        if len(parts) >= 2 and parts[-2] == suffix and parts[-1] == "v1":
            return topic
        if len(parts) >= 3 and parts[-3] == suffix and parts[-2] == "v1":
            return topic
    raise ValueError(f"No topic found with suffix '{suffix}.v1'")


def _index_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    """Build dictionary index for deterministic key-based joins."""
    return {row[key]: row for row in rows}
