import unittest

from fastapi.testclient import TestClient

from backend.main import app


class HealthTests(unittest.TestCase):
    def test_health_is_public(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
