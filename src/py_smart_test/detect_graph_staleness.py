import logging

import typer  # type: ignore

from . import _paths
from .file_hash_manager import get_current_hashes, load_hashes

app = typer.Typer()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_graph_stale(verbose: bool = False) -> bool:
    graph_file = _paths.get_graph_file()

    if not graph_file.exists():
        if verbose:
            logger.info("Graph file does not exist.")
        return True

    # Load stored hashes
    stored_hashes = load_hashes()
    if not stored_hashes:
        if verbose:
            logger.info("No stored hashes found. Graph is stale.")
        return True

    # Compute current hashes
    current_hashes = get_current_hashes()

    # Compare
    # 1. Check for new or modified files
    for path, current_hash in current_hashes.items():
        if path not in stored_hashes:
            if verbose:
                logger.info(f"New file detected: {path}")
            return True
        if stored_hashes[path] != current_hash:
            if verbose:
                logger.info(f"File modified: {path}")
            return True

    # 2. Check for deleted files
    for path in stored_hashes:
        if path not in current_hashes:
            if verbose:
                logger.info(f"File deleted: {path}")
            return True

    if verbose:
        logger.info("Graph is up to date.")
    return False


@app.command()
def main(verbose: bool = False):
    if is_graph_stale(verbose):
        raise typer.Exit(1)
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
