"""E2E tests for the ``py-smart-test`` / ``pst`` CLI tool.

These tests run the CLI commands inside the ``sample_project`` fixture
and verify correct output and behaviour.
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


def _run_cli(
    project: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command inside the sample project."""
    cmd = ["uv", "run", *args]
    return subprocess.run(
        cmd,
        cwd=project,
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "UV_LINK_MODE": "copy"},
    )


# ── Tests ───────────────────────────────────────────────────────────


class TestPstDefault:
    """``pst`` (no args) should default to smart behaviour."""

    def test_pst_no_args(self, sample_project: Path) -> None:
        """Running ``pst`` without arguments should invoke pytest --smart."""
        result = _run_cli(sample_project, "pst", check=False)
        # Should succeed — exit code 5 (no tests selected) is mapped to 0 by pst
        assert result.returncode == 0


class TestPstJsonOutput:
    """``pst --json`` should output JSON without running tests."""

    def test_json_flag(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "py-smart-test", "--json")
        assert result.returncode == 0
        # Output should contain JSON-like content
        assert "{" in result.stdout or "tests" in result.stdout


class TestPstDryRun:
    """``pst --dry-run`` should show the plan without executing."""

    def test_dry_run(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "py-smart-test", "--dry-run")
        assert result.returncode == 0
        assert "Dry run" in result.stdout or "Would execute" in result.stdout


class TestPstRegenerateGraph:
    """``pst --regenerate-graph`` should force graph regen."""

    def test_regenerate(self, sample_project: Path) -> None:
        result = _run_cli(
            sample_project, "py-smart-test", "--regenerate-graph", "--dry-run"
        )
        assert result.returncode == 0
        assert (
            "dependency graph" in result.stdout.lower()
            or "Regenerating" in result.stdout
        )


class TestPstAffected:
    """``pst-affected`` should list affected modules."""

    def test_affected_basic(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "pst-affected")
        assert result.returncode == 0

    def test_affected_json(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "pst-affected", "--json")
        assert result.returncode == 0
        assert "{" in result.stdout  # JSON output


class TestPstGraphGen:
    """``pst-gen`` should generate the dependency graph."""

    def test_graph_gen(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "pst-gen")
        assert result.returncode == 0
        # Graph file should exist
        graph_file = sample_project / ".py_smart_test" / "dependency_graph.json"
        assert graph_file.exists()


class TestPstStale:
    """``pst-stale`` should check graph staleness."""

    def test_stale_check(self, sample_project: Path) -> None:
        result = _run_cli(sample_project, "pst-stale", check=False)
        # May exit 0 or 1 depending on staleness — just verify it runs
        assert result.returncode in (0, 1)


class TestCliErrorConditions:
    """Test CLI error handling."""

    def test_pst_affected_with_missing_graph(self, tmp_path: Path) -> None:
        """Test pst-affected when no graph exists."""
        project = tmp_path / "no_graph_project"
        project.mkdir()

        # Create minimal project
        (project / "pyproject.toml").write_text(
            textwrap.dedent(
                """\
                [project]
                name = "no-graph-test"
                version = "0.1.0"
                requires-python = ">=3.11"
                dependencies = ["py-smart-test"]
                """
            )
        )

        # Install py-smart-test
        subprocess.run(
            ["uv", "add", "--dev", str(_PROJECT_ROOT)], cwd=project, check=True
        )

        # Run pst-affected without graph
        result = subprocess.run(
            ["uv", "run", "pst-affected"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        # Should handle gracefully (may exit with error or show empty results)
        assert result.returncode in (0, 1)
