"""Test ingestion of VCF that already contains VRS annotations."""

import io
import shutil
import time
from http import HTTPStatus

import pytest
from celery.contrib.testing.worker import start_worker
from celery.result import AsyncResult
from fastapi.testclient import TestClient

from anyvar.queueing.celery_worker import celery_app


@pytest.fixture
def basic_vcf():
    file_contents = b"""##fileformat=VCFv4.2
##FILTER=<ID=PASS,Description="All filters passed">
##hailversion=0.2.100-2ea2615a797a
##INFO=<ID=QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=SB,Number=.,Type=Integer,Description="">
##INFO=<ID=MQ,Number=1,Type=Float,Description="">
##INFO=<ID=MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_pab_max,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQ,Number=1,Type=Float,Description="">
##INFO=<ID=QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=FS,Number=1,Type=Float,Description="">
##INFO=<ID=AS_FS,Number=1,Type=Float,Description="">
##INFO=<ID=ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SB_TABLE,Number=.,Type=Integer,Description="">
##INFO=<ID=AS_VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SOR,Number=1,Type=Float,Description="">
##INFO=<ID=SOR,Number=1,Type=Float,Description="">
##INFO=<ID=singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=transmitted_singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=omni,Number=0,Type=Flag,Description="">
##INFO=<ID=mills,Number=0,Type=Flag,Description="">
##INFO=<ID=monoallelic,Number=0,Type=Flag,Description="">
##INFO=<ID=AS_VQSLOD,Number=1,Type=Float,Description="">
##INFO=<ID=InbreedingCoeff,Number=1,Type=Float,Description="">
##FILTER=<ID=AC0,Description="Allele count is zero after filtering out low-confidence genotypes (GQ < 20; DP < 10; and AB < 0.2 for het calls)">
##FILTER=<ID=AS_VQSR,Description="Failed VQSR filtering thresholds of -2.7739 for SNPs and -1.0606 for indels">
##contig=<ID=chr1,length=248956422,assembly=GRCh38>
##INFO=<ID=VRS_Allele_IDs,Number=R,Type=String,Description="The computed identifiers for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles [VRS version=2.0.1;VRS-Python version=2.1.2]">
##INFO=<ID=VRS_Error,Number=.,Type=String,Description="If an error occurred computing a VRS Identifier, the error message">
##INFO=<ID=VRS_Starts,Number=R,Type=Integer,Description="Interresidue coordinates used as the location starts for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
##INFO=<ID=VRS_Ends,Number=R,Type=Integer,Description="Interresidue coordinates used as the location ends for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
##INFO=<ID=VRS_States,Number=R,Type=String,Description="The literal sequence states used for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	10330	.	CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA	C	.	PASS	QUALapprox=21493;SB=325,1077,113,694;MQ=32.1327;MQRankSum=0.72;VarDP=2236;AS_ReadPosRankSum=-0.736;AS_pab_max=1;AS_QD=5.17857;AS_MQ=29.5449;QD=9.61225;AS_MQRankSum=0;FS=8.55065;AS_FS=.;ReadPosRankSum=0.727;AS_QUALapprox=145;AS_SB_TABLE=325,1077,2,5;AS_VarDP=28;AS_SOR=0.311749;SOR=1.481;singleton;AS_VQSLOD=13.4641;InbreedingCoeff=-0.000517845;VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6;VRS_Starts=10329,10330;VRS_Ends=10383,10392;VRS_States=CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA,CCCTAACCC"""
    return io.BytesIO(file_contents)


