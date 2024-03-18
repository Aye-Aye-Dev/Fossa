from tests.base import BaseTest

from fossa.app import api_base_url


class TestWeb(BaseTest):
    def test_empty_api(self):
        resp = self.test_client.get(api_base_url)
        self.assertEqual(200, resp.status_code)
        self.assertEqual({"hello": "world"}, resp.json)

    def test_node_info(self):
        resp = self.test_client.get(api_base_url + "node_info")
        self.assertEqual(200, resp.status_code)

        # just check a couple of items
        self.assertIn("node_info", resp.json)
        self.assertIn("recent_completed_tasks", resp.json)

        node_info = resp.json["node_info"]
        self.assertIn("node_ident", node_info)
        self.assertIn("max_concurrent_tasks", node_info)
