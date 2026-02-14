"""Regression tests for Bugs #2 and #3.

Bug #2: run_pytest() returns silently on empty test list but caller
        still calls update_hashes(), incorrectly recording a baseline.

Bug #3: Hashes updated after a *partial* test run can mask changes to
        files whose tests were not in the affected set.
"""

from unittest.mock import MagicMock

from typer.testing import CliRunner

from py_smart_test.smart_test_runner import app, run_pytest

runner = CliRunner()


class TestBug2EmptyTestList:
    """run_pytest() should return False when no tests are given."""

    def test_returns_false_on_empty_list(self):
        result = run_pytest([], [])
        assert result is False

    def test_returns_false_with_extra_args(self):
        result = run_pytest([], ["-v"])
        assert result is False


class TestBug3PartialHashUpdate:
    """Hashes should only be updated on full runs, not partial."""

    def test_affected_mode_does_not_update_hashes(self, monkeypatch):
        """In 'affected' mode with existing history, hashes should NOT update."""
        from py_smart_test import smart_test_runner

        monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
        monkeypatch.setattr(
            smart_test_runner,
            "HASH_FILE",
            MagicMock(exists=MagicMock(return_value=True)),
        )
        monkeypatch.setattr(
            smart_test_runner,
            "get_affected_tests",
            lambda *a: {"tests": ["tests/test_a.py"], "affected_modules": []},
        )
        monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: True)
        monkeypatch.setattr(smart_test_runner, "generate_graph_main", lambda: None)
        monkeypatch.setattr(smart_test_runner, "mapper_main", lambda: None)

        mock_update = MagicMock()
        monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

        # Use --regenerate-graph to bypass fast path
        result = runner.invoke(app, ["--regenerate-graph", "--mode", "affected"])
        assert result.exit_code == 0
        mock_update.assert_not_called()

    def test_all_mode_updates_hashes(self, monkeypatch):
        """In 'all' mode, hashes SHOULD be updated."""
        from py_smart_test import smart_test_runner

        monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
        monkeypatch.setattr(
            smart_test_runner,
            "HASH_FILE",
            MagicMock(exists=MagicMock(return_value=True)),
        )
        monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: True)

        mock_update = MagicMock()
        monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

        result = runner.invoke(app, ["--mode", "all"])
        assert result.exit_code == 0
        mock_update.assert_called_once()

    def test_first_run_updates_hashes(self, monkeypatch):
        """First run (no hash file) should update hashes."""
        from py_smart_test import smart_test_runner

        monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
        monkeypatch.setattr(
            smart_test_runner,
            "HASH_FILE",
            MagicMock(exists=MagicMock(return_value=False)),
        )
        monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: True)
        monkeypatch.setattr(smart_test_runner, "generate_graph_main", lambda: None)
        monkeypatch.setattr(smart_test_runner, "mapper_main", lambda: None)

        mock_update = MagicMock()
        monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

        # Use --regenerate-graph to bypass fast path
        result = runner.invoke(app, ["--regenerate-graph", "--mode", "affected"])
        assert result.exit_code == 0
        mock_update.assert_called_once()
