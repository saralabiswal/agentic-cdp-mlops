from __future__ import annotations

"""NBA model implementation with TensorFlow-first training pipeline."""

import random
import shutil
from statistics import mean
from pathlib import Path
from typing import Any

from models.base import UseCaseModel
from models.runtime_utils import optional_import, set_reproducible_seed, write_json
from pipelines.contract_loader import UseCaseContract


class NBARetentionModel(UseCaseModel):
    """Generates action-level uplift recommendations per customer.

    Runtime strategy:
    1. Use TensorFlow multi-head model when available.
    2. Fall back to deterministic heuristic scoring when TensorFlow is missing.
    """

    ACTIONS = [
        ("offer_10pct_discount", "email"),
        ("free_shipping_offer", "push"),
        ("loyalty_bonus_points", "email"),
        ("retargeting_creative_a", "paid"),
    ]
    ACTION_TO_INDEX = {action_id: idx for idx, (action_id, _) in enumerate(ACTIONS)}

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
        """Dispatch TensorFlow backend when available; otherwise use heuristic."""
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

        rows, metrics = self._run_heuristic(records=records, contract=contract, seed=seed)
        metrics["model_backend"] = "heuristic_fallback"
        if warnings:
            metrics["backend_warnings"] = warnings
        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            report = {
                "backend": "heuristic_fallback",
                "warnings": warnings,
                "seed": seed,
                "rows_scored": len(rows),
            }
            artifacts["model_training_report"] = write_json(
                artifact_dir / "nba_training_report.json",
                report,
            )
        return rows, metrics, artifacts

    def _run_heuristic(
        self,
        *,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fallback deterministic heuristic scoring."""
        rng = random.Random(seed)
        rows: list[dict[str, Any]] = []

        for record in records:
            action_id, action_channel = rng.choice(self.ACTIONS)
            risk = record["risk_score"]
            value = record["value_score"]

            # Simple uplift proxy: higher risk/value tends to higher intervention uplift.
            expected_uplift = round(min(0.30, 0.04 + 0.22 * risk + 0.08 * value), 4)
            confidence = round(max(0.50, min(0.99, 0.65 + (value - risk) * 0.2)), 4)

            rows.append(
                {
                    "customer_id": record["customer_id"],
                    "action_id": action_id,
                    "action_channel": action_channel,
                    "expected_uplift": expected_uplift,
                    "confidence": confidence,
                    "reason_codes": [
                        "high_churn_risk" if risk > 0.6 else "moderate_churn_risk",
                        "high_customer_value" if value > 0.6 else "standard_customer_value",
                    ],
                    "score_ts": record["score_ts"],
                    "model_version": "nba_retention_heuristic_v1",
                    "policy_version": "policy_v1",
                }
            )

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_expected_uplift": round(mean(r["expected_uplift"] for r in rows), 4),
            "avg_confidence": round(mean(r["confidence"] for r in rows), 4),
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
        """Train TensorFlow multi-head network for action ranking and uplift."""
        set_reproducible_seed(seed)
        tf.keras.utils.set_random_seed(seed)
        try:
            tf.config.experimental.enable_op_determinism()
        except Exception:
            pass

        feature_rows = [[float(row["risk_score"]), float(row["value_score"])] for row in records]
        x = tf.convert_to_tensor(feature_rows, dtype=tf.float32)

        target_actions: list[list[float]] = []
        target_uplift: list[list[float]] = []
        observed_action_labels = 0
        observed_uplift_labels = 0
        for row in records:
            utilities = self._action_utilities(risk=float(row["risk_score"]), value=float(row["value_score"]))
            labeled_idx = self._label_action_index(row)
            if labeled_idx is not None:
                best_idx = labeled_idx
                observed_action_labels += 1
            else:
                best_idx = max(range(len(utilities)), key=lambda idx: utilities[idx])
            one_hot = [0.0] * len(self.ACTIONS)
            one_hot[best_idx] = 1.0
            target_actions.append(one_hot)
            labeled_uplift = self._label_uplift(row)
            if labeled_uplift is not None:
                target_uplift.append([labeled_uplift])
                observed_uplift_labels += 1
            else:
                target_uplift.append([round(min(0.35, max(0.01, utilities[best_idx])), 6)])

        y_action = tf.convert_to_tensor(target_actions, dtype=tf.float32)
        y_uplift = tf.convert_to_tensor(target_uplift, dtype=tf.float32)

        train_idx, holdout_idx = self._split_indices(total=len(records), seed=seed)
        x_train = tf.gather(x, train_idx)
        x_holdout = tf.gather(x, holdout_idx)
        y_action_train = tf.gather(y_action, train_idx)
        y_action_holdout = tf.gather(y_action, holdout_idx)
        y_uplift_train = tf.gather(y_uplift, train_idx)
        y_uplift_holdout = tf.gather(y_uplift, holdout_idx)

        model = self._build_tensorflow_model(tf=tf)
        history = model.fit(
            x_train,
            {"action_head": y_action_train, "uplift_head": y_uplift_train},
            validation_data=(
                x_holdout,
                {"action_head": y_action_holdout, "uplift_head": y_uplift_holdout},
            ),
            epochs=18,
            batch_size=max(1, min(32, len(train_idx))),
            verbose=0,
        )
        holdout_eval = model.evaluate(
            x_holdout,
            {"action_head": y_action_holdout, "uplift_head": y_uplift_holdout},
            verbose=0,
            return_dict=True,
        )
        pred_action, pred_uplift = model.predict(x, verbose=0)

        rows: list[dict[str, Any]] = []
        for idx, row in enumerate(records):
            probs = [float(value) for value in pred_action[idx]]
            chosen_idx = max(range(len(probs)), key=lambda i: probs[i])
            action_id, action_channel = self.ACTIONS[chosen_idx]
            expected_uplift = round(min(0.35, max(0.0, float(pred_uplift[idx][0]))), 4)
            confidence = round(min(0.999, max(0.5, max(probs))), 4)
            risk = float(row["risk_score"])
            value = float(row["value_score"])
            rows.append(
                {
                    "customer_id": row["customer_id"],
                    "action_id": action_id,
                    "action_channel": action_channel,
                    "expected_uplift": expected_uplift,
                    "confidence": confidence,
                    "reason_codes": [
                        "high_churn_risk" if risk > 0.6 else "moderate_churn_risk",
                        "high_customer_value" if value > 0.6 else "standard_customer_value",
                    ],
                    "score_ts": row["score_ts"],
                    "model_version": "nba_retention_tf_v1",
                    "policy_version": "policy_tf_v2",
                }
            )

        metrics: dict[str, Any] = {
            "primary_kpi": contract.primary_kpi,
            "avg_expected_uplift": round(mean(r["expected_uplift"] for r in rows), 4),
            "avg_confidence": round(mean(r["confidence"] for r in rows), 4),
            "model_backend": "tensorflow",
            "train_rows": len(train_idx),
            "holdout_rows": len(holdout_idx),
            "tf_train_loss": self._history_last(history, "loss"),
            "tf_train_action_acc": self._history_last(history, "action_head_action_acc"),
            "tf_holdout_loss": float(holdout_eval.get("loss", 0.0)),
            "tf_holdout_action_acc": float(holdout_eval.get("action_head_action_acc", 0.0)),
            "supervision_mode": "observed_labels"
            if (observed_action_labels > 0 or observed_uplift_labels > 0)
            else "proxy_labels",
            "observed_action_labels": observed_action_labels,
            "observed_uplift_labels": observed_uplift_labels,
        }

        artifacts: dict[str, str] = {}
        if artifact_dir is not None:
            tf_dir = artifact_dir / "nba_tf_saved_model"
            if tf_dir.exists():
                shutil.rmtree(tf_dir)
            tf.saved_model.save(model, str(tf_dir))
            artifacts["model_binary"] = str(tf_dir.as_posix())
            artifacts["model_training_report"] = write_json(
                artifact_dir / "nba_training_report.json",
                {
                    "backend": "tensorflow",
                    "seed": seed,
                    "train_rows": len(train_idx),
                    "holdout_rows": len(holdout_idx),
                    "history_tail": {
                        "loss": self._history_last(history, "loss"),
                        "action_acc": self._history_last(history, "action_head_action_acc"),
                        "val_loss": self._history_last(history, "val_loss"),
                        "val_action_acc": self._history_last(history, "val_action_head_action_acc"),
                    },
                    "holdout_eval": {key: float(value) for key, value in holdout_eval.items()},
                },
            )

        return rows, metrics, artifacts

    def _build_tensorflow_model(self, *, tf: Any) -> Any:
        """Build Keras multi-output model for NBA action and uplift heads."""
        inputs = tf.keras.Input(shape=(2,), name="input_features")
        hidden = tf.keras.layers.Dense(24, activation="relu")(inputs)
        hidden = tf.keras.layers.Dense(12, activation="relu")(hidden)

        action_head = tf.keras.layers.Dense(
            len(self.ACTIONS), activation="softmax", name="action_head"
        )(hidden)
        uplift_head = tf.keras.layers.Dense(1, activation="sigmoid", name="uplift_head")(hidden)

        model = tf.keras.Model(inputs=inputs, outputs=[action_head, uplift_head])
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.01),
            loss={
                "action_head": "categorical_crossentropy",
                "uplift_head": "mse",
            },
            metrics={
                "action_head": [tf.keras.metrics.CategoricalAccuracy(name="action_acc")],
                "uplift_head": [tf.keras.metrics.MeanAbsoluteError(name="uplift_mae")],
            },
        )
        return model

    def _action_utilities(self, *, risk: float, value: float) -> list[float]:
        """Compute pseudo-utility targets used for supervised action learning."""
        return [
            0.06 + 0.24 * risk + 0.05 * value,  # offer_10pct_discount
            0.05 + 0.18 * risk + 0.09 * value,  # free_shipping_offer
            0.04 + 0.12 * risk + 0.18 * value,  # loyalty_bonus_points
            0.03 + 0.20 * risk + 0.12 * value,  # retargeting_creative_a
        ]

    def _split_indices(self, *, total: int, seed: int) -> tuple[list[int], list[int]]:
        """Build deterministic train/holdout index split."""
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

    def _label_action_index(self, row: dict[str, Any]) -> int | None:
        """Resolve optional observed action label into class index."""
        raw = row.get("historical_action_id")
        if not isinstance(raw, str):
            return None
        return self.ACTION_TO_INDEX.get(raw.strip())

    def _label_uplift(self, row: dict[str, Any]) -> float | None:
        """Resolve optional observed uplift label when present."""
        value = row.get("observed_uplift")
        if isinstance(value, (int, float)):
            return round(min(0.35, max(0.0, float(value))), 6)
        if isinstance(value, str):
            try:
                parsed = float(value.strip())
            except ValueError:
                return None
            return round(min(0.35, max(0.0, parsed)), 6)
        return None
