# /// script
# dependencies = [
#   "requests",
#   "click",
#   "pysam",
# ]
# ///

import time
import json
from dataclasses import dataclass
from pathlib import Path

import click
import pysam
import requests


def submit_variants(file: Path, anyvar_host: str) -> None:
    run_id = 1234
    with file.open("rb") as f:
        response = requests.put(
            f"{anyvar_host}/annotated_vcf",
            files={"vcf": (file.name, f, "text/plain")},
            params={
                "allow_async_write": True,
                "run_async": True,
                "require_validation": False,
                "run_id": run_id,
            },
            timeout=60,
            headers={"accept": "application/json"},
        )
    click.echo("Submitting VCF to ingestion endpoint")
    response.raise_for_status()
    click.echo("Submission successful")
    while True:
        click.echo("Polling ingestion status...")
        time.sleep(5)
        response = requests.get(f"{anyvar_host}/vcf/{run_id}")
        if response.json()["status"] != "PENDING":
            click.echo("ingestion complete!")
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


def submit_annotation(vrs_id: str, annotation: Annotation, anyvar_host: str) -> None:
    response = requests.post(
        f"{anyvar_host}/variation/{vrs_id}/annotations", json=annotation.to_request()
    )
    response.raise_for_status()


def submit_annotations(vcf: Path, anyvar_host: str) -> None:
    click.echo("submitting annotations...")
    variantfile = pysam.VariantFile(vcf.absolute().as_posix())
    for record in variantfile:
        vrs_ids = record.info.get("VRS_Allele_IDs", [])
        if len(vrs_ids) < 2:
            continue  # skip if there are no ALT alleles or missing VRS IDs

        # Extract INFO fields per-allele (should align with ALT order)
        ac = record.info.get("AC", [])
        ac_hemi = record.info.get("AC_Hemi", [])
        ac_het = record.info.get("AC_Het", [])
        ac_hom = record.info.get("AC_Hom", [])
        af = record.info.get("AF", [])
        an = record.info.get("AN")

        # Loop over ALT alleles and their corresponding VRS ID (skipping index 0 == REF)
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
                continue  # skip if no meaningful data

            annotation = Annotation(
                annotation_type="allele_frequency_summary",
                value=json.dumps(annotation_value),
            )

            try:
                submit_annotation(vrs_id, annotation, anyvar_host)
            except requests.HTTPError as e:
                click.echo(f"Failed to submit annotation for {vrs_id}: {e}", err=True)
    click.echo("All annotations submitted")


@click.command()
@click.argument("filepath", type=click.Path(exists=True, path_type=Path))
def main(filepath):
    click.echo(f"Received file path: {filepath}")
    anyvar_host = "http://localhost:8000"
    submit_variants(filepath, anyvar_host)
    submit_annotations(filepath, anyvar_host)


if __name__ == "__main__":
    main()
