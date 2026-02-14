"""Tests for the smart_test_runner CLI.

Tests are split into:
- **Fast-path tests**: verify ``pst`` (default) delegates to ``pytest --smart``
- **Orchestration-path tests**: verify ``--mode all``, ``--json``, ``--dry-run``,
  ``--regenerate-graph`` and the fallback logic.
"""

from unittest.mock import MagicMock

from typer.testing import CliRunner  # type: ignore

from py_smart_test import smart_test_runner

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════
# Fast-path tests (pst defaults → pytest --smart)
# ═══════════════════════════════════════════════════════════════════


def test_fast_path_default(monkeypatch):
    """Running pst with no args should call ``pytest --smart -m 'not e2e'``."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(smart_test_runner.subprocess, "run", mock_run)

    result = runner.invoke(smart_test_runner.app, [])
    assert result.exit_code == 0

    args = mock_run.call_args[0][0]
    assert args[0] == "pytest"
    assert "--smart" in args
    assert "-m" in args


def test_fast_path_with_since(monkeypatch):
    """``pst --since develop`` should pass ``--smart-since develop``."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(smart_test_runner.subprocess, "run", mock_run)

    result = runner.invoke(smart_test_runner.app, ["--since", "develop"])
    assert result.exit_code == 0

    args = mock_run.call_args[0][0]
    assert "--smart-since" in args
    assert "develop" in args


def test_fast_path_with_staged(monkeypatch):
    """``pst --staged`` should pass ``--smart-staged``."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(smart_test_runner.subprocess, "run", mock_run)

    result = runner.invoke(smart_test_runner.app, ["--staged"])
    assert result.exit_code == 0

    args = mock_run.call_args[0][0]
    assert "--smart-staged" in args


def test_fast_path_no_exclude_e2e(monkeypatch):
    """``pst --no-exclude-e2e`` should omit the ``-m`` flag."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(smart_test_runner.subprocess, "run", mock_run)

    result = runner.invoke(smart_test_runner.app, ["--no-exclude-e2e"])
    assert result.exit_code == 0

    args = mock_run.call_args[0][0]
    assert "-m" not in args


def test_fast_path_failure_propagates(monkeypatch):
    """Non-zero exit from pytest should bubble up."""
    mock_run = MagicMock(return_value=MagicMock(returncode=1))
    monkeypatch.setattr(smart_test_runner.subprocess, "run", mock_run)

    result = runner.invoke(smart_test_runner.app, [])
    assert result.exit_code == 1


# ═══════════════════════════════════════════════════════════════════
# Orchestration-path tests (--mode all, --json, --dry-run, --regenerate-graph)
# ═══════════════════════════════════════════════════════════════════


def test_smart_runner_all(monkeypatch):
    """``pst --mode all`` should use the orchestration path."""
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 0

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[0] == "pytest"
    assert "tests/" in cmd
    assert "-m" in cmd
    assert "not e2e" in cmd


def test_smart_runner_json_output(monkeypatch):
    """``pst --json`` should output JSON and exit without running pytest."""
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda *a: {"tests": ["t.py"]}
    )

    result = runner.invoke(smart_test_runner.app, ["--json"])
    assert result.exit_code == 0
    assert "t.py" in result.stdout


def test_smart_runner_dry_run(monkeypatch):
    result = runner.invoke(smart_test_runner.app, ["--mode", "all", "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.stdout


def test_smart_runner_graph_regen(monkeypatch):
    """``pst --regenerate-graph`` should trigger the orchestration path."""
    # --regenerate-graph forces full orchestration path
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    mock_gen = MagicMock()
    mock_map = MagicMock()
    monkeypatch.setattr(smart_test_runner, "generate_graph_main", mock_gen)
    monkeypatch.setattr(smart_test_runner, "mapper_main", mock_map)
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda s, st: {"tests": []}
    )

    result = runner.invoke(
        smart_test_runner.app, ["--regenerate-graph", "--mode", "affected"]
    )
    assert result.exit_code == 0

    mock_gen.assert_called_once()
    mock_map.assert_called_once()


def test_regenerate_graph_failure(monkeypatch, caplog):
    """Graph generation failure should fall back gracefully."""
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: True)
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    def mock_gen():
        raise Exception("Gen failed")

    monkeypatch.setattr(smart_test_runner, "generate_graph_main", mock_gen)
    monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: None)
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda *a: {"tests": []}
    )

    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    # Use --regenerate-graph to force orchestration path
    result = runner.invoke(
        smart_test_runner.app, ["--regenerate-graph", "--mode", "affected"]
    )
    assert result.exit_code == 0


