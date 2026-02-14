"""Native pytest plugin for py-smart-test.

Integrates smart test selection directly into the pytest workflow.  Register
via ``[project.entry-points."pytest11"]`` so users just run::

    pytest --smart            # only affected tests
    pytest --smart-first      # affected first, then the rest
    pytest --smart-no-collect # deselect unaffected entirely (same as --smart)

Options
-------
--smart              Run only tests affected by code changes.
--smart-first        Run affected tests first, then remaining tests.
--smart-since REF    Git ref to diff against (default: auto-detected branch).
--smart-staged       Diff staged changes only.
--smart-working-tree Use ``git status`` to detect unstaged/untracked files.
"""

import logging
from typing import Any, Generator, List, Set

import pytest

from . import _paths  # noqa: E402
from .find_affected_modules import get_affected_tests  # noqa: E402
from .find_affected_modules import get_working_tree_changes
from .test_outcome_store import load_failed_tests  # noqa: E402
from .test_outcome_store import Outcome, load_test_durations, save_outcomes
from .test_prioritizer import prioritize_tests  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register ``--smart*`` CLI options."""
    group = parser.getgroup("smart-test", "py-smart-test options")
    group.addoption(
        "--smart",
        action="store_true",
        default=False,
        help="Run only tests affected by code changes.",
    )
    group.addoption(
        "--smart-first",
        action="store_true",
        default=False,
        help="Run affected tests first, then remaining tests.",
    )
    group.addoption(
        "--smart-no-collect",
        action="store_true",
        default=False,
        help="Deselect unaffected tests entirely (alias for --smart).",
    )
    group.addoption(
        "--smart-since",
        default=None,
        help="Git ref to diff against (default: auto-detected).",
    )
    group.addoption(
        "--smart-staged",
        action="store_true",
        default=False,
        help="Diff staged changes only.",
    )
    group.addoption(
        "--smart-working-tree",
        action="store_true",
        default=False,
        help="Detect changes via git status (unstaged/untracked files).",
    )


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: List[pytest.Item],
) -> None:
    """Filter and/or reorder collected tests based on smart analysis."""
    smart = config.getoption("--smart") or config.getoption("--smart-no-collect")
    smart_first = config.getoption("--smart-first")

    if not smart and not smart_first:
        return

    # Determine which files changed
    since = config.getoption("--smart-since") or _paths.DEFAULT_BRANCH
    staged = config.getoption("--smart-staged")
    working_tree = config.getoption("--smart-working-tree")

    if working_tree:
        # Inject working-tree files into the affected analysis
        _wt_files = get_working_tree_changes()
        # For now, fall through to the standard get_affected_tests which
        # already handles git diff.  Working-tree mode replaces the diff
        # source, so we synthesize a result.

        result = get_affected_tests(since, staged)
        # Merge in working-tree files that may not appear in git diff
        wt_paths = {str(p) for p in _wt_files}
        existing = set(result.get("tests", []))
        for path in wt_paths:
            if path.startswith("tests/") and path.endswith(".py"):
                existing.add(path)
        result["tests"] = sorted(existing)
    else:
        result = get_affected_tests(since, staged)

    affected_node_ids: Set[str] = set()
    affected_test_files = set(result.get("tests", []))

    # Map collected items to affected set
    for item in items:
        # item.fspath gives the absolute path; relativize it
        try:
            rel = str(item.path.relative_to(_paths.REPO_ROOT))
        except (ValueError, AttributeError):
            rel = str(getattr(item, "fspath", ""))
        if rel in affected_test_files:
            affected_node_ids.add(item.nodeid)

    # Load historical data for prioritization
    failed = set(load_failed_tests())
    durations = load_test_durations()
    all_node_ids = [item.nodeid for item in items]

    if smart:
        # Deselect unaffected tests entirely
        # But always keep previously failed tests
        keep_ids = affected_node_ids | failed
        selected = []
        deselected = []
        for item in items:
            if item.nodeid in keep_ids:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            config.hook.pytest_deselected(items=deselected)

        # Reorder selected tests (failed first, then affected)
        ordered_ids = prioritize_tests(
            [it.nodeid for it in selected],
            affected_node_ids,
            failed,
            durations,
        )
        id_to_item = {it.nodeid: it for it in selected}
        items[:] = [id_to_item[nid] for nid in ordered_ids if nid in id_to_item]

        msg = (
            f"Smart mode: selected {len(selected)} / "
            f"{len(selected) + len(deselected)} tests"
        )
        logger.info(msg)

    elif smart_first:
        # Keep all tests but reorder: affected first
        ordered_ids = prioritize_tests(
            all_node_ids,
            affected_node_ids,
            failed,
            durations,
        )
        id_to_item = {it.nodeid: it for it in items}
        items[:] = [id_to_item[nid] for nid in ordered_ids if nid in id_to_item]

        logger.info(
            f"Smart-first mode: {len(affected_node_ids)} affected tests prioritized"
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, Any, None]:
    """Record outcomes for each test."""
    outcome = yield
    report = outcome.get_result()

    # Only record the "call" phase (not setup/teardown)
    if report.when != "call":
        return

    # Store on the item so sessionfinish can collect them
    if not hasattr(item, "_smart_test_outcome"):
        item._smart_test_outcome = {}  # type: ignore[attr-defined]

    item._smart_test_outcome = {  # type: ignore[attr-defined]
        "node_id": item.nodeid,
        "status": report.outcome,  # "passed", "failed", "skipped"
        "duration": report.duration,
    }


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Persist test outcomes after the session."""
    config = session.config
    smart = (
        config.getoption("--smart", default=False)
        or config.getoption("--smart-first", default=False)
        or config.getoption("--smart-no-collect", default=False)
    )
    if not smart:
        return

    outcomes = []
    for item in session.items:
        info = getattr(item, "_smart_test_outcome", None)
        if info:
            outcomes.append(
                Outcome(
                    node_id=info["node_id"],
                    status=info["status"],
                    duration=info["duration"],
                )
            )

    if outcomes:
        save_outcomes(outcomes)
        logger.debug(f"Saved {len(outcomes)} test outcomes")
