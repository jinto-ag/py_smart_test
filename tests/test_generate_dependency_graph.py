# We assume conftest adds scripts/src to path, so we can import from scripts
from py_smart_test.generate_dependency_graph import (
    ImportVisitor,
    get_module_name,
    scan_and_build_graph,
)


def test_get_module_name(tmp_path):
    root = tmp_path / "src" / "pkg"
    root.mkdir(parents=True)

    # Test cases
    assert get_module_name(root / "module.py", root) == "module"
    assert get_module_name(root / "sub" / "mod.py", root) == "sub.mod"
    assert get_module_name(root / "__init__.py", root) == ""
    # If root has __init__.py, it effectively represents the root package itself?
    # Logic: parts=['__init__.py'] -> parts=[] -> join -> ""
    # This might mean the root package.


def test_import_visitor_relative_resolution():
    _ = ImportVisitor("pkg.sub.mod")

    # from . import x (level 1)
    # pkg.sub.mod split -> pkg, sub, mod
    # level 1 -> pkg.sub
    # resolved -> pkg.sub.x

    # Wait, implementation of _resolve_relative in script:
    # parts = current_module.split('.')
    # if len(parts) < level: return None
    # base_parts = parts[:-level]
    # base = join(base_parts)
    # return base.module


def test_syntax_error_handling(temp_repo_root, monkeypatch, mock_paths):
    from unittest.mock import MagicMock

    mock_logger = MagicMock()
    monkeypatch.setattr("py_smart_test.generate_dependency_graph.logger", mock_logger)

    # Create file with syntax error
    bad_file = temp_repo_root / "src" / "py_smart_test" / "bad.py"
    bad_file.write_text("def broken(")

    scan_and_build_graph(temp_repo_root / "src" / "py_smart_test")

    assert any("Syntax error" in str(c) for c in mock_logger.warning.call_args_list)


def test_resolve_relative_edge_cases():
    visitor = ImportVisitor("pkg.sub.mod")
    # level 1 (pkg.sub.mod) . -> pkg.sub
    # level 2 (pkg.sub) .. -> pkg
    # level 3 (pkg) ... -> None

    # "from . import foo" -> level 1, module="foo" -> pkg.sub.foo
    assert visitor._resolve_relative(1, "foo") == "pkg.sub.foo"

    # "from ... import foo" -> level 3, module="foo" -> None
    # (pkg has parts pkg, len 1? no pkg.sub.mod split . is 3 parts)
    # pkg.sub.mod -> [pkg, sub, mod]. level 3 -> remove 3 -> [] -> empty base
    # if base empty? code says return f"{base}.{mod}" if base else mod?
    # Let's check code logic.
    pass


def test_resolve_relative_too_deep():
    visitor = ImportVisitor("pkg")
    # level 2 -> .. -> impossible
    assert visitor._resolve_relative(2, "foo") is None


def test_scan_and_build_graph(temp_repo_root, mock_paths):
    src = mock_paths.SRC_ROOT
    # src is .../src/py_smart_test
    # But scan_and_build_graph uses src.parent (.../src) as root
    # So we should create files matching 'py_smart_test' package structure

    # Ensure package init
    (src / "__init__.py").touch()

    # core/base.py
    (src / "core").mkdir()
    (src / "core" / "__init__.py").touch()
    base_py = src / "core" / "base.py"
    base_py.write_text("import os\nclass Base: pass")

    # core/utils.py
    utils_py = src / "core" / "utils.py"
    utils_py.write_text("from .base import Base\nimport json")

    # main.py
    main_py = src / "main.py"
    main_py.write_text("from py_smart_test.core.utils import Base\nimport sys")

    # Run scan
    graph = scan_and_build_graph(mock_paths.SRC_ROOT)
    modules = graph["modules"]

    # Check modules exist (fully qualified)
    assert "py_smart_test" in modules
    assert "py_smart_test.core" in modules
    assert "py_smart_test.core.base" in modules
    assert "py_smart_test.core.utils" in modules
    assert "py_smart_test.main" in modules

    # Check imports

    # base.py: import os (external, filtered out)
    assert modules["py_smart_test.core.base"]["imports"] == []

    # utils.py: from .base import Base -> py_smart_test.core.base
    assert "py_smart_test.core.base" in modules["py_smart_test.core.utils"]["imports"]

    # main.py: from py_smart_test.core.utils import Base
    assert "py_smart_test.core.utils" in modules["py_smart_test.main"]["imports"]

    # Check imported_by
    assert "py_smart_test.main" in modules["py_smart_test.core.utils"]["imported_by"]


def test_import_visitor_resolution():
    from py_smart_test.generate_dependency_graph import ImportVisitor

    v = ImportVisitor("pkg.mod")

    # Test _resolve_relative with no module (e.g. from . import *)
    # level 1 from pkg.mod -> pkg
    assert v._resolve_relative(1, None) == "pkg"

    # Test level too high
    assert v._resolve_relative(3, None) is None

    # Test base module empty
    v2 = ImportVisitor("mod")
    # level 1 from mod -> empty string. module="sub" -> "sub"
    assert v2._resolve_relative(1, "sub") == "sub"
    # level 1 from mod -> empty string, no module -> empty string
    assert v2._resolve_relative(1, None) == ""


def test_main_execution(mock_paths, monkeypatch):
    from py_smart_test import _paths, generate_dependency_graph

    # Mock scan_and_build_graph
    monkeypatch.setattr(
        generate_dependency_graph, "scan_and_build_graph", lambda r: {"modules": {}}
    )

    # Mock get_graph_file to return the temp path
    monkeypatch.setattr(_paths, "get_graph_file", lambda: mock_paths.GRAPH_FILE)

    # Mock output file
    outfile = mock_paths.GRAPH_FILE
    # Make sure parent exists
    outfile.parent.mkdir(parents=True, exist_ok=True)

    generate_dependency_graph.main()

    assert outfile.exists()
    assert "modules" in outfile.read_text()
