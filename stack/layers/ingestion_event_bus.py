from __future__ import annotations

"""Stage 2: Ingestion + Event Bus.

This layer normalizes source tables into topic-based events and stores an
append-only event log as JSONL artifacts. The in-memory bus keeps the runner
self-contained while preserving event-driven semantics.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LocalEventBus:
    """Minimal in-memory event bus abstraction used by local fallback runs."""

    topics: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Append event payload to a topic with ingestion timestamp."""
        event = {
            "event_ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "payload": payload,
        }
        self.topics.setdefault(topic, []).append(event)

    def all_events(self) -> list[dict[str, Any]]:
        """Return all events in deterministic topic order for reproducible outputs."""
        all_events: list[dict[str, Any]] = []
        for topic in sorted(self.topics):
            all_events.extend(self.topics[topic])
        return all_events


def ingest_to_event_bus(
    use_case_id: str,
    source_tables: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> tuple[LocalEventBus, dict[str, str]]:
    """Publish source rows to canonical raw topics and persist topic files."""
    bus = LocalEventBus()
    use_case_slug = use_case_id.lower().replace("-", "_")

    for table_name, rows in source_tables.items():
        topic = f"raw.{use_case_slug}.{table_name}.v1"
        for row in rows:
            bus.publish(topic=topic, payload=row)

    target = output_dir / "ingestion" / "event_bus"
    target.mkdir(parents=True, exist_ok=True)

    artifact_paths: dict[str, str] = {}
    for topic, events in bus.topics.items():
        safe_topic = topic.replace(".", "_")
        topic_file = target / f"{safe_topic}.jsonl"
        with topic_file.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        artifact_paths[topic] = str(topic_file)

    return bus, artifact_paths
