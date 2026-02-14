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


def run_pytest(tests: List[str], extra_args: List[str]):
    cmd = ["pytest"] + extra_args
    if tests:
        cmd.extend(tests)
    else:
        logger.info("No tests provided. Running nothing.")
        return

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
    # capture extra args for pytest?
    # Typer doesn't support arbitrary extra args easily in same command signature.
    # use ctx?
):
    """
    Smart test runner.
    """
    log_file = setup_logging()
    logger.info(f"Logging run to {log_file}")

    # Check for first run / missing history
    # If no hash file exists, we consider this a fresh state.
    first_run = not HASH_FILE.exists()

    # 1. Regenerate graph if needed
    if regenerate_graph or is_graph_stale():
        logger.info("Regenerating dependency graph...")
        try:
            generate_graph_main()
            mapper_main()
            # Do NOT update hashes here. Only update after successful test run.
            # update_hashes()
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
                result = get_affected_tests(since, staged)
                tests_to_run = result["tests"]

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

    if dry_run:
        print("Dry run. Would execute:")
        print(f"pytest {' '.join(extra_pytest_args)} {' '.join(tests_to_run)}")
        raise typer.Exit(0)

    # Execute pytest
    # We pass the list of test files.
    # If list is huge with 'all', ideally we pass 'tests/' directory.
    # tests_to_run handles this (list of files OR ['tests/']).

    try:
        run_pytest(tests_to_run, extra_pytest_args)

        # If successful and not dry run, update hashes
        if not dry_run:
            update_hashes()

    except subprocess.CalledProcessError as e:
        logger.error("Tests failed.")
        raise typer.Exit(e.returncode)


if __name__ == "__main__":
    app()
