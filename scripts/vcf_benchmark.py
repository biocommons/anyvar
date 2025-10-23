# /// script
# dependencies = [
#   "requests",
#   "click",
# ]
# ///
#
# invoke with e.g. `uv run scripts/vcf_benchmark.py --workers 2 vcfs/vcf_1.vcf vcfs/vcf_2.vcf`

import logging
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from timeit import default_timer as timer

import click
import requests

# -------------------------------------------------------------------
# Logging setup
# -------------------------------------------------------------------
LOG_FILE = "anyvar_benchmark.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),  # still output to console
    ],
)
logger = logging.getLogger(__name__)
# -------------------------------------------------------------------


def submit_variants(file: Path, anyvar_host: str) -> None:
    with file.open("rb") as f:
        response = requests.put(
            f"{anyvar_host}/vcf",
            files={"vcf": (file.name, f, "text/plain")},
            params={
                "allow_async_write": True,
                "run_async": True,
                "require_validation": False,
            },
            timeout=60,
            headers={"accept": "application/json"},
        )
    logger.info("Submitting VCF to ingestion endpoint")
    response.raise_for_status()
    run_id = response.json()["run_id"]
    logger.info("Submission successful for %s", run_id)
    while True:
        logger.info("Polling ingestion status...")
        time.sleep(5)
        response = requests.get(f"{anyvar_host}/vcf/{run_id}")
        if response.json()["status"] != "PENDING":
            logger.info("Ingestion complete!")
            break


def process_file(filepath: Path) -> None:
    anyvar_host = "http://localhost:8000"
    start = timer()
    submit_variants(filepath, anyvar_host)
    end = timer()
    logger.info(f"Completed VCF submission of {filepath} in {end - start:.5f}")


@click.command()
@click.argument("filepaths", type=click.Path(exists=True, path_type=Path), nargs=-1)
@click.option(
    "--workers",
    type=int,
    default=4,
    show_default=True,
    help="Number of parallel workers",
)
def main(filepaths: tuple[Path], workers: int):
    logger.info("Received %s file(s):", len(filepaths))
    for fp in filepaths:
        logger.info("- %s", fp)
    logger.info("Using %s workers", workers)
    start = timer()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(process_file, filepaths))
    for result in results:
        logger.info(result)

    end = timer()
    duration = end - start
    logger.info(f"Completed ingest of {filepaths} in {duration:.5f}")


if __name__ == "__main__":
    main()
