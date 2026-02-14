from unittest.mock import MagicMock

from typer.testing import CliRunner  # type: ignore

from py_smart_test import smart_test_runner

runner = CliRunner()


def test_smart_runner_all(monkeypatch):
    # Mock subprocess.Popen
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    # Mock is_graph_stale to False
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 0

    # Verify pytest called with tests/ and not e2e
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[0] == "pytest"
    assert "tests/" in cmd
    assert "-m" in cmd
    assert "not e2e" in cmd


def test_smart_runner_affected(monkeypatch):
    # Mock subprocess.Popen
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    # Mock get_affected_tests
    def mock_get_affected(since, staged):
        return {"tests": ["tests/test_foo.py"]}

    monkeypatch.setattr(smart_test_runner, "get_affected_tests", mock_get_affected)

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert "tests/test_foo.py" in cmd


def test_smart_runner_affected_fallback(monkeypatch):
    # Mock subprocess.Popen
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    # Mock get_affected_tests to raise exception
    def mock_get_affected_fail(since, staged):
        raise Exception("Git error")

    monkeypatch.setattr(smart_test_runner, "get_affected_tests", mock_get_affected_fail)

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0

    # Should fall back to tests/
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert "tests/" in cmd


def test_smart_runner_graph_regen(monkeypatch):
    # Mock subprocess.Popen (run_pytest uses Popen, not run)
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: True)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    # Mock generate and mapper
    mock_gen = MagicMock()
    mock_map = MagicMock()
    monkeypatch.setattr(smart_test_runner, "generate_graph_main", mock_gen)
    monkeypatch.setattr(smart_test_runner, "mapper_main", mock_map)

    # Mock get_affected
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda s, st: {"tests": []}
    )

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0

    # Verify regen called
    mock_gen.assert_called_once()
    mock_map.assert_called_once()


def test_smart_runner_no_tests(monkeypatch):
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    # Mock get_affected returning empty
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda s, st: {"tests": []}
    )

    # Mock logger
    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0

    # Verify logger called
    # logger.info("No affected tests found...")
    assert any(
        "No affected tests found" in str(c) for c in mock_logger.info.call_args_list
    )


def test_smart_runner_subprocess_error(monkeypatch):
    # Mock subprocess.Popen to raise CalledProcessError
    mock_popen = MagicMock()
    mock_process = MagicMock()
    mock_process.stdout = None
    mock_process.wait.return_value = 1  # Non-zero exit code
    mock_popen.return_value = mock_process
    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    # Mock is_graph_stale to prevent actual graph operations
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    result = runner.invoke(smart_test_runner.app, ["--mode", "all"])
    assert result.exit_code == 1


def test_smart_runner_dry_run(monkeypatch):
    result = runner.invoke(smart_test_runner.app, ["--mode", "all", "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.stdout


def test_smart_runner_updates_hashes_on_success(monkeypatch):
    from py_smart_test import smart_test_runner

    # Mock everything to simulate success
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda *a: {"tests": ["t.py"]}
    )
    monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: None)

    # Mock update_hashes
    mock_update = MagicMock()
    monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0

    assert mock_update.called


def test_smart_runner_does_not_update_hashes_on_failure(monkeypatch):
    import subprocess

    from py_smart_test import smart_test_runner

    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: False)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda *a: {"tests": ["t.py"]}
    )

    def mock_run(*a):
        raise subprocess.CalledProcessError(1, "pytest")

    monkeypatch.setattr(smart_test_runner, "run_pytest", mock_run)

    mock_update = MagicMock()
    monkeypatch.setattr(smart_test_runner, "update_hashes", mock_update)

    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 1

    assert not mock_update.called


def test_run_pytest_empty(caplog):
    from unittest.mock import patch

    from py_smart_test import smart_test_runner

    # Mock logger
    with (
        patch.object(smart_test_runner, "logger") as mock_logger,
        patch("py_smart_test.smart_test_runner.subprocess") as mock_sub,
    ):
        smart_test_runner.run_pytest([], [])
        # Should log info
        mock_logger.info.assert_called_with("No tests provided. Running nothing.")
        mock_sub.Popen.assert_not_called()


def test_regenerate_graph_failure(monkeypatch, caplog):
    from unittest.mock import MagicMock

    from py_smart_test import smart_test_runner

    # Mock graph stale
    monkeypatch.setattr(smart_test_runner, "is_graph_stale", lambda: True)

    # Mock HASH_FILE.exists() to True so first-run path is not triggered
    monkeypatch.setattr(
        smart_test_runner, "HASH_FILE", MagicMock(exists=MagicMock(return_value=True))
    )

    # Mock generation failure
    def mock_gen():
        raise Exception("Gen failed")

    monkeypatch.setattr(smart_test_runner, "generate_graph_main", mock_gen)

    # Mock run_pytest to avoid actual execution
    monkeypatch.setattr(smart_test_runner, "run_pytest", lambda *a: None)
    # Mock get_affected_tests to avoid actual execution
    monkeypatch.setattr(
        smart_test_runner, "get_affected_tests", lambda *a: {"tests": []}
    )

    # Mock logger to capture error calls
    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    # Run in affected mode
    result = runner.invoke(smart_test_runner.app, ["--mode", "affected"])
    assert result.exit_code == 0  # Should succeed after fallback


def test_run_pytest_stdout_processing(monkeypatch):
    """Test that run_pytest processes stdout correctly."""
    from unittest.mock import MagicMock

    # Mock subprocess.Popen
    mock_popen = MagicMock()
    mock_process = MagicMock()

    # Create a mock stdout that yields lines
    mock_stdout = MagicMock()
    mock_stdout.__iter__ = MagicMock(return_value=iter(["line 1\n", "line 2\n"]))
    mock_process.stdout = mock_stdout
    mock_process.wait.return_value = 0
    mock_popen.return_value = mock_process

    monkeypatch.setattr(smart_test_runner.subprocess, "Popen", mock_popen)

    # Mock logger
    mock_logger = MagicMock()
    monkeypatch.setattr(smart_test_runner, "logger", mock_logger)

    # Call run_pytest
    smart_test_runner.run_pytest(["tests/"], [])

    # Verify Popen was called
    mock_popen.assert_called_once()
