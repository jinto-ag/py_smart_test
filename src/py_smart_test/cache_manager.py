"""Centralized cache manager for py_smart_test.

This module provides a unified interface for managing all cached data:
- Dependency graphs
- File hashes
- Test outcomes
- Coverage mappings

Benefits:
- Single load/save operation instead of 20+ scattered I/O operations
- In-memory caching with dirty flag tracking
- Thread-safe for xdist compatibility
- Lazy loading only when needed
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from . import _paths

logger = logging.getLogger(__name__)

# Import remote cache support (optional)
try:
    from .remote_cache import get_remote_cache_backend

    HAS_REMOTE_CACHE = True
except ImportError:
    HAS_REMOTE_CACHE = False
    get_remote_cache_backend = None  # type: ignore


class CacheEntry:
    """Individual cache entry with dirty flag tracking."""

    def __init__(self, file_path: Path, data: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self._data = data
        self._dirty = False
        self._loaded = data is not None

    @property
    def data(self) -> Dict[str, Any]:
        """Get data, loading from disk if needed."""
        if not self._loaded:
            self._load()
        return self._data or {}

    @data.setter
    def data(self, value: Dict[str, Any]) -> None:
        """Set data and mark as dirty."""
        self._data = value
        self._dirty = True
        self._loaded = True

    def _load(self) -> None:
        """Load data from disk."""
        if not self.file_path.exists():
            self._data = {}
            self._loaded = True
            return

        try:
            with open(self.file_path, "rb" if HAS_ORJSON else "r") as f:
                if HAS_ORJSON:
                    self._data = orjson.loads(f.read())
                else:
                    self._data = json.load(f)
            self._loaded = True
            logger.debug(f"Loaded cache from {self.file_path}")
        except Exception as e:
            logger.warning(f"Failed to load cache from {self.file_path}: {e}")
            self._data = {}
            self._loaded = True

    def save(self, force: bool = False) -> None:
        """Save data to disk if dirty or forced."""
        if not self._dirty and not force:
            return

        if self._data is None:
            logger.debug(f"Skipping save for {self.file_path} (no data)")
            return

        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.file_path, "wb" if HAS_ORJSON else "w") as f:
                if HAS_ORJSON:
                    f.write(orjson.dumps(self._data, option=orjson.OPT_INDENT_2))
                else:
                    json.dump(self._data, f, indent=2)

            self._dirty = False
            logger.debug(f"Saved cache to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save cache to {self.file_path}: {e}")

    def invalidate(self) -> None:
        """Mark cache as invalid (will reload on next access)."""
        self._loaded = False
        self._dirty = False
        self._data = None


class CacheManager:
    """Centralized cache manager for all py_smart_test data.

    This is a singleton that manages all cached data in memory and coordinates
    disk I/O operations. Thread-safe for xdist compatibility.

    Usage:
        cache = CacheManager.get_instance()

        # Access cached data
        graph = cache.dependency_graph
        hashes = cache.file_hashes

        # Modify data (automatically marks as dirty)
        cache.file_hashes = new_hashes

        # Save all dirty caches
        cache.save_all()
    """

    _instance: Optional["CacheManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize cache manager. Use get_instance() instead."""
        if CacheManager._instance is not None:
            raise RuntimeError("Use CacheManager.get_instance()")

        self._entry_lock = threading.Lock()

        # Initialize cache entries
        self._dependency_graph = CacheEntry(_paths.get_graph_file())
        self._file_hashes = CacheEntry(_paths.PY_SMART_TEST_DIR / "file_hashes.json")
        self._test_outcomes = CacheEntry(
            _paths.PY_SMART_TEST_DIR / "test_outcomes.json"
        )
        self._coverage_mapping = CacheEntry(
            _paths.PY_SMART_TEST_DIR / "coverage_mapping.json"
        )
        self._test_module_mapping = CacheEntry(
            _paths.PY_SMART_TEST_DIR / "test_module_mapping.json"
        )
        self._ast_parse_cache = CacheEntry(
            _paths.PY_SMART_TEST_DIR / "ast_parse_cache.json"
        )

    @classmethod
    def get_instance(cls) -> "CacheManager":
        """Get or create singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    # Dependency graph
    @property
    def dependency_graph(self) -> Dict[str, Any]:
        """Get dependency graph data."""
        with self._entry_lock:
            return self._dependency_graph.data

    @dependency_graph.setter
    def dependency_graph(self, value: Dict[str, Any]) -> None:
        """Set dependency graph data."""
        with self._entry_lock:
            self._dependency_graph.data = value

    def invalidate_dependency_graph(self) -> None:
        """Invalidate dependency graph cache."""
        with self._entry_lock:
            self._dependency_graph.invalidate()

    # File hashes
    @property
    def file_hashes(self) -> Dict[str, str]:
        """Get file hashes data."""
        with self._entry_lock:
            data = self._file_hashes.data
            return data.get("files", {})

    @file_hashes.setter
    def file_hashes(self, value: Dict[str, str]) -> None:
        """Set file hashes data."""
        with self._entry_lock:
            self._file_hashes.data = {"files": value}

    # Test outcomes
    @property
    def test_outcomes(self) -> Dict[str, Any]:
        """Get test outcomes data."""
        with self._entry_lock:
            data = self._test_outcomes.data
            return data.get("outcomes", {})

    @test_outcomes.setter
    def test_outcomes(self, value: Dict[str, Any]) -> None:
        """Set test outcomes data."""
        with self._entry_lock:
            self._test_outcomes.data = {"outcomes": value}

    # Coverage mapping
    @property
    def coverage_mapping(self) -> Dict[str, Any]:
        """Get coverage mapping data."""
        with self._entry_lock:
            return self._coverage_mapping.data

    @coverage_mapping.setter
    def coverage_mapping(self, value: Dict[str, Any]) -> None:
        """Set coverage mapping data."""
        with self._entry_lock:
            self._coverage_mapping.data = value

    # Test module mapping
    @property
    def test_module_mapping(self) -> Dict[str, Any]:
        """Get test module mapping data."""
        with self._entry_lock:
            return self._test_module_mapping.data

    @test_module_mapping.setter
    def test_module_mapping(self, value: Dict[str, Any]) -> None:
        """Set test module mapping data."""
        with self._entry_lock:
            self._test_module_mapping.data = value

    # AST parse cache
    @property
    def ast_parse_cache(self) -> Dict[str, Any]:
        """Get AST parse cache data.

        Cache structure:
        {
            "src/module.py": {
                "hash": "abc123...",
                "module_name": "myapp.module",
                "imports": ["typing", "pathlib"],
                "timestamp": 1704000000
            }
        }
        """
        with self._entry_lock:
            data = self._ast_parse_cache.data
            return data.get("cache", {})

    @ast_parse_cache.setter
    def ast_parse_cache(self, value: Dict[str, Any]) -> None:
        """Set AST parse cache data."""
        with self._entry_lock:
            self._ast_parse_cache.data = {"cache": value}

    def update_ast_cache(self, file_path: str, data: Dict[str, Any]) -> None:
        """Update a single entry in AST parse cache.

        Args:
            file_path: Relative path to source file
            data: Parse result with hash, module_name, imports
        """
        with self._entry_lock:
            cache = self._ast_parse_cache.data.get("cache", {})
            cache[file_path] = data
            self._ast_parse_cache.data = {"cache": cache}

    def save_all(self, force: bool = False) -> None:
        """Save all dirty caches to disk.

        Args:
            force: Save even if not dirty
        """
        with self._entry_lock:
            logger.debug("Saving all caches...")
            self._dependency_graph.save(force)
            self._file_hashes.save(force)
            self._test_outcomes.save(force)
            self._coverage_mapping.save(force)
            self._test_module_mapping.save(force)
            self._ast_parse_cache.save(force)
            logger.debug("All caches saved")

            # Sync to remote cache if configured
            self._sync_to_remote()

    def _sync_to_remote(self) -> None:
        """Sync AST cache to remote backend if configured."""
        if not HAS_REMOTE_CACHE:
            return

        backend = get_remote_cache_backend()
        if not backend:
            return

        try:
            # Only sync AST cache to remote (most valuable for sharing)
            cache_data = self.ast_parse_cache
            if cache_data:
                backend.set("ast_parse_cache", cache_data)
                logger.debug("Synced AST cache to remote backend")
        except Exception as e:
            logger.warning(f"Failed to sync to remote cache: {e}")

    def _sync_from_remote(self) -> None:
        """Load AST cache from remote backend if available."""
        if not HAS_REMOTE_CACHE:
            return

        backend = get_remote_cache_backend()
        if not backend:
            return

        try:
            remote_data = backend.get("ast_parse_cache")
            if remote_data:
                # Merge with local cache (local takes precedence)
                local_cache = self.ast_parse_cache
                for key, value in remote_data.items():
                    if key not in local_cache:
                        local_cache[key] = value

                self.ast_parse_cache = local_cache
                logger.info(f"Loaded {len(remote_data)} entries from remote cache")
        except Exception as e:
            logger.warning(f"Failed to load from remote cache: {e}")

    def invalidate_all(self) -> None:
        """Invalidate all caches (force reload on next access)."""
        with self._entry_lock:
            logger.debug("Invalidating all caches...")
            self._dependency_graph.invalidate()
            self._file_hashes.invalidate()
            self._test_outcomes.invalidate()
            self._coverage_mapping.invalidate()
            self._test_module_mapping.invalidate()
            self._ast_parse_cache.invalidate()


# Convenience function for getting cache instance
def get_cache() -> CacheManager:
    """Get the global cache manager instance."""
    return CacheManager.get_instance()
