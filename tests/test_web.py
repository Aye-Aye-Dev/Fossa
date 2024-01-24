from tests.base import BaseTest


class TestWeb(BaseTest):
    def test_empty_root(self):
        resp = self.test_client.get("/")
        self.assertEqual(200, resp.status_code)
        self.assertIn("Fossa", str(resp.data))
