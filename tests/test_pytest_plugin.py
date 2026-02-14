"""Tests for pytest_plugin module.

Tests the plugin options registration and hook logic by calling hooks
directly with mocked objects.
"""

from unittest.mock import MagicMock, patch


class TestPluginOptions:
    """Test that the plugin registers its CLI options correctly."""

    def test_smart_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart", default="MISSING")
        assert val != "MISSING"

    def test_smart_first_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart-first", default="MISSING")
        assert val != "MISSING"

    def test_smart_since_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart-since", default="MISSING")
        assert val != "MISSING"

    def test_smart_staged_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart-staged", default="MISSING")
        assert val != "MISSING"

    def test_smart_working_tree_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart-working-tree", default="MISSING")
        assert val != "MISSING"

    def test_smart_no_collect_option_registered(self, pytestconfig):
        val = pytestconfig.getoption("--smart-no-collect", default="MISSING")
        assert val != "MISSING"

    def test_default_smart_is_false(self, pytestconfig):
        assert pytestconfig.getoption("--smart") is False

    def test_default_smart_first_is_false(self, pytestconfig):
        assert pytestconfig.getoption("--smart-first") is False

    def test_default_smart_since_is_none(self, pytestconfig):
        assert pytestconfig.getoption("--smart-since") is None


def _make_config(options: dict) -> MagicMock:
    """Create a mock pytest config with the given option values."""
    config = MagicMock()

    def _getoption(name, default=None):
        return options.get(name, default)

    config.getoption = _getoption
    config.hook = MagicMock()
    return config


def _make_item(nodeid: str, path_str: str, repo_root=None) -> MagicMock:
    """Create a mock pytest.Item."""
    item = MagicMock()
    item.nodeid = nodeid
    if repo_root:
        item.path = repo_root / path_str
    else:
        item.path = MagicMock()
        item.path.relative_to = MagicMock(return_value=path_str)
    return item


class TestCollectionModifyItemsNoOp:
    """When --smart flags are off, the hook should be a no-op."""

    def test_no_modification_without_flags(self):
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        config = _make_config(
            {
                "--smart": False,
                "--smart-no-collect": False,
                "--smart-first": False,
            }
        )
        items = [_make_item("test_a", "tests/test_a.py")]
        original = list(items)
        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)
        assert items == original  # unchanged


class TestCollectionModifyItemsSmart:
    """Test --smart mode (deselect unaffected)."""

    @patch("py_smart_test.pytest_plugin.load_test_durations", return_value={})
    @patch("py_smart_test.pytest_plugin.load_failed_tests", return_value=[])
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_smart_deselects_unaffected(self, mock_affected, mock_failed, mock_dur):
        from py_smart_test import _paths
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}

        config = _make_config(
            {
                "--smart": True,
                "--smart-no-collect": False,
                "--smart-first": False,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": False,
            }
        )

        item_a = _make_item(
            "tests/test_a.py::test_one", "tests/test_a.py", _paths.REPO_ROOT
        )
        item_b = _make_item(
            "tests/test_b.py::test_two", "tests/test_b.py", _paths.REPO_ROOT
        )
        items = [item_a, item_b]

        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)

        # Only test_a should remain
        assert len(items) == 1
        assert items[0].nodeid == "tests/test_a.py::test_one"
        # Deselection should have been called
        config.hook.pytest_deselected.assert_called_once()

    @patch("py_smart_test.pytest_plugin.load_test_durations", return_value={})
    @patch(
        "py_smart_test.pytest_plugin.load_failed_tests",
        return_value=["tests/test_b.py::test_two"],
    )
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_smart_keeps_failed_tests(self, mock_affected, mock_failed, mock_dur):
        """Previously failed tests should always be kept even if not affected."""
        from py_smart_test import _paths
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}

        config = _make_config(
            {
                "--smart": True,
                "--smart-no-collect": False,
                "--smart-first": False,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": False,
            }
        )

        item_a = _make_item(
            "tests/test_a.py::test_one", "tests/test_a.py", _paths.REPO_ROOT
        )
        item_b = _make_item(
            "tests/test_b.py::test_two", "tests/test_b.py", _paths.REPO_ROOT
        )
        item_c = _make_item(
            "tests/test_c.py::test_three", "tests/test_c.py", _paths.REPO_ROOT
        )
        items = [item_a, item_b, item_c]

        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)

        # test_a (affected) and test_b (previously failed) kept; test_c deselected
        nodeids = [it.nodeid for it in items]
        assert "tests/test_a.py::test_one" in nodeids
        assert "tests/test_b.py::test_two" in nodeids
        assert "tests/test_c.py::test_three" not in nodeids

    @patch("py_smart_test.pytest_plugin.load_test_durations", return_value={})
    @patch("py_smart_test.pytest_plugin.load_failed_tests", return_value=[])
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_smart_no_deselect_when_all_affected(
        self, mock_affected, mock_failed, mock_dur
    ):
        from py_smart_test import _paths
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}

        config = _make_config(
            {
                "--smart": True,
                "--smart-no-collect": False,
                "--smart-first": False,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": False,
            }
        )

        item_a = _make_item(
            "tests/test_a.py::test_one", "tests/test_a.py", _paths.REPO_ROOT
        )
        items = [item_a]

        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)
        assert len(items) == 1
        # No deselection call since nothing was deselected
        config.hook.pytest_deselected.assert_not_called()


