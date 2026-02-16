"""Tests for utility functions."""

from unittest.mock import patch

from py_smart_test.utils import has_optional_dependency, get_optional_dependency_message


class TestHasOptionalDependency:
    """Tests for has_optional_dependency function."""

    def test_returns_true_for_installed_module(self):
        """Test that function returns True for installed modules."""
        # pytest should be installed since we're running tests
        assert has_optional_dependency("pytest") is True

    def test_returns_false_for_missing_module(self):
        """Test that function returns False for missing modules."""
        assert has_optional_dependency("nonexistent_module_xyz") is False

    def test_handles_import_errors_gracefully(self):
        """Test that function handles import errors without raising."""
        # Should not raise an exception
        result = has_optional_dependency("module.with.broken.imports")
        assert result is False


class TestGetOptionalDependencyMessage:
    """Tests for get_optional_dependency_message function."""

    def test_default_package_name(self):
        """Test message with default package name."""
        msg = get_optional_dependency_message("xdist")
        assert "xdist" in msg
        assert "pip install xdist" in msg

    def test_custom_package_name(self):
        """Test message with custom package name."""
        msg = get_optional_dependency_message("pytest_cov", "pytest-cov")
        assert "pytest_cov" in msg
        assert "pip install pytest-cov" in msg

    def test_replaces_underscores(self):
        """Test that underscores are replaced with hyphens in package names."""
        msg = get_optional_dependency_message("pytest_xdist")
        assert "pip install pytest-xdist" in msg