@pytest.fixture
def vcf_incorrect_id():
    file_contents = b"""##fileformat=VCFv4.2
##FILTER=<ID=PASS,Description="All filters passed">
##hailversion=0.2.100-2ea2615a797a
##INFO=<ID=QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=SB,Number=.,Type=Integer,Description="">
##INFO=<ID=MQ,Number=1,Type=Float,Description="">
##INFO=<ID=MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_pab_max,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQ,Number=1,Type=Float,Description="">
##INFO=<ID=QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=FS,Number=1,Type=Float,Description="">
##INFO=<ID=AS_FS,Number=1,Type=Float,Description="">
##INFO=<ID=ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SB_TABLE,Number=.,Type=Integer,Description="">
##INFO=<ID=AS_VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SOR,Number=1,Type=Float,Description="">
##INFO=<ID=SOR,Number=1,Type=Float,Description="">
##INFO=<ID=singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=transmitted_singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=omni,Number=0,Type=Flag,Description="">
##INFO=<ID=mills,Number=0,Type=Flag,Description="">
##INFO=<ID=monoallelic,Number=0,Type=Flag,Description="">
##INFO=<ID=AS_VQSLOD,Number=1,Type=Float,Description="">
##INFO=<ID=InbreedingCoeff,Number=1,Type=Float,Description="">
##FILTER=<ID=AC0,Description="Allele count is zero after filtering out low-confidence genotypes (GQ < 20; DP < 10; and AB < 0.2 for het calls)">
##FILTER=<ID=AS_VQSR,Description="Failed VQSR filtering thresholds of -2.7739 for SNPs and -1.0606 for indels">
##contig=<ID=chr1,length=248956422,assembly=GRCh38>
##INFO=<ID=VRS_Allele_IDs,Number=R,Type=String,Description="The computed identifiers for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles [VRS version=2.0.1;VRS-Python version=2.1.2]">
##INFO=<ID=VRS_Error,Number=.,Type=String,Description="If an error occurred computing a VRS Identifier, the error message">
##INFO=<ID=VRS_Starts,Number=R,Type=Integer,Description="Interresidue coordinates used as the location starts for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
##INFO=<ID=VRS_Ends,Number=R,Type=Integer,Description="Interresidue coordinates used as the location ends for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
##INFO=<ID=VRS_States,Number=R,Type=String,Description="The literal sequence states used for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	10330	.	CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA	C	.	PASS	QUALapprox=21493;SB=325,1077,113,694;MQ=32.1327;MQRankSum=0.72;VarDP=2236;AS_ReadPosRankSum=-0.736;AS_pab_max=1;AS_QD=5.17857;AS_MQ=29.5449;QD=9.61225;AS_MQRankSum=0;FS=8.55065;AS_FS=.;ReadPosRankSum=0.727;AS_QUALapprox=145;AS_SB_TABLE=325,1077,2,5;AS_VarDP=28;AS_SOR=0.311749;SOR=1.481;singleton;AS_VQSLOD=13.4641;InbreedingCoeff=-0.000517845;VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6z;VRS_Starts=10329,10330;VRS_Ends=10383,10392;VRS_States=CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA,CCCTAACCC"""
    return io.BytesIO(file_contents)


@pytest.fixture
def vcf_incomplete_annotations():
    file_contents = b"""##fileformat=VCFv5.2
##FILTER=<ID=PASS,Description="All filters passed">
##hailversion=0.2.100-2ea2615a797a
##INFO=<ID=QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=SB,Number=.,Type=Integer,Description="">
##INFO=<ID=MQ,Number=1,Type=Float,Description="">
##INFO=<ID=MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_pab_max,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQ,Number=1,Type=Float,Description="">
##INFO=<ID=QD,Number=1,Type=Float,Description="">
##INFO=<ID=AS_MQRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=FS,Number=1,Type=Float,Description="">
##INFO=<ID=AS_FS,Number=1,Type=Float,Description="">
##INFO=<ID=ReadPosRankSum,Number=1,Type=Float,Description="">
##INFO=<ID=AS_QUALapprox,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SB_TABLE,Number=.,Type=Integer,Description="">
##INFO=<ID=AS_VarDP,Number=1,Type=Integer,Description="">
##INFO=<ID=AS_SOR,Number=1,Type=Float,Description="">
##INFO=<ID=SOR,Number=1,Type=Float,Description="">
##INFO=<ID=singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=transmitted_singleton,Number=0,Type=Flag,Description="">
##INFO=<ID=omni,Number=0,Type=Flag,Description="">
##INFO=<ID=mills,Number=0,Type=Flag,Description="">
##INFO=<ID=monoallelic,Number=0,Type=Flag,Description="">
##INFO=<ID=AS_VQSLOD,Number=1,Type=Float,Description="">
##INFO=<ID=InbreedingCoeff,Number=1,Type=Float,Description="">
##FILTER=<ID=AC0,Description="Allele count is zero after filtering out low-confidence genotypes (GQ < 20; DP < 10; and AB < 0.2 for het calls)">
##FILTER=<ID=AS_VQSR,Description="Failed VQSR filtering thresholds of -2.7739 for SNPs and -1.0606 for indels">
##contig=<ID=chr1,length=248956422,assembly=GRCh38>
##INFO=<ID=VRS_Allele_IDs,Number=R,Type=String,Description="The computed identifiers for the GA4GH VRS Alleles corresponding to the GT indexes of the REF and ALT alleles [VRS version=2.0.1;VRS-Python version=2.1.2]">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	10330	.	CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA	C	.	PASS	QUALapprox=21493;SB=325,1077,113,694;MQ=32.1327;MQRankSum=0.72;VarDP=2236;AS_ReadPosRankSum=-0.736;AS_pab_max=1;AS_QD=5.17857;AS_MQ=29.5449;QD=9.61225;AS_MQRankSum=0;FS=8.55065;AS_FS=.;ReadPosRankSum=0.727;AS_QUALapprox=145;AS_SB_TABLE=325,1077,2,5;AS_VarDP=28;AS_SOR=0.311749;SOR=1.481;singleton;AS_VQSLOD=13.4641;InbreedingCoeff=-0.000517845;VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"""
    return io.BytesIO(file_contents)


