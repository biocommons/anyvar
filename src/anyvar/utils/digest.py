import base64
import collections
import hashlib

import canonicaljson


def sha512t_b64us(blob, tlen=24):
    return base64.urlsafe_b64encode(hashlib.sha512(blob).digest()[:tlen])


def vmc_digest2(o):
    if isinstance(o, collections.Mapping):
        b = canonicaljson.encode_canonical_json(o)
    elif isinstance(o, str):
        b = o.encode("ascii")
    else:
        raise RuntimeError("Don't know how to encode type " + str(type(o)))

    return sha512t_b64us(b).decode("ascii")


def vmc_identifer(prefix, o):
    return prefix + "_" + vmc_digest2(o)
