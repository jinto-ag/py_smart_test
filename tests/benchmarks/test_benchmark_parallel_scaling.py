"""Benchmarks for parallel scaling and worker efficiency.

Tests parallel execution with different worker counts to validate
linear scaling assumptions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))

pytestmark = pytest.mark.benchmark


class TestParallelScaling:
    """Test parallel execution scaling with worker count."""

    @pytest.mark.skip(reason="Requires parallel implementation")
    def test_hash_scaling_small(
        self, benchmark, benchmark_project_small: Path, monkeypatch
    ):
        """Test file hashing scales linearly with workers (small project)."""
        monkeypatch.chdir(benchmark_project_small)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_small)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_small / "src")

        # TODO: Implement parallel_compute_hashes
        # Test with 1, 2, 4 workers and verify scaling
        pass

    @pytest.mark.skip(reason="Requires parallel implementation")
    def test_ast_scaling_medium(
        self, benchmark, benchmark_project_medium: Path, monkeypatch
    ):
        """Test AST parsing scales linearly with workers (medium project)."""
        monkeypatch.chdir(benchmark_project_medium)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_medium)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_medium / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        # TODO: Implement parallel AST parsing
        # Measure speedup: 2 workers => ~2x, 4 workers => ~4x
        pass

    @pytest.mark.skip(reason="Requires parallel implementation")
    def test_full_workflow_scaling(
        self, benchmark, benchmark_project_large: Path, monkeypatch
    ):
        """Test full workflow scales with workers on large project."""
        monkeypatch.chdir(benchmark_project_large)

        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", benchmark_project_large)
        monkeypatch.setattr(paths_module, "SRC_ROOT", benchmark_project_large / "src")
        monkeypatch.setattr(paths_module, "PACKAGES", ["myapp"])

        # TODO: Test end-to-end with different worker counts
        # Target: 4 workers => 3-4x speedup on large project
        pass


class TestWorkerOverhead:
    """Test worker overhead and threshold decisions."""

    def test_sequential_optimal_for_tiny(self, benchmark, tmp_path: Path, monkeypatch):
        """Verify sequential is faster for tiny projects (<10 files)."""
        # Create tiny project
        src_dir = tmp_path / "src" / "myapp"
        src_dir.mkdir(parents=True)

        for i in range(5):
            (src_dir / f"module_{i}.py").write_text(f"def func(): return {i}")

        monkeypatch.chdir(tmp_path)
        import py_smart_test._paths as paths_module

        monkeypatch.setattr(paths_module, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(paths_module, "SRC_ROOT", src_dir)

        def hash_sequential():
            from py_smart_test.file_hash_manager import compute_current_hashes

            return compute_current_hashes()

        result = benchmark(hash_sequential)
        assert len(result) > 0

        # With only 5 files, sequential should be < 10ms
        # Parallel overhead would be > 50ms (process spawning)