def test_registration_sync(
    monkeypatch, client: TestClient, basic_vcf: io.BytesIO, vcf_incorrect_id: io.BytesIO
):
    """Test basic file registration, synchronous + no validation"""
    recorded = []
    monkeypatch.setattr(
        client.app.state.anyvar,
        "put_objects",
        lambda allele_list: recorded.extend(allele_list),
    )
    resp = client.put("/annotated_vcf", files={"vcf": ("test.vcf", basic_vcf)})

    assert resp.status_code == HTTPStatus.OK
    assert recorded, "put_objects was never called"
    assert recorded[0].id == "ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe"
    assert recorded[1].id == "ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"

    # ignore wrong IDs
    resp = client.put("/annotated_vcf", files={"vcf": ("test.vcf", vcf_incorrect_id)})

    assert resp.status_code == HTTPStatus.OK
    assert recorded, "put_objects was never called"
    assert recorded[2].id == "ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe"
    assert recorded[3].id == "ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"


def test_registration_sync_validate(
    monkeypatch,
    client: TestClient,
    basic_vcf: io.BytesIO,
    vcf_incorrect_id: io.BytesIO,
):
    """Test basic file registration, synchronous + validation"""
    recorded = []
    monkeypatch.setattr(
        client.app.state.anyvar,
        "put_objects",
        lambda allele_list: recorded.extend(allele_list),
    )
    resp = client.put(
        "/annotated_vcf",
        files={"vcf": ("test.vcf", basic_vcf)},
        params={"require_validation": True},
    )

    assert resp.status_code == HTTPStatus.OK
    assert recorded, "put_objects was never called"
    assert recorded[0].id == "ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe"
    assert recorded[1].id == "ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
    assert resp.content.count(b"\n") == 1  # just header

    # handle wrong ID
    resp = client.put(
        "/annotated_vcf",
        files={"vcf": ("test.vcf", vcf_incorrect_id)},
        params={"require_validation": True},
    )

    assert resp.status_code == HTTPStatus.OK
    assert recorded, "put_objects was never called"
    assert recorded[0].id == "ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe"
    # use correct ID (it's wrong in the input)
    assert recorded[1].id == "ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
    assert resp.content.count(b"\n") == 2
    assert b"ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6z" in resp.content


