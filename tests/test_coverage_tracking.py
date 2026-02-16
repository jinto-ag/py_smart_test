"""Tests for coverage tracking feature."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from py_smart_test.coverage_tracker import (
    load_coverage_mapping,
    save_coverage_mapping,
    merge_coverage_mapping,
    get_tests_for_files,
    clear_coverage_mapping,
)


class TestCoverageMapping:
    """Tests for coverage mapping persistence."""

    def test_load_coverage_mapping_not_exists(self, tmp_path, monkeypatch):
        """Test loading when file doesn't exist returns empty dict."""
        fake_file = tmp_path / "nonexistent.json"
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            result = load_coverage_mapping()
            assert result == {}

    def test_load_coverage_mapping_success(self, tmp_path, monkeypatch):
        """Test loading coverage mapping from file."""
        fake_file = tmp_path / "coverage_mapping.json"
        mapping = {
            "src/module.py": ["tests/test_module.py::test_func"],
            "src/other.py": ["tests/test_other.py::test_other"],
        }
        fake_file.write_text(json.dumps(mapping))
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            result = load_coverage_mapping()
            assert result == mapping

    def test_load_coverage_mapping_invalid_json(self, tmp_path):
        """Test loading with invalid JSON returns empty dict."""
        fake_file = tmp_path / "coverage_mapping.json"
        fake_file.write_text("invalid json {")
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            result = load_coverage_mapping()
            assert result == {}

    def test_save_coverage_mapping(self, tmp_path):
        """Test saving coverage mapping to file."""
        fake_file = tmp_path / "coverage_mapping.json"
        mapping = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            save_coverage_mapping(mapping)
            
            # Verify file was created with correct content
            assert fake_file.exists()
            saved_data = json.loads(fake_file.read_text())
            assert saved_data == mapping

    def test_save_coverage_mapping_creates_directory(self, tmp_path):
        """Test saving creates parent directories if needed."""
        fake_file = tmp_path / "nested" / "dir" / "coverage_mapping.json"
        mapping = {"src/module.py": ["tests/test_module.py"]}
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            save_coverage_mapping(mapping)
            
            assert fake_file.exists()
            assert fake_file.parent.exists()


class TestMergeCoverageMapping:
    """Tests for merging coverage mappings."""

    def test_merge_empty_existing(self):
        """Test merging with empty existing mapping."""
        existing = {}
        new_data = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        
        result = merge_coverage_mapping(existing, new_data)
        
        assert result == new_data

    def test_merge_new_files(self):
        """Test merging adds new files."""
        existing = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        new_data = {
            "src/other.py": ["tests/test_other.py::test_other"],
        }
        
        result = merge_coverage_mapping(existing, new_data)
        
        assert "src/module.py" in result
        assert "src/other.py" in result
        assert result["src/module.py"] == existing["src/module.py"]
        assert result["src/other.py"] == new_data["src/other.py"]

    def test_merge_deduplicates_tests(self):
        """Test merging deduplicates test lists."""
        existing = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        new_data = {
            "src/module.py": ["tests/test_module.py::test_func", "tests/test_other.py::test_other"],
        }
        
        result = merge_coverage_mapping(existing, new_data)
        
        assert sorted(result["src/module.py"]) == [
            "tests/test_module.py::test_func",
            "tests/test_other.py::test_other",
        ]

    def test_merge_sorts_tests(self):
        """Test merging sorts test lists."""
        existing = {
            "src/module.py": ["tests/z.py::test_z"],
        }
        new_data = {
            "src/module.py": ["tests/a.py::test_a"],
        }
        
        result = merge_coverage_mapping(existing, new_data)
        
        assert result["src/module.py"] == [
            "tests/a.py::test_a",
            "tests/z.py::test_z",
        ]


