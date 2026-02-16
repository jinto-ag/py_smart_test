"""End-to-end benchmarks measuring full workflow performance.

Tests complete workflows:
- Cold start (first run with graph generation)
- Warm run (cached graph, no changes)
- Incremental run (small changes)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

pytestmark = pytest.mark.benchmark


class TestColdStart:
    """Benchmark cold start performance (first run)."""

    def test_cold_start_small(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark cold start on small project."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])
        monkeypatch.setattr(
            paths_module,
            "PY_SMART_TEST_DIR",
            benchmark_project_small / ".py_smart_test",
        )

        def cold_start():
            """Full analysis phase including graph generation."""
            import json

            from py_smart_test.file_hash_manager import update_hashes
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            # Generate dependency graph
            graph = scan_and_build_graph(benchmark_project_small / "src")
            out_file = (
                benchmark_project_small / ".py_smart_test" / "dependency_graph.json"
            )
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w") as f:
                json.dump(graph, f)

            # Update file hashes
            update_hashes()

            return True

        result = benchmark(cold_start)
        assert result is True

    def test_cold_start_medium(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark cold start on medium project."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])
        monkeypatch.setattr(
            paths_module,
            "PY_SMART_TEST_DIR",
            benchmark_project_medium / ".py_smart_test",
        )

        def cold_start():
            import json

            from py_smart_test.file_hash_manager import update_hashes
            from py_smart_test.generate_dependency_graph import scan_and_build_graph

            graph = scan_and_build_graph(benchmark_project_medium / "src")
            out_file = (
                benchmark_project_medium / ".py_smart_test" / "dependency_graph.json"
            )
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w") as f:
                json.dump(graph, f)

            update_hashes()

            return True

        result = benchmark(cold_start)
        assert result is True


class TestWarmRun:
    """Benchmark warm run performance (cached graph, no changes)."""

    def test_warm_run_small(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark warm run on small project."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])
        monkeypatch.setattr(
            paths_module,
            "PY_SMART_TEST_DIR",
            benchmark_project_small / ".py_smart_test",
        )

        # Setup: generate graph and hashes

        from py_smart_test.file_hash_manager import update_hashes
        from py_smart_test.generate_dependency_graph import scan_and_build_graph

        graph = scan_and_build_graph(benchmark_project_small / "src")
        out_file = benchmark_project_small / ".py_smart_test" / "dependency_graph.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w") as f:
            json.dump(graph, f)
        update_hashes()

        def warm_run():
            """Check staleness and load cached data."""
            from py_smart_test.detect_graph_staleness import is_graph_stale
            from py_smart_test.find_affected_modules import get_affected_tests

            # Should detect graph is fresh
            is_stale = is_graph_stale()
            assert not is_stale

            # Get affected tests (should load from cache)
            result = get_affected_tests(base="HEAD", staged=False)
            return result

        result = benchmark(warm_run)
        assert "tests" in result or "graph" in result

    def test_warm_run_medium(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Benchmark warm run on medium project."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])
        monkeypatch.setattr(
            paths_module,
            "PY_SMART_TEST_DIR",
            benchmark_project_medium / ".py_smart_test",
        )

        from py_smart_test.file_hash_manager import update_hashes
        from py_smart_test.generate_dependency_graph import scan_and_build_graph

        graph = scan_and_build_graph(benchmark_project_medium / "src")
        out_file = benchmark_project_medium / ".py_smart_test" / "dependency_graph.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w") as f:
            json.dump(graph, f)
        update_hashes()

        def warm_run():
            from py_smart_test.detect_graph_staleness import is_graph_stale
            from py_smart_test.find_affected_modules import get_affected_tests

            is_stale = is_graph_stale()
            assert not is_stale

            result = get_affected_tests(base="HEAD", staged=False)
            return result

        result = benchmark(warm_run)
        assert "tests" in result or "graph" in result


class TestIncrementalRun:
    """Benchmark incremental run (small changes detected)."""

    def test_incremental_small(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Benchmark incremental run with 1 file changed."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])
        monkeypatch.setattr(
            paths_module,
            "PY_SMART_TEST_DIR",
            benchmark_project_small / ".py_smart_test",
        )

        # Setup: generate graph

        from py_smart_test.file_hash_manager import update_hashes
        from py_smart_test.generate_dependency_graph import scan_and_build_graph

        graph = scan_and_build_graph(benchmark_project_small / "src")
        out_file = benchmark_project_small / ".py_smart_test" / "dependency_graph.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w") as f:
            json.dump(graph, f)
        update_hashes()

        # Modify one file
        module_file = benchmark_project_small / "src" / "myapp" / "module_5.py"
        original_content = module_file.read_text()
        module_file.write_text(original_content + "\n# Modified\n")

        def incremental_run():
            """Detect change and find affected tests."""
            from py_smart_test.file_hash_manager import (
                compute_current_hashes,
                load_hashes,
            )

            # Compute changes
            old_hashes = load_hashes()
            new_hashes = compute_current_hashes()

            # Find affected (mock git for hash-based)
            changed_files = [
                path
                for path, hash_val in new_hashes.items()
                if old_hashes.get(path) != hash_val
            ]

            assert len(changed_files) > 0
            return changed_files

        result = benchmark(incremental_run)
        assert len(result) > 0
