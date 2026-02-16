"""Path constants for dependency graph system.

Automatically discovers the project layout by scanning the current working
directory for source packages and reading optional configuration from
pyproject.toml ``[tool.py-smart-test]``.

Supported configuration keys in ``[tool.py-smart-test]``::

    src_dir = "src"              # Source directory (default: auto-detected)
    packages = ["my_package"]    # Package names (default: auto-discovered)
    test_dir = "tests"           # Test directory (default: "tests")
    default_branch = "main"      # Git base branch (default: auto-detected)
"""

import subprocess
import tomllib
from pathlib import Path
from typing import List


def _load_config(repo_root: Path) -> dict:
    """Load py-smart-test config from pyproject.toml [tool.py-smart-test]."""
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return data.get("tool", {}).get("py-smart-test", {})
        except Exception:
            return {}
    return {}


def _discover_src_dir(repo_root: Path, config: dict) -> Path:
    """Discover the source directory containing Python packages."""
    if "src_dir" in config:
        return repo_root / config["src_dir"]

    # Standard src layout
    src = repo_root / "src"
    if src.is_dir():
        return src

    # Flat layout (source in repo root)
    return repo_root


def _discover_packages(src_dir: Path, config: dict) -> List[str]:
    """Discover Python packages under the source directory."""
    if "packages" in config:
        return config["packages"]

    packages = []
    if src_dir.is_dir():
        for item in sorted(src_dir.iterdir()):
            if (
                item.is_dir()
                and (item / "__init__.py").exists()
                and not item.name.startswith((".", "_"))
            ):
                packages.append(item.name)
    return packages


def _discover_test_dir(repo_root: Path, config: dict) -> Path:
    """Discover the test directory."""
    if "test_dir" in config:
        return repo_root / config["test_dir"]
    return repo_root / "tests"


def _discover_default_branch(repo_root: Path, config: dict) -> str:
    """Auto-detect the git default branch."""
    if "default_branch" in config:
        return config["default_branch"]

    # Try git symbolic-ref (works when remote is configured)
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        return result.stdout.strip().split("/")[-1]
    except Exception:
        pass

    # Try common branch names
    for branch in ["main", "master", "develop"]:
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )
            return branch
        except Exception:
            continue

    return "main"


# ── Project root ──────────────────────────────────────────────────────
REPO_ROOT = Path.cwd()

# ── Configuration ─────────────────────────────────────────────────────
_CONFIG = _load_config(REPO_ROOT)

# ── Source layout ─────────────────────────────────────────────────────
SRC_ROOT = _discover_src_dir(REPO_ROOT, _CONFIG)
PACKAGES = _discover_packages(SRC_ROOT, _CONFIG)
TEST_ROOT = _discover_test_dir(REPO_ROOT, _CONFIG)
DEFAULT_BRANCH = _discover_default_branch(REPO_ROOT, _CONFIG)

# ── Dependency graph locations ────────────────────────────────────────
PY_SMART_TEST_DIR = REPO_ROOT / ".py_smart_test"
GRAPH_DIR = PY_SMART_TEST_DIR
GRAPH_FILE = GRAPH_DIR / "dependency_graph.json"
CACHE_DIR = GRAPH_DIR / "cache"
CACHE_FILE = CACHE_DIR / "dependency_graph_cache.json"

# ── Ensure directories exist ─────────────────────────────────────────
GRAPH_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = PY_SMART_TEST_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Auto-generate .gitignore for generated files ─────────────────────
GITIGNORE_FILE = PY_SMART_TEST_DIR / ".gitignore"
if not GITIGNORE_FILE.exists():
    GITIGNORE_FILE.write_text(
        """# Generated files - do not commit
dependency_graph.json
file_hashes.json
coverage_mapping.json
test_outcomes.json
ast_parse_cache.json
cache/
logs/
"""
    )


def get_graph_file() -> Path:
    """Get the dependency graph file path."""
    return GRAPH_FILE
