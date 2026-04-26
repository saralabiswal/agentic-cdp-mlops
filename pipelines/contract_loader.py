from __future__ import annotations

"""Use-case contract loading and validation.

Contracts are the control plane for this platform. They define expected entities,
features, output schema, decision policy, experimentation setup, governance,
and monitoring configuration.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_DIR = Path("use_cases/configs")


@dataclass(frozen=True)
class OutputContract:
    """Output schema and service-level metadata for model results."""

    type: str
    fields: list[str]
    sla_latency_ms: int
    refresh: str


@dataclass(frozen=True)
class UseCaseContract:
    """Typed representation of one YAML use-case contract."""

    use_case_id: str
    name: str
    primary_kpi: str
    baseline: float | None
    target: float | None
    entities: list[str]
    features: list[str]
    output_contract: OutputContract
    decision_policy: dict[str, Any]
    experiment: dict[str, Any]
    governance: dict[str, Any]
    monitoring: dict[str, Any]
    raw: dict[str, Any]


def list_config_paths(config_dir: Path = DEFAULT_CONFIG_DIR) -> list[Path]:
    """List all YAML configs discovered under the use-case config directory."""
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory does not exist: {config_dir}")
    return sorted(config_dir.glob("*.yaml"))


def load_contract(config_path: Path) -> UseCaseContract:
    """Load and validate one YAML file into a strongly-typed contract object."""
    with config_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    _validate_required(raw, config_path)
    output = raw["output_contract"]

    return UseCaseContract(
        use_case_id=raw["use_case_id"],
        name=raw["name"],
        primary_kpi=raw["primary_kpi"],
        baseline=raw.get("baseline"),
        target=raw.get("target"),
        entities=list(raw.get("entities", [])),
        features=list(raw.get("features", [])),
        output_contract=OutputContract(
            type=output["type"],
            fields=list(output.get("fields", [])),
            sla_latency_ms=int(output.get("sla_latency_ms", 0)),
            refresh=str(output.get("refresh", "")),
        ),
        decision_policy=dict(raw.get("decision_policy", {})),
        experiment=dict(raw.get("experiment", {})),
        governance=dict(raw.get("governance", {})),
        monitoring=dict(raw.get("monitoring", {})),
        raw=raw,
    )


def load_contract_by_id(
    use_case_id: str, config_dir: Path = DEFAULT_CONFIG_DIR
) -> UseCaseContract:
    """Resolve contract by use-case identifier."""
    for path in list_config_paths(config_dir):
        contract = load_contract(path)
        if contract.use_case_id == use_case_id:
            return contract
    raise FileNotFoundError(f"No config found for use_case_id '{use_case_id}'")


def _validate_required(raw: dict[str, Any], config_path: Path) -> None:
    """Validate required top-level and output-contract keys."""
    required_top = {
        "use_case_id",
        "name",
        "primary_kpi",
        "entities",
        "features",
        "output_contract",
        "decision_policy",
        "experiment",
        "governance",
        "monitoring",
    }
    missing_top = sorted(required_top - set(raw))
    if missing_top:
        raise ValueError(f"{config_path} missing top-level keys: {missing_top}")

    output = raw.get("output_contract")
    if not isinstance(output, dict):
        raise ValueError(f"{config_path} 'output_contract' must be an object")

    required_output = {"type", "fields", "sla_latency_ms", "refresh"}
    missing_output = sorted(required_output - set(output))
    if missing_output:
        raise ValueError(f"{config_path} missing output keys: {missing_output}")
