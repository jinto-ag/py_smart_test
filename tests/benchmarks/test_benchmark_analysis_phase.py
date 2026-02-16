"""Benchmarks for individual analysis phase operations.

Tests the performance of:
- File hashing
- AST parsing
- Dependency graph generation
- Test module mapping
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[3] / "src"))


pytestmark = pytest.mark.benchmark


class TestFileHashing:
    """Benchmark file hashing operations."""

    def test_hash_small_project_sequential(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark file hashing on small project (100 files)."""
        monkeypatch.chdir(benchmark_project_small)

        # Mock paths to point to benchmark project
        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")

        def hash_all_files():
            """Hash all Python files in project."""
            from py_smart_test.file_hash_manager import get_current_hashes

            return get_current_hashes()

        result = benchmark(hash_all_files)
        assert len(result) > 0

    @pytest.mark.skip(reason="Parallel hashing removed - sequential is 3.4x faster")
    def test_hash_small_project_parallel(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark parallel file hashing on small project (100 files).

        NOTE: This test is disabled. Parallel file hashing was tested but found to be
        3.4x slower than sequential due to disk I/O bottlenecks.
        """
        pass

    def test_hash_medium_project_sequential(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark file hashing on medium project (500 files)."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")

        def hash_all_files():
            from py_smart_test.file_hash_manager import get_current_hashes

            return get_current_hashes()

        result = benchmark(hash_all_files)
        assert len(result) > 0

    @pytest.mark.skip(reason="Parallel hashing removed - sequential is 3.4x faster")
    def test_hash_medium_project_parallel(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark parallel file hashing on medium project (500 files).

        NOTE: This test is disabled. Parallel file hashing was tested but found to be
        3.4x slower than sequential due to disk I/O bottlenecks.
        """
        pass

    def test_hash_large_project_sequential(
        self, benchmark, benchmark_project_large: Path, monkeypatch
    ):
        """Benchmark file hashing on large project (2000 files)."""
        monkeypatch.chdir(benchmark_project_large)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_large)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_large / "src")

        def hash_all_files():
            from py_smart_test.file_hash_manager import get_current_hashes

            return get_current_hashes()

        result = benchmark(hash_all_files)
        assert len(result) > 0

    @pytest.mark.skip(reason="Parallel hashing removed - sequential is 3.4x faster")
    def test_hash_large_project_parallel(
        self, benchmark, benchmark_project_large: Path, monkeypatch
    ):
        """Benchmark parallel file hashing on large project (2000 files).

        NOTE: This test is disabled. Parallel file hashing was tested but found to be
        3.4x slower than sequential due to disk I/O bottlenecks.
        """
        pass


class TestASTParsing:
    """Benchmark AST parsing and import analysis."""

    def test_parse_small_project(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark AST parsing on small project."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        def parse_and_build_graph():
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            return scan_and_build_graph(benchmark_project_small / "src", parallel=False)

        result = benchmark(parse_and_build_graph)
        assert "modules" in result

    def test_parse_medium_project(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark AST parsing on medium project."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        def parse_and_build_graph():
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            return scan_and_build_graph(
                benchmark_project_medium / "src", parallel=False
            )

        result = benchmark(parse_and_build_graph)
        assert "modules" in result

    def test_parse_large_project(
        self, benchmark, benchmark_project_large: Path, monkeypatch
    ):
        """Benchmark AST parsing on large project (sequential)."""
        monkeypatch.chdir(benchmark_project_large)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_large)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_large / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        def parse_and_build_graph():
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            return scan_and_build_graph(benchmark_project_large / "src", parallel=False)

        result = benchmark(parse_and_build_graph)
        assert "modules" in result

    def test_parse_large_project_parallel(
        self, benchmark, benchmark_project_large: Path, monkeypatch
    ):
        """Benchmark AST parsing on large project (parallel with 8 workers)."""
        monkeypatch.chdir(benchmark_project_large)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_large)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_large / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        def parse_and_build_graph():
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            return scan_and_build_graph(
                benchmark_project_large / "src", parallel=True, workers=8
            )

        result = benchmark(parse_and_build_graph)
        assert "modules" in result


class TestTestModuleMapping:
    """Benchmark test-to-module mapping."""

    def test_map_small_project(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark test module mapping on small project."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        # First generate graph
        from py_smart_test.generate_dependency_graph import scan_and_build_graph

        _ = scan_and_build_graph(benchmark_project_small / "src")

        def map_tests():
            from py_smart_test.test_module_mapper import map_tests_to_modules

            return map_tests_to_modules(benchmark_project_small / "tests")

        result = benchmark(map_tests)
        assert isinstance(result, dict)

    def test_map_medium_project(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark test module mapping on medium project."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        from py_smart_test.generate_dependency_graph import scan_and_build_graph

        _ = scan_and_build_graph(benchmark_project_medium / "src")

        def map_tests():
            from py_smart_test.test_module_mapper import map_tests_to_modules

            return map_tests_to_modules(benchmark_project_medium / "tests")

        result = benchmark(map_tests)
        assert isinstance(result, dict)
