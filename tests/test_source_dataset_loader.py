from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipelines.source_dataset_loader import load_source_tables_for_use_case


def test_load_source_tables_for_use_case_nba_happy_path(tmp_path: Path) -> None:
    use_case_root = tmp_path / "UC-NBA-RET-001"
    use_case_root.mkdir(parents=True, exist_ok=True)

    _write_csv(
        use_case_root / "crm_customers.csv",
        header=[
            "customer_id",
            "consent_status",
            "profile_completeness",
            "no_critical_service_case",
            "do_not_contact",
        ],
        rows=[
            ["CUST-0001", "true", "0.95", "true", "false"],
        ],
    )
    _write_csv(
        use_case_root / "behavior_signals.csv",
        header=[
            "customer_id",
            "risk_score",
            "value_score",
            "score_ts",
            "historical_action_id",
            "observed_uplift",
            "retained_30d",
        ],
        rows=[
            [
                "CUST-0001",
                "0.7",
                "0.8",
                "2026-04-22T00:00:00Z",
                "offer_10pct_discount",
                "0.19",
                "1",
            ],
        ],
    )
    _write_csv(
        use_case_root / "contact_history.csv",
        header=[
            "customer_id",
            "last_marketing_contact_hours",
            "contacts_last_7d",
        ],
        rows=[
            ["CUST-0001", "84", "2"],
        ],
    )

    tables, metadata = load_source_tables_for_use_case(
        use_case_id="UC-NBA-RET-001",
        data_root=tmp_path,
    )

    assert metadata["mode"] == "real_dataset"
    assert tables["crm_customers"][0]["consent_status"] is True
    assert tables["crm_customers"][0]["profile_completeness"] == 0.95
    assert tables["behavior_signals"][0]["observed_uplift"] == 0.19
    assert tables["behavior_signals"][0]["retained_30d"] == 1
    assert tables["contact_history"][0]["last_marketing_contact_hours"] == 84


def test_load_source_tables_emits_dataset_fingerprint_and_readiness_metadata(tmp_path: Path) -> None:
    use_case_root = tmp_path / "UC-NBA-RET-001"
    use_case_root.mkdir(parents=True, exist_ok=True)

    _write_csv(
        use_case_root / "crm_customers.csv",
        header=[
            "customer_id",
            "consent_status",
            "profile_completeness",
            "no_critical_service_case",
            "do_not_contact",
        ],
        rows=[
            ["CUST-0001", "true", "0.95", "true", "false"],
            ["CUST-0002", "true", "0.93", "true", "false"],
            ["CUST-0003", "true", "0.91", "true", "false"],
        ],
    )
    _write_csv(
        use_case_root / "behavior_signals.csv",
        header=[
            "customer_id",
            "risk_score",
            "value_score",
            "score_ts",
            "historical_action_id",
            "observed_uplift",
            "retained_30d",
        ],
        rows=[
            ["CUST-0001", "0.7", "0.8", "2026-04-22T00:00:00Z", "offer_10pct_discount", "0.19", "1"],
            ["CUST-0002", "0.6", "0.7", "2026-04-22T00:00:00Z", "loyalty_bonus_points", "0.18", "0"],
            ["CUST-0003", "0.5", "0.6", "2026-04-22T00:00:00Z", "free_shipping_offer", "0.17", "1"],
        ],
    )
    _write_csv(
        use_case_root / "contact_history.csv",
        header=[
            "customer_id",
            "last_marketing_contact_hours",
            "contacts_last_7d",
        ],
        rows=[
            ["CUST-0001", "84", "2"],
            ["CUST-0002", "96", "1"],
            ["CUST-0003", "72", "3"],
        ],
    )

    _, metadata = load_source_tables_for_use_case(
        use_case_id="UC-NBA-RET-001",
        data_root=tmp_path,
    )
    assert metadata["dataset_versioning"]["schema_version"] == "v1"
    assert metadata["dataset_versioning"]["dataset_fingerprint_sha256"]
    assert metadata["dataset_versioning"]["dataset_version_id"]
    assert metadata["volume_validation"]["status"] == "pass"
    assert metadata["readiness"]["status"] == "pass"


def test_load_source_tables_missing_required_file_raises(tmp_path: Path) -> None:
    use_case_root = tmp_path / "UC-NBA-RET-001"
    use_case_root.mkdir(parents=True, exist_ok=True)
    _write_csv(
        use_case_root / "crm_customers.csv",
        header=[
            "customer_id",
            "consent_status",
            "profile_completeness",
            "no_critical_service_case",
            "do_not_contact",
        ],
        rows=[["CUST-1", "true", "0.9", "true", "false"]],
    )

    with pytest.raises(FileNotFoundError, match="behavior_signals"):
        load_source_tables_for_use_case(
            use_case_id="UC-NBA-RET-001",
            data_root=tmp_path,
        )


def test_load_source_tables_emits_fail_warn_data_quality_checks(tmp_path: Path) -> None:
    use_case_root = tmp_path / "UC-NBA-RET-001"
    use_case_root.mkdir(parents=True, exist_ok=True)

    _write_csv(
        use_case_root / "crm_customers.csv",
        header=[
            "customer_id",
            "consent_status",
            "profile_completeness",
            "no_critical_service_case",
            "do_not_contact",
        ],
        rows=[
            ["CUST-0001", "true", "0.95", "true", "false"],
            ["CUST-0001", "true", "0.94", "true", "false"],
        ],
    )
    _write_csv(
        use_case_root / "behavior_signals.csv",
        header=[
            "customer_id",
            "risk_score",
            "value_score",
            "score_ts",
            "historical_action_id",
            "observed_uplift",
            "retained_30d",
        ],
        rows=[
            [
                "CUST-0001",
                "1.20",
                "0.8",
                "2026-04-22T00:00:00Z",
                "unsupported_action",
                "0.19",
                "1",
            ],
            [
                "CUST-0002",
                "0.6",
                "0.5",
                "2026-04-22T00:00:00Z",
                "offer_10pct_discount",
                "0.18",
                "0",
            ],
        ],
    )
    _write_csv(
        use_case_root / "contact_history.csv",
        header=[
            "customer_id",
            "last_marketing_contact_hours",
            "contacts_last_7d",
        ],
        rows=[
            ["CUST-0001", "84", "2"],
            ["CUST-0002", "72", "1"],
        ],
    )

    _, metadata = load_source_tables_for_use_case(
        use_case_id="UC-NBA-RET-001",
        data_root=tmp_path,
    )
    data_quality = metadata["data_quality"]
    assert data_quality["status"] == "fail"
    assert data_quality["summary"]["failed_checks"] >= 1
    assert data_quality["summary"]["warn_checks"] >= 1

    failed_names = {
        row["name"]
        for row in data_quality["checks"]
        if row["status"] == "fail"
    }
    warn_names = {
        row["name"]
        for row in data_quality["checks"]
        if row["status"] == "warn"
    }
    assert "unique_key_customer_id" in failed_names
    assert "range_risk_score" in failed_names
    assert "enum_historical_action_id" in warn_names


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
