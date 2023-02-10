from ga4gh.core import ga4gh_identify
from ga4gh.vrs import models

from ..globals import get_anyvar


def put(body):
    request = body
    defn = request.pop("definition")

    av = get_anyvar()

    messages = []

    if "members" in defn:
        return {"messages": ["unsupported"]}, 400

    if "member_ids" in defn:
        vo = models.VariationSet(members=defn["member_ids"])
        vo._id = ga4gh_identify(vo)
        av.put_object(vo)

    result = {
        "messages": messages,
        "data": vo.as_dict(),
    }

    return result, 200


def get(id):
    av = get_anyvar()
    return av.get_object(id).as_dict(), 200
