"""Path constants for dependency graph system."""

from pathlib import Path

# Get repo root (Use current working directory as project root)
REPO_ROOT = Path.cwd()

# Dependency graph locations (in main project)
PY_SMART_TEST_DIR = REPO_ROOT / ".py_smart_test"
GRAPH_DIR = PY_SMART_TEST_DIR
GRAPH_FILE = GRAPH_DIR / "dependency_graph.json"
CACHE_DIR = GRAPH_DIR / "cache"
CACHE_FILE = CACHE_DIR / "dependency_graph_cache.json"

# Application directories (in main project)
SRC_ROOT = REPO_ROOT / "src" / "py_smart_test"
TEST_ROOT = REPO_ROOT / "tests"

# Ensure directories exist
GRAPH_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = PY_SMART_TEST_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure .gitignore exists for generated files
GITIGNORE_FILE = PY_SMART_TEST_DIR / ".gitignore"
if not GITIGNORE_FILE.exists():
    GITIGNORE_FILE.write_text(
        """# Generated files - do not commit
dependency_graph.json
file_hashes.json
cache/
logs/
"""
    )


def get_graph_file() -> Path:
    """Get the dependency graph file path."""
    return GRAPH_FILE
