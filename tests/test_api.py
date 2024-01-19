from tests.base import BaseTest

from fossa.app import api_base_url


class TestWeb(BaseTest):
    def test_empty_api(self):
        resp = self.test_client.get(api_base_url)
        self.assertEqual(200, resp.status_code)
        self.assertEqual({"hello": "world"}, resp.json)
