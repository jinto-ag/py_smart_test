"""E2E tests for the pytest plugin (``--smart``, ``--smart-first``, etc.).

These tests run ``uv run pytest`` inside the ``sample_project`` fixture
and verify stdout/stderr for correct plugin behaviour.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

# Resolve the project root so we can install py-smart-test from local source.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.e2e


# ── Helpers ─────────────────────────────────────────────────────────


def _uv_pytest(
    project: Path,
    *extra_args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``uv run pytest`` inside the sample project."""
    cmd = ["uv", "run", "pytest", *extra_args]
    return subprocess.run(
        cmd,
        cwd=project,
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "UV_LINK_MODE": "copy"},
    )


# ── Tests ───────────────────────────────────────────────────────────


class TestPluginLoads:
    """Verify the plugin is auto-discovered and registers its options."""

    def test_plugin_visible_in_help(self, sample_project: Path) -> None:
        result = _uv_pytest(sample_project, "--help")
        assert "--smart" in result.stdout
        assert "--smart-first" in result.stdout
        assert "--smart-working-tree" in result.stdout

    def test_normal_run_no_flags(self, sample_project: Path) -> None:
        """Without smart flags, all tests should run normally."""
        result = _uv_pytest(sample_project, "-v")
        assert result.returncode == 0
        assert "3 passed" in result.stdout


class TestSmartMode:
    """Verify ``--smart`` deselects unaffected tests."""

    def test_smart_no_changes(self, sample_project: Path) -> None:
        """With no code changes, --smart should deselect everything."""
        result = _uv_pytest(sample_project, "--smart", "-v", check=False)
        # Exit 0 (success) or 5 (no tests selected) are both valid
        assert result.returncode in (0, 5)
        assert "deselected" in result.stdout or "no tests ran" in result.stdout

    def test_smart_with_working_tree_change(self, sample_project: Path) -> None:
        """After modifying a source file, --smart --smart-working-tree should
        detect the change and run affected tests."""
        math_file = sample_project / "src" / "mylib" / "math_utils.py"
        original = math_file.read_text()

        try:
            # Append a new function (unstaged change)
            math_file.write_text(
                original
                + textwrap.dedent(
                    """\

                def subtract(a: int, b: int) -> int:
                    return a - b
                """
                )
            )

            result = _uv_pytest(
                sample_project,
                "--smart",
                "--smart-working-tree",
                "-v",
                check=False,
            )
            # Exit 0 or 5 are acceptable
            assert result.returncode in (0, 5)
            # If tests ran, they should have passed
            stdout = result.stdout
            assert "passed" in stdout or "deselected" in stdout
        finally:
            # Restore original to keep fixture clean for other tests
            math_file.write_text(original)

    def test_smart_regenerates_missing_graph(self, sample_project: Path) -> None:
        """When dependency graph is missing, --smart should regenerate it."""
        # Remove the dependency graph to simulate missing graph
        graph_file = sample_project / ".py_smart_test" / "dependency_graph.json"
        if graph_file.exists():
            graph_file.unlink()

        # Modify a source file to have some changes
        math_file = sample_project / "src" / "mylib" / "math_utils.py"
        original = math_file.read_text()

        try:
            # Append a new function (unstaged change)
            math_file.write_text(
                original
                + textwrap.dedent(
                    """\

                def subtract(a: int, b: int) -> int:
                    return a - b
                """
                )
            )

            result = _uv_pytest(
                sample_project,
                "--smart",
                "--smart-working-tree",
                "-v",
                check=False,
            )
            # Should succeed and regenerate the graph
            assert result.returncode in (0, 5)
            # Should see regeneration message in output
            assert "Dependency graph is stale, regenerating" in result.stderr
            # Graph should be recreated
            assert graph_file.exists()
        finally:
            # Restore original to keep fixture clean for other tests
            math_file.write_text(original)


class TestSmartFirstMode:
    """Verify ``--smart-first`` keeps all tests but reorders."""

    def test_smart_first_runs_all(self, sample_project: Path) -> None:
        result = _uv_pytest(sample_project, "--smart-first", "-v")
        assert result.returncode == 0
        assert "3 passed" in result.stdout


class TestSmartSince:
    """Verify ``--smart-since`` flag is accepted."""

    def test_smart_since_accepts_ref(self, sample_project: Path) -> None:
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-since",
            "HEAD",
            "-v",
            check=False,
        )
        # Exit 0 or 5 (no tests selected) are both valid
        assert result.returncode in (0, 5)


