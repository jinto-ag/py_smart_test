import sys
from pathlib import Path

import pytest

# Ensure scripts package is importable if running from repo root without installation
# Add scripts/src to sys.path
# Add scripts/src to sys.path
# conftest is at scripts/tests/conftest.py
# .parent -> tests
# .parent.parent -> scripts
# We want scripts/src
SCRIPT_SRC = Path(__file__).resolve().parent.parent / "src"
if str(SCRIPT_SRC) not in sys.path:
    sys.path.insert(0, str(SCRIPT_SRC))


@pytest.fixture
def temp_repo_root(tmp_path):
    """
    Create a temporary repository structure for testing.
    repo/
      src/
        py_smart_test/
      tests/
      .py_smart_test/
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    src = repo / "src" / "py_smart_test"
    src.mkdir(parents=True)

    tests = repo / "tests"
    tests.mkdir()

    graph_dir = repo / ".py_smart_test"
    graph_dir.mkdir()
    (graph_dir / "cache").mkdir()

    return repo


@pytest.fixture
def mock_paths(monkeypatch, temp_repo_root):
    """
    Mock _paths module to point to temp_repo_root.
    """
    # Import inside fixture to avoid import errors at collection time if paths wrong
    from py_smart_test import _paths

    monkeypatch.setattr(_paths, "REPO_ROOT", temp_repo_root)
    monkeypatch.setattr(_paths, "SRC_ROOT", temp_repo_root / "src")
    monkeypatch.setattr(_paths, "PACKAGES", ["py_smart_test"])
    monkeypatch.setattr(_paths, "DEFAULT_BRANCH", "main")
    monkeypatch.setattr(_paths, "TEST_ROOT", temp_repo_root / "tests")
    monkeypatch.setattr(_paths, "GRAPH_DIR", temp_repo_root / ".py_smart_test")
    monkeypatch.setattr(
        _paths,
        "GRAPH_FILE",
        temp_repo_root / ".py_smart_test" / "dependency_graph.json",
    )
    monkeypatch.setattr(
        _paths, "CACHE_DIR", temp_repo_root / ".py_smart_test" / "cache"
    )
    monkeypatch.setattr(
        _paths,
        "CACHE_FILE",
        temp_repo_root / ".py_smart_test" / "cache" / "dependency_graph_cache.json",
    )

    return _paths
