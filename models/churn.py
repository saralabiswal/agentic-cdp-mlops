from __future__ import annotations

"""Churn model implementation with TensorFlow-first training pipeline."""

import shutil
from statistics import mean
from pathlib import Path
from typing import Any

from models.base import UseCaseModel
from models.runtime_utils import optional_import, set_reproducible_seed, write_json
from pipelines.contract_loader import UseCaseContract


class ChurnRetentionModel(UseCaseModel):
    """Computes churn risk and retention actions.

    Runtime strategy:
    1. Use TensorFlow binary classification when available.
    2. Fall back to deterministic heuristic scoring.
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
        """Run model and persist optional TensorFlow training artifacts."""
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
        """Dispatch TensorFlow backend when available; otherwise fallback."""
        tf_module, tf_import_error = optional_import("tensorflow")
        warnings: list[str] = []
        if tf_import_error:
            warnings.append(f"TensorFlow unavailable: {tf_import_error}")

        if tf_module is not None:
            try:
                return self._run_tensorflow(
                    tf=tf_module,
                    records=records,
                    contract=contract,
                    seed=seed,
                    artifact_dir=artifact_dir,
                )
            except Exception as exc:  # pragma: no cover - depends on optional runtime libs.
                warnings.append(f"TensorFlow backend failed: {exc}")

        rows, metrics = self._run_heuristic(records=records, contract=contract)
        metrics["model_backend"] = "heuristic_fallback"
        if warnings:
            metrics["backend_warnings"] = warnings
        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            artifacts["model_training_report"] = write_json(
                artifact_dir / "churn_training_report.json",
                {
                    "backend": "heuristic_fallback",
                    "warnings": warnings,
                    "seed": seed,
                    "rows_scored": len(rows),
                },
            )
        return rows, metrics, artifacts

    def _run_heuristic(
        self,
        *,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fallback deterministic formula for churn scoring."""
        rows: list[dict[str, Any]] = []

        for record in records:
            risk_score = min(
                0.99,
                max(
                    0.01,
                    0.15
                    + 0.40 * record["recency_norm"]
                    + 0.25 * (1 - record["engagement_norm"])
                    + 0.20 * record["support_ticket_norm"],
                ),
            )
            expected_uplift = max(0.0, round(0.28 * risk_score - 0.03, 4))

            if risk_score >= 0.75:
                risk_band = "high"
                recommended_action = "priority_retention_offer"
            elif risk_score >= 0.45:
                risk_band = "medium"
                recommended_action = "nurture_sequence"
            else:
                risk_band = "low"
                recommended_action = "light_touch_message"

            rows.append(
                {
                    "customer_id": record["customer_id"],
                    "churn_risk_score": round(risk_score, 4),
                    "risk_band": risk_band,
                    "recommended_action": recommended_action,
                    "expected_uplift": expected_uplift,
                    "reason_codes": [
                        "low_recent_engagement" if record["engagement_norm"] < 0.4 else "engaged_recently",
                        "high_recency_gap" if record["recency_norm"] > 0.6 else "healthy_activity",
                    ],
                    "score_ts": record["score_ts"],
                    "model_version": "churn_retention_heuristic_v1",
                }
            )

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_churn_risk_score": round(mean(r["churn_risk_score"] for r in rows), 4),
            "avg_expected_uplift": round(mean(r["expected_uplift"] for r in rows), 4),
        }
        return rows, metrics

    def _run_tensorflow(
        self,
        *,
        tf: Any,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
        artifact_dir: Path | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        """Train TensorFlow churn classifier and derive actioning outputs."""
        set_reproducible_seed(seed)
        tf.keras.utils.set_random_seed(seed)
        try:
            tf.config.experimental.enable_op_determinism()
        except Exception:
            pass

        features = [
            [
                float(row["recency_norm"]),
                float(row["engagement_norm"]),
                float(row["support_ticket_norm"]),
            ]
            for row in records
        ]
        x = tf.convert_to_tensor(features, dtype=tf.float32)

        # Build pseudo-supervised churn label from known risk dynamics.
        y_values: list[list[float]] = []
        observed_labels = 0
        for row in records:
            observed = self._observed_churn_label(row)
            if observed is not None:
                y_values.append([observed])
                observed_labels += 1
            else:
                proxy_risk = (
                    0.15
                    + 0.40 * float(row["recency_norm"])
                    + 0.25 * (1 - float(row["engagement_norm"]))
                    + 0.20 * float(row["support_ticket_norm"])
                )
                y_values.append([1.0 if proxy_risk >= 0.55 else 0.0])
        y = tf.convert_to_tensor(y_values, dtype=tf.float32)

        train_idx, holdout_idx = self._split_indices(total=len(records), seed=seed)
        x_train = tf.gather(x, train_idx)
        x_holdout = tf.gather(x, holdout_idx)
        y_train = tf.gather(y, train_idx)
        y_holdout = tf.gather(y, holdout_idx)

        model = self._build_tensorflow_model(tf=tf)
        history = model.fit(
            x_train,
            y_train,
            validation_data=(x_holdout, y_holdout),
            epochs=20,
            batch_size=max(1, min(32, len(train_idx))),
            verbose=0,
        )
        holdout_eval = model.evaluate(
            x_holdout,
            y_holdout,
            verbose=0,
            return_dict=True,
        )
        pred = model.predict(x, verbose=0)

        rows: list[dict[str, Any]] = []
        for idx, record in enumerate(records):
            risk_score = round(min(0.99, max(0.01, float(pred[idx][0]))), 4)
            expected_uplift = max(0.0, round(0.28 * risk_score - 0.03, 4))
            if risk_score >= 0.75:
                risk_band = "high"
                recommended_action = "priority_retention_offer"
            elif risk_score >= 0.45:
                risk_band = "medium"
                recommended_action = "nurture_sequence"
            else:
                risk_band = "low"
                recommended_action = "light_touch_message"

            rows.append(
                {
                    "customer_id": record["customer_id"],
                    "churn_risk_score": risk_score,
                    "risk_band": risk_band,
                    "recommended_action": recommended_action,
                    "expected_uplift": expected_uplift,
                    "reason_codes": [
                        "low_recent_engagement"
                        if record["engagement_norm"] < 0.4
                        else "engaged_recently",
                        "high_recency_gap" if record["recency_norm"] > 0.6 else "healthy_activity",
                    ],
                    "score_ts": record["score_ts"],
                    "model_version": "churn_retention_tf_v1",
                }
            )

        auc_metric = tf.keras.metrics.AUC(curve="ROC")
        auc_metric.update_state(y, pred)

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_churn_risk_score": round(mean(r["churn_risk_score"] for r in rows), 4),
            "avg_expected_uplift": round(mean(r["expected_uplift"] for r in rows), 4),
            "model_backend": "tensorflow",
            "train_rows": len(train_idx),
            "holdout_rows": len(holdout_idx),
            "tf_train_loss": self._history_last(history, "loss"),
            "tf_holdout_loss": float(holdout_eval.get("loss", 0.0)),
            "tf_holdout_auc": float(holdout_eval.get("auc", 0.0)),
            "auc_overall": float(auc_metric.result().numpy()),
            "supervision_mode": "observed_labels" if observed_labels > 0 else "proxy_labels",
            "observed_churn_labels": observed_labels,
        }

        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            tf_dir = artifact_dir / "churn_tf_saved_model"
            if tf_dir.exists():
                shutil.rmtree(tf_dir)
            tf.saved_model.save(model, str(tf_dir))
            artifacts["model_binary"] = str(tf_dir.as_posix())
            artifacts["model_training_report"] = write_json(
                artifact_dir / "churn_training_report.json",
                {
                    "backend": "tensorflow",
                    "seed": seed,
                    "train_rows": len(train_idx),
                    "holdout_rows": len(holdout_idx),
                    "history_tail": {
                        "loss": self._history_last(history, "loss"),
                        "auc": self._history_last(history, "auc"),
                        "val_loss": self._history_last(history, "val_loss"),
                        "val_auc": self._history_last(history, "val_auc"),
                    },
                    "holdout_eval": {key: float(value) for key, value in holdout_eval.items()},
                },
            )

        return rows, metrics, artifacts

    def _build_tensorflow_model(self, *, tf: Any) -> Any:
        """Build Keras binary classifier for churn risk."""
        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(3,)),
                tf.keras.layers.Dense(16, activation="relu"),
                tf.keras.layers.Dense(8, activation="relu"),
                tf.keras.layers.Dense(1, activation="sigmoid"),
            ]
        )
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.01),
            loss="binary_crossentropy",
            metrics=[tf.keras.metrics.AUC(name="auc")],
        )
        return model

    def _split_indices(self, *, total: int, seed: int) -> tuple[list[int], list[int]]:
        """Build deterministic train/holdout index split."""
        import random

        rng = random.Random(seed)
        all_idx = list(range(total))
        rng.shuffle(all_idx)
        holdout_size = max(1, int(0.2 * total))
        holdout = sorted(all_idx[:holdout_size])
        train = sorted(all_idx[holdout_size:])
        if not train and holdout:
            train = [holdout.pop()]
        return train, holdout

    def _history_last(self, history: Any, key: str) -> float | None:
        """Read last value from Keras history key when present."""
        values = history.history.get(key, [])
        if not values:
            return None
        return float(values[-1])

    def _observed_churn_label(self, row: dict[str, Any]) -> float | None:
        """Resolve optional observed churn label when available."""
        value = row.get("churned_60d")
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return 1.0 if float(value) >= 0.5 else 0.0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes"}:
                return 1.0
            if lowered in {"0", "false", "no"}:
                return 0.0
        return None
