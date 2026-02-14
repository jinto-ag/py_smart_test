import json
from pathlib import Path
from typing import Any, Dict

from py_smart_test.find_affected_modules import get_transitive_dependents

# Note: we can't easily test get_changed_files with git in unit tests
# without a full git repo fixture.
# We will mock it or focus on logic tests.


def test_transitive_dependency_logic():
    graph = {
        "modules": {
            "a": {"imported_by": ["b"]},
            "b": {"imported_by": ["c"]},
            "c": {"imported_by": []},
            "d": {"imported_by": ["a"]},  # d imported by a
            "e": {"imported_by": []},
        }
    }

    # Change in 'a' -> affects 'a', 'b', 'c'
    deps = get_transitive_dependents(graph, {"a"})
    assert "a" in deps
    assert "b" in deps
    assert "c" in deps
    assert "d" not in deps
    assert "e" not in deps

    # Change in 'd' -> affects 'd', 'a', 'b', 'c'
    deps_d = get_transitive_dependents(graph, {"d"})
    assert "d" in deps_d
    assert "a" in deps_d
    assert "c" in deps_d


def test_affected_modules_integration(temp_repo_root, mock_paths, monkeypatch):
    """
    Test whole flow with mocked git and graph.
    """
    from typer.testing import CliRunner  # type: ignore

    from py_smart_test import find_affected_modules

    runner = CliRunner()

    # Create graph
    graph = {
        "modules": {
            "pkg.a": {
                "file": "src/pkg/a.py",
                "imported_by": ["pkg.b"],
                "tests": ["tests/test_a.py"],
            },
            "pkg.b": {
                "file": "src/pkg/b.py",
                "imported_by": [],
                "tests": ["tests/test_b.py"],
            },
        }
    }

    graph_file = mock_paths.GRAPH_FILE
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    graph_file.write_text(json.dumps(graph))

    # Mock get_changed_files to return src/pkg/a.py
    # Note: repo root relative path
    def mock_get_changed_files(base, staged):
        return [Path("src/pkg/a.py")]

    monkeypatch.setattr(
        find_affected_modules, "get_changed_files", mock_get_changed_files
    )

    # Create the file so get_module_name works?
    # find_affected_modules checks if file exists.
    # It also calls get_module_name.
    # We need to mock get_module_name or create the file.
    (mock_paths.REPO_ROOT / "src/pkg").mkdir(parents=True)
    (mock_paths.REPO_ROOT / "src/pkg/a.py").touch()

    # Exec command
    result = runner.invoke(find_affected_modules.app, ["--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    affected = data["affected_modules"]
    tests = data["tests"]

    # Changed a.py -> pkg.a
    # pkg.a -> imported_by pkg.b
    # So affected: pkg.a, pkg.b
    assert "pkg.a" in affected
    assert "pkg.b" in affected

    # Tests: test_a.py (from mod_a), test_b.py (from mod_b)
    assert "tests/test_a.py" in tests
    assert "tests/test_b.py" in tests


def test_get_changed_files_git_error(monkeypatch):
    import subprocess
    from unittest.mock import MagicMock

    from py_smart_test import find_affected_modules

    def mock_run(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Mock hash manager fallback
    mock_hash_fallback = MagicMock(return_value=[Path("fallback.py")])
    monkeypatch.setattr(
        "py_smart_test.find_affected_modules.get_changed_files_hash", mock_hash_fallback
    )

    files = find_affected_modules.get_changed_files()

    # Should call fallback
    assert mock_hash_fallback.called
    assert files == [Path("fallback.py")]


def test_get_affected_tests_exception_handling(monkeypatch, mock_paths):
    from unittest.mock import MagicMock

    from py_smart_test import find_affected_modules

    # Mock get_changed_files to return a file that causes error
    monkeypatch.setattr(
        find_affected_modules, "get_changed_files", lambda *a: [Path("error.py")]
    )

    # Mock graph existence
    (mock_paths.PY_SMART_TEST_DIR / "dependency_graph.json").write_text("{}")

    # Mock get_module_name to raise exception
    monkeypatch.setattr(
        "py_smart_test.find_affected_modules.get_module_name",
        MagicMock(side_effect=Exception("Boom")),
    )

    # Run
    result = find_affected_modules.get_affected_tests()

    # Should handle exception and continue
    assert result["affected_modules"] == []


def test_get_changed_files_success(monkeypatch, mock_paths):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(*args, **kwargs):
        # Return mocked stdout
        return subprocess.CompletedProcess(
            args, 0, stdout="file1.py\nfile2.py\n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    files = find_affected_modules.get_changed_files()
    assert len(files) == 2
    assert files[0].name == "file1.py"


def test_main_graph_missing(mock_paths, monkeypatch, caplog):
    from typer.testing import CliRunner  # type: ignore

    from py_smart_test import find_affected_modules

    # Ensure graph file doesn't exist
    if mock_paths.GRAPH_FILE.exists():
        mock_paths.GRAPH_FILE.unlink()

    runner = CliRunner()

    # Mock get_changed_files
    monkeypatch.setattr(find_affected_modules, "get_changed_files", lambda *a, **k: [])

    result = runner.invoke(find_affected_modules.app)
    assert result.exit_code == 0
    assert "Graph not found" in caplog.text


def test_deleted_file_logic(mock_paths, monkeypatch, temp_repo_root):
    from py_smart_test import find_affected_modules

    # Graph knows about pkg.a
    graph = {"modules": {"pkg.a": {"imported_by": ["pkg.b"]}}}
    graph_file = mock_paths.GRAPH_FILE
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    graph_file.write_text(json.dumps(graph))

    # Mock changed files: src/pkg/a.py (deleted)
    changed = [Path("src/pkg/a.py")]

    # File does NOT exist on disk (deleted)

    # But logic requires src structure to infer module name?
    # Logic:
    # if parts[0] == "src":
    #   rel_parts = parts[1:] ...

    monkeypatch.setattr(
        find_affected_modules, "get_changed_files", lambda *a, **k: changed
    )

    result = find_affected_modules.get_affected_tests()

    # Should identify pkg.a -> pkg.b
    assert "pkg.a" in result["affected_modules"]


def test_get_changed_files_staged(monkeypatch):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(cmd, **kwargs):
        assert "--cached" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="staged.py", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)
    find_affected_modules.get_changed_files(staged=True)


def test_deleted_init_file(mock_paths, monkeypatch, temp_repo_root):
    from py_smart_test import find_affected_modules

    graph: Dict[str, Any] = {"modules": {"pkg": {}}}
    graph_file = mock_paths.GRAPH_FILE
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    graph_file.write_text(json.dumps(graph))

    # src/pkg/__init__.py -> pkg
    changed = [Path("src/pkg/__init__.py")]

    monkeypatch.setattr(
        find_affected_modules, "get_changed_files", lambda *a, **k: changed
    )

    result = find_affected_modules.get_affected_tests()
    assert "pkg" in result["affected_modules"]


def test_main_output(mock_paths, monkeypatch):
    from typer.testing import CliRunner  # type: ignore

    from py_smart_test import find_affected_modules

    runner = CliRunner()

    # Mock get_affected_tests
    monkeypatch.setattr(
        find_affected_modules,
        "get_affected_tests",
        lambda b, s: {"affected_modules": ["mod"], "tests": ["test.py"]},
    )

    result = runner.invoke(find_affected_modules.app)
    assert result.exit_code == 0
    assert "test.py" in result.stdout


# ── Working Tree Changes tests ───────────────────────────────────────────────


def test_get_working_tree_changes_success(monkeypatch):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=" M src/pkg/a.py\n?? tests/test_new.py\n M README.md\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    files = find_affected_modules.get_working_tree_changes()

    # Only .py files returned
    paths = [str(f) for f in files]
    assert "src/pkg/a.py" in paths
    assert "tests/test_new.py" in paths
    assert "README.md" not in paths


def test_get_working_tree_changes_renames(monkeypatch):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="R  old_name.py -> new_name.py\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    files = find_affected_modules.get_working_tree_changes()
    assert len(files) == 1
    assert str(files[0]) == "new_name.py"


def test_get_working_tree_changes_empty(monkeypatch):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)
    files = find_affected_modules.get_working_tree_changes()
    assert files == []


def test_get_working_tree_changes_git_error(monkeypatch):
    import subprocess
    from unittest.mock import MagicMock

    from py_smart_test import find_affected_modules

    def mock_run(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git status")

    monkeypatch.setattr(subprocess, "run", mock_run)

    mock_hash_fallback = MagicMock(return_value=[Path("fallback.py")])
    monkeypatch.setattr(
        "py_smart_test.find_affected_modules.get_changed_files_hash", mock_hash_fallback
    )

    files = find_affected_modules.get_working_tree_changes()
    assert mock_hash_fallback.called
    assert files == [Path("fallback.py")]


def test_get_working_tree_changes_blank_lines(monkeypatch):
    import subprocess

    from py_smart_test import find_affected_modules

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=" M foo.py\n\n   \n M bar.py\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    files = find_affected_modules.get_working_tree_changes()
    assert len(files) == 2


def test_main_cli_json_output(monkeypatch):
    from typer.testing import CliRunner

    from py_smart_test import find_affected_modules

    # Mock get_affected_tests
    monkeypatch.setattr(
        find_affected_modules,
        "get_affected_tests",
        lambda *a: {"affected_modules": ["a"], "tests": ["t"]},
    )
    runner = CliRunner()
    result = runner.invoke(find_affected_modules.app, ["--json"])
    assert result.exit_code == 0
    # Parse JSON to verify
    data = json.loads(result.stdout)
    assert data["affected_modules"] == ["a"]
    assert data["tests"] == ["t"]
