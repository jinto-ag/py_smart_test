"""E2E test fixtures for py-smart-test.

Provides a ``sample_project`` fixture that creates a fully initialized
Git repository with source modules, tests, and py-smart-test installed
as an editable dependency.  Tests in this package are marked ``e2e``
and excluded from normal ``pytest`` runs.
"""
