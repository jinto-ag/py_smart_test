"""Tests for _paths module — path discovery and configuration loading."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from py_smart_test._paths import (
    _discover_default_branch,
    _discover_packages,
    _discover_src_dir,
    _discover_test_dir,
    _load_config,
    get_graph_file,
)


class TestLoadConfig:
    """Test [tool.py-smart-test] config loading from pyproject.toml."""

    def test_returns_config_when_present(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[tool.py-smart-test]\nsrc_dir = "lib"\ndefault_branch = "develop"\n'
        )
        config = _load_config(tmp_path)
        assert config["src_dir"] == "lib"
        assert config["default_branch"] == "develop"

    def test_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        assert _load_config(tmp_path) == {}

    def test_returns_empty_when_no_tool_section(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text("[project]\nname = 'foo'\n")
        assert _load_config(tmp_path) == {}

    def test_returns_empty_on_invalid_toml(self, tmp_path: Path) -> None:
        toml = tmp_path / "pyproject.toml"
        toml.write_text("this is not valid TOML {{{}}}}}}")
        assert _load_config(tmp_path) == {}


class TestDiscoverSrcDir:
    def test_uses_config_src_dir(self, tmp_path: Path) -> None:
        assert _discover_src_dir(tmp_path, {"src_dir": "lib"}) == tmp_path / "lib"

    def test_finds_src_layout(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        assert _discover_src_dir(tmp_path, {}) == tmp_path / "src"

    def test_falls_back_to_root(self, tmp_path: Path) -> None:
        assert _discover_src_dir(tmp_path, {}) == tmp_path


class TestDiscoverPackages:
    def test_uses_config_packages(self, tmp_path: Path) -> None:
        result = _discover_packages(tmp_path, {"packages": ["foo", "bar"]})
        assert result == ["foo", "bar"]

    def test_discovers_packages_with_init(self, tmp_path: Path) -> None:
        pkg = tmp_path / "my_package"
        pkg.mkdir()
        (pkg / "__init__.py").touch()
        # Also create a non-package dir
        (tmp_path / "data").mkdir()
        result = _discover_packages(tmp_path, {})
        assert result == ["my_package"]

    def test_skips_hidden_and_private_dirs(self, tmp_path: Path) -> None:
        for name in [".hidden", "_private"]:
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").touch()
        assert _discover_packages(tmp_path, {}) == []

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        assert _discover_packages(Path("/nonexistent"), {}) == []


class TestDiscoverTestDir:
    def test_uses_config_test_dir(self, tmp_path: Path) -> None:
        assert _discover_test_dir(tmp_path, {"test_dir": "spec"}) == tmp_path / "spec"

    def test_defaults_to_tests(self, tmp_path: Path) -> None:
        assert _discover_test_dir(tmp_path, {}) == tmp_path / "tests"


class TestDiscoverDefaultBranch:
    def test_uses_config_default_branch(self, tmp_path: Path) -> None:
        assert _discover_default_branch(tmp_path, {"default_branch": "dev"}) == "dev"

    @patch("py_smart_test._paths.subprocess.run")
    def test_reads_symbolic_ref(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            stdout="refs/remotes/origin/main\n", returncode=0
        )
        result = _discover_default_branch(tmp_path, {})
        assert result == "main"

    @patch("py_smart_test._paths.subprocess.run")
    def test_falls_back_to_branch_probing(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        # First call (symbolic-ref) fails, second (rev-parse main) fails,
        # third (rev-parse master) succeeds
        mock_run.side_effect = [
            Exception("no remote"),
            Exception("no main"),
            MagicMock(returncode=0),
        ]
        result = _discover_default_branch(tmp_path, {})
        assert result == "master"

    @patch("py_smart_test._paths.subprocess.run")
    def test_defaults_to_main_when_all_fail(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.side_effect = Exception("all fail")
        result = _discover_default_branch(tmp_path, {})
        assert result == "main"


class TestGetGraphFile:
    def test_returns_path(self) -> None:
        result = get_graph_file()
        assert isinstance(result, Path)
        assert result.name == "dependency_graph.json"


def test_reload_paths_module_coverage():
    """Reload _paths module to cover module-level code."""
    import importlib

    from py_smart_test import _paths

    importlib.reload(_paths)
