# Contributing to Py Smart Test

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to `py-smart-test` (a.k.a `pst`). These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- **Python 3.13+**
- **uv**: We use `uv` for dependency management. [Install uv](https://github.com/astral-sh/uv).

### Installation

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/your-username/py-smart-test.git
    cd py-smart-test
    ```
3.  **Install dependencies** using `uv`:
    ```bash
    uv sync --all-extras --dev
    ```
4.  **Install pre-commit hooks**:
    ```bash
    uv run pre-commit install --install-hooks
    uv run pre-commit install --hook-type commit-msg
    ```

## Development Workflow

1.  **Create a branch** for your changes:

    ```bash
    git checkout -b feat/my-new-feature
    ```

    _Note: We follow [Conventional Commits](https://www.conventionalcommits.org/). Please name your branch accordingly (e.g., `feat/...`, `fix/...`)._

2.  **Make your changes**.

3.  **Run tests** to ensure you haven't broken anything:

    ```bash
    uv run pytest
    ```

    Or use the verification script:

    ```bash
    ./verify.sh
    ```

4.  **Run linting and formatting**:
    ```bash
    uv run ruff check src/ tests/
    uv run black src/ tests/
    uv run mypy src/
    ```

### Running the Tool Locally

You can run the tool directly from source:

```bash
uv run py-smart-test --help
```

## Commit Messages

We use **Conventional Commits** to automate versioning and changelogs.
The commit message should be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to our CI configuration files and scripts
- `chore`: Other changes that don't modify src or test files
- `revert`: Reverts a previous commit

**Example:**

```
feat(cli): add --json flag for output formatting
```

## Pull Requests

1.  Refine your changes and ensure your commit history is clean.
2.  Push your branch to your fork.
3.  Open a Pull Request against the `main` branch.
4.  Fill out the Pull Request Template details.
5.  Wait for CI checks to pass and for a maintainer to review your PR.

## Reporting Bugs

Bugs are tracked as GitHub issues. When filing an issue, please explain the problem and include additional details to help maintainers reproduce the problem:

- Use a clear and descriptive title.
- Describe the exact steps to reproduce the problem.
- Describe the behavior you observed after following the steps.
- Explain which behavior you expected to see instead and why.
- Include screenshots/logs if possible.

## License

By contributing, you agree that your contributions will be licensed under its [MIT License](LICENSE).
