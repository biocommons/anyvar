"""Test VCF input/output features."""

import io
import os
import pathlib
import time
from http import HTTPStatus

import pytest
from billiard.exceptions import TimeLimitExceeded
from celery.exceptions import WorkerLostError
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from anyvar.restapi.vcf import _working_file_cleanup


@pytest.fixture
def sample_vcf_grch38():
    """Basic GRCh38 VCF fixture to use in tests."""
    file_content = b"""##fileformat=VCFv4.2
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
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
chr1	10330	.	CCCCTAACCCTAACCCTAACCCTACCCTAACCCTAACCCTAACCCTAACCCTAA	C	.	PASS	QUALapprox=21493;SB=325,1077,113,694;MQ=32.1327;MQRankSum=0.720000;VarDP=2236;AS_ReadPosRankSum=-0.736000;AS_pab_max=1.00000;AS_QD=5.17857;AS_MQ=29.5449;QD=9.61225;AS_MQRankSum=0.00000;FS=8.55065;AS_FS=.;ReadPosRankSum=0.727000;AS_QUALapprox=145;AS_SB_TABLE=325,1077,2,5;AS_VarDP=28;AS_SOR=0.311749;SOR=1.48100;singleton;AS_VQSLOD=13.4641;InbreedingCoeff=-0.000517845"""
    return io.BytesIO(file_content)


def test_vcf_registration_default_assembly(
    restapi_client: TestClient, sample_vcf_grch38: io.BytesIO
):
    """Test registration and annotation of VCFs with default assembly"""
    resp = restapi_client.put("/vcf", files={"vcf": ("test.vcf", sample_vcf_grch38)})
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.5PqxTNMJZYJqQZ8MgF_77I1I_qcddGN_,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
        in resp.content
    )


def test_vcf_registration_vrs_attrs(
    restapi_client: TestClient, sample_vcf_grch38: io.BytesIO
):
    """Test optional inclusion of VRS attrs"""
    resp = restapi_client.put(
        "/vcf",
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
        params={"add_vrs_attributes": True},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Starts=10329,10330;VRS_Ends=10383,10392;VRS_States=,CCCTAACCC;VRS_Lengths=54,9;VRS_RepeatSubunitLengths=54,53"
        in resp.content
    )


def test_vcf_registration_grch38(
    restapi_client: TestClient, sample_vcf_grch38: io.BytesIO
):
    """Test registration and annotation of VCFs specifying GRCh38 as the assembly to use"""
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "GRCh38"},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.5PqxTNMJZYJqQZ8MgF_77I1I_qcddGN_,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
        in resp.content
    )


@pytest.fixture
def sample_vcf_grch37():
    """Basic GRCh37 VCF fixture to use in tests."""
    file_content = b"""##fileformat=VCFv4.2
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
##contig=<ID=11,length=248956422,assembly=GRCh37>
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO
11	47352948	.	TGAGAA	CCT	.	PASS	QUALapprox=21493;SB=325,1077,113,694;MQ=32.1327;MQRankSum=0.720000;VarDP=2236;AS_ReadPosRankSum=-0.736000;AS_pab_max=1.00000;AS_QD=5.17857;AS_MQ=29.5449;QD=9.61225;AS_MQRankSum=0.00000;FS=8.55065;AS_FS=.;ReadPosRankSum=0.727000;AS_QUALapprox=145;AS_SB_TABLE=325,1077,2,5;AS_VarDP=28;AS_SOR=0.311749;SOR=1.48100;singleton;AS_VQSLOD=13.4641;InbreedingCoeff=-0.000517845"""
    return io.BytesIO(file_content)


def test_vcf_registration_grch37(
    restapi_client: TestClient, sample_vcf_grch37: io.BytesIO
):
    """Test registration and annotation of VCFs with GRCh37 assembly"""
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "GRCh37"},
        files={"vcf": ("test.vcf", sample_vcf_grch37)},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.STbZFTK0grB7JO2cs3TCblpDiMjIMJWq,ga4gh:VA.CNSRLQlBrly3rRcdldN85dw2Tjos7Cas"
        in resp.content
    )


def test_vcf_registration_invalid_assembly(
    restapi_client: TestClient, sample_vcf_grch37: io.BytesIO
):
    """Test registration and annotation of VCFs with invalid assembly param value"""
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "hg19"},
        files={"vcf": ("test.vcf", sample_vcf_grch37)},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_vcf_registration_async(
    restapi_client: TestClient,
    sample_vcf_grch38: io.BytesIO,
    celery_context,  # noqa: ARG001
    vcf_run_id: str,
):
    """Test the async VCF annotation process using a real Celery worker and background task"""
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "GRCh38", "run_id": vcf_run_id, "run_async": True},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.ACCEPTED, resp.text
    assert "status_message" in resp.json()
    assert (
        resp.json()["status_message"]
        == f"Run submitted. Check status at /vcf/{vcf_run_id}"
    )
    assert "status" in resp.json()
    assert resp.json()["status"] == "PENDING"
    assert "run_id" in resp.json()
    assert resp.json()["run_id"] == vcf_run_id

    while True:
        resp = restapi_client.get(f"/vcf/{vcf_run_id}")
        if resp.status_code == HTTPStatus.ACCEPTED:
            time.sleep(1)
        elif resp.status_code == HTTPStatus.OK:
            break
        else:
            raise AssertionError(f"Unexpected HTTP response: {resp.status_code}")

    assert (
        b"VRS_Allele_IDs=ga4gh:VA.5PqxTNMJZYJqQZ8MgF_77I1I_qcddGN_,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
        in resp.content
    )


