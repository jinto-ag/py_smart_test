from py_smart_test import main


def test_main_function(capsys):
    """Test the main function prints the expected message."""
    main()
    captured = capsys.readouterr()
    assert (
        "This package contains scripts for dependency graph analysis and smart testing."
        in captured.out
    )


def test_init_module_coverage():
    """Reload py_smart_test to cover module-level code."""
    import importlib

    import py_smart_test

    importlib.reload(py_smart_test)
