"""Utility functions for py_smart_test."""

import cProfile
import functools
import logging
import pstats
import time
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def has_optional_dependency(module_name: str) -> bool:
    """Check if an optional dependency is available.

    Args:
        module_name: Name of the module to check (e.g., 'xdist', 'pytest_cov')

    Returns:
        True if the module can be imported, False otherwise
    """
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def get_optional_dependency_message(
    module_name: str, install_package: Optional[str] = None
) -> str:
    """Get a user-friendly message about a missing optional dependency.

    Args:
        module_name: Name of the module that's missing
        install_package: Package name for installation (defaults to module_name)

    Returns:
        Formatted message string
    """
    package = install_package or module_name.replace("_", "-")
    return f"{module_name} not found. Install with: uv add {package}"


def timed(func: F) -> F:
    """Decorator to measure and log function execution time.

    Usage:
        @timed
        def my_function():
            ...

    Args:
        func: Function to measure

    Returns:
        Wrapped function that logs execution time
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed = end_time - start_time

        logger.debug(f"{func.__module__}.{func.__name__} took {elapsed:.3f}s")

        return result

    return wrapper  # type: ignore


def profile_to_file(output_path: Path) -> Callable[[F], F]:
    """Decorator to profile a function and save results to file.

    Usage:
        @profile_to_file(Path("profile.stats"))
        def my_function():
            ...

    Args:
        output_path: Path to save profiling stats

    Returns:
        Decorator function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                result = func(*args, **kwargs)
            finally:
                profiler.disable()

                # Save stats to file
                profiler.dump_stats(str(output_path))

                # Also log top 10 functions
                stream = StringIO()
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats("cumulative")
                stats.print_stats(10)

                logger.info(
                    f"Profile for {func.__name__} saved to {output_path}\n"
                    f"Top 10 functions:\n{stream.getvalue()}"
                )

            return result

        return wrapper  # type: ignore

    return decorator


def measure_memory() -> dict[str, Any]:
    """Measure current memory usage.

    Returns:
        Dictionary with memory statistics (in MB)
    """
    import tracemalloc

    if not tracemalloc.is_tracing():
        return {"error": "tracemalloc not enabled"}

    current, peak = tracemalloc.get_traced_memory()

    return {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024,
    }


class PerformanceTimer:
    """Context manager for timing code blocks.

    Usage:
        with PerformanceTimer("my operation") as timer:
            # ... do work ...
            pass
        print(f"Took {timer.elapsed}s")
    """

    def __init__(self, name: str, log_on_exit: bool = True):
        self.name = name
        self.log_on_exit = log_on_exit
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "PerformanceTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time

        if self.log_on_exit:
            logger.info(f"{self.name} took {self.elapsed:.3f}s")
