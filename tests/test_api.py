import json

from tests.base import BaseTest

from examples.example_etl import NothingEtl
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

    def test_submit_task(self):
        # Fakes
        self.governor.available_processing_capacity.value = 1
        self.governor.set_accepted_class(NothingEtl)

        task_doc = {"model_class": "NothingEtl"}

        rv = self.test_client.post(
            api_base_url + "task",
            data=json.dumps(task_doc),
            content_type="application/json",
        )
        self.assertEqual(200, rv.status_code)
        resp_doc = json.loads(rv.data)

        # just check a few expected fields are present
        self.assertTrue(
            resp_doc["_metadata"]["links"]["task"].startswith(
                "http://localhost.localdomain/api/0.01/task/"
            )
        )
        self.assertIn("governor_accepted_ident", resp_doc)
        self.assertIn("task_id", resp_doc)
