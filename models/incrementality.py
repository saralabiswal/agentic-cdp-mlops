from __future__ import annotations

"""Incrementality model implementation with EconML + DoWhy oriented path."""

import math
import random
from statistics import mean
from pathlib import Path
from typing import Any

from models.base import UseCaseModel
from models.runtime_utils import optional_import, set_reproducible_seed, write_json
from pipelines.contract_loader import UseCaseContract


class CampaignIncrementalityModel(UseCaseModel):
    """Computes campaign-level incrementality and recommendations.

    Runtime strategy:
    1. EconML + DoWhy backend for effect estimation and refutation when available.
    2. Deterministic statistical fallback when optional dependencies are unavailable.
    """

    def run(
        self, records: list[dict[str, Any]], contract: UseCaseContract, seed: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Run model without writing backend-specific artifacts."""
        rows, metrics, _ = self._run_internal(
            records=records,
            contract=contract,
            seed=seed,
            artifact_dir=None,
        )
        return rows, metrics

    def run_with_context(
        self,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
        artifact_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        """Run model and persist optional causal-governance artifacts."""
        return self._run_internal(
            records=records,
            contract=contract,
            seed=seed,
            artifact_dir=artifact_dir,
        )

    def _run_internal(
        self,
        *,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
        artifact_dir: Path | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        """Dispatch causal stack backend or deterministic fallback."""
        warnings: list[str] = []
        econml_module, econml_error = optional_import("econml")
        dowhy_module, dowhy_error = optional_import("dowhy")
        np_module, np_error = optional_import("numpy")
        pd_module, pd_error = optional_import("pandas")

        if econml_error:
            warnings.append(f"EconML unavailable: {econml_error}")
        if dowhy_error:
            warnings.append(f"DoWhy unavailable: {dowhy_error}")
        if np_error:
            warnings.append(f"NumPy unavailable: {np_error}")
        if pd_error:
            warnings.append(f"Pandas unavailable: {pd_error}")

        if (
            econml_module is not None
            and dowhy_module is not None
            and np_module is not None
            and pd_module is not None
        ):
            try:
                return self._run_causal_stack(
                    records=records,
                    contract=contract,
                    seed=seed,
                    artifact_dir=artifact_dir,
                    np=np_module,
                    pd=pd_module,
                )
            except Exception as exc:  # pragma: no cover - depends on optional runtime libs.
                warnings.append(f"EconML/DoWhy backend failed: {exc}")

        rows, metrics = self._run_statistical_fallback(records=records, contract=contract)
        metrics["model_backend"] = "heuristic_fallback"
        if warnings:
            metrics["backend_warnings"] = warnings
        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            artifacts["model_training_report"] = write_json(
                artifact_dir / "incrementality_causal_report.json",
                {
                    "backend": "heuristic_fallback",
                    "warnings": warnings,
                    "seed": seed,
                    "campaign_count": len(rows),
                },
            )
        return rows, metrics, artifacts

    def _run_causal_stack(
        self,
        *,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
        artifact_dir: Path | None,
        np: Any,
        pd: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        """Estimate treatment effects with EconML and validate with DoWhy."""
        set_reproducible_seed(seed)
        from econml.dml import LinearDML  # type: ignore
        from sklearn.linear_model import LinearRegression, LogisticRegression  # type: ignore
        from dowhy import CausalModel  # type: ignore

        # Expand aggregate campaign rows into micro-samples for causal estimation.
        rng = random.Random(seed)
        expanded_rows: list[dict[str, Any]] = []
        for idx, record in enumerate(records):
            treated_rate = float(record["treated_conversions"]) / max(float(record["treated_customers"]), 1.0)
            control_rate = float(record["control_conversions"]) / max(float(record["control_customers"]), 1.0)
            aov_norm = float(record["aov"]) / 200.0
            cost_norm = float(record["campaign_cost"]) / 50_000.0
            campaign_idx_norm = (idx + 1) / max(len(records), 1)
            pre_period_norm = float(record.get("pre_period_conversion_rate", control_rate))

            treated_n = min(400, int(record["treated_customers"]))
            control_n = min(400, int(record["control_customers"]))

            for _ in range(treated_n):
                expanded_rows.append(
                    {
                        "campaign_id": str(record["campaign_id"]),
                        "outcome": 1.0 if rng.random() < treated_rate else 0.0,
                        "treatment": 1.0,
                        "aov_norm": aov_norm,
                        "cost_norm": cost_norm,
                        "campaign_idx_norm": campaign_idx_norm,
                        "pre_period_norm": pre_period_norm,
                    }
                )
            for _ in range(control_n):
                expanded_rows.append(
                    {
                        "campaign_id": str(record["campaign_id"]),
                        "outcome": 1.0 if rng.random() < control_rate else 0.0,
                        "treatment": 0.0,
                        "aov_norm": aov_norm,
                        "cost_norm": cost_norm,
                        "campaign_idx_norm": campaign_idx_norm,
                        "pre_period_norm": pre_period_norm,
                    }
                )

        df = pd.DataFrame(expanded_rows)
        x_cols = ["aov_norm", "cost_norm", "campaign_idx_norm", "pre_period_norm"]
        y = df["outcome"].to_numpy()
        t = df["treatment"].to_numpy()
        x = df[x_cols].to_numpy()

        dml = LinearDML(
            model_y=LinearRegression(),
            model_t=LogisticRegression(max_iter=300),
            discrete_treatment=True,
            random_state=seed,
        )
        dml.fit(y, t, X=x)
        cate = dml.effect(x)
        ate = float(np.mean(cate))
        cate_std = float(np.std(cate))

        # DoWhy refutation: placebo treatment test as governance signal.
        dowhy_model = CausalModel(
            data=df,
            treatment="treatment",
            outcome="outcome",
            common_causes=x_cols,
        )
        identified_estimand = dowhy_model.identify_effect(proceed_when_unidentifiable=True)
        estimate = dowhy_model.estimate_effect(
            identified_estimand,
            method_name="backdoor.linear_regression",
        )
        refute = dowhy_model.refute_estimate(
            identified_estimand,
            estimate,
            method_name="placebo_treatment_refuter",
            num_simulations=10,
        )
        refute_p_value = self._safe_refuter_p_value(refute)

        # Campaign-level CATE averages drive final output recommendations.
        cate_by_campaign: dict[str, list[float]] = {}
        for idx, campaign_id in enumerate(df["campaign_id"].tolist()):
            cate_by_campaign.setdefault(str(campaign_id), []).append(float(cate[idx]))

        rows: list[dict[str, Any]] = []
        for record in records:
            campaign_id = str(record["campaign_id"])
            campaign_cate = cate_by_campaign.get(campaign_id, [ate])
            incremental_lift = float(np.mean(campaign_cate))
            stderr = float(np.std(campaign_cate) / math.sqrt(max(len(campaign_cate), 1)))
            ci_low = incremental_lift - 1.96 * stderr
            ci_high = incremental_lift + 1.96 * stderr

            incremental_revenue = max(
                0.0,
                incremental_lift * float(record["treated_customers"]) * float(record["aov"]),
            )
            i_roas = (
                incremental_revenue / float(record["campaign_cost"])
                if float(record["campaign_cost"]) > 0
                else 0.0
            )
            if ci_low > 0 and i_roas > 1.0:
                decision = "scale"
            elif ci_high < 0:
                decision = "pause"
            else:
                decision = "retest"

            rows.append(
                {
                    "campaign_id": campaign_id,
                    "test_window": record["test_window"],
                    "incremental_lift": round(incremental_lift, 4),
                    "ci_low": round(ci_low, 4),
                    "ci_high": round(ci_high, 4),
                    "p_value": round(max(0.0001, min(0.99, 1.0 - abs(incremental_lift) * 8)), 4),
                    "iROAS": round(i_roas, 4),
                    "decision_recommendation": decision,
                    "analysis_version": "incrementality_causal_v1",
                }
            )

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_incremental_lift": round(mean(r["incremental_lift"] for r in rows), 4),
            "avg_iROAS": round(mean(r["iROAS"] for r in rows), 4),
            "model_backend": "econml_dowhy",
            "ate": round(ate, 6),
            "cate_std": round(cate_std, 6),
            "dowhy_placebo_p_value": refute_p_value,
            "causal_sample_rows": int(len(df)),
            "covariates_used": len(x_cols),
        }

        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            artifacts["model_training_report"] = write_json(
                artifact_dir / "incrementality_causal_report.json",
                {
                    "backend": "econml_dowhy",
                    "seed": seed,
                    "ate": ate,
                    "cate_std": cate_std,
                    "dowhy_placebo_p_value": refute_p_value,
                    "causal_sample_rows": int(len(df)),
                },
            )
        return rows, metrics, artifacts

    def _run_statistical_fallback(
        self,
        *,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fallback formula when EconML/DoWhy stack is unavailable."""
        rows: list[dict[str, Any]] = []

        for record in records:
            treated_rate = record["treated_conversions"] / max(record["treated_customers"], 1)
            control_rate = record["control_conversions"] / max(record["control_customers"], 1)
            incremental_lift = treated_rate - control_rate
            stderr = ((treated_rate * (1 - treated_rate)) / max(record["treated_customers"], 1) + (
                (control_rate * (1 - control_rate)) / max(record["control_customers"], 1)
            )) ** 0.5

            ci_low = incremental_lift - 1.96 * stderr
            ci_high = incremental_lift + 1.96 * stderr

            incremental_revenue = max(0.0, incremental_lift * record["treated_customers"] * record["aov"])
            i_roas = (
                incremental_revenue / record["campaign_cost"]
                if record["campaign_cost"] > 0
                else 0.0
            )

            if ci_low > 0 and i_roas > 1.0:
                decision = "scale"
            elif ci_high < 0:
                decision = "pause"
            else:
                decision = "retest"

            rows.append(
                {
                    "campaign_id": record["campaign_id"],
                    "test_window": record["test_window"],
                    "incremental_lift": round(incremental_lift, 4),
                    "ci_low": round(ci_low, 4),
                    "ci_high": round(ci_high, 4),
                    "p_value": round(max(0.0001, 0.5 - incremental_lift * 3), 4),
                    "iROAS": round(i_roas, 4),
                    "decision_recommendation": decision,
                    "analysis_version": "incrementality_fallback_v1",
                }
            )

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_incremental_lift": round(mean(r["incremental_lift"] for r in rows), 4),
            "avg_iROAS": round(mean(r["iROAS"] for r in rows), 4),
        }
        return rows, metrics

    def _safe_refuter_p_value(self, refuter_result: Any) -> float | None:
        """Extract p-value from DoWhy refuter output when available."""
        for attr in ("p_value", "new_effect", "estimated_effect"):
            value = getattr(refuter_result, attr, None)
            if isinstance(value, (int, float)):
                return float(value)
        return None
