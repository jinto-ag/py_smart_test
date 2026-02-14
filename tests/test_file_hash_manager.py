from pathlib import Path
from unittest.mock import patch

import pytest

from py_smart_test import file_hash_manager
from py_smart_test.file_hash_manager import (
    compute_file_hash,
    get_changed_files_hash,
    get_current_hashes,
    load_hashes,
    save_hashes,
    update_hashes,
)


@pytest.fixture
def mock_paths(tmp_path):
    with patch("py_smart_test.file_hash_manager._paths") as mock_p:
        mock_p.REPO_ROOT = tmp_path
        mock_p.SRC_ROOT = tmp_path / "src"
        mock_p.PY_SMART_TEST_DIR = tmp_path / ".py_smart_test"
        file_hash_manager.HASH_FILE = mock_p.PY_SMART_TEST_DIR / "file_hashes.json"
        yield mock_p


def test_compute_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")

    h = compute_file_hash(f)
    assert h  # Should be non-empty string
    assert len(h) == 32  # MD5 length


def test_load_save_hashes(mock_paths):
    hashes = {"file1.py": "abc", "file2.py": "def"}

    save_hashes(hashes)
    assert file_hash_manager.HASH_FILE.exists()

    loaded = load_hashes()
    assert loaded == hashes


def test_get_current_hashes(mock_paths):
    # Create some files
    (mock_paths.SRC_ROOT).mkdir(parents=True)
    f1 = mock_paths.SRC_ROOT / "a.py"
    f1.write_text("a")

    (mock_paths.REPO_ROOT / "tests").mkdir()
    f2 = mock_paths.REPO_ROOT / "tests" / "test_a.py"
    f2.write_text("b")

    hashes = get_current_hashes()
    assert "src/a.py" in hashes
    assert "tests/test_a.py" in hashes
    assert len(hashes) == 2


def test_get_changed_files_hash_no_baseline(mock_paths, caplog):
    # No hash file exists
    (mock_paths.SRC_ROOT).mkdir(parents=True)
    f1 = mock_paths.SRC_ROOT / "a.py"
    f1.write_text("a")

    changed = get_changed_files_hash()

    # Should detect all files as changed
    assert len(changed) == 1
    assert changed[0].name == "a.py"
    assert "No saved hashes found" in caplog.text


def test_get_changed_files_hash_detection(mock_paths):
    (mock_paths.SRC_ROOT).mkdir(parents=True)

    f1 = mock_paths.SRC_ROOT / "unchanged.py"
    f1.write_text("content")

    f2 = mock_paths.SRC_ROOT / "modified.py"
    f2.write_text("old_content")

    f3 = mock_paths.SRC_ROOT / "deleted.py"
    f3.write_text("content")

    # Save baseline
    update_hashes()

    # Modify
    f2.write_text("new_content")

    # Delete
    f3.unlink()

    # Add new
    f4 = mock_paths.SRC_ROOT / "new.py"
    f4.write_text("content")

    changed = get_changed_files_hash()
    names = sorted([f.name for f in changed])

    assert "unchanged.py" not in names
    assert "new.py" in names


def test_compute_file_hash_error():
    # Simulate read error
    with patch("builtins.open", side_effect=OSError("Read error")):
        h = compute_file_hash(Path("dummy"))
        assert h == ""


def test_load_hashes_error(mock_paths, caplog):
    file_hash_manager.HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_hash_manager.HASH_FILE.write_text("{invalid_json")
    hashes = load_hashes()
    assert hashes == {}
    assert "Failed to load hashes" in caplog.text


def test_save_hashes_error(mock_paths, caplog):
    # Simulate permission error by making parent directory read-only (mocking mkdir)
    with patch.object(Path, "mkdir", side_effect=OSError("Permission denied")):
        save_hashes({})
    assert "Failed to save hashes" in caplog.text


def test_get_current_hashes_value_error(mock_paths, monkeypatch):
    # Mock get_all_py_files to return a path outside REPO_ROOT
    # This should trigger ValueError in relative_to

    outside_file = Path("/tmp/outside.py")
    monkeypatch.setattr(
        "py_smart_test.file_hash_manager.get_all_py_files", lambda: [outside_file]
    )

    # Should not raise exception
    hashes = get_current_hashes()
    assert hashes == {}
