from __future__ import annotations

"""Stage 4: Identity Resolution + Customer 360.

For customer-level use cases, this layer creates a deterministic unified ID
and household grouping. For aggregate use cases (MMM/incrementality), it
passes data through and records that identity stitching is not applicable.
"""

import json
from pathlib import Path
from typing import Any


def resolve_identity_customer_360(
    use_case_id: str, curated_rows: list[dict[str, Any]], output_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Resolve/augment identity records and persist identity artifacts."""
    target_dir = output_dir / "identity_360"
    target_dir.mkdir(parents=True, exist_ok=True)

    if use_case_id in {"UC-NBA-RET-001", "UC-CHURN-RET-002"}:
        identity_map: list[dict[str, Any]] = []
        updated_rows: list[dict[str, Any]] = []

        for row in curated_rows:
            customer_id = row["customer_id"]
            unified_id = f"U-{customer_id}"
            # Stable synthetic household key to demonstrate household-level grouping.
            household_id = f"H-{int(customer_id.split('-')[1]) % 25:03d}"
            identity_map.append(
                {
                    "source_customer_id": customer_id,
                    "unified_customer_id": unified_id,
                    "household_id": household_id,
                    "match_confidence": 0.98,
                    "resolution_type": "deterministic",
                }
            )

            updated = dict(row)
            updated["unified_customer_id"] = unified_id
            updated["household_id"] = household_id
            updated_rows.append(updated)

        map_file = target_dir / "identity_map.json"
        with map_file.open("w", encoding="utf-8") as f:
            json.dump(identity_map, f, indent=2)

        resolved_file = target_dir / "resolved_records.json"
        with resolved_file.open("w", encoding="utf-8") as f:
            json.dump(updated_rows, f, indent=2)

        return updated_rows, {
            "identity_map": str(map_file),
            "resolved_records": str(resolved_file),
        }

    passthrough_file = target_dir / "resolved_records.json"
    with passthrough_file.open("w", encoding="utf-8") as f:
        json.dump(curated_rows, f, indent=2)

    note_file = target_dir / "note.txt"
    note_file.write_text(
        "Customer-level identity resolution is not applicable for this use case.",
        encoding="utf-8",
    )

    return curated_rows, {"resolved_records": str(passthrough_file), "note": str(note_file)}
