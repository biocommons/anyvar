# /// script
# dependencies = [
#   "requests",
#   "click",
#   "pysam",
# ]
# ///

import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from timeit import default_timer as timer

import click
import pysam
import requests

# -------------------------------------------------------------------
# Logging setup
# -------------------------------------------------------------------
LOG_FILE = "gregor_experiment.log"
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
            f"{anyvar_host}/annotated_vcf",
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
    logger.info(f"Submission successful for {run_id}")
    while True:
        logger.info("Polling ingestion status...")
        time.sleep(5)
        response = requests.get(f"{anyvar_host}/vcf/{run_id}")
        if response.json()["status"] != "PENDING":
            logger.info("Ingestion complete!")
            break


@dataclass
class Annotation:
    annotation_type: str
    value: str

    def to_request(self) -> dict:
        return {
            "annotation_type": self.annotation_type,
            "annotation": {"value": self.value},
        }


def submit_annotation(
    vrs_id: str, annotation: Annotation, anyvar_host: str, session: requests.Session
) -> None:
    response = session.post(
        f"{anyvar_host}/variation/{vrs_id}/annotations", json=annotation.to_request()
    )
    response.raise_for_status()


def submit_annotations(vcf: Path, anyvar_host: str) -> None:
    logger.info("Submitting annotations...")
    variantfile = pysam.VariantFile(vcf.absolute().as_posix())
    with requests.Session() as session:
        for record in variantfile:
            vrs_ids = record.info.get("VRS_Allele_IDs", [])
            if len(vrs_ids) < 2:
                continue  # skip if there are no ALT alleles or missing VRS IDs

            ac = record.info.get("AC", [])
            ac_hemi = record.info.get("AC_Hemi", [])
            ac_het = record.info.get("AC_Het", [])
            ac_hom = record.info.get("AC_Hom", [])
            af = record.info.get("AF", [])
            an = record.info.get("AN")

            for i, alt in enumerate(record.alts or []):
                try:
                    vrs_id = vrs_ids[i + 1]  # skip REF
                except IndexError:
                    continue  # inconsistent VRS_IDs array

                annotation_value = {
                    "AC": ac[i] if i < len(ac) else None,
                    "AC_Het": ac_het[i] if i < len(ac_het) else None,
                    "AC_Hom": ac_hom[i] if i < len(ac_hom) else None,
                    "AC_Hemi": ac_hemi[i] if i < len(ac_hemi) else None,
                    "AF": af[i] if i < len(af) else None,
                    "AN": an,
                }

                # Filter out None values
                annotation_value = {
                    k: v for k, v in annotation_value.items() if v is not None
                }

                if not annotation_value:
                    continue

                annotation = Annotation(
                    annotation_type="allele_frequency_summary",
                    value=json.dumps(annotation_value),
                )

                try:
                    submit_annotation(vrs_id, annotation, anyvar_host, session)
                except requests.HTTPError as e:
                    logger.error(f"Failed to submit annotation for {vrs_id}: {e}")
    logger.info("All annotations submitted")


def process_file(filepath: Path) -> None:
    anyvar_host = "http://localhost:8000"
    start = timer()
    submit_variants(filepath, anyvar_host)
    end = timer()
    logger.info(f"Completed VCF submission of {filepath} in {end - start:.5f}")
    start = timer()
    submit_annotations(filepath, anyvar_host)
    end = timer()
    logger.info(f"Completed annotations submission of {filepath} in {end - start:.5f}")


@click.command()
@click.argument("filepaths", type=click.Path(exists=True, path_type=Path), nargs=-1)
@click.option(
    "--workers",
    type=int,
    default=4,
    show_default=True,
    help="Number of parallel workers",
)
def main(filepaths, workers):
    logger.info(f"Received {len(filepaths)} file(s):")
    for fp in filepaths:
        logger.info(f"- {fp}")
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
