import json
import logging
import subprocess
import sys
from typing import List

import typer  # type: ignore

from . import _paths
from .detect_graph_staleness import is_graph_stale
from .file_hash_manager import HASH_FILE, update_hashes
from .find_affected_modules import get_affected_tests
from .generate_dependency_graph import main as generate_graph_main
from .test_module_mapper import main as mapper_main
from .utils import get_optional_dependency_message, has_optional_dependency

# ... imports ...

app = typer.Typer()
logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging to file and console."""
    # Group logs by date
    log_dir = _paths.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "latest_run.log"

    # File handler (captures everything)
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (cleaner output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []  # Clear default handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return log_file


def run_pytest(
    tests: List[str],
    extra_args: List[str],
    parallel: bool = False,
    workers: str = "auto",
    coverage: bool = False,
) -> bool:
    """Run pytest with the given tests and extra args.

    Returns True if tests were executed successfully, False if no tests to run.
    Raises CalledProcessError if tests fail.
    """
    cmd = ["pytest"] + extra_args

    # Add parallel execution flags if requested
    if parallel:
        if has_optional_dependency("xdist"):
            cmd.extend(["-n", workers])
            logger.info(f"Parallel execution enabled with {workers} workers")
        else:
            logger.warning(get_optional_dependency_message("xdist", "pytest-xdist"))
            logger.warning("Falling back to sequential execution.")

    # Add coverage flags if requested
    if coverage:
        if has_optional_dependency("pytest_cov"):
            cmd.extend(["--cov", str(_paths.SRC_ROOT), "--cov-report", "term-missing"])
            logger.info("Coverage reporting enabled")
        else:
            logger.warning(get_optional_dependency_message("pytest_cov", "pytest-cov"))
            logger.warning("Coverage reporting disabled.")

    if tests:
        cmd.extend(tests)
    else:
        logger.info("No tests provided. Running nothing.")
        return False

    logger.info(f"Running command: {' '.join(cmd)}")

    # Run and capture output to log it
    # We use Popen to stream output to both console and file
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    # Stream output
    if process.stdout:
        for line in process.stdout:
            sys.stdout.write(line)  # to console
            logger.debug(line.strip())  # to log file (as debug/info)

    exit_code = process.wait()

    if exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, cmd)

    return True


@app.command()
def main(
    mode: str = typer.Option("affected", help="Mode: 'affected' or 'all'"),
    since: str = typer.Option(
        _paths.DEFAULT_BRANCH, help="Git base reference for changes"
    ),
    staged: bool = typer.Option(False, help="Check staged changes only"),
    regenerate_graph: bool = typer.Option(
        False, help="Force regenerate dependency graph"
    ),
    exclude_e2e: bool = typer.Option(True, help="Exclude E2E tests"),
    dry_run: bool = typer.Option(False, help="Print plan but don't run tests"),
    json_output: bool = typer.Option(
        False, "--json", help="Output affected tests as JSON and exit (no test run)"
    ),
    parallel: bool = typer.Option(
        False, "--parallel", help="Run tests in parallel using pytest-xdist"
    ),
    parallel_workers: str = typer.Option(
        "auto", "--parallel-workers", help="Number of parallel workers (default: auto)"
    ),
    coverage: bool = typer.Option(
        False, "--coverage", help="Enable coverage tracking and reporting"
    ),
):
    """
    Smart test runner.

    With no arguments, delegates to ``pytest --smart`` so the plugin handles
    test selection and prioritization.  Use ``--mode all``, ``--json``,
    ``--dry-run``, or ``--regenerate-graph`` for advanced behaviour.
    """
    log_file = setup_logging()
    logger.info(f"Logging run to {log_file}")

    # ── Fast path: delegate to pytest --smart when using defaults ───
    # When the user runs `pst` with no special flags, we just run
    # `pytest --smart` and let the plugin handle everything.
    use_fast_path = (
        mode == "affected"
        and not json_output
        and not dry_run
        and not regenerate_graph
        and not parallel
        and not coverage
    )
    if use_fast_path:
        pytest_cmd = ["pytest", "--smart"]
        if since != _paths.DEFAULT_BRANCH:
            pytest_cmd.extend(["--smart-since", since])
        if staged:
            pytest_cmd.append("--smart-staged")
        if exclude_e2e:
            pytest_cmd.extend(["-m", "not e2e"])
        logger.info(f"Running command: {' '.join(pytest_cmd)}")
        result = subprocess.run(pytest_cmd)
        # Exit code 5 = no tests selected (--smart deselected all), treat as success
        exit_code = 0 if result.returncode == 5 else result.returncode
        raise typer.Exit(exit_code)

    # ── Full orchestration path ────────────────────────────────────
    # Check for first run / missing history
    # If no hash file exists, we consider this a fresh state.
    first_run = not HASH_FILE.exists()

    # 1. Regenerate graph if needed
    if regenerate_graph or is_graph_stale():
        logger.info("Regenerating dependency graph...")
        try:
            generate_graph_main()
            mapper_main()
        except Exception as e:
            logger.error(f"Failed to regenerate graph: {e}")
            if mode == "affected":
                logger.warning(
                    "Graph generation failed. Falling back to running ALL tests."
                )

    extra_pytest_args = []
    if exclude_e2e:
        extra_pytest_args.extend(["-m", "not e2e"])

    tests_to_run = []

    if mode == "all":
        logger.info("Running ALL tests.")
        # tests_to_run empty means run everything (pytest default) if we pass directory.
        # But to be explicit we might pass 'tests/'
        tests_to_run = ["tests/"]

    elif mode == "affected":
        # Force full run on first execution
        if first_run:
            logger.warning(
                "No execution history found. Running ALL tests to establish baseline."
            )
            tests_to_run = ["tests/"]
        else:
            try:
                affected_data = get_affected_tests(since, staged, coverage)
                tests_to_run = affected_data["tests"]

                if not tests_to_run:
                    logger.info("No affected tests found. Everything looks good! ✨")
                    raise typer.Exit(0)

                logger.info(f"Identified {len(tests_to_run)} affected tests.")

            except typer.Exit:
                raise
            except Exception as e:
                logger.error(f"Error determining affected tests: {e}")
                logger.warning("Falling back to ALL tests.")
                tests_to_run = ["tests/"]

    if json_output:
        result_data = (
            get_affected_tests(since, staged, coverage)
            if mode == "affected"
            else {"tests": tests_to_run}
        )
        print(json.dumps(result_data, indent=2))
        raise typer.Exit(0)

    if dry_run:
        print("Dry run. Would execute:")
        print(f"pytest {' '.join(extra_pytest_args)} {' '.join(tests_to_run)}")
        raise typer.Exit(0)

    # Execute pytest
    # We pass the list of test files.
    # If list is huge with 'all', ideally we pass 'tests/' directory.
    # tests_to_run handles this (list of files OR ['tests/']).

    # Track whether this is a full run (safe to update all hashes)
    is_full_run = first_run or mode == "all"

    try:
        tests_ran = run_pytest(
            tests_to_run, extra_pytest_args, parallel, parallel_workers, coverage
        )

        # Only update hashes when tests actually ran
        # Bug #3: Only update hashes on full runs to avoid masking
        # changes to files whose tests weren't in the affected set
        if tests_ran and not dry_run and is_full_run:
            update_hashes()
        elif tests_ran and not dry_run:
            logger.debug(
                "Partial test run — skipping hash update to avoid masking changes."
            )

    except subprocess.CalledProcessError as e:
        logger.error("Tests failed.")
        raise typer.Exit(e.returncode)


if __name__ == "__main__":
    app()
