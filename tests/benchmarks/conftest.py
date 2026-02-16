"""Benchmark fixtures and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def benchmark_project_small(tmp_path: Path) -> Path:
    """Create a small synthetic project (50-200 files) for benchmarking.

    Structure:
    - 50 source files in src/
    - 50 test files in tests/
    - Simple import dependencies
    """
    src_dir = tmp_path / "src" / "myapp"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    # Create 50 source modules
    for i in range(50):
        module_file = src_dir / f"module_{i}.py"
        imports = []
        if i > 0:
            # Each module imports 1-3 previous modules
            for j in range(max(0, i - 3), i):
                imports.append(f"from myapp.module_{j} import func_{j}")

        content = (
            "\n".join(imports)
            + f"""

def func_{i}():
    \"\"\"Function {i}.\"\"\"
    return {i}

class Class_{i}:
    \"\"\"Class {i}.\"\"\"
    def method(self):
        return {i}
"""
        )
        module_file.write_text(content)

    # Create 50 test files
    for i in range(50):
        test_file = tests_dir / f"test_module_{i}.py"
        content = f"""import pytest
from myapp.module_{i} import func_{i}, Class_{i}

def test_func_{i}():
    assert func_{i}() == {i}

def test_class_{i}():
    obj = Class_{i}()
    assert obj.method() == {i}
"""
        test_file.write_text(content)

    # Create __init__.py
    (src_dir / "__init__.py").write_text("")

    return tmp_path


@pytest.fixture
def benchmark_project_medium(tmp_path: Path) -> Path:
    """Create a medium synthetic project (200-500 files) for benchmarking.

    Structure:
    - 250 source files in src/
    - 250 test files in tests/
    - More complex import dependencies
    """
    src_dir = tmp_path / "src" / "myapp"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    # Create source modules with packages
    for pkg in range(5):
        pkg_dir = src_dir / f"package_{pkg}"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        for i in range(50):
            module_file = pkg_dir / f"module_{i}.py"
            imports = []
            # Import from same package
            if i > 0:
                imports.append(f"from .module_{max(0, i-1)} import func_{max(0, i-1)}")
            # Cross-package imports
            if pkg > 0:
                imports.append(
                    f"from myapp.package_{pkg-1}.module_{i % 50} import func_{i % 50}"
                )

            content = (
                "\n".join(imports)
                + f"""

def func_{i}():
    \"\"\"Function {i}.\"\"\"
    return {i}

class Class_{i}:
    \"\"\"Class {i}.\"\"\"
    def method(self):
        return {i}
"""
            )
            module_file.write_text(content)

    # Create test files
    for pkg in range(5):
        for i in range(50):
            test_file = tests_dir / f"test_package_{pkg}_module_{i}.py"
            content = f"""import pytest
from myapp.package_{pkg}.module_{i} import func_{i}, Class_{i}

def test_func_{i}():
    assert func_{i}() == {i}

def test_class_{i}():
    obj = Class_{i}()
    assert obj.method() == {i}
"""
            test_file.write_text(content)

    (src_dir / "__init__.py").write_text("")

    return tmp_path


@pytest.fixture
def benchmark_project_large(tmp_path: Path) -> Path:
    """Create a large synthetic project (1000+ files) for benchmarking.

    Structure:
    - 1000 source files in src/
    - 1000 test files in tests/
    - Complex nested package structure
    """
    src_dir = tmp_path / "src" / "myapp"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    # Create 10 packages with 10 subpackages each with 10 modules
    for pkg in range(10):
        pkg_dir = src_dir / f"package_{pkg}"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        for subpkg in range(10):
            subpkg_dir = pkg_dir / f"subpackage_{subpkg}"
            subpkg_dir.mkdir()
            (subpkg_dir / "__init__.py").write_text("")

            for i in range(10):
                module_file = subpkg_dir / f"module_{i}.py"
                imports = []
                # Complex imports
                if i > 0:
                    imports.append(f"from .module_{i-1} import func_{i-1}")
                if subpkg > 0:
                    imports.append(
                        f"from ..subpackage_{subpkg-1}.module_{i} import func_{i}"
                    )

                content = (
                    "\n".join(imports)
                    + f"""

def func_{i}():
    \"\"\"Function {i}.\"\"\"
    return {i}

class Class_{i}:
    \"\"\"Class {i}.\"\"\"
    def method(self):
        return {i}
"""
                )
                module_file.write_text(content)

    # Create test files
    for pkg in range(10):
        for subpkg in range(10):
            for i in range(10):
                test_file = tests_dir / f"test_p{pkg}_sp{subpkg}_m{i}.py"
                content = f"""import pytest
from myapp.package_{pkg}.subpackage_{subpkg}.module_{i} import func_{i}, Class_{i}

def test_func_{i}():
    assert func_{i}() == {i}

def test_class_{i}():
    obj = Class_{i}()
    assert obj.method() == {i}
"""
                test_file.write_text(content)

    (src_dir / "__init__.py").write_text("")

    return tmp_path
