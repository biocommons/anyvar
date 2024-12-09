"""Test VCF input/output features."""

import io
import os
import pathlib
import shutil
import time
from http import HTTPStatus

import pytest
from billiard.exceptions import TimeLimitExceeded
from celery.contrib.testing.worker import start_worker
from celery.exceptions import WorkerLostError

import anyvar.anyvar
from anyvar.queueing.celery_worker import celery_app


@pytest.fixture()
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


def test_vcf_registration_default_assembly(client, sample_vcf_grch38):
    """Test registration and annotation of VCFs with default assembly"""
    resp = client.put("/vcf", files={"vcf": ("test.vcf", sample_vcf_grch38)})
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
        in resp.content
    )


def test_vcf_registration_grch38(client, sample_vcf_grch38):
    """Test registration and annotation of VCFs specifying GRCh38 as the assembly to use"""
    resp = client.put(
        "/vcf",
        params={"assembly": "GRCh38"},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
        in resp.content
    )


@pytest.fixture()
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


def test_vcf_registration_grch37(client, sample_vcf_grch37):
    """Test registration and annotation of VCFs with GRCh37 assembly"""
    resp = client.put(
        "/vcf",
        params={"assembly": "GRCh37"},
        files={"vcf": ("test.vcf", sample_vcf_grch37)},
    )
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.iwk6beQfvJGkeW33NBbSqalr29XkDBE5,ga4gh:VA.CNSRLQlBrly3rRcdldN85dw2Tjos7Cas"
        in resp.content
    )


def test_vcf_registration_invalid_assembly(client, sample_vcf_grch37):
    """Test registration and annotation of VCFs with invalid assembly param value"""
    resp = client.put(
        "/vcf",
        params={"assembly": "hg19"},
        files={"vcf": ("test.vcf", sample_vcf_grch37)},
    )
    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_vcf_registration_async(client, sample_vcf_grch38, mocker):
    """Test the async VCF annotation process using a real Celery worker and background task"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "tests/tmp_async_work_dir"}
    )
    assert anyvar.anyvar.has_queueing_enabled(), "async vcf queueing is not enabled"
    with start_worker(
        celery_app,
        pool="solo",
        loglevel="info",
        perform_ping_check=False,
        shutdown_timeout=30,
    ):
        resp = client.put(
            "/vcf",
            params={"assembly": "GRCh38", "run_id": "12345", "run_async": True},
            files={"vcf": ("test.vcf", sample_vcf_grch38)},
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
        assert (
            b"VRS_Allele_IDs=ga4gh:VA.ryPubD68BB0D-D78L_kK4993mXmsNNWe,ga4gh:VA._QhHH18HBAIeLos6npRgR-S_0lAX5KR6"
            in resp.content
        )
        shutil.rmtree("tests/tmp_async_work_dir")


def test_vcf_submit_no_async(client, sample_vcf_grch38, mocker):
    """Tests that a 400 is returned when async processing is not enabled"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "", "CELERY_BROKER_URL": ""}
    )
    resp = client.put(
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


def test_vcf_submit_duplicate_run_id(client, sample_vcf_grch38, mocker):
    """Tests the submit VCF endpoint when there is already a run for the specified run id"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "SENT"
    resp = client.put(
        "/vcf",
        params={"assembly": "GRCh38", "run_id": "12345", "run_async": True},
        files={"vcf": ("test.vcf", sample_vcf_grch38)},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in resp.json()
    assert (
        resp.json()["error"]
        == "An existing run with id 12345 is SENT.  Fetch the completed run result before submitting with the same run_id."
    )


def test_vcf_get_result_no_async(client, mocker):
    """Tests that a 400 is returned when async processing is not enabled"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "", "CELERY_BROKER_URL": ""}
    )
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "error" in resp.json()
    assert (
        resp.json()["error"]
        == "Required modules and/or configurations for asynchronous VCF annotation are missing"
    )


def test_vcf_get_result_success(client, mocker):
    """Tests the get async VCF result endpoint when annotation was successful"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "SUCCESS"
    mock_result.return_value.result = __file__
    mock_bg_tasks = mocker.patch("anyvar.restapi.main.BackgroundTasks.add_task")
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.OK
    with pathlib.Path(__file__).open(mode="rb") as fd:
        assert resp.content == fd.read()
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_with(os.unlink, __file__)


def test_vcf_get_result_failure_timeout(client, mocker):
    """Tests the get async VCF result endpoint when annotation fails due to task timeout"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = TimeLimitExceeded("task timed out")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.main.BackgroundTasks.add_task")
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "error" in resp.json()
    assert resp.json()["error"] == "TimeLimitExceeded('task timed out',)"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "TIME_LIMIT_EXCEEDED"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_failure_worker_lost(client, mocker):
    """Tests the get async VCF result endpoint when annotation failed due to lost worker"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = WorkerLostError("killed")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.main.BackgroundTasks.add_task")
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "error" in resp.json()
    assert resp.json()["error"] == "killed"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "WORKER_LOST_ERROR"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_failure_other(client, mocker):
    """Tests the get async VCF result endpoint when annotation failed due to an error"""
    mocker.patch.dict(
        os.environ,
        {
            "ANYVAR_VCF_ASYNC_WORK_DIR": "./",
            "CELERY_BROKER_URL": "redis://",
            "ANYVAR_VCF_ASYNC_FAILURE_STATUS_CODE": "200",
        },
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "FAILURE"
    mock_result.return_value.result = KeyError("foo")
    mock_result.return_value.kwargs = {"input_file_path": __file__}
    mock_bg_tasks = mocker.patch("anyvar.restapi.main.BackgroundTasks.add_task")
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.OK
    assert "error" in resp.json()
    assert resp.json()["error"] == "'foo'"
    assert "error_code" in resp.json()
    assert resp.json()["error_code"] == "RUN_FAILURE"
    mock_result.return_value.forget.assert_called_once()
    mock_bg_tasks.assert_called_once()


def test_vcf_get_result_notfound(client, mocker):
    """Tests the get async VCF result endpoint when run id is not found"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "PENDING"
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert "status_message" in resp.json()
    assert resp.json()["status_message"] == "Run not found"
    assert "status" in resp.json()
    assert resp.json()["status"] == "NOT_FOUND"
    assert "run_id" in resp.json()
    assert resp.json()["run_id"] == "12345"


def test_vcf_get_result_notcomplete(client, mocker):
    """Tests the get async VCF result endpoint when annotation is not yet complete"""
    mocker.patch.dict(
        os.environ, {"ANYVAR_VCF_ASYNC_WORK_DIR": "./", "CELERY_BROKER_URL": "redis://"}
    )
    mock_result = mocker.patch("anyvar.restapi.main.AsyncResult")
    mock_result.return_value.status = "SENT"
    resp = client.get("/vcf/12345")
    assert resp.status_code == HTTPStatus.ACCEPTED
    assert "status_message" in resp.json()
    assert (
        resp.json()["status_message"] == "Run not completed. Check status at /vcf/12345"
    )
    assert "status" in resp.json()
    assert resp.json()["status"] == "PENDING"
    assert "run_id" in resp.json()
    assert resp.json()["run_id"] == "12345"
