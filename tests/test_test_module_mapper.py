import json
from pathlib import Path
from typing import Any, Dict

from py_smart_test import test_module_mapper
from py_smart_test.test_module_mapper import main as mapper_main
from py_smart_test.test_module_mapper import map_tests_to_modules


def test_map_tests_to_modules_no_graph(mock_paths, caplog):
    # Should log error and return empty
    result = map_tests_to_modules(Path("dummy"))
    assert result == {}
    assert "Dependency graph not found" in caplog.text


def test_map_tests_to_modules_integration(mock_paths, temp_repo_root):
    # Setup graph
    graph: Dict[str, Any] = {"modules": {"py_smart_test.core.backtest": {}}}
    graph_file = temp_repo_root / ".py_smart_test" / "dependency_graph.json"
    with open(graph_file, "w") as f:
        json.dump(graph, f)

    # Setup test file
    test_file = temp_repo_root / "tests" / "core" / "test_backtest.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.touch()

    # Run mapping
    mapping = map_tests_to_modules(temp_repo_root / "tests")

    # Expect: py_smart_test.core.backtest -> [tests/core/test_backtest.py]
    # Note: the mapper logic tries to match 'core.backtest' or
    # 'py_smart_test.core.backtest'
    # 'tests/core/test_backtest.py' -> parts=['core', 'test_backtest.py']
    # -> base='backtest' -> candidate='core.backtest'
    # Matches 'py_smart_test.core.backtest' via prefix check?

    assert "py_smart_test.core.backtest" in mapping
    assert len(mapping["py_smart_test.core.backtest"]) == 1
    assert "tests/core/test_backtest.py" in mapping["py_smart_test.core.backtest"][0]


def test_mapper_main_end_to_end(mock_paths, temp_repo_root):
    # Setup graph
    graph: Dict[str, Any] = {"modules": {"py_smart_test.utils": {}}}
    graph_file = temp_repo_root / ".py_smart_test" / "dependency_graph.json"
    with open(graph_file, "w") as f:
        json.dump(graph, f)

    # Setup test
    (temp_repo_root / "tests").mkdir(exist_ok=True)
    (temp_repo_root / "tests" / "test_utils.py").touch()

    # Run main
    mapper_main()

    # Verify graph updated
    with open(graph_file) as f:
        data = json.load(f)

    assert "tests" in data["modules"]["py_smart_test.utils"]
    assert len(data["modules"]["py_smart_test.utils"]["tests"]) > 0
    assert "test_map" in data


def test_map_tests_nested_package(temp_repo_root, mock_paths):
    # Rename test to reflect what we are testing: mapping logic for nested files

    # Setup graph
    graph: Dict[str, Any] = {"modules": {"pkg.foo": {}}}
    graph_file = mock_paths.GRAPH_FILE
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    with open(graph_file, "w") as f:
        json.dump(graph, f)

    (temp_repo_root / "tests").mkdir(exist_ok=True)
    # tests/pkg/test_foo.py -> base=foo -> candidate pkg.foo
    (temp_repo_root / "tests" / "pkg").mkdir(parents=True, exist_ok=True)
    (temp_repo_root / "tests" / "pkg" / "test_foo.py").touch()

    # map
    mapping = map_tests_to_modules(temp_repo_root / "tests")

    assert "pkg.foo" in mapping
    assert len(mapping["pkg.foo"]) == 1


def test_map_tests_exact_suffix_match(temp_repo_root, mock_paths):
    # candidate suffix match
    graph: Dict[str, Any] = {"modules": {"core.utils": {}}}
    graph_file = mock_paths.GRAPH_FILE
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    with open(graph_file, "w") as f:
        json.dump(graph, f)

    (temp_repo_root / "tests" / "core").mkdir(parents=True, exist_ok=True)
    (temp_repo_root / "tests" / "core" / "test_utils.py").touch()

    mapping = map_tests_to_modules(temp_repo_root / "tests")

    assert "core.utils" in mapping


def test_mapper_main_execution(mock_paths, monkeypatch):
    from py_smart_test import _paths

    # Mock map_tests_to_modules to return something
    monkeypatch.setattr(
        test_module_mapper, "map_tests_to_modules", lambda r: {"mod": ["test.py"]}
    )

    # Mock get_graph_file to return the temp path
    monkeypatch.setattr(_paths, "get_graph_file", lambda: mock_paths.GRAPH_FILE)

    # Ensure graph file exists
    mock_paths.GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    mock_paths.GRAPH_FILE.write_text(json.dumps({"modules": {}}))

    test_module_mapper.main()

    # Check if graph updated
    content = json.loads(mock_paths.GRAPH_FILE.read_text())
    assert "test_map" in content


def test_mapper_no_test_root(mock_paths, monkeypatch, caplog):
    from py_smart_test import _paths

    # Mock TEST_ROOT to non-existent
    monkeypatch.setattr(mock_paths, "TEST_ROOT", mock_paths.REPO_ROOT / "non_existent")
    # Mock get_graph_file to return the temp path
    monkeypatch.setattr(_paths, "get_graph_file", lambda: mock_paths.GRAPH_FILE)

    test_module_mapper.main()

    assert "Test root" in caplog.text


def test_main_no_graph(mock_paths, monkeypatch, caplog):
    from py_smart_test import _paths

    if mock_paths.GRAPH_FILE.exists():
        mock_paths.GRAPH_FILE.unlink()

    # Mock get_graph_file to return the temp path
    monkeypatch.setattr(_paths, "get_graph_file", lambda: mock_paths.GRAPH_FILE)

    mapper_main()
    assert "Dependency graph not found" in caplog.text
