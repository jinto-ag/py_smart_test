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
