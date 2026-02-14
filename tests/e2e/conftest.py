"""Shared fixtures for E2E tests.

The ``sample_project`` fixture creates a temporary Git repository with:
- pyproject.toml (depends on py-smart-test from local source)
- src/mylib/ with two inter-dependent Python modules
- tests/ with two test files

The project is initialised with an initial commit and ``uv pip install``
so that ``uv run pytest`` can be used to exercise the plugin.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

# Resolve the project root so we can install py-smart-test from local source.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def sample_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temp Git project with py-smart-test installed.

    Returns the project root ``Path``.  Session-scoped for speed — most
    tests can share the same project.
    """
    project = tmp_path_factory.mktemp("e2e_project")

    # ── pyproject.toml ──────────────────────────────────────────────
    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
        [project]
        name = "e2e-sample"
        version = "0.1.0"
        requires-python = ">=3.11"
        dependencies = ["py-smart-test"]

        [tool.pytest.ini_options]
        testpaths = ["tests"]
        pythonpath = ["src"]
        """
        )
    )

    # ── Source modules ──────────────────────────────────────────────
    src = project / "src" / "mylib"
    src.mkdir(parents=True)
    (src / "__init__.py").touch()
    (src / "math_utils.py").write_text(
        textwrap.dedent(
            """\
        def add(a: int, b: int) -> int:
            return a + b

        def multiply(a: int, b: int) -> int:
            return a * b
        """
        )
    )
    (src / "string_utils.py").write_text(
        textwrap.dedent(
            """\
        from .math_utils import add

        def repeat_string(s: str, n: int) -> str:
            total = add(n, 0)
            return s * total
        """
        )
    )

    # ── Tests ───────────────────────────────────────────────────────
    tests = project / "tests"
    tests.mkdir()
    (tests / "__init__.py").touch()
    (tests / "test_math.py").write_text(
        textwrap.dedent(
            """\
        from mylib.math_utils import add, multiply

        def test_add():
            assert add(1, 2) == 3

        def test_multiply():
            assert multiply(3, 4) == 12
        """
        )
    )
    (tests / "test_string.py").write_text(
        textwrap.dedent(
            """\
        from mylib.string_utils import repeat_string

        def test_repeat():
            assert repeat_string("ab", 3) == "ababab"
        """
        )
    )

    # ── Git init + initial commit ───────────────────────────────────
    _run(["git", "init"], cwd=project)
    _run(["git", "config", "user.email", "e2e@test.local"], cwd=project)
    _run(["git", "config", "user.name", "E2E"], cwd=project)
    _run(["git", "add", "-A"], cwd=project)
    _run(["git", "commit", "-m", "initial commit"], cwd=project)

    # ── Virtual env + install ───────────────────────────────────────
    _run(
        ["uv", "add", "--dev", str(_PROJECT_ROOT), "pytest"],
        cwd=project,
    )

    return project


# ── Helpers ─────────────────────────────────────────────────────────


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command in the project directory."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "UV_LINK_MODE": "copy"},
    )
