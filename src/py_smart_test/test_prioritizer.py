"""Test prioritization for smarter execution ordering.

Sorts tests so that the most relevant ones run first:
1. Previously failed tests (highest priority)
2. Affected tests (sorted by fastest first)
3. Unaffected tests (sorted by fastest first)
"""

import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


def prioritize_tests(
    all_tests: List[str],
    affected_tests: Set[str],
    failed_tests: Set[str],
    durations: Dict[str, float],
) -> List[str]:
    """Reorder tests for optimal feedback.

    Priority order:
        1. Previously failed tests (fastest first)
        2. Affected by code changes (fastest first)
        3. Remaining tests (fastest first)

    Args:
        all_tests: Complete list of collected test node IDs.
        affected_tests: Tests affected by code changes.
        failed_tests: Tests that failed on the previous run.
        durations: Historical duration per test (seconds).

    Returns:
        Reordered list of test node IDs.
    """

    def _sort_key(node_id: str) -> float:
        return durations.get(node_id, float("inf"))

    bucket_failed: List[str] = []
    bucket_affected: List[str] = []
    bucket_rest: List[str] = []

    for t in all_tests:
        if t in failed_tests:
            bucket_failed.append(t)
        elif t in affected_tests:
            bucket_affected.append(t)
        else:
            bucket_rest.append(t)

    bucket_failed.sort(key=_sort_key)
    bucket_affected.sort(key=_sort_key)
    bucket_rest.sort(key=_sort_key)

    reordered = bucket_failed + bucket_affected + bucket_rest

    if bucket_failed:
        logger.info(
            f"🔄 Re-running {len(bucket_failed)} previously failed test(s) first"
        )
    if bucket_affected:
        logger.info(f"🎯 {len(bucket_affected)} test(s) affected by code changes")

    return reordered