class TestCollectionModifyItemsSmartFirst:
    """Test --smart-first mode (reorder but keep all)."""

    @patch(
        "py_smart_test.pytest_plugin.load_test_durations",
        return_value={
            "tests/test_b.py::test_two": 0.1,
            "tests/test_a.py::test_one": 1.0,
        },
    )
    @patch("py_smart_test.pytest_plugin.load_failed_tests", return_value=[])
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_smart_first_reorders(self, mock_affected, mock_failed, mock_dur):
        from py_smart_test import _paths
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}

        config = _make_config(
            {
                "--smart": False,
                "--smart-no-collect": False,
                "--smart-first": True,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": False,
            }
        )

        item_a = _make_item(
            "tests/test_a.py::test_one", "tests/test_a.py", _paths.REPO_ROOT
        )
        item_b = _make_item(
            "tests/test_b.py::test_two", "tests/test_b.py", _paths.REPO_ROOT
        )
        items = [item_b, item_a]  # b is first initially

        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)

        # All tests kept, but affected (test_a) should be first
        assert len(items) == 2
        assert items[0].nodeid == "tests/test_a.py::test_one"
        # No deselection in smart-first
        config.hook.pytest_deselected.assert_not_called()


class TestCollectionModifyItemsWorkingTree:
    """Test --smart-working-tree mode."""

    @patch("py_smart_test.pytest_plugin.load_test_durations", return_value={})
    @patch("py_smart_test.pytest_plugin.load_failed_tests", return_value=[])
    @patch("py_smart_test.pytest_plugin.get_working_tree_changes")
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_working_tree_merges_files(
        self, mock_affected, mock_wt, mock_failed, mock_dur
    ):
        from pathlib import Path

        from py_smart_test import _paths
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}
        mock_wt.return_value = [Path("tests/test_b.py"), Path("src/foo.py")]

        config = _make_config(
            {
                "--smart": True,
                "--smart-no-collect": False,
                "--smart-first": False,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": True,
            }
        )

        item_a = _make_item(
            "tests/test_a.py::test_one", "tests/test_a.py", _paths.REPO_ROOT
        )
        item_b = _make_item(
            "tests/test_b.py::test_two", "tests/test_b.py", _paths.REPO_ROOT
        )
        items = [item_a, item_b]

        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)

        # Both kept: test_a from git diff, test_b from working tree
        nodeids = [it.nodeid for it in items]
        assert "tests/test_a.py::test_one" in nodeids
        assert "tests/test_b.py::test_two" in nodeids