def test_registration_async(
    monkeypatch,
    client: TestClient,
    basic_vcf: io.BytesIO,
    vcf_incorrect_id: io.BytesIO,
):
    """Test async file registration"""

    monkeypatch.setenv("ANYVAR_VCF_ASYNC_WORK_DIR", "tests/tmp_async_work_dir")
    with start_worker(
        celery_app,
        pool="solo",
        loglevel="info",
        perform_ping_check=False,
        shutdown_timeout=30,
    ):
        run_id = 12345

        celery_app.control.purge()
        AsyncResult(f"{run_id}").forget()

        resp = client.put(
            "/annotated_vcf",
            files={"vcf": ("test.vcf", basic_vcf)},
            params={"run_async": True, "run_id": run_id},
        )
        assert resp.status_code == HTTPStatus.ACCEPTED
        assert "status_message" in resp.json()
        assert (
            resp.json()["status_message"]
            == f"Run submitted. Check status at /vcf/{run_id}"
        )
        assert "status" in resp.json()
        assert resp.json()["status"] == "PENDING"
        assert "run_id" in resp.json()
        assert resp.json()["run_id"] == f"{run_id}"

        time.sleep(5)

        resp = client.get(f"/vcf/{run_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["status"] == "SUCCESS"

        resp = client.put(
            "/annotated_vcf",
            files={"vcf": ("test.vcf", vcf_incorrect_id)},
            params={"run_async": True, "run_id": run_id},
        )

        assert resp.status_code == HTTPStatus.ACCEPTED
        assert "status_message" in resp.json()
        assert (
            resp.json()["status_message"]
            == f"Run submitted. Check status at /vcf/{run_id}"
        )
        assert "status" in resp.json()
        assert resp.json()["status"] == "PENDING"
        assert "run_id" in resp.json()
        assert resp.json()["run_id"] == f"{run_id}"

        time.sleep(5)

        resp = client.get(f"/vcf/{run_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["status"] == "SUCCESS"

        shutil.rmtree("tests/tmp_async_work_dir")


def test_registration_async_validate(
    monkeypatch,
    client: TestClient,
    basic_vcf: io.BytesIO,
):
    """Test file registration, asynchronous + validation"""
    monkeypatch.setenv("ANYVAR_VCF_ASYNC_WORK_DIR", "tests/tmp_async_work_dir")

    with start_worker(
        celery_app,
        pool="solo",
        loglevel="info",
        perform_ping_check=False,
        shutdown_timeout=30,
    ):
        run_id = 12345
        resp = client.put(
            "/annotated_vcf",
            files={"vcf": ("test.vcf", basic_vcf)},
            params={"require_validation": True, "run_async": True, "run_id": run_id},
        )
        assert resp.status_code == HTTPStatus.ACCEPTED
        assert "status_message" in resp.json()
        assert (
            resp.json()["status_message"]
            == f"Run submitted. Check status at /vcf/{run_id}"
        )
        assert "status" in resp.json()
        assert resp.json()["status"] == "PENDING"
        assert "run_id" in resp.json()
        assert resp.json()["run_id"] == f"{run_id}"

        time.sleep(5)

        resp = client.get(f"/vcf/{run_id}")
        assert resp.status_code == HTTPStatus.OK
        assert resp.content.count(b"\n") == 1  # just header

        shutil.rmtree("tests/tmp_async_work_dir")


def test_registration_async_validate_wrongid(
    vcf_incorrect_id: io.BytesIO,
    client: TestClient,
    monkeypatch,
):
    """Test file registration, asynchronous + validation of a file with a wrong ID"""
    monkeypatch.setenv("ANYVAR_VCF_ASYNC_WORK_DIR", "tests/tmp_async_work_dir")

    with start_worker(
        celery_app,
        pool="solo",
        loglevel="info",
        perform_ping_check=False,
        shutdown_timeout=30,
    ):
        run_id = 12345
        resp = client.put(
            "/annotated_vcf",
            files={"vcf": ("test.vcf", vcf_incorrect_id)},
            params={"require_validation": True, "run_async": True, "run_id": run_id},
        )

        assert resp.status_code == HTTPStatus.ACCEPTED
        assert "status_message" in resp.json()
        assert (
            resp.json()["status_message"] == "Run submitted. Check status at /vcf/12345"
        )
        assert "status" in resp.json()
        assert resp.json()["status"] == "PENDING"
        assert "run_id" in resp.json()
        assert resp.json()["run_id"] == "12345"

        time.sleep(5)

        resp = client.get("/vcf/12345")
        assert resp.status_code == HTTPStatus.OK
        assert b"ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6z" in resp.content

        shutil.rmtree("tests/tmp_async_work_dir")


def test_handle_incomplete_annotation(
    client: TestClient, vcf_incomplete_annotations: io.BytesIO
):
    """Test that client gracefully handles an incompletely-annotated VCF"""
    resp = client.put(
        "/annotated_vcf", files={"vcf": ("test.vcf", vcf_incomplete_annotations)}
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "Required VRS annotations are missing" in resp.json()["error"]
