# Py Smart Test

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-59%20passed-green.svg)](#testing)

**Smart Test Runner and Dependency Graph System** for Python projects. Optimizes development workflows by running only the tests affected by your code changes, with robust fallbacks and comprehensive dependency analysis.

## 🚀 Features

- **Smart Test Execution**: Runs only tests relevant to changed code (Git diff or hash-based detection)
- **Dependency Graph Analysis**: Statically analyzes Python imports to build comprehensive dependency maps
- **Multiple Change Detection Methods**:
  - Git-based: Compare against branches/tags (default: `main`)
  - Staged changes: Test only staged modifications
  - Hash-based fallback: Works without Git repository
- **Robust Fallbacks**:
  - Automatically falls back to full test suite if graph generation fails
  - Automatically switches to hash-based detection if Git is unavailable
  - Graceful error handling with informative logging
- **Auto-Regeneration**: Detects stale dependency graphs and regenerates them automatically
- **Comprehensive CLI**: Multiple entry points for different use cases
- **Structured Logging**: All operations logged to files with configurable verbosity
- **Production Ready**: Full test coverage, type hints, and comprehensive error handling

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Architecture](#-architecture)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Development](#-development)
- [Production Readiness](#-production-readiness)
- [Contributing](#-contributing)
- [License](#-license)

## 🛠️ Installation

### Requirements

- Python 3.13+
- Git (optional, for Git-based change detection)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd py-smart-test

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Install from PyPI (when published)

```bash
pip install py-smart-test
```

## 🚀 Quick Start

```bash
# Run affected tests (compares current branch vs main)
py-smart-test  # or: pst

# Run affected tests for staged changes only
py-smart-test --staged  # or: pst --staged

# Dry run to see what would be tested
py-smart-test --dry-run  # or: pst --dry-run

# Run all tests (bypass smart detection)
py-smart-test --mode all  # or: pst --mode all
```

## � Command Aliases

For convenience, short aliases are available for all commands:

| Full Command              | Alias          | Purpose                   |
| ------------------------- | -------------- | ------------------------- |
| `py-smart-test`           | `pst`          | Smart test runner         |
| `py-smart-test-graph-gen` | `pst-gen`      | Generate dependency graph |
| `py-smart-test-map-tests` | `pst-map`      | Test module mapping       |
| `py-smart-test-affected`  | `pst-affected` | Find affected modules     |
| `py-smart-test-stale`     | `pst-stale`    | Check graph staleness     |

## �💻 Usage

### Main Commands

#### `py-smart-test` (alias: `pst`) - Smart Test Runner

The primary command for running tests intelligently.

```bash
py-smart-test [OPTIONS]  # or: pst [OPTIONS]
```

**Options:**

- `--mode [affected|all]`: Test mode (default: `affected`)
- `--since REF`: Git reference to compare against (default: `main`)
- `--staged`: Use only staged changes
- `--regenerate-graph`: Force dependency graph regeneration
- `--no-exclude-e2e`: Include E2E tests (excluded by default)
- `--dry-run`: Show what would run without executing tests
- `--verbose`: Enable verbose logging

**Examples:**

```bash
# Test changes since main branch
py-smart-test

# Test only staged changes
py-smart-test --staged

# Test changes since a specific commit
py-smart-test --since abc123

# Force graph regeneration and test
py-smart-test --regenerate-graph

# See what tests would run
py-smart-test --dry-run --verbose
```

#### `py-smart-test-graph-gen` (alias: `pst-gen`) - Generate Dependency Graph

Manually generate or update the dependency graph.

```bash
py-smart-test-graph-gen  # or: pst-gen
```

#### `py-smart-test-map-tests` (alias: `pst-map`) - Test Module Mapping

Debug test-to-module mapping logic.

```bash
py-smart-test-map-tests  # or: pst-map
```

#### `py-smart-test-affected` (alias: `pst-affected`) - Find Affected Modules

Debug affected module detection.

```bash
py-smart-test-affected [OPTIONS]
```

#### `py-smart-test-stale` (alias: `pst-stale`) - Check Graph Staleness

Check if the dependency graph needs regeneration.

```bash
py-smart-test-stale  # or: pst-stale
```

### Integration with Development Workflows

#### With `uv` and `verify.sh`

The project includes a `verify.sh` script that uses `py-smart-test` by default:

```bash
./verify.sh  # Runs smart tests
```

#### CI/CD Integration

For CI/CD pipelines, you can use the `--mode all` flag to run full test suites:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: py-smart-test --mode all
```

## 📂 Architecture

### Core Components

```text
src/py_smart_test/
├── smart_test_runner.py      # Main CLI orchestrator
├── detect_graph_staleness.py # Graph freshness detection
├── file_hash_manager.py      # Hash-based change detection
├── find_affected_modules.py  # Core dependency traversal logic
├── generate_dependency_graph.py # AST-based import analysis
├── test_module_mapper.py     # Test-to-module heuristics
├── _paths.py                 # Path configuration and constants
└── __init__.py               # Package initialization
```

### Data Flow

1. **Change Detection**: Identify modified files via Git or hash comparison
2. **Module Mapping**: Convert file paths to Python module names
3. **Dependency Analysis**: Traverse import graph to find all affected modules
4. **Test Selection**: Map affected modules to their corresponding tests
5. **Test Execution**: Run selected tests with pytest

### Storage Structure

```text
.py_smart_test/
├── dependency_graph.json     # Import dependency graph
├── file_hashes.json         # File hash snapshots
├── logs/
│   └── latest_run.log       # Execution logs
└── cache/                   # Reserved for future use
```

### Fallback Strategy

The system implements a robust fallback hierarchy:

1. **Primary**: Git-based change detection
2. **Fallback 1**: Hash-based change detection
3. **Fallback 2**: Full test suite execution
4. **Fallback 3**: Graceful error with informative messages

## ⚙️ Configuration

### Environment Variables

- `PY_SMART_TEST_LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `PY_SMART_TEST_CACHE_DIR`: Override cache directory location

### Configuration Files

- `.flake8`: Linting configuration (line length: 88 chars)
- `pyproject.toml`: Project metadata and dependencies

### Path Configuration

The system automatically detects project structure:

- Repository root: Current working directory
- Source code: `src/py_smart_test/`
- Tests: `tests/`
- Cache: `.py_smart_test/`

## 🧪 Testing

### Test Suite

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/py_smart_test --cov-report=html

# Run specific test file
uv run pytest tests/test_smart_test_runner.py
```

### Test Coverage

- **59 tests** covering all major functionality
- **Core modules**: 100% coverage target
- **Integration tests**: End-to-end workflow validation
- **Error handling**: Comprehensive edge case testing

### Test Categories

- Unit tests for individual functions
- Integration tests for component interaction
- CLI interface tests
- Error handling and fallback scenarios
- Graph generation and traversal tests

## 🏗️ Development

### Setup Development Environment

```bash
# Install development dependencies
uv add --dev -e .

# Install pre-commit hooks (recommended)
uv run pre-commit install --install-hooks

# Install pre-commit hooks for commit messages
uv run pre-commit install --hook-type commit-msg
```

### Code Quality

The project uses comprehensive code quality tools:

```bash
# Run all quality checks
python-verify --paths=src

# Format code
black src/
isort src/

# Lint code
ruff check src/
flake8 src/
mypy src/
```

### Adding New Features

1. Add functionality to appropriate module
2. Add comprehensive tests
3. Update documentation
4. Run quality checks: `python-verify --paths=src`
5. Update CHANGELOG.md

### Conventional Commits

This project uses [Conventional Commits](https://conventionalcommits.org/) for commit messages. Pre-commit hooks will validate commit messages automatically.

**Format:**

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Testing changes
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Maintenance tasks
- `revert`: Revert changes

**Examples:**

```bash
feat: add smart test detection for changed files
fix: resolve circular import in dependency graph
docs: update installation instructions
```

### Version Management & Changelog

This project uses [Commitizen](https://commitizen-tools.github.io/commitizen/) for version management and [git-cliff](https://git-cliff.org/) for changelog generation.

**Creating a new release:**

```bash
# Update version and generate changelog
uv run cz bump

# Or preview what would happen
uv run cz bump --dry-run
```

**Manual changelog generation:**

```bash
# Generate changelog from conventional commits
uv run git-cliff --latest --strip=all > CHANGELOG.md
```

## ✅ Production Readiness

### ✅ Completed Requirements

- **License**: MIT License included
- **Version**: 1.0.0 (production ready)
- **Documentation**: Comprehensive README and docstrings
- **Testing**: 59 tests with good coverage
- **Type Hints**: Full type annotation coverage
- **Error Handling**: Robust error handling with fallbacks
- **Logging**: Structured logging with file output
- **Packaging**: Proper Python packaging with entry points
- **Dependencies**: Minimal, well-maintained dependencies

### 🔄 Recommended Improvements

#### High Priority

- **CI/CD Pipeline**: Add GitHub Actions or similar for automated testing
- **Security Scanning**: Regular dependency vulnerability checks
- **Performance Monitoring**: Add timing metrics for large codebases

#### Medium Priority

- **Configuration File**: Add `.py-smart-test.toml` for user configuration
- **Plugin System**: Allow custom test mappers and change detectors
- **Caching**: Implement intelligent caching for graph regeneration

#### Low Priority

- **Web UI**: Optional web interface for graph visualization
- **IDE Integration**: VS Code extension for smart test running
- **Multi-language Support**: Extend beyond Python projects

### Security Considerations

- No sensitive data handling
- Minimal dependencies reduce attack surface
- Hash-based detection uses MD5 (acceptable for change detection, not security)
- File operations are read-only except for cache/logging

### Performance Characteristics

- **Graph Generation**: O(n) where n is number of Python files
- **Change Detection**: O(m) where m is number of changed files
- **Test Selection**: O(d) where d is dependency graph depth
- **Memory Usage**: Proportional to codebase size

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started, our development workflow, and the PR process.

Please also note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) for CLI interface
- Uses [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- Inspired by modern development workflow optimization tools
