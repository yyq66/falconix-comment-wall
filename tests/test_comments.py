import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


class CommentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.url = "sqlite:///" + (Path(cls.temp.name) / "wall.db").as_posix()
        cls.app = create_app(cls.url, seed_demo=False)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()
        cls.client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"})
        cls.a_cookie = dict(cls.client.cookies)
        cls.client.post("/api/auth/login", json={"username": "demo_b", "password": "Wall2027!"})
        cls.b_cookie = dict(cls.client.cookies)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    def setUp(self):
        self.client.cookies.clear()
        # The second login replaced the previous session, so obtain an independent session for A.
        self.client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"})

    def create(self, content="<p>一条建议</p>", **kwargs):
        return self.client.post("/api/comments", json={"content_html": content, "x": 420, "y": 200, "request_id": str(uuid.uuid4()), **kwargs})

    def own_comment(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        return response.json()["comments"][-1]

    def test_authentication_required(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/board").status_code, 401)
        self.assertEqual(self.create().status_code, 401)

    def test_rich_text_is_sanitized_and_persisted(self):
        id = str(uuid.uuid4())
        result = self.create('<p onclick="bad()"><strong>更好</strong><script>alert(1)</script><img src="x" onerror="bad()">的建议</p>', request_id=id)
        comment = next(c for c in result.json()["comments"] if c["id"] == id)
        self.assertEqual(comment["content_html"], "<p><strong>更好</strong>的建议</p>")
        self.assertEqual(comment["text"], "更好的建议")
        with TestClient(create_app(self.url, seed_demo=False)) as restored:
            restored.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"})
            saved = next(c for c in restored.get("/api/board").json()["comments"] if c["id"] == id)
            self.assertEqual(saved, comment)

    def test_create_retry_is_idempotent(self):
        id = str(uuid.uuid4())
        first = self.create(request_id=id).json()
        second = self.create(request_id=id).json()
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual(len([c for c in second["comments"] if c["id"] == id]), 1)

    def test_validation_rejects_empty_long_and_invalid_coordinates(self):
        for content in ["<p> </p>", "<p>\u200b</p>", "<p>" + "字" * 1001 + "</p>"]:
            self.assertEqual(self.create(content).status_code, 422)
        self.assertEqual(self.create(x=-5).status_code, 422)

    def test_others_cannot_edit_even_via_direct_api(self):
        comment = self.own_comment()
        self.client.cookies.clear()
        self.client.cookies.update(self.b_cookie)
        result = self.client.patch(f'/api/comments/{comment["id"]}/content', json={"content_html": "<p>不该修改</p>", "content_version": 1})
        self.assertEqual(result.status_code, 403)

    def test_optimistic_version_prevents_silent_overwrite(self):
        comment = self.own_comment()
        url = f'/api/comments/{comment["id"]}/content'
        self.assertEqual(self.client.patch(url, json={"content_html": "<p>新版本</p>", "content_version": 1}).status_code, 200)
        self.assertEqual(self.client.patch(url, json={"content_html": "<p>旧版本覆盖</p>", "content_version": 1}).status_code, 409)
