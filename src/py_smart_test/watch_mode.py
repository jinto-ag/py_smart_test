"""Watch mode for automatic test execution on file changes.

This module provides file watching capabilities that automatically re-run
affected tests when source files change, enabling a continuous testing workflow.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional, Set

from . import _paths

logger = logging.getLogger(__name__)

# Optional dependency - gracefully handle if not installed
try:
    from watchdog.events import (  # type: ignore[import-untyped]
        FileSystemEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer  # type: ignore[import-untyped]

    HAS_WATCHDOG = True
    _ObserverType = Observer
except ImportError:
    HAS_WATCHDOG = False
    # Fallback types for when watchdog is not installed
    FileSystemEventHandler = object  # type: ignore[misc,assignment]
    FileSystemEvent = None  # type: ignore[misc,assignment]
    Observer = None  # type: ignore[misc,assignment]
    _ObserverType = Any  # type: ignore[misc,assignment]


class SourceFileWatcher(FileSystemEventHandler):
    """Watch for changes to Python source files."""

    def __init__(
        self,
        on_change: Callable[[Set[Path]], None],
        debounce_seconds: float = 0.5,
    ):
        """Initialize the file watcher.

        Args:
            on_change: Callback function called with set of changed files
            debounce_seconds: Wait time to collect multiple changes
        """
        super().__init__()
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._pending_changes: Set[Path] = set()
        self._last_event_time = 0.0

    def on_modified(self, event: Any) -> None:  # FileSystemEvent when available
        """Handle file modification events."""
        if event.is_directory:
            return

        path = Path(event.src_path)

        # Only watch Python files
        if path.suffix != ".py":
            return

        # Ignore __pycache__ and generated files
        if "__pycache__" in path.parts or path.name.startswith("."):
            return

        logger.debug(f"File modified: {path}")
        self._pending_changes.add(path)
        self._last_event_time = time.time()

    def on_created(self, event: Any) -> None:  # FileSystemEvent when available
        """Handle file creation events."""
        self.on_modified(event)

    def flush_pending_changes(self) -> None:
        """Process accumulated changes if debounce period has elapsed."""
        if not self._pending_changes:
            return

        # Check if enough time has passed since last event
        time_since_last = time.time() - self._last_event_time
        if time_since_last < self.debounce_seconds:
            return

        # Process the changes
        changes = self._pending_changes.copy()
        self._pending_changes.clear()

        # Convert to relative paths
        relative_changes = set()
        for path in changes:
            try:
                rel_path = path.relative_to(_paths.REPO_ROOT)
                relative_changes.add(rel_path)
            except ValueError:
                # File outside repo root, ignore
                continue

        if relative_changes:
            logger.info(f"Processing {len(relative_changes)} changed file(s)")
            self.on_change(relative_changes)


def start_watch_mode(
    on_change: Callable[[Set[Path]], None],
    debounce_seconds: float = 0.5,
) -> Any:  # Returns Observer when watchdog is available, None otherwise
    """Start watching for file changes.

    Args:
        on_change: Callback function called with set of changed files
        debounce_seconds: Wait time to collect multiple changes

    Returns:
        Observer instance if watchdog is available, None otherwise
    """
    if not HAS_WATCHDOG or Observer is None:
        logger.error(
            "Watch mode requires 'watchdog' package. "
            "Install with: pip install watchdog"
        )
        return None

    # Create event handler
    handler = SourceFileWatcher(on_change, debounce_seconds)

    # Create observer
    observer = Observer()

    # Watch source directory
    if _paths.SRC_ROOT.exists():
        observer.schedule(handler, str(_paths.SRC_ROOT), recursive=True)
        logger.info(f"Watching: {_paths.SRC_ROOT}")

    # Watch tests directory
    tests_root = _paths.REPO_ROOT / "tests"
    if tests_root.exists():
        observer.schedule(handler, str(tests_root), recursive=True)
        logger.info(f"Watching: {tests_root}")

    # Start observer and debounce check loop
    try:
        observer.start()
        logger.info("Watch mode started. Press Ctrl+C to stop.")

        # Start debounce check loop
        while True:
            time.sleep(0.1)
            handler.flush_pending_changes()
    except KeyboardInterrupt:
        logger.info("Stopping watch mode...")
        observer.stop()
        observer.join()
        return None
    finally:
        # Ensure cleanup even if exception other than KeyboardInterrupt
        if observer.is_alive():
            observer.stop()
            observer.join()

    return observer


def watch_and_test(
    test_command: Optional[list[str]] = None,
    debounce_seconds: float = 0.5,
) -> None:
    """Watch for changes and run tests automatically.

    Args:
        test_command: Command to run tests (default: pytest with smart flags)
        debounce_seconds: Wait time to collect multiple changes
    """
    if test_command is None:
        test_command = ["pytest", "--smart", "--smart-working-tree", "-x"]

    def run_tests(changed_files: Set[Path]) -> None:
        """Run tests for changed files."""
        print("\n" + "=" * 70)
        print(f"🔄 Changes detected in {len(changed_files)} file(s)")
        for path in sorted(changed_files):
            print(f"   - {path}")
        print("=" * 70 + "\n")

        try:
            result = subprocess.run(
                test_command,
                cwd=_paths.REPO_ROOT,
                capture_output=False,
            )
            if result.returncode == 0:
                print("\n✅ All tests passed!\n")
            else:
                print(f"\n❌ Tests failed with exit code {result.returncode}\n")
        except Exception as e:
            logger.error(f"Failed to run tests: {e}")

        print("Waiting for changes...\n")

    # Initial test run
    print("Running initial test suite...\n")
    run_tests(set())

    # Start watching
    start_watch_mode(run_tests, debounce_seconds)


def get_optional_dependency_message() -> str:
    """Get message about missing watchdog dependency."""
    return (
        "Watch mode requires the 'watchdog' package.\n"
        "Install with: pip install watchdog\n"
        "Or install py-smart-test with watch support: "
        "pip install 'py-smart-test[watch]'"
    )
