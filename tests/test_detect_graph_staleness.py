from typer.testing import CliRunner  # type: ignore

from py_smart_test import detect_graph_staleness
from py_smart_test.detect_graph_staleness import is_graph_stale

runner = CliRunner()


def test_is_graph_stale_no_graph(mock_paths):
    # If graph file doesn't exist, it should be stale
    assert is_graph_stale() is True
    assert is_graph_stale(verbose=True) is True


def test_is_graph_stale_no_hashes(mock_paths, monkeypatch):
    # Graph exists, but no stored hashes
    mock_paths.GRAPH_FILE.touch()

    # Mock load_hashes to return empty
    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: {})

    assert is_graph_stale() is True


def test_is_graph_stale_fresh(mock_paths, monkeypatch):
    mock_paths.GRAPH_FILE.touch()

    # Hashes match
    hashes = {"file1.py": "abc", "file2.py": "def"}
    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: hashes)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: hashes)

    assert is_graph_stale() is False
    assert is_graph_stale(verbose=True) is False


def test_is_graph_stale_modified(mock_paths, monkeypatch):
    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc"}
    current = {"file1.py": "xyz"}  # Modified

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    assert is_graph_stale() is True


def test_is_graph_stale_new_file(mock_paths, monkeypatch):
    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc"}
    current = {"file1.py": "abc", "file2.py": "def"}  # New file

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    assert is_graph_stale() is True


def test_is_graph_stale_deleted_file(mock_paths, monkeypatch):
    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc", "file2.py": "def"}
    current = {"file1.py": "abc"}  # Deleted file2

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    assert is_graph_stale() is True


def test_is_graph_stale_verbose_no_hashes(mock_paths, monkeypatch):
    """Test verbose logging when no stored hashes found."""
    from unittest.mock import MagicMock

    mock_paths.GRAPH_FILE.touch()
    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: {})

    mock_logger = MagicMock()
    monkeypatch.setattr(detect_graph_staleness, "logger", mock_logger)

    assert is_graph_stale(verbose=True) is True
    mock_logger.info.assert_called_with("No stored hashes found. Graph is stale.")


def test_is_graph_stale_verbose_new_file(mock_paths, monkeypatch):
    """Test verbose logging when new file detected."""
    from unittest.mock import MagicMock

    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc"}
    current = {"file1.py": "abc", "file2.py": "def"}  # New file

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    mock_logger = MagicMock()
    monkeypatch.setattr(detect_graph_staleness, "logger", mock_logger)

    assert is_graph_stale(verbose=True) is True
    mock_logger.info.assert_called_with("New file detected: file2.py")


def test_is_graph_stale_verbose_modified(mock_paths, monkeypatch):
    """Test verbose logging when file modified."""
    from unittest.mock import MagicMock

    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc"}
    current = {"file1.py": "xyz"}  # Modified

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    mock_logger = MagicMock()
    monkeypatch.setattr(detect_graph_staleness, "logger", mock_logger)

    assert is_graph_stale(verbose=True) is True
    mock_logger.info.assert_called_with("File modified: file1.py")


def test_is_graph_stale_verbose_deleted(mock_paths, monkeypatch):
    """Test verbose logging when file deleted."""
    from unittest.mock import MagicMock

    mock_paths.GRAPH_FILE.touch()

    stored = {"file1.py": "abc", "file2.py": "def"}
    current = {"file1.py": "abc"}  # Deleted file2

    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: stored)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: current)

    mock_logger = MagicMock()
    monkeypatch.setattr(detect_graph_staleness, "logger", mock_logger)

    assert is_graph_stale(verbose=True) is True
    mock_logger.info.assert_called_with("File deleted: file2.py")


def test_is_graph_stale_verbose_fresh(mock_paths, monkeypatch):
    """Test verbose logging when graph is up to date."""
    from unittest.mock import MagicMock

    mock_paths.GRAPH_FILE.touch()

    hashes = {"file1.py": "abc", "file2.py": "def"}
    monkeypatch.setattr(detect_graph_staleness, "load_hashes", lambda: hashes)
    monkeypatch.setattr(detect_graph_staleness, "get_current_hashes", lambda: hashes)

    mock_logger = MagicMock()
    monkeypatch.setattr(detect_graph_staleness, "logger", mock_logger)

    assert is_graph_stale(verbose=True) is False
    mock_logger.info.assert_called_with("Graph is up to date.")
    result = runner.invoke(detect_graph_staleness.app)
    assert result.exit_code == 0
