from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _configure_test_warning_filters() -> None:
    """Apply targeted warning filters for noisy third-party causal backends."""
    warnings.filterwarnings(
        "ignore",
        message=r"The copy keyword is deprecated and will be removed in a future version.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"divide by zero encountered in scalar divide",
        category=RuntimeWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"invalid value encountered in scalar divide",
        category=RuntimeWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Co-variance matrix is underdetermined\. Inference will be invalid!",
        category=UserWarning,
    )


def pytest_configure() -> None:
    """Ensure filters remain active after pytest warning configuration."""
    _configure_test_warning_filters()


_configure_test_warning_filters()
