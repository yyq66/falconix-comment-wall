import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = create_app("sqlite:///" + (Path(cls.temp.name) / "interactions.db").as_posix(), seed_demo=False)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()
        cls.client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"})
        cls.cookies_a = dict(cls.client.cookies)
        cls.client.cookies.clear()
        cls.client.post("/api/auth/login", json={"username": "demo_b", "password": "Wall2027!"})
        cls.cookies_b = dict(cls.client.cookies)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    def setUp(self):
        self.client.cookies.clear()
        self.client.cookies.update(self.cookies_a)
        self.id = str(uuid.uuid4())
        self.client.post("/api/comments", json={"request_id": self.id, "content_html": "<p>拖动和点赞测试</p>", "x": 120, "y": 200})

    def note(self, response):
        return next(n for n in response.json()["comments"] if n["id"] == self.id)

    def test_move_saved_without_overwriting_recent_content(self):
        self.client.patch(f"/api/comments/{self.id}/content", json={"content_html": "<p>更新的正文</p>", "content_version": 1})
        response = self.client.patch(f"/api/comments/{self.id}/position", json={"x": 780, "y": 470, "position_version": 1})
        self.assertEqual(response.status_code, 200)
        note = self.note(self.client.get("/api/board"))
        self.assertEqual((note["x"], note["y"], note["text"]), (780, 470, "更新的正文"))
        self.assertEqual(note["position_version"], 2)
        stale = self.client.patch(f"/api/comments/{self.id}/position", json={"x": 100, "y": 200, "position_version": 1})
        self.assertEqual(stale.status_code, 409)

    def test_other_user_cannot_move_or_edit(self):
        self.client.cookies.clear()
        self.client.cookies.update(self.cookies_b)
        response = self.client.patch(f"/api/comments/{self.id}/position", json={"x": 700, "y": 300, "position_version": 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.note(self.client.get("/api/board"))["x"], 120)

    def test_like_is_unique_retries_are_idempotent_and_can_be_cancelled(self):
        url = f"/api/comments/{self.id}/like"
        one = self.client.put(url, json={"liked": True})
        again = self.client.put(url, json={"liked": True})
        self.assertEqual(self.note(again)["liked_by"], ["user-a"])
        self.assertEqual(one.json()["revision"], again.json()["revision"])
        self.client.cookies.clear()
        self.client.cookies.update(self.cookies_b)
        both = self.client.put(url, json={"liked": True})
        self.assertEqual(self.note(both)["liked_by"], ["user-a", "user-b"])
        cancelled = self.client.put(url, json={"liked": False})
        self.assertEqual(self.note(cancelled)["liked_by"], ["user-a"])

    def test_move_invalid_coordinates_and_missing_note(self):
        self.assertEqual(self.client.patch(f"/api/comments/{self.id}/position", json={"x": 6000, "y": 300, "position_version": 1}).status_code, 422)
        self.assertEqual(self.client.put("/api/comments/missing/like", json={"liked": True}).status_code, 404)

    def test_edit_reclassifies_and_keeps_shared_position(self):
        url = f"/api/comments/{self.id}/content"
        positive = self.client.patch(url, json={"content_html": "<p>感谢，非常好用</p>", "content_version": 1})
        self.assertEqual(self.note(positive)["sentiment"], "positive")
        negative = self.client.patch(url, json={"content_html": "<p>失望，太难用了</p>", "content_version": 2})
        note = self.note(negative)
        self.assertEqual(note["sentiment"], "negative")
        self.assertEqual((note["x"], note["y"]), (120, 200))
