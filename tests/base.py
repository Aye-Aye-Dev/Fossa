import unittest

from fossa.settings.test_config import Config


class BaseTest(unittest.TestCase):
    """
    A unittest base class to use test config etc.
    """

    def setUp(self):
        """
        Set up each test
        """
        self.config = Config()

        from fossa.app import create_app

        self.app = create_app(self.config)

        self.test_client = self.app.test_client()

        self.request_context = self.app.test_request_context()
        self.request_context.push()

    def tearDown(self):
        self.request_context.pop()