class TestGetTestsForFiles:
    """Tests for getting tests from coverage mapping."""

    def test_get_tests_for_files_empty_mapping(self):
        """Test with empty coverage mapping."""
        changed_files = [Path("src/module.py")]
        mapping = {}
        
        result = get_tests_for_files(changed_files, mapping)
        
        assert result == set()

    def test_get_tests_for_files_found(self):
        """Test finding tests for changed files."""
        changed_files = [Path("src/module.py")]
        mapping = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        
        result = get_tests_for_files(changed_files, mapping)
        
        assert result == {"tests/test_module.py::test_func"}

    def test_get_tests_for_files_multiple_files(self):
        """Test finding tests for multiple changed files."""
        changed_files = [Path("src/module.py"), Path("src/other.py")]
        mapping = {
            "src/module.py": ["tests/test_module.py::test_func"],
            "src/other.py": ["tests/test_other.py::test_other"],
        }
        
        result = get_tests_for_files(changed_files, mapping)
        
        assert result == {
            "tests/test_module.py::test_func",
            "tests/test_other.py::test_other",
        }

    def test_get_tests_for_files_not_found(self):
        """Test with file not in mapping."""
        changed_files = [Path("src/unknown.py")]
        mapping = {
            "src/module.py": ["tests/test_module.py::test_func"],
        }
        
        result = get_tests_for_files(changed_files, mapping)
        
        assert result == set()


class TestClearCoverageMapping:
    """Tests for clearing coverage mapping."""

    def test_clear_coverage_mapping_exists(self, tmp_path):
        """Test clearing when file exists."""
        fake_file = tmp_path / "coverage_mapping.json"
        fake_file.write_text("{}")
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            clear_coverage_mapping()
            
            assert not fake_file.exists()

    def test_clear_coverage_mapping_not_exists(self, tmp_path):
        """Test clearing when file doesn't exist (should not error)."""
        fake_file = tmp_path / "nonexistent.json"
        
        with patch("py_smart_test.coverage_tracker.COVERAGE_DATA_FILE", fake_file):
            # Should not raise an error
            clear_coverage_mapping()
            
            assert not fake_file.exists()


class TestCoverageIntegration:
    """Integration tests for coverage tracking in find_affected_modules."""

    def test_get_affected_tests_with_coverage_disabled(self):
        """Test that coverage tracking is optional."""
        from py_smart_test.find_affected_modules import get_affected_tests
        
        with patch("py_smart_test.find_affected_modules.get_changed_files") as mock_changed:
            with patch("py_smart_test.find_affected_modules._paths.get_graph_file") as mock_graph:
                mock_changed.return_value = []
                mock_graph_file = MagicMock()
                mock_graph_file.exists.return_value = True
                mock_graph.return_value = mock_graph_file
                
                with patch("builtins.open", mock_open(read_data='{"modules": {}}')):
                    result = get_affected_tests(use_coverage=False)
                    
                    # Should work without coverage
                    assert "tests" in result
                    assert "affected_modules" in result

    def test_get_affected_tests_with_coverage_enabled(self):
        """Test that coverage tracking augments results."""
        from py_smart_test.find_affected_modules import get_affected_tests
        
        with patch("py_smart_test.find_affected_modules.get_changed_files") as mock_changed:
            with patch("py_smart_test.find_affected_modules._paths.get_graph_file") as mock_graph:
                with patch("py_smart_test.coverage_tracker.load_coverage_mapping") as mock_load:
                    with patch("py_smart_test.coverage_tracker.get_tests_for_files") as mock_get_tests:
                        mock_changed.return_value = [Path("src/module.py")]
                        mock_graph_file = MagicMock()
                        mock_graph_file.exists.return_value = True
                        mock_graph.return_value = mock_graph_file
                        
                        mock_load.return_value = {"src/module.py": ["tests/test_cov.py::test_it"]}
                        mock_get_tests.return_value = {"tests/test_cov.py::test_it"}
                        
                        with patch("builtins.open", mock_open(read_data='{"modules": {}}')):
                            result = get_affected_tests(use_coverage=True)
                            
                            # Should include coverage-based tests
                            assert "tests/test_cov.py::test_it" in result["tests"]
