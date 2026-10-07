import json

from django.conf import settings
from ninja.responses import NinjaJSONEncoder

from radscheduler.core.api import api


def test_elm_client_is_generated_from_the_current_api():
    """
    The Elm editor's API client is generated from the committed schema. If the API changes, regenerate it so
    the Elm types and decoders match what Django sends.
    """
    committed = json.loads((settings.BASE_DIR / "radscheduler/static/elm/openapi.json").read_text())
    current = json.loads(json.dumps(api.get_openapi_schema(), cls=NinjaJSONEncoder))

    assert current == committed, "The API has changed: run `devenv shell -- elm:api` and commit the result."
