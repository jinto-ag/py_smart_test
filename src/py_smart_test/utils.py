"""Utility functions for py_smart_test."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


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


def get_optional_dependency_message(module_name: str, install_package: Optional[str] = None) -> str:
    """Get a user-friendly message about a missing optional dependency.
    
    Args:
        module_name: Name of the module that's missing
        install_package: Package name for installation (defaults to module_name)
    
    Returns:
        Formatted message string
    """
    package = install_package or module_name.replace('_', '-')
    return f"{module_name} not found. Install with: uv add {package}"
