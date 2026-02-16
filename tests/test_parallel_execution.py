"""Tests for parallel execution feature."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from py_smart_test.smart_test_runner import run_pytest


class TestParallelExecution:
    """Tests for parallel execution functionality."""

    def test_run_pytest_with_parallel_flag(self):
        """Test that run_pytest adds -n flag when parallel is True."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = []
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = run_pytest(["test_file.py"], [], parallel=True, workers="4")

            # Verify the command includes -n flag
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "-n" in cmd
            assert "4" in cmd
            assert result is True

    def test_run_pytest_sequential_without_parallel_flag(self):
        """Test that run_pytest runs sequentially without parallel flag."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = []
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = run_pytest(["test_file.py"], [], parallel=False)

            # Verify the command does not include -n flag
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "-n" not in cmd
            assert result is True

    def test_run_pytest_parallel_auto_workers(self):
        """Test that run_pytest uses 'auto' for worker count by default."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = []
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = run_pytest(["test_file.py"], [], parallel=True, workers="auto")

            # Verify the command includes -n auto
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "-n" in cmd
            assert "auto" in cmd
            assert result is True

    def test_run_pytest_parallel_without_xdist(self):
        """Test that run_pytest falls back gracefully when xdist is not installed."""
        with patch("subprocess.Popen") as mock_popen:
            with patch("builtins.__import__", side_effect=ImportError("No module named 'xdist'")):
                mock_process = MagicMock()
                mock_process.stdout = []
                mock_process.wait.return_value = 0
                mock_popen.return_value = mock_process

                # Should still run without error, just without -n flag
                result = run_pytest(["test_file.py"], [], parallel=True, workers="4")

                # Verify the command does not include -n flag (fallback)
                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                assert "-n" not in cmd
                assert result is True

    def test_run_pytest_parallel_with_extra_args(self):
        """Test that run_pytest correctly combines parallel and extra args."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = []
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = run_pytest(
                ["test_file.py"],
                ["-v", "--tb=short"],
                parallel=True,
                workers="2"
            )

            # Verify all args are present
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "-n" in cmd
            assert "2" in cmd
            assert "-v" in cmd
            assert "--tb=short" in cmd
            assert result is True


class TestPytestPluginParallel:
    """Tests for pytest plugin parallel configuration."""

    def test_pytest_addoption_registers_parallel_flags(self):
        """Test that pytest_addoption registers --smart-parallel flags."""
        from py_smart_test.pytest_plugin import pytest_addoption

        mock_parser = MagicMock()
        mock_group = MagicMock()
        mock_parser.getgroup.return_value = mock_group

        pytest_addoption(mock_parser)

        # Check that --smart-parallel options were added
        calls = [str(call) for call in mock_group.addoption.call_args_list]
        assert any("--smart-parallel" in str(call) for call in calls)
        assert any("--smart-parallel-workers" in str(call) for call in calls)

    def test_pytest_configure_with_parallel_enabled(self):
        """Test that pytest_configure sets up xdist when --smart-parallel is used."""
        from py_smart_test.pytest_plugin import pytest_configure

        mock_config = MagicMock()
        mock_config.getoption.side_effect = lambda opt, default=None: {
            "--smart-parallel": True,
            "--smart-parallel-workers": "4",
            "-n": None,
        }.get(opt, default)
        mock_config.option = MagicMock()

        # Should not raise an error
        pytest_configure(mock_config)

        # Verify numprocesses was set
        assert mock_config.option.numprocesses == "4"

    def test_pytest_configure_without_parallel(self):
        """Test that pytest_configure does nothing when --smart-parallel is not used."""
        from py_smart_test.pytest_plugin import pytest_configure

        mock_config = MagicMock()
        mock_config.getoption.return_value = False
        mock_config.option.numprocesses = None

        # Should not raise an error
        pytest_configure(mock_config)

        # Verify numprocesses was not modified
        assert mock_config.option.numprocesses is None
