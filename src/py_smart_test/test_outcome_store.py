"""Track test outcomes (pass/fail/duration) across runs.

Stores results in `.py_smart_test/test_outcomes.json` to enable:
- Re-running previously failed tests automatically
- Prioritizing tests by historical duration
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from . import _paths

logger = logging.getLogger(__name__)

OUTCOMES_FILE = _paths.PY_SMART_TEST_DIR / "test_outcomes.json"


@dataclass
class Outcome:
    """Result of a single test execution."""

    node_id: str  # pytest node ID, e.g. "tests/test_foo.py::test_bar"
    status: str  # "passed", "failed", "error", "skipped"
    duration: float = 0.0  # seconds
    timestamp: float = field(default_factory=time.time)
    error_message: Optional[str] = None


def _load_raw() -> dict:
    """Load raw outcome data from disk."""
    if not OUTCOMES_FILE.exists():
        return {}
    try:
        with open(OUTCOMES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load test outcomes: {e}")
        return {}


def _save_raw(data: dict) -> None:
    """Save raw outcome data to disk."""
    try:
        OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTCOMES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save test outcomes: {e}")


def save_outcomes(outcomes: List[Outcome]) -> None:
    """Save test outcomes, merging with existing data."""
    data = _load_raw()
    for outcome in outcomes:
        data[outcome.node_id] = asdict(outcome)
    _save_raw(data)
    logger.debug(f"Saved {len(outcomes)} test outcomes")


def load_failed_tests() -> List[str]:
    """Return node IDs of tests that failed on the last run."""
    data = _load_raw()
    failed = []
    for node_id, info in data.items():
        if info.get("status") in ("failed", "error"):
            failed.append(node_id)
    return sorted(failed)


def load_test_durations() -> Dict[str, float]:
    """Return mapping of node_id → duration_seconds from last run."""
    data = _load_raw()
    return {
        node_id: info.get("duration", 0.0)
        for node_id, info in data.items()
        if "duration" in info
    }


def clear_outcomes() -> None:
    """Remove all stored outcomes."""
    if OUTCOMES_FILE.exists():
        OUTCOMES_FILE.unlink()
