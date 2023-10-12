"""Test VCF input/output features."""
import io
from http import HTTPStatus

import pytest


@pytest.fixture(scope="function")
def sample_vcf():
    """Basic VCF fixture to use in tests."""
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
    file = io.BytesIO(file_content)
    return file


def test_vcf_registration(client, sample_vcf):
    """Test registration and annotation of VCFs"""
    resp = client.put("/vcf", files={"vcf": ("test.vcf", sample_vcf)})
    assert resp.status_code == HTTPStatus.OK
    assert (
        b"VRS_Allele_IDs=ga4gh:VA.8MVWsPFeScEY_19U32k4LVI_3lEOKGUL,ga4gh:VA.l7crC9qxgcDtexejZkfp6yPNevEMnZ5y"
        in resp.content
    )
