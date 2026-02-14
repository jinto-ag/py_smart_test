import json
import logging
from pathlib import Path
from typing import Dict, List

from . import _paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def map_tests_to_modules(test_root: Path) -> Dict[str, List[str]]:
    """
    Map test files to the modules they test.
    Returns: { "module_name": ["tests/test_module.py", ...] }
    """
    mapping: Dict[str, List[str]] = {}

    graph_file = _paths.get_graph_file()
    if not graph_file.exists():
        logger.error(
            "Dependency graph not found. Run generate_dependency_graph.py first."
        )
        return {}

    with open(graph_file, "r") as f:
        graph = json.load(f)

    valid_modules = set(graph.get("modules", {}).keys())

    # Iterate all test files
    for test_file in test_root.rglob("test_*.py"):
        rel_path = test_file.relative_to(test_root)
        test_file_str = test_file.relative_to(_paths.REPO_ROOT).as_posix()

        parts = list(rel_path.parts)
        filename = parts[-1]

        # Extract potential module name from filename
        # test_backtest.py -> backtest
        if filename.startswith("test_"):
            base_name = filename[5:-3]
        else:
            # Should be unreachable given rglob("test_*.py")
            # But just in case pattern changes
            base_name = filename[:-3]

        # Strategy 1: Mirror structure + prefix
        # tests/core/test_backtest.py -> core.backtest
        # We try to match against valid_modules

        # Build candidate path parts
        # e.g. ['core', 'backtest']
        candidate_parts = parts[:-1] + [base_name]
        candidate_suffix = ".".join(candidate_parts)

        # Try finding a module that ends with this suffix
        # Or commonly, prefixed with 'py_smart_test'

        matches = []

        # Exact match (unlikely if valid_modules starts with py_smart_test)
        if candidate_suffix in valid_modules:
            matches.append(candidate_suffix)

        # Prefix match: try each discovered package name
        for pkg in _paths.PACKAGES:
            prefixed = f"{pkg}.{candidate_suffix}"
            if prefixed in valid_modules:
                matches.append(prefixed)

        if matches:
            for m in matches:
                mapping.setdefault(m, []).append(test_file_str)
        else:
            # Fallback: fuzzy search?
            # e.g. tests/test_cli_integration.py -> cli.app?
            # Hard to guess without conventions.
            pass

    return mapping


def main():
    # We use src/py_smart_test/tests? No, _paths.TEST_ROOT is tests/
    test_root = _paths.TEST_ROOT
    if not test_root.exists():
        logger.warning(f"Test root {test_root} does not exist.")
        return

    test_map = map_tests_to_modules(test_root)

    graph_file = _paths.get_graph_file()
    if not graph_file.exists():
        logger.warning("Graph file not found, skipping map update.")
        return

    with open(graph_file, "r") as f:
        graph = json.load(f)

    # 1. Update "modules" section with "tests" list
    for mod_name, tests in test_map.items():
        if mod_name in graph["modules"]:
            graph["modules"][mod_name]["tests"] = sorted(list(set(tests)))

    # 2. Create "test_map" section
    test_to_modules: Dict[str, List[str]] = {}
    for mod, tests in test_map.items():
        for t in tests:
            test_to_modules.setdefault(t, []).append(mod)

    graph["test_map"] = test_to_modules

    with open(graph_file, "w") as f:
        json.dump(graph, f, indent=2)

    logger.info(f"Updated dependency graph with {len(test_map)} mapped modules.")


if __name__ == "__main__":
    main()