def test_smart_runner_no_tests(monkeypatch):
    """No affected tests found should exit cleanly."""
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda s, st: {"tests": []}
    )

    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    # Use --json to force orchestration path
    result = runner.invoke(smart_test_runner.app, ["--json"])
    assert result.exit_code == 0


def test_smart_runner_subprocess_error(monkeypatch):
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 1
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 1


def test_smart_runner_updates_hashes_on_success(monkeypatch):
    """Full run (mode=all) should update hashes on success."""
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    mock_update = MagicMock()
    monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 0
    mock_update.assert_called_once()


def test_smart_runner_does_not_update_hashes_on_failure(monkeypatch):
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 1
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    mock_update = MagicMock()
    monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 1
    assert not mock_update.called


# ═══════════════════════════════════════════════════════════════════
# Unit tests for run_pytest helper
# ═══════════════════════════════════════════════════════════════════


def test_run_pytest_empty(monkeypatch):
    """run_pytest with no tests should do nothing."""
    from unittest.mock import patch

    with (
        patch.object(smart_test_runner, "logger") as mock_logger,
        patch("py_smart_test.smart_test_runner.subprocess") as mock_sub,
    ):
        smart_test_runner.run_pytest([], [])
        mock_logger.info.assert_called_with("No tests provided. Running nothing.")
        mock_sub.Popen.assert_not_called()


def test_run_pytest_stdout_processing(monkeypatch):
    """run_pytest should process and print stdout lines."""
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.__iter__ = MagicMock(return_value=iter(["line 1\n", "line 2\n"]))
    mock_process.stdout = mock_stdout
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    smart_test_runner.run_pytest(["tests/"], [])
    mock_popen.assert_called_once()


def test_affected_mode_fallback_on_error(monkeypatch):
    """Test fallback to running all tests when get_affected_tests fails."""
    # Mock logger to verify calls
    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    # Mock get_affected_tests to raise Exception
    monkeypatch.setattr(
        smart_test_runner,
        "get_affected_tests",
        MagicMock(side_effect=Exception("Git error")),
    )
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)
    # Mock HASH_FILE.exists to skip first run logic
    monkeypatch.setattr(
        smart_test_runner,
        "HASH_FILE",
        MagicMock(exists=MagicMock(return_value=True)),
    )

    # Mock run_pytest to avoid actual execution
    monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: True)

    # Use dry-run to trigger orchestration path but avoid actual execution
    # Passing --dry-run avoids fast path.

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected", "--dry-run"])

    assert result.exit_code == 0
    # Check that we fell back to ALL tests by verifying logger calls
    # Note: call_args[0][0] is the first positional arg (message)
    error_calls = [str(call) for call in mock_logger.error.mock_calls]
    warning_calls = [str(call) for call in mock_logger.warning.mock_calls]

    assert any("Error determining affected tests" in c for c in error_calls)
    assert any("Falling back to ALL tests" in c for c in warning_calls)
    # Check result.stdout contains "tests/" (from dry run output or fallback list)
    # The default tests_to_run is ["tests/"] in fallback
    # And run_pytest is mocked, but wait:
    # Code says:
    # if dry_run:
    #    print("Dry run. Would execute:")
    #    print(f"pytest ... {' '.join(tests_to_run)}")
    #    raise typer.Exit(0)
    # So it prints to stdout.
    assert "tests/" in result.stdout
