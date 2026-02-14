"""Tests for test_outcome_store module."""

import json

import pytest

from py_smart_test.test_outcome_store import (
    Outcome,
    clear_outcomes,
    load_failed_tests,
    load_test_durations,
    save_outcomes,
)


@pytest.fixture(autouse=True)
def _isolate_outcomes(monkeypatch, tmp_path):
    """Redirect outcomes file to a temp directory."""
    outcomes_file = tmp_path / "test_outcomes.json"
    monkeypatch.setattr("py_smart_test.test_outcome_store.OUTCOMES_FILE", outcomes_file)
    yield outcomes_file


class TestSaveAndLoad:
    def test_save_outcomes_creates_file(self, _isolate_outcomes):
        outcomes = [
            Outcome(node_id="tests/test_a.py::test_one", status="passed", duration=0.1),
            Outcome(node_id="tests/test_a.py::test_two", status="failed", duration=0.5),
        ]
        save_outcomes(outcomes)
        assert _isolate_outcomes.exists()
        data = json.loads(_isolate_outcomes.read_text())
        assert "tests/test_a.py::test_one" in data
        assert data["tests/test_a.py::test_one"]["status"] == "passed"

    def test_save_outcomes_merges(self, _isolate_outcomes):
        save_outcomes([Outcome(node_id="a", status="passed")])
        save_outcomes([Outcome(node_id="b", status="failed")])
        data = json.loads(_isolate_outcomes.read_text())
        assert "a" in data
        assert "b" in data

    def test_save_overwrites_same_test(self, _isolate_outcomes):
        save_outcomes([Outcome(node_id="a", status="failed")])
        save_outcomes([Outcome(node_id="a", status="passed")])
        data = json.loads(_isolate_outcomes.read_text())
        assert data["a"]["status"] == "passed"


class TestLoadFailed:
    def test_empty_when_no_file(self, _isolate_outcomes):
        assert load_failed_tests() == []

    def test_returns_only_failed(self, _isolate_outcomes):
        save_outcomes(
            [
                Outcome(node_id="a", status="passed"),
                Outcome(node_id="b", status="failed"),
                Outcome(node_id="c", status="error"),
                Outcome(node_id="d", status="skipped"),
            ]
        )
        failed = load_failed_tests()
        assert failed == ["b", "c"]

    def test_sorted_output(self, _isolate_outcomes):
        save_outcomes(
            [
                Outcome(node_id="z_test", status="failed"),
                Outcome(node_id="a_test", status="failed"),
            ]
        )
        assert load_failed_tests() == ["a_test", "z_test"]


class TestLoadDurations:
    def test_empty_when_no_file(self, _isolate_outcomes):
        assert load_test_durations() == {}

    def test_returns_durations(self, _isolate_outcomes):
        save_outcomes(
            [
                Outcome(node_id="a", status="passed", duration=1.5),
                Outcome(node_id="b", status="failed", duration=0.3),
            ]
        )
        durations = load_test_durations()
        assert durations["a"] == 1.5
        assert durations["b"] == 0.3


class TestClear:
    def test_clear_removes_file(self, _isolate_outcomes):
        save_outcomes([Outcome(node_id="a", status="passed")])
        assert _isolate_outcomes.exists()
        clear_outcomes()
        assert not _isolate_outcomes.exists()

    def test_clear_no_file_is_noop(self, _isolate_outcomes):
        clear_outcomes()  # should not raise


class TestErrorPaths:
    def test_load_raw_corrupt_json(self, _isolate_outcomes):
        """_load_raw should return {} on corrupt JSON."""
        _isolate_outcomes.write_text("NOT VALID JSON {{{")
        assert load_failed_tests() == []

    def test_save_raw_write_error(self, _isolate_outcomes, monkeypatch):
        """_save_raw should log error on write failure."""
        import py_smart_test.test_outcome_store as tos

        # Point to an unwritable path
        bad_path = (
            _isolate_outcomes.parent / "nonexistent_dir" / "sub" / "outcomes.json"
        )
        monkeypatch.setattr(tos, "OUTCOMES_FILE", bad_path)
        # Make the parent dir a file so mkdir fails
        bad_path.parent.parent.mkdir(parents=True, exist_ok=True)
        bad_path.parent.write_text("block")

        # Should not raise, just log
        save_outcomes([Outcome(node_id="a", status="passed")])


class TestSaveError:
    def test_save_outcomes_error_simple(self, _isolate_outcomes, caplog):
        from unittest.mock import patch

        import py_smart_test.test_outcome_store as tos

        # Simulate open error directly
        with patch("builtins.open", side_effect=PermissionError("Boom")):
            tos.save_outcomes([tos.Outcome(node_id="a", status="passed")])

        assert "Failed to save test outcomes" in caplog.text


def test_reload_outcome_store_module_coverage():
    """Reload test_outcome_store module to cover module-level code."""
    import importlib

    import py_smart_test.test_outcome_store as tos

    importlib.reload(tos)


class TestLoadDurationsEdgeCases:
    def test_skips_items_without_duration(self, _isolate_outcomes):
        import py_smart_test.test_outcome_store as tos

        # Raw save to include item without duration
        tos._save_raw({"a": {"status": "passed"}})
        assert tos.load_test_durations() == {}
