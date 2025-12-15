# /// script  # noqa: D100
# dependencies = [
#   "requests",
#   "click",
# ]
#
# invoke with e.g. `uv run scripts/vcf_benchmark.py --workers 2 vcfs/vcf_1.vcf vcfs/vcf_2.vcf vcfs/vcf_3.vcf vcfs/vcf_4.vcf`
# ///

import logging
import time
from concurrent.futures import ProcessPoolExecutor
from enum import StrEnum
from functools import partial
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

HTTP_TIMEOUT = 120


def submit_variants(
    file: Path,
    anyvar_host: str,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    run_async: bool,
) -> None:
    with file.open("rb") as f:
        response = requests.put(
            f"{anyvar_host}/vcf",
            files={"vcf": (file.name, f, "text/plain")},
            params={
                "for_ref": for_ref,
                "allow_async_write": allow_async_write,
                "assembly": assembly,
                "run_async": run_async,
            },
            timeout=HTTP_TIMEOUT,
            headers={"accept": "application/json"},
        )
    logger.info("Submitting VCF to ingestion endpoint")
    response.raise_for_status()
    if run_async:
        run_id = response.json()["run_id"]
        logger.info("Submission successful for %s", run_id)
        while True:
            logger.info("Polling ingestion status...")
            time.sleep(5)
            response = requests.get(f"{anyvar_host}/vcf/{run_id}", timeout=HTTP_TIMEOUT)
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
                return
    # don't need to poll for sync response
    # timeouts should be expected for larger files though
    if response.text.startswith("##fileformat="):
        logger.info("Annotated VCF returned successfully")
    else:
        logger.info("Something has gone wrong: %s", response.text)


class AssemblyOption(StrEnum):
    GRCH38 = "GRCh38"
    GRCH37 = "GRCh37"


def process_file(
    filepath: Path,
    *,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    run_async: bool,
) -> None:
    anyvar_host = "http://localhost:8000"
    start = timer()
    submit_variants(
        filepath, anyvar_host, for_ref, allow_async_write, assembly, run_async
    )
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
@click.option("--for-ref", type=bool, default=True)
@click.option("--allow-async-write", type=bool, default=True)
@click.option("--assembly", type=click.Choice(AssemblyOption, case_sensitive=False))
@click.option("--run-async", type=bool, default=True)
def main(
    filepaths: tuple[Path],
    workers: int,
    for_ref: bool,
    allow_async_write: bool,
    assembly: str,
    run_async: bool,
):
    logger.info("Received %s file(s):", len(filepaths))
    for fp in filepaths:
        logger.info("- %s", fp)
    logger.info("Using %s workers", workers)
    start = timer()
    _process_file = partial(
        process_file,
        for_ref=for_ref,
        allow_async_write=allow_async_write,
        assembly=assembly,
        run_async=run_async,
    )
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_process_file, filepaths))
    for result in results:
        logger.info(result)

    end = timer()
    duration = end - start
    logger.info("Completed ingest of %s in %s", filepaths, f"{duration:.5f}")


if __name__ == "__main__":
    main()
