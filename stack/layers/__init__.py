"""Architecture layer exports in execution order.

Order:
1. collect_source_data
2. ingest_to_event_bus
3. build_raw_and_curated_storage
4. resolve_identity_customer_360
5. build_feature_layer
6. run_model_layer
7. run_serving_and_activation
8. run_monitoring_and_governance
"""

from stack.layers.data_sources import collect_source_data
from stack.layers.data_sources import collect_source_data_with_metadata
from stack.layers.features import build_feature_layer
from stack.layers.identity_360 import resolve_identity_customer_360
from stack.layers.ingestion_event_bus import ingest_to_event_bus
from stack.layers.modeling import run_model_layer
from stack.layers.monitoring_governance import run_monitoring_and_governance
from stack.layers.serving_activation import run_serving_and_activation
from stack.layers.storage import build_raw_and_curated_storage

__all__ = [
    "collect_source_data",
    "collect_source_data_with_metadata",
    "ingest_to_event_bus",
    "build_raw_and_curated_storage",
    "resolve_identity_customer_360",
    "build_feature_layer",
    "run_model_layer",
    "run_serving_and_activation",
    "run_monitoring_and_governance",
]
