import json
import os
import re
import socket

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest  # noqa: E402
from django.conf import settings as django_settings  # noqa: E402
from webpack_loader import config as webpack_config  # noqa: E402
from webpack_loader.utils import get_loader  # noqa: E402

# Each Elm page: its elm-watch build and its webpack bundle.
ELM_PAGES = {"editor.js": "editor_elm", "leave_requests.js": "leave_requests"}


@pytest.fixture
def real_bundles(monkeypatch):
    """Serve the built bundles instead of the test settings' fake ones, for the Elm pages."""
    stats = django_settings.BASE_DIR / "webpack-stats.json"
    chunks = json.loads(stats.read_text()).get("chunks", {}) if stats.exists() else {}
    for build, bundle in ELM_PAGES.items():
        elm = django_settings.BASE_DIR / "radscheduler/static/elm-build" / build
        if not elm.exists() or bundle not in chunks:
            pytest.fail("The Elm pages aren't built; run `pnpm build` first.")
        # A build from `elm-watch hot` loads its code from elm-watch, so it only works while that runs.
        hot = re.search(r'webSocketPort":(\d+)', elm.read_text())
        if hot and socket.socket().connect_ex(("localhost", int(hot[1]))) != 0:
            pytest.fail(f"{build} is from `elm-watch hot`, which isn't running: run `pnpm build` first.")
    # django-webpack-loader reads its settings once, at import.
    real = {**webpack_config.user_config["DEFAULT"], "LOADER_CLASS": "webpack_loader.loaders.WebpackLoader"}
    monkeypatch.setitem(webpack_config.user_config, "DEFAULT", real)
    get_loader.cache_clear()
    yield
    get_loader.cache_clear()


def sign_in(page, live_server, username):
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='login']", username)
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
