# TEST CASES

# SUCCESS
# Make sure this is a mix of a) types of variants, and b) types of start/end coords (int vs Range) - ranges need to be for /vrs_variation endpoint ONLY, and c) positive and negative strands

# - /vrs_variation input that can be lifted over successfully from GRCH37 > GRCH38
# {
#     "type": "CopyNumberCount",
#     "location": {
#         "sequenceReference": {
#             "type": "SequenceReference",
#             "refgetAccession": "SQ.iy_UbUrvECxFRX5LPTH_KPojdlT7BKsf"
#         },
#         "start": [None, 29652251],
#         "end": [29981821, None],
#         "type": "SequenceLocation"
#     },
#     "copies": 3
# }
# ^ this is on GRCH37

# - /vrs_variation input that can be lifted over successfully from GRCH38 > GRCH37
# {
# 	"sequenceReference": {
# 		"type": "SequenceReference",
# 		"refgetAccession": "SQ.-A1QmD_MatoqxvgVxBLZTONHz9-c7nQo",
# 	},
# 	"start": [None, 30417575],
# 	"end": [31394018, None],
# 	"type": "SequenceLocation",
# }
# ^ This is on GRCH38

# - /variation input that can be lifted over successfully from GRCH37 > GRCH38
# NC_000007.13:g.140453136A>T
# ^ This is GRCH37, and on the Negative strand


# - /variation input that can be lifted over successfully from GRCH38 > GRCH37


# FAILURES

# - /vrs_variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly
# - /variation input that can NOT be lifted over successfully > where original location doesn't exist in the other reference assembly

# - don't need to liftover because we already have a stored liftaver annotation
# ^ Run any of the above a second time

# - case where initial registration failed and we don't have a vrs_id

# - case where the variant is on an unsupported assembly
# {
#     "type": "CopyNumberChange",
#     "location": {
#         "start": [15400349, 15414665],
#         "end": [16308334, 16345666],
#         "type": "SequenceLocation",
#         "sequenceReference": {
#             "type": "SequenceReference",
#             "refgetAccession": ...
#         },
#     },
#     "copyChange": "complete genomic loss"
# }
# ^ This is on GRCH36
