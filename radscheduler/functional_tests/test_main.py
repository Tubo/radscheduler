import pytest
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django_functest import FuncBaseMixin, FuncSeleniumMixin, FuncWebTestMixin
from selenium import webdriver

pytestmark = pytest.mark.django_db


class WebTestBase(FuncWebTestMixin, TestCase):
    def setUp(self):
        super(WebTestBase, self).setUp()  # Remember to call this!
        # Your custom stuff here etc.


class SeleniumTestBase(FuncSeleniumMixin, StaticLiveServerTestCase):
    host = "django"
    driver_name = "Remote"

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        # This allows the test case to use webpack dev server in testing
        settings.WEBPACK_LOADER["DEFAULT"] = {
            "DEFAULT": {
                "CACHE": not settings.DEBUG,
                "STATS_FILE": settings.BASE_DIR / "webpack-stats.json",
                "POLL_INTERVAL": 0.1,
                "IGNORE": [r".+\.hot-update.js", r".+\.map"],
            }
        }

    @classmethod
    def get_webdriver_options(cls):
        # Use remote webdriver
        return {"command_executor": "http://firefox:4444/wd/hub", "options": webdriver.FirefoxOptions()}


class ContactFormSeleniumTests(SeleniumTestBase):
    def test_foo(self):
        self.get_url("home")
        self.assertTextPresent("Leaves")
