import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set

import typer  # type: ignore

from . import _paths
from .file_hash_manager import get_changed_files_hash
from .generate_dependency_graph import get_module_name

app = typer.Typer()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_changed_files(base_ref: str = "main", staged: bool = False) -> List[Path]:
    cmd = ["git", "diff", "--name-only"]
    if staged:
        cmd.append("--cached")
    else:
        # If base_ref is provided, we diff against it.
        # But commonly we want diff between base_ref and current HEAD?
        # git diff main...HEAD
        # If base_ref is just 'main', git diff main shows diff of working tree vs main?
        # Use simple git diff name-only base_ref?
        cmd.append(base_ref)

    try:
        # Run from repo root
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=_paths.REPO_ROOT
        )
        files = [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]
        return files
    except subprocess.CalledProcessError as e:
        logger.warning(
            f"Git command failed ({e}). Falling back to hash-based detection."
        )
        return get_changed_files_hash()


def get_working_tree_changes() -> List[Path]:
    """Detect unstaged and untracked files using ``git status --porcelain``.

    This mirrors pytest-picked's default mode — ideal for active development
    where changes haven't been staged or committed yet.
    """
    cmd = ["git", "status", "--porcelain"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=_paths.REPO_ROOT
        )
        files: List[Path] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            # porcelain format: XY filename  (or XY old -> new for renames)
            file_path = line[3:].strip()
            # Handle renames (old -> new)
            if " -> " in file_path:
                file_path = file_path.split(" -> ")[-1]
            # Only include .py files
            if file_path.endswith(".py"):
                files.append(Path(file_path))
        return files
    except subprocess.CalledProcessError as e:
        logger.warning(
            f"git status failed ({e}). Falling back to hash-based detection."
        )
        return get_changed_files_hash()


def get_transitive_dependents(graph: Dict[str, Any], modules: Set[str]) -> Set[str]:
    """
    Return set of modules that depend on the given modules (transitively).
    """
    affected = set(modules)
    queue = list(modules)

    visited = set(modules)

    while queue:
        current = queue.pop(0)
        # Find who imports current
        if current in graph["modules"]:
            dependents = graph["modules"][current].get("imported_by", [])
            for dep in dependents:
                if dep not in visited:
                    visited.add(dep)
                    affected.add(dep)
                    queue.append(dep)
    return affected


def get_affected_tests(
    base: str = "main", staged: bool = False
) -> Dict[str, List[str]]:
    changed_files = get_changed_files(base, staged)
    logger.info(f"Changed files: {[str(f) for f in changed_files]}")

    # Load graph
    graph_file = _paths.get_graph_file()
    if not graph_file.exists():
        logger.error(f"Graph not found at {graph_file}")
        # Return empty or raise? If graph missing, we can't find affected.
        return {"affected_modules": [], "tests": []}

    with open(graph_file) as f:
        graph = json.load(f)

    # Map changes to modules
    affected_modules = set()
    direct_test_files = set()

    src_root = _paths.SRC_ROOT
    valid_modules = set(graph["modules"].keys())

    for file_path in changed_files:
        try:
            str_path = (
                file_path.as_posix()
                if hasattr(file_path, "as_posix")
                else str(file_path).replace("\\", "/")
            )

            # Case 1: Source file
            if "src/" in str_path and str_path.endswith(".py"):
                abs_path = _paths.REPO_ROOT / file_path
                if abs_path.exists():
                    mod_name = get_module_name(abs_path, src_root)
                    if mod_name in valid_modules:
                        affected_modules.add(mod_name)
                else:
                    # Deleted file logic
                    parts = str_path.split("/")
                    try:
                        if parts[0] == "src":
                            # Strip src/
                            rel_parts = parts[1:]
                            if rel_parts[-1] == "__init__.py":
                                rel_parts = rel_parts[:-1]
                            else:
                                rel_parts[-1] = rel_parts[-1][:-3]

                            mod_name = ".".join(rel_parts)
                            if mod_name in valid_modules:
                                affected_modules.add(mod_name)
                    except Exception:
                        pass

            # Case 2: Test file
            elif "tests/" in str_path and str_path.endswith(".py"):
                direct_test_files.add(str_path)

        except Exception as e:
            logger.warning(f"Error processing file {file_path}: {e}")

    # Compute impacted modules
    all_affected_modules = get_transitive_dependents(graph, affected_modules)

    # Collect tests
    tests_to_run = set(direct_test_files)

    for mod in all_affected_modules:
        if mod in graph["modules"]:
            tests = graph["modules"][mod].get("tests", [])
            tests_to_run.update(tests)

    final_list = sorted(list(tests_to_run))
    return {"affected_modules": sorted(list(all_affected_modules)), "tests": final_list}


@app.command()
def main(
    base: str = typer.Option(_paths.DEFAULT_BRANCH, help="Git base reference"),
    staged: bool = typer.Option(False, help="Check staged changes only"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
):
    result = get_affected_tests(base, staged)

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        logger.info(f"Affected modules: {len(result['affected_modules'])}")
        logger.info(f"Tests to run: {len(result['tests'])}")
        for t in result["tests"]:
            print(t)


if __name__ == "__main__":
    app()
