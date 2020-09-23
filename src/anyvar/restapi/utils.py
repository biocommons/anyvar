import re


def replace_dollar_ref(openapi_yaml, ref_map):
    """replace $ref values with filesystem paths

    The resolver used by connexion doesn't handle relative paths in
    files. This function replaces all $ref values that have a
    corresponding entry in ref_map.

      $ref: "file:///vr.json#/definitions/Allele"

    """

    ref_re = re.compile(r"""^(\s+\$ref:\s+["']file:)(\w[^#]+)(#)""", re.MULTILINE)
    return ref_re.sub(lambda m: m.group(1) + "//" + ref_map[m.group(2)] + m.group(3), openapi_yaml)
