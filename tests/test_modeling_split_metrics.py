from __future__ import annotations

from stack.layers.modeling import _build_split_metrics


def _sample_incrementality_rows(row_count: int) -> list[dict[str, object]]:
    """Create deterministic synthetic incrementality rows for split diagnostics."""
    rows: list[dict[str, object]] = []
    for idx in range(1, row_count + 1):
        rows.append(
            {
                "campaign_id": f"CMP-{idx:03d}",
                "test_window": "2026-03-01_to_2026-04-12",
                "incremental_lift": round(0.001 * idx, 6),
                "iROAS": round(0.75 + (idx * 0.03), 6),
                "analysis_version": "incrementality_causal_v1",
            }
        )
    return rows


def test_split_metrics_incrementality_default_seed_respects_thresholds() -> None:
    rows = _sample_incrementality_rows(row_count=18)
    metrics = _build_split_metrics(
        rows=rows,
        seed=7,
        use_case_id="UC-INCR-MKT-004",
    )

    assert metrics["train_row_count"] >= 10
    assert metrics["holdout_row_count"] >= 2
    assert 0.05 <= float(metrics["holdout_ratio"]) <= 0.45
    assert (metrics["train_row_count"] + metrics["holdout_row_count"]) == 18


def test_split_metrics_deterministic_for_same_seed() -> None:
    rows = _sample_incrementality_rows(row_count=18)
    first = _build_split_metrics(
        rows=rows,
        seed=7,
        use_case_id="UC-INCR-MKT-004",
    )
    second = _build_split_metrics(
        rows=rows,
        seed=7,
        use_case_id="UC-INCR-MKT-004",
    )
    assert first == second

