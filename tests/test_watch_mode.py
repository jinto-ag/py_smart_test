"""Tests for watch mode functionality."""

import time
from unittest.mock import Mock, patch

import pytest

from py_smart_test.watch_mode import (
    HAS_WATCHDOG,
    SourceFileWatcher,
    get_optional_dependency_message,
    start_watch_mode,
    watch_and_test,
)


class TestSourceFileWatcher:
    """Tests for SourceFileWatcher class."""

    def test_init(self):
        """Test initialization of watcher."""
        callback = Mock()
        watcher = SourceFileWatcher(callback, debounce_seconds=1.0)

        assert watcher.on_change is callback
        assert watcher.debounce_seconds == 1.0
        assert len(watcher._pending_changes) == 0

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_on_modified_python_file(self, tmp_path):
        """Test handling of Python file modifications."""
        callback = Mock()
        watcher = SourceFileWatcher(callback, debounce_seconds=0.1)

        # Create a mock event for a Python file
        test_file = tmp_path / "test.py"
        test_file.touch()

        event = Mock()
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_modified(event)

        assert test_file in watcher._pending_changes

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_on_modified_ignores_non_python(self, tmp_path):
        """Test that non-Python files are ignored."""
        callback = Mock()
        watcher = SourceFileWatcher(callback)

        test_file = tmp_path / "test.txt"
        test_file.touch()

        event = Mock()
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_modified(event)

        assert len(watcher._pending_changes) == 0

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_on_modified_ignores_directory(self, tmp_path):
        """Test that directories are ignored."""
        callback = Mock()
        watcher = SourceFileWatcher(callback)

        event = Mock()
        event.is_directory = True
        event.src_path = str(tmp_path)

        watcher.on_modified(event)

        assert len(watcher._pending_changes) == 0

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_on_modified_ignores_pycache(self, tmp_path):
        """Test that __pycache__ files are ignored."""
        callback = Mock()
        watcher = SourceFileWatcher(callback)

        pycache_file = tmp_path / "__pycache__" / "test.pyc"
        pycache_file.parent.mkdir()
        pycache_file.touch()

        event = Mock()
        event.is_directory = False
        event.src_path = str(pycache_file)

        watcher.on_modified(event)

        assert len(watcher._pending_changes) == 0

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_flush_pending_changes(self, tmp_path):
        """Test flushing pending changes after debounce period."""
        callback = Mock()
        watcher = SourceFileWatcher(callback, debounce_seconds=0.1)

        test_file = tmp_path / "test.py"
        test_file.touch()

        event = Mock()
        event.is_directory = False
        event.src_path = str(test_file)

        # Mock REPO_ROOT to be tmp_path so relative_to works
        with patch("py_smart_test.watch_mode._paths.REPO_ROOT", tmp_path):
            watcher.on_modified(event)

            # Should not flush immediately
            watcher.flush_pending_changes()
            callback.assert_not_called()

            # Wait for debounce period
            time.sleep(0.15)

            # Should flush now
            watcher.flush_pending_changes()
            callback.assert_called_once()
            assert len(watcher._pending_changes) == 0

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    def test_on_created_calls_on_modified(self):
        """Test that on_created delegates to on_modified."""
        callback = Mock()
        watcher = SourceFileWatcher(callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/tmp/test.py"

        with patch.object(watcher, "on_modified") as mock_modified:
            watcher.on_created(event)
            mock_modified.assert_called_once_with(event)


class TestStartWatchMode:
    """Tests for start_watch_mode function."""

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    @patch("py_smart_test.watch_mode.Observer")
    def test_start_watch_mode_creates_observer(self, mock_observer_class, tmp_path):
        """Test that start_watch_mode creates and starts observer."""
        callback = Mock()
        mock_observer = Mock()
        # Ensure join() and stop() don't block
        mock_observer.join = Mock()
        mock_observer.stop = Mock()
        mock_observer.is_alive = Mock(return_value=False)
        mock_observer_class.return_value = mock_observer

        # Mock KeyboardInterrupt to exit loop immediately after start
        mock_observer.start.side_effect = KeyboardInterrupt

        with patch("py_smart_test.watch_mode._paths.SRC_ROOT", tmp_path / "src"):
            with patch("py_smart_test.watch_mode._paths.REPO_ROOT", tmp_path):
                (tmp_path / "src").mkdir()
                (tmp_path / "tests").mkdir()

                _ = start_watch_mode(callback, debounce_seconds=0.5)

                # Should have attempted to create observer
                mock_observer_class.assert_called_once()
                mock_observer.start.assert_called_once()
                # Should have cleaned up on interrupt
                mock_observer.stop.assert_called_once()
                mock_observer.join.assert_called_once()

    @pytest.mark.skipif(HAS_WATCHDOG, reason="Test expects watchdog NOT installed")
    def test_start_watch_mode_without_watchdog(self):
        """Test graceful handling when watchdog is not installed."""
        callback = Mock()
        result = start_watch_mode(callback)

        assert result is None


class TestWatchAndTest:
    """Tests for watch_and_test function."""

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    @patch("py_smart_test.watch_mode.start_watch_mode")
    @patch("py_smart_test.watch_mode.subprocess.run")
    def test_watch_and_test_runs_initial_tests(self, mock_run, mock_start, tmp_path):
        """Test that watch_and_test runs tests initially."""
        mock_run.return_value = Mock(returncode=0)
        # Mock start_watch_mode to raise KeyboardInterrupt immediately
        mock_start.side_effect = KeyboardInterrupt

        with patch("py_smart_test.watch_mode._paths.REPO_ROOT", tmp_path):
            with pytest.raises(KeyboardInterrupt):
                watch_and_test(test_command=["pytest", "--version"])

            # Should have run tests at least once before interrupt
            assert mock_run.call_count >= 1

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    @patch("py_smart_test.watch_mode.subprocess.run")
    def test_watch_and_test_with_custom_command(self, mock_run, tmp_path):
        """Test watch_and_test with custom test command."""
        mock_run.return_value = Mock(returncode=0)

        with patch("py_smart_test.watch_mode._paths.REPO_ROOT", tmp_path):
            with patch("py_smart_test.watch_mode.start_watch_mode") as mock_start:
                mock_start.side_effect = KeyboardInterrupt

                with pytest.raises(KeyboardInterrupt):
                    watch_and_test(test_command=["echo", "test"])

                # Should use custom command
                mock_run.assert_called()
                assert mock_run.call_args[0][0] == ["echo", "test"]

    @pytest.mark.skipif(not HAS_WATCHDOG, reason="watchdog not installed")
    @patch("py_smart_test.watch_mode.subprocess.run")
    def test_watch_and_test_handles_test_failure(self, mock_run, tmp_path):
        """Test handling of test failures."""
        mock_run.return_value = Mock(returncode=1)

        with patch("py_smart_test.watch_mode._paths.REPO_ROOT", tmp_path):
            with patch("py_smart_test.watch_mode.start_watch_mode") as mock_start:
                mock_start.side_effect = KeyboardInterrupt

                with pytest.raises(KeyboardInterrupt):
                    watch_and_test()

                # Should still run despite failure
                mock_run.assert_called()


class TestOptionalDependency:
    """Tests for optional dependency handling."""

    def test_get_optional_dependency_message(self):
        """Test getting dependency message."""
        message = get_optional_dependency_message()

        assert "watchdog" in message.lower()
        assert "pip install" in message.lower()