class TestCollectionItemPathFallback:
    """Test the ValueError fallback when item.path.relative_to fails."""

    @patch("py_smart_test.pytest_plugin.load_test_durations", return_value={})
    @patch("py_smart_test.pytest_plugin.load_failed_tests", return_value=[])
    @patch("py_smart_test.pytest_plugin.get_affected_tests")
    def test_relative_to_failure_uses_fspath(
        self, mock_affected, mock_failed, mock_dur
    ):
        from py_smart_test.pytest_plugin import pytest_collection_modifyitems

        mock_affected.return_value = {"tests": ["tests/test_a.py"]}

        config = _make_config(
            {
                "--smart": True,
                "--smart-no-collect": False,
                "--smart-first": False,
                "--smart-since": None,
                "--smart-staged": False,
                "--smart-working-tree": False,
            }
        )

        # Create item where relative_to raises ValueError
        item = MagicMock()
        item.nodeid = "tests/test_a.py::test_one"
        item.path = MagicMock()
        item.path.relative_to = MagicMock(side_effect=ValueError("no common root"))
        item.fspath = "tests/test_a.py"

        items = [item]
        pytest_collection_modifyitems(session=MagicMock(), config=config, items=items)

        # Should still work via fspath fallback
        assert len(items) == 1


class TestSessionFinish:
    """Test pytest_sessionfinish hook."""

    def test_no_op_without_smart(self):
        from py_smart_test.pytest_plugin import pytest_sessionfinish

        session = MagicMock()
        session.config.getoption = lambda name, default=None: default

        with patch("py_smart_test.pytest_plugin.save_outcomes") as mock_save:
            pytest_sessionfinish(session, exitstatus=0)
            mock_save.assert_not_called()

    def test_saves_outcomes_with_smart(self):
        from py_smart_test.pytest_plugin import pytest_sessionfinish

        session = MagicMock()
        options = {"--smart": True, "--smart-first": False, "--smart-no-collect": False}
        session.config.getoption = lambda name, default=None: options.get(name, default)

        item1 = MagicMock()
        item1._smart_test_outcome = {
            "node_id": "tests/test_a.py::test_one",
            "status": "passed",
            "duration": 0.1,
        }
        item2 = MagicMock()
        item2._smart_test_outcome = {
            "node_id": "tests/test_a.py::test_two",
            "status": "failed",
            "duration": 0.5,
        }
        session.items = [item1, item2]

        with patch("py_smart_test.pytest_plugin.save_outcomes") as mock_save:
            pytest_sessionfinish(session, exitstatus=1)
            mock_save.assert_called_once()
            outcomes = mock_save.call_args[0][0]
            assert len(outcomes) == 2
            assert outcomes[0].node_id == "tests/test_a.py::test_one"
            assert outcomes[1].status == "failed"

    def test_skips_items_without_outcome(self):
        from py_smart_test.pytest_plugin import pytest_sessionfinish

        session = MagicMock()
        options = {"--smart": True, "--smart-first": False, "--smart-no-collect": False}
        session.config.getoption = lambda name, default=None: options.get(name, default)

        item1 = MagicMock(spec=[])  # no _smart_test_outcome attr
        session.items = [item1]

        with patch("py_smart_test.pytest_plugin.save_outcomes") as mock_save:
            pytest_sessionfinish(session, exitstatus=0)
            # No outcomes to save, so save_outcomes shouldn't be called
            mock_save.assert_not_called()


class TestMakereport:
    """Test pytest_runtest_makereport hook."""

    def test_records_call_phase(self):
        from py_smart_test.pytest_plugin import pytest_runtest_makereport

        item = MagicMock()
        item.nodeid = "tests/test_a.py::test_one"
        call = MagicMock()

        report = MagicMock()
        report.when = "call"
        report.outcome = "passed"
        report.duration = 0.05

        gen = pytest_runtest_makereport(item, call)
        next(gen)  # advance to yield

        # Simulate the hookwrapper by sending the outcome
        outcome = MagicMock()
        outcome.get_result.return_value = report
        try:
            gen.send(outcome)
        except StopIteration:
            pass

        assert item._smart_test_outcome["node_id"] == "tests/test_a.py::test_one"
        assert item._smart_test_outcome["status"] == "passed"
        assert item._smart_test_outcome["duration"] == 0.05

    def test_ignores_setup_phase(self):
        from py_smart_test.pytest_plugin import pytest_runtest_makereport

        item = MagicMock(spec=[])  # no _smart_test_outcome
        call = MagicMock()

        report = MagicMock()
        report.when = "setup"
        report.outcome = "passed"

        gen = pytest_runtest_makereport(item, call)
        next(gen)

        outcome = MagicMock()
        outcome.get_result.return_value = report
        try:
            gen.send(outcome)
        except StopIteration:
            pass

        assert not hasattr(item, "_smart_test_outcome")