def test_vcf_submit_no_async(
    restapi_client: TestClient, sample_vcf_grch38: io.BytesIO, mocker: MockerFixture
):
    """Tests that a 400 is returned when async processing is not enabled"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "", "CELERY_BROKER_URL": ""}
    )
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "GRCh38", "run_id": "12345", "run_async": True},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in resp.json()
    assert (
        resp.json()["error"]
        == "Required modules and/or configurations for asynchronous VCF annotation are missing"
    )


def test_vcf_submit_duplicate_run_id(
    restapi_client: TestClient, sample_vcf_grch38: io.BytesIO, mocker: MockerFixture
):
    """Tests the submit VCF endpoint when there is already a run for the specified run id"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "SENT"
    resp = restapi_client.put(
        "/vcf",
        params={"assembly": "GRCh38", "run_id": "12345", "run_async": True},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in resp.json()
    assert (
        resp.json()["error"]
        == "An existing run with id 12345 is SENT. Fetch the completed run result before submitting with the same run_id."
    )


def test_vcf_get_result_no_async(restapi_client: TestClient, mocker: MockerFixture):
    """Tests that a 400 is returned when async processing is not enabled"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "", "CELERY_BROKER_URL": ""}
    )
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in resp.json()
    assert (
        resp.json()["error"]
        == "Required modules and/or configurations for asynchronous VCF annotation are missing"
    )


def test_vcf_get_result_success(restapi_client: TestClient, mocker: MockerFixture):
    """Tests the get async VCF result endpoint when annotation was successful"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "SUCCESS"
    mock_result.return_value.result = __file__
    mock_bg_tasks = mocker.patch("anyvar.restapi.vcf.BackgroundTasks.add_task")
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.OK
    with pathlib.Path(__file__).open(mode="rb") as fd:
        assert resp.content == fd.read()
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_with(_working_file_cleanup, __file__)


def test_vcf_get_result_failure_timeout(
    restapi_client: TestClient, mocker: MockerFixture
):
    """Tests the get async VCF result endpoint when annotation fails due to task timeout"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = TimeLimitExceeded("task timed out")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.vcf.BackgroundTasks.add_task")
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "error" in resp.json()
    assert resp.json()["error"] == "TimeLimitExceeded('task timed out',)"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "TIME_LIMIT_EXCEEDED"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_failure_worker_lost(
    restapi_client: TestClient, mocker: MockerFixture
):
    """Tests the get async VCF result endpoint when annotation failed due to lost worker"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = WorkerLostError("killed")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.vcf.BackgroundTasks.add_task")
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "error" in resp.json()
    assert resp.json()["error"] == "killed"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "WORKER_LOST_ERROR"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_failure_other(
    restapi_client: TestClient, mocker: MockerFixture
):
    """Tests the get async VCF result endpoint when annotation failed due to an error"""
    mocker.patch.dict(
        os.environ,
        {
            "ANYVAR_VCF_ASYNC_WORK_DIR": "./",
            "CELERY_BROKER_URL": "redis://",
            "ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE": "200",
        },
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = KeyError("foo")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.vcf.BackgroundTasks.add_task")
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.OK
    assert "error" in resp.json()
    assert resp.json()["error"] == "'foo'"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "RUN_FAILURE"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_notfound(restapi_client: TestClient, mocker: MockerFixture):
    """Tests the get async VCF result endpoint when run id is not found"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "PENDING"
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert "status_message" in resp.json()
    assert resp.json()["status_message"] == "Run not found"
    assert "status" in resp.json()
    assert resp.json()["status"] == "NOT_FOUND"
    assert "run_id" in resp.json()
    assert resp.json()["run_id"] == "12345"


def test_vcf_get_result_notcomplete(restapi_client: TestClient, mocker: MockerFixture):
    """Tests the get async VCF result endpoint when annotation is not yet complete"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.vcf.AsyncResult")
    mock_result.return_value.status = "SENT"
    resp = restapi_client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert "status_message" in resp.json()
    assert (
        resp.json()["status_message"] == "Run not completed. Check status at /vcf/12345"
    )
    assert "status" in resp.json()
    assert resp.json()["status"] == "PENDING"
    assert "run_id" in resp.json()
    assert resp.json()["run_id"] == "12345"
