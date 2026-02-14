import ast
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

from . import _paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImportVisitor(ast.NodeVisitor):
    def __init__(self, current_module: str):
        self.current_module = current_module
        self.imports: Set[str] = set()

    def _resolve_relative(self, level: int, module: Optional[str]) -> Optional[str]:
        parts = self.current_module.split(".")
        # If current module is 'pkg.module', __package__ is 'pkg'
        # But here current_module is the full name.
        # If it's a package (ends in __init__ originally), it behaves differently?
        # Typically we treat all as modules.
        # Strict handling:
        # if current_module is a.b.c:
        # level 1 (.) -> a.b
        # level 2 (..) -> a

        if len(parts) < level:
            return None  # Error or separate root

        base_parts = parts[:-level]
        base_module = ".".join(base_parts)

        if module:
            if base_module:
                return f"{base_module}.{module}"
            return module
        return base_module

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.add(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level == 0:
            # Absolute import
            if node.module:
                self.imports.add(node.module)
        else:
            # Relative import
            resolved = self._resolve_relative(node.level, node.module)
            if resolved:
                self.imports.add(resolved)


def get_module_name(file_path: Path, src_root: Path) -> str:
    """
    Convert file path to dotted module name.
    src/py_smart_test/core/test.py -> py_smart_test.core.test
    src/py_smart_test/__init__.py -> py_smart_test
    """
    rel_path = file_path.relative_to(src_root)
    parts = list(rel_path.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # remove .py

    return ".".join(parts)


def scan_and_build_graph(src_root: Path) -> Dict[str, Any]:
    # src_root is the source directory (e.g., REPO/src/) containing packages
    logging.info(f"Scanning modules in {src_root}")

    modules_map: Dict[str, Any] = {}

    # Collect all python files under the source directory
    all_files = list(src_root.rglob("*.py"))

    # First pass: map all valid local modules
    valid_modules: Set[str] = set()
    for file_path in all_files:
        mod_name = get_module_name(file_path, src_root)
        valid_modules.add(mod_name)

    # Second pass: parse and resolve
    for file_path in all_files:
        mod_name = get_module_name(file_path, src_root)

        try:
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"), filename=str(file_path)
            )
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            continue

        visitor = ImportVisitor(mod_name)
        visitor.visit(tree)

        # Filter: keep only imports that exist in valid_modules
        # Also matching sub-packages: if 'py_smart_test.core' is imported,
        # and 'py_smart_test.core' is a package (has __init__), it is in valid_modules.
        # But if 'py_smart_test.core.utils' is imported, check strict match.

        resolved_imports = []
        for imp in visitor.imports:
            # 1. Exact match
            if imp in valid_modules:
                resolved_imports.append(imp)
                continue

            # 2. Parent match (e.g. importing a class from a module)
            # from py_smart_test.core.settings import Settings -> imports
            # 'py_smart_test.core.settings'
            # What if imp is 'py_smart_test.core.settings.Settings'?
            # We split and check if strict prefix is a module
            parts = imp.split(".")
            for i in range(len(parts), 0, -1):
                sub = ".".join(parts[:i])
                if sub in valid_modules:
                    resolved_imports.append(sub)
                    break
                # If we matched 'py_smart_test.core.settings', we depend on that file.
                # We don't need to depend on 'py_smart_test.core' unless
                # explicitly imported?
                # Actually, importing a submodule usually implies
                # importing parent?
                # For affected checking, yes: changing settings.py affects this file.

        modules_map[mod_name] = {
            "imports": sorted(list(set(resolved_imports))),  # dedupe
            "file": file_path.relative_to(_paths.REPO_ROOT).as_posix(),
            # We can add "imported_by" later by inverting this list
        }

    # Invert graph to populate "imported_by"
    for mod, data in modules_map.items():
        data["imported_by"] = []

    for mod, data in modules_map.items():
        for dep in data["imports"]:
            if dep in modules_map:
                modules_map[dep]["imported_by"].append(mod)

    return {"modules": modules_map}


def main():
    graph = scan_and_build_graph(_paths.SRC_ROOT)

    out_file = _paths.get_graph_file()
    logger.info(f"Writing dependency graph to {out_file}")

    with open(out_file, "w") as f:
        json.dump(graph, f, indent=2)


if __name__ == "__main__":
    main()
