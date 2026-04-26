from __future__ import annotations

import json
from pathlib import Path

from stack.run_registry import (
    build_run_registry_index,
    get_run_summary,
    list_run_summaries,
    prune_run_artifacts,
)


def test_list_run_summaries_filters_search_and_pagination(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        run_status="fail",
        infra_profile="oss",
        seed=202,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-CHURN-RET-002",
        run_id="20270103T010101Z",
        run_status="pass",
        infra_profile="oss",
        seed=101,
    )

    payload = list_run_summaries(artifacts_root=artifacts_root, limit=10)
    assert payload["total"] == 3
    assert payload["count"] == 3
    assert payload["runs"][0]["run_id"] == "20270103T010101Z"

    filtered = list_run_summaries(
        artifacts_root=artifacts_root,
        run_status="pass",
        infra_profile="oss",
        seed=101,
        limit=10,
    )
    assert filtered["total"] == 1
    assert filtered["runs"][0]["use_case_id"] == "UC-CHURN-RET-002"

    searched = list_run_summaries(
        artifacts_root=artifacts_root,
        query="nba",
        limit=10,
    )
    assert searched["total"] == 2

    paged = list_run_summaries(
        artifacts_root=artifacts_root,
        sort="asc",
        limit=1,
        offset=1,
    )
    assert paged["total"] == 3
    assert paged["count"] == 1
    assert paged["runs"][0]["run_id"] == "20270102T010101Z"


def test_get_run_summary_found_and_missing(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-MMM-PLN-003",
        run_id="20270104T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=55,
    )

    payload = get_run_summary(
        use_case_id="UC-MMM-PLN-003",
        run_id="20270104T010101Z",
        artifacts_root=artifacts_root,
    )
    assert payload is not None
    assert payload["use_case_id"] == "UC-MMM-PLN-003"
    assert payload["run_id"] == "20270104T010101Z"
    assert "summary_path" in payload

    missing = get_run_summary(
        use_case_id="UC-MMM-PLN-003",
        run_id="does-not-exist",
        artifacts_root=artifacts_root,
    )
    assert missing is None


def test_run_registry_index_build_and_refresh(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )

    index_payload = build_run_registry_index(artifacts_root=artifacts_root)
    assert index_payload["rows_indexed"] == 1
    index_path = artifacts_root / ".run_registry_index.json"
    assert index_path.exists()

    listed = list_run_summaries(artifacts_root=artifacts_root, limit=10)
    assert listed["index"]["used"] is True
    assert listed["index"]["entry_count"] == 1

    # Add one more run and verify index refresh happens on next listing.
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        run_status="fail",
        infra_profile="oss",
        seed=202,
    )
    listed_after_add = list_run_summaries(artifacts_root=artifacts_root, limit=10)
    assert listed_after_add["total"] == 2
    assert listed_after_add["index"]["entry_count"] == 2


def test_prune_run_artifacts_dry_run_and_apply(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )

    dry_run = prune_run_artifacts(
        artifacts_root=artifacts_root,
        keep_per_use_case=1,
        apply=False,
    )
    assert dry_run["apply"] is False
    assert len(dry_run["planned_deletions"]) == 1
    assert dry_run["deleted_count"] == 0

    applied = prune_run_artifacts(
        artifacts_root=artifacts_root,
        keep_per_use_case=1,
        apply=True,
    )
    assert applied["apply"] is True
    assert applied["deleted_count"] == 1

    listed = list_run_summaries(artifacts_root=artifacts_root, limit=10)
    assert listed["total"] == 1


def _write_summary(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    run_status: str,
    infra_profile: str,
    seed: int,
) -> None:
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "use_case_id": use_case_id,
        "name": f"Name {use_case_id}",
        "run_id": run_id,
        "seed": seed,
        "infra_profile": infra_profile,
        "run_status": run_status,
        "model_metrics": {"primary_kpi": "kpi_metric"},
        "records": {
            "curated_rows": 10,
            "feature_rows": 10,
            "model_rows": 10,
            "activation_rows": 10,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")