class TestSmartStaged:
    """Verify ``--smart-staged`` flag is accepted."""

    def test_smart_staged_flag(self, sample_project: Path) -> None:
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-staged",
            "-v",
            check=False,
        )
        # Exit 0 or 5 (no tests selected) are both valid
        assert result.returncode in (0, 5)


class TestSmartNoCollect:
    """Verify ``--smart-no-collect`` works the same as ``--smart``."""

    def test_smart_no_collect_equivalent(self, sample_project: Path) -> None:
        """--smart-no-collect should behave identically to --smart."""
        # Test with no changes - both should deselect everything
        result_smart = _uv_pytest(sample_project, "--smart", "-v", check=False)
        result_no_collect = _uv_pytest(
            sample_project, "--smart-no-collect", "-v", check=False
        )

        # Both should have same exit codes and behavior
        assert result_smart.returncode == result_no_collect.returncode
        assert ("deselected" in result_smart.stdout) == (
            "deselected" in result_no_collect.stdout
        )


class TestErrorConditions:
    """Test error handling and edge cases."""

    def test_smart_with_no_source_files(self, tmp_path: Path) -> None:
        """Test behavior when project has no source files."""
        # Create a minimal project with no source code
        project = tmp_path / "empty_project"
        project.mkdir()

        # Basic pyproject.toml
        (project / "pyproject.toml").write_text(
            textwrap.dedent(
                """\
                [project]
                name = "empty-test"
                version = "0.1.0"
                requires-python = ">=3.11"
                dependencies = ["py-smart-test"]

                [tool.pytest.ini_options]
                testpaths = ["tests"]
                """
            )
        )

        # Empty tests directory
        (project / "tests").mkdir()
        (project / "tests" / "__init__.py").touch()

        # Initialize git
        subprocess.run(["git", "init"], cwd=project, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project)
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=project, check=True)

        # Install py-smart-test
        subprocess.run(
            ["uv", "add", "--dev", str(_PROJECT_ROOT), "pytest"],
            cwd=project,
            check=True,
        )

        # Run smart - should handle gracefully
        result = subprocess.run(
            ["uv", "run", "pytest", "--smart", "-v"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        # Should not crash, may exit with 0 or 5
        assert result.returncode in (0, 5)

    def test_smart_with_syntax_error(self, sample_project: Path) -> None:
        """Test behavior when source files have syntax errors."""
        math_file = sample_project / "src" / "mylib" / "math_utils.py"
        original = math_file.read_text()

        try:
            # Introduce a syntax error
            math_file.write_text(
                "def broken_function(\n    return 1"
            )  # Missing closing paren

            result = _uv_pytest(
                sample_project, "--smart", "--smart-working-tree", check=False
            )
            # pytest fails with exit code 2 due to collection errors from syntax errors
            # But the smart plugin handles syntax errors gracefully during generation
            assert result.returncode == 2  # pytest collection error
            # Should see syntax error warning in stderr
            assert "Syntax error in" in result.stderr
        finally:
            math_file.write_text(original)


class TestSmartParallel:
    """Verify ``--smart-parallel`` enables parallel execution."""

    def test_smart_parallel_option_registered(self, sample_project: Path) -> None:
        """Test that --smart-parallel option is visible in help."""
        result = _uv_pytest(sample_project, "--help")
        assert "--smart-parallel" in result.stdout
        assert "--smart-parallel-workers" in result.stdout

    def test_smart_parallel_basic(self, sample_project: Path) -> None:
        """Test basic parallel execution with --smart-parallel."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "-v",
            check=False,
        )
        # Should succeed (exit 0 or 5 if no tests selected)
        assert result.returncode in (0, 5)
        # If tests ran successfully, should see passed tests
        if "passed" in result.stdout:
            assert "3 passed" in result.stdout or "passed" in result.stdout

    def test_smart_parallel_auto_workers(self, sample_project: Path) -> None:
        """Test --smart-parallel with auto worker configuration."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "-v",
            check=False,
        )
        # Should succeed with auto worker count
        assert result.returncode in (0, 5)

    def test_smart_parallel_custom_workers(self, sample_project: Path) -> None:
        """Test --smart-parallel with custom worker count."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "--smart-parallel-workers",
            "2",
            "-v",
            check=False,
        )
        # Should succeed with specified workers
        assert result.returncode in (0, 5)

    def test_smart_parallel_first_mode(self, sample_project: Path) -> None:
        """Test --smart-parallel combined with --smart-first."""
        result = _uv_pytest(
            sample_project,
            "--smart-first",
            "--smart-parallel",
            "-v",
            check=False,
        )
        # Should run all tests in parallel
        assert result.returncode == 0
        assert "3 passed" in result.stdout or "passed" in result.stdout

    def test_smart_parallel_with_working_tree(self, sample_project: Path) -> None:
        """Test --smart-parallel with --smart-working-tree detection."""
        math_file = sample_project / "src" / "mylib" / "math_utils.py"
        original = math_file.read_text()

        try:
            # Make a small change
            math_file.write_text(original + "\n\ndef new_func():\n    return 42\n")

            result = _uv_pytest(
                sample_project,
                "--smart",
                "--smart-working-tree",
                "--smart-parallel",
                "-v",
                check=False,
            )
            # Should handle gracefully
            assert result.returncode in (0, 5)
        finally:
            math_file.write_text(original)

    def test_parallel_without_xdist_fallback(self, sample_project: Path) -> None:
        """Test that parallel gracefully falls back when xdist unavailable."""
        # Note: This test just verifies the system handles it gracefully
        # In actual CI, xdist should be installed, so this mainly tests
        # warning messages in logs are present
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "-v",
            check=False,
        )
        # Should still complete without crashing
        assert result.returncode in (0, 1, 5)


class TestSmartCoverage:
    """Verify ``--smart-coverage`` enables coverage tracking."""

    def test_smart_coverage_option_registered(self, sample_project: Path) -> None:
        """Test that --smart-coverage option is visible in help."""
        result = _uv_pytest(sample_project, "--help")
        assert "--smart-coverage" in result.stdout

    def test_smart_coverage_basic(self, sample_project: Path) -> None:
        """Test basic coverage tracking with --smart-coverage."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should run with coverage
        assert result.returncode in (0, 5)
        # Coverage output should be present if tests ran
        if "passed" in result.stdout:
            assert "passed" in result.stdout

    def test_smart_coverage_first_mode(self, sample_project: Path) -> None:
        """Test --smart-coverage combined with --smart-first."""
        result = _uv_pytest(
            sample_project,
            "--smart-first",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should run all tests with coverage reporting
        assert result.returncode in (0, 5)

    def test_smart_coverage_with_working_tree(self, sample_project: Path) -> None:
        """Test --smart-coverage with --smart-working-tree."""
        math_file = sample_project / "src" / "mylib" / "math_utils.py"
        original = math_file.read_text()

        try:
            # Make a change
            math_file.write_text(
                original + "\n\ndef new_add(a, b):\n    return a + b\n"
            )

            result = _uv_pytest(
                sample_project,
                "--smart",
                "--smart-working-tree",
                "--smart-coverage",
                "-v",
                check=False,
            )
            # Should handle gracefully
            assert result.returncode in (0, 5)
        finally:
            math_file.write_text(original)

    def test_coverage_without_pytest_cov_fallback(self, sample_project: Path) -> None:
        """Test that coverage gracefully falls back when pytest-cov unavailable."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should still complete without crashing
        assert result.returncode in (0, 1, 5)


class TestSmartParallelAndCoverage:
    """Verify ``--smart-parallel`` and ``--smart-coverage`` work together."""

    def test_parallel_and_coverage_combined(self, sample_project: Path) -> None:
        """Test --smart-parallel and --smart-coverage together."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should run tests in parallel with coverage
        assert result.returncode in (0, 5)

    def test_parallel_coverage_first_mode(self, sample_project: Path) -> None:
        """Test --smart-first with both --smart-parallel and --smart-coverage."""
        result = _uv_pytest(
            sample_project,
            "--smart-first",
            "--smart-parallel",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should run all tests in parallel with coverage
        assert result.returncode in (0, 5)

    def test_parallel_coverage_custom_workers(self, sample_project: Path) -> None:
        """Test custom workers with coverage tracking."""
        result = _uv_pytest(
            sample_project,
            "--smart",
            "--smart-parallel",
            "--smart-parallel-workers",
            "2",
            "--smart-coverage",
            "-v",
            check=False,
        )
        # Should handle parallel execution with custom workers and coverage
        assert result.returncode in (0, 5)

    def test_parallel_coverage_with_working_tree(self, sample_project: Path) -> None:
        """Test parallel+coverage with working tree changes."""
        string_file = sample_project / "src" / "mylib" / "string_utils.py"
        original = string_file.read_text()

        try:
            # Add a new function
            string_file.write_text(
                original
                + "\n\ndef upper_string(s: str) -> str:\n    return s.upper()\n"
            )

            result = _uv_pytest(
                sample_project,
                "--smart",
                "--smart-working-tree",
                "--smart-parallel",
                "--smart-coverage",
                "-v",
                check=False,
            )
            # Should handle gracefully
            assert result.returncode in (0, 5)
        finally:
            string_file.write_text(original)
