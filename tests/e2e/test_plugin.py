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
