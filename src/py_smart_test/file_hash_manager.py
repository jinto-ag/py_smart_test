import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List

from . import _paths

logger = logging.getLogger(__name__)

HASH_FILE = _paths.PY_SMART_TEST_DIR / "file_hashes.json"


def compute_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    try:
        # Use MD5 for speed, security is not a concern here
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to hash file {file_path}: {e}")
        return ""


def get_all_py_files() -> List[Path]:
    """Scan src/ and tests/ for .py files."""
    files: List[Path] = []

    # Scan src
    if _paths.SRC_ROOT.exists():
        files.extend(_paths.SRC_ROOT.rglob("*.py"))

    # Scan tests
    tests_root = _paths.REPO_ROOT / "tests"
    if tests_root.exists():
        files.extend(tests_root.rglob("*.py"))

    return files


def load_hashes() -> Dict[str, str]:
    """Load saved hashes from disk."""
    if not HASH_FILE.exists():
        return {}
    try:
        with open(HASH_FILE, "r") as f:
            data = json.load(f)
            return data.get("files", {})
    except Exception as e:
        logger.warning(f"Failed to load hashes from {HASH_FILE}: {e}")
        return {}


def save_hashes(hashes: Dict[str, str]):
    """Save hashes to disk."""
    try:
        HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HASH_FILE, "w") as f:
            json.dump({"files": hashes}, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save hashes to {HASH_FILE}: {e}")


def get_current_hashes() -> Dict[str, str]:
    """Compute hashes for all current .py files."""
    current_hashes = {}
    for file_path in get_all_py_files():
        try:
            rel_path = file_path.relative_to(_paths.REPO_ROOT).as_posix()
            file_hash = compute_file_hash(file_path)
            if file_hash:
                current_hashes[rel_path] = file_hash
        except ValueError:
            # Should not happen if paths are correct
            continue
    return current_hashes


def get_changed_files_hash() -> List[Path]:
    """
    Detect changed files by comparing current state with saved hashes.
    Returns list of paths relative to REPO_ROOT.
    """
    logger.info("Using hash-based change detection...")

    old_hashes = load_hashes()
    if not old_hashes:
        logger.warning("No saved hashes found. Assuming all files are new/changed.")
        # If no baseline, everything is "changed"
        return [f.relative_to(_paths.REPO_ROOT) for f in get_all_py_files()]

    new_hashes = get_current_hashes()

    changed = []

    # Check for modified or new files
    for path, new_hash in new_hashes.items():
        if path not in old_hashes:
            logger.debug(f"File added: {path}")
            changed.append(Path(path))
        elif old_hashes[path] != new_hash:
            logger.debug(f"File modified: {path}")
            changed.append(Path(path))

    # Check for deleted files (in old but not in new)
    for path in old_hashes:
        if path not in new_hashes:
            logger.debug(f"File deleted: {path}")
            changed.append(Path(path))

    return changed


def update_hashes():
    """Scan and save current hashes."""
    logger.info("Updating file hash snapshot...")
    hashes = get_current_hashes()
    save_hashes(hashes)
