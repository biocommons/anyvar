"""Test location lookup endpoint"""
# TODO pending resolution to issue 29 https://github.com/biocommons/anyvar/issues/29
# def test_location(client, alleles):
#     for allele in alleles.values():
#         expected_location = allele["response"]["object"]["location"]
#         print(f"/locations/{expected_location['sequence_id']}")
#         resp = client.get(f"/locations/{expected_location['sequence_id']}")
#         assert resp.status_code == 200
#         assert resp.json == expected_location
