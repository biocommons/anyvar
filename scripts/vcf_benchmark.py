# /// script  # noqa: D100
# dependencies = [
#   "requests",
#   "click",
# ]
# ///

import logging
import time
from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from pathlib import Path
from timeit import default_timer as timer

import click
import requests

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
        try:
            if response.json()["status"] != "PENDING":
                logger.info("Ingestion complete!")
                break
        except JSONDecodeError:
            # presumably a successful response
            if response.text.startswith("##fileformat="):
                logger.info("Annotated VCF returned successfully")
            else:
                filename = f"vcf_benchmark_output_{run_id}"
                with Path(filename).open("w") as f:
                    f.write(response.text)
                logger.info(
                    "Received malformed response from vcf run ID lookup. Saved to %s",
                    filename,
                )
            break


def process_file(filepath: Path) -> None:
    anyvar_host = "http://localhost:8000"
    start = timer()
    submit_variants(filepath, anyvar_host)
    end = timer()
    logger.info("Completed VCF submission of %s in %s", filepath, f"{end - start:.5f}")


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
    logger.info("Completed ingest of %s in %s", filepaths, f"{duration:.5f}")


if __name__ == "__main__":
    main()
