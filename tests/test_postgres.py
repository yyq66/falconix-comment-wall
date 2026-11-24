import os
import unittest
import uuid

from fastapi.testclient import TestClient

from backend.main import create_app


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "PostgreSQL integration runs in CI with a dedicated test database")
class PostgresTests(unittest.TestCase):
    def test_production_database_and_realtime_round_trip(self):
        url = os.environ["TEST_DATABASE_URL"]
        with TestClient(create_app(url)) as client:
            self.assertEqual(client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"}).status_code, 200)
            self.assertGreaterEqual(len(client.get("/api/board").json()["comments"]), 8)
            with client.websocket_connect("/api/ws") as ws:
                self.assertEqual(ws.receive_json()["type"], "board")
                self.assertEqual(ws.receive_json()["type"], "presence")
                id = str(uuid.uuid4())
                created = client.post("/api/comments", json={"request_id": id, "content_html": "<p><strong>PostgreSQL 很好用</strong></p>", "x": 330, "y": 250})
                self.assertEqual(created.status_code, 200, created.text)
                pushed = ws.receive_json()
                self.assertEqual(pushed["board"], created.json())
                note = next(n for n in created.json()["comments"] if n["id"] == id)
                self.assertGreater(note["created_at"], 2**31)
                self.assertEqual(note["sentiment"], "positive")
                self.assertEqual(client.patch(f"/api/comments/{id}/content", json={"content_html": "<p>PostgreSQL 数据保存</p>", "content_version": 1}).status_code, 200)
                self.assertEqual(ws.receive_json()["type"], "board")
                self.assertEqual(client.patch(f"/api/comments/{id}/position", json={"x": 700, "y": 500, "position_version": 1}).status_code, 200)
                self.assertEqual(ws.receive_json()["type"], "board")
                self.assertEqual(client.put(f"/api/comments/{id}/like", json={"liked": True}).status_code, 200)
                self.assertEqual(ws.receive_json()["type"], "board")
        with TestClient(create_app(url)) as reopened:
            reopened.post("/api/auth/login", json={"username": "demo_b", "password": "Wall2027!"})
            note = next(n for n in reopened.get("/api/board").json()["comments"] if n["id"] == id)
            self.assertEqual((note["text"], note["x"], note["y"], note["liked_by"]), ("PostgreSQL 数据保存", 700, 500, ["user-a"]))
            self.assertEqual(reopened.patch(f"/api/comments/{id}/content", json={"content_html": "<p>越权</p>", "content_version": 2}).status_code, 403)
            versions = {'content_version': 2, 'position_version': 2}
            self.assertEqual(reopened.request('DELETE', f'/api/comments/{id}', json=versions).status_code, 403)
            reopened.post('/api/auth/login', json={'username': 'demo_a', 'password': 'Wall2027!'})
            removed = reopened.request('DELETE', f'/api/comments/{id}', json=versions)
            self.assertEqual(removed.status_code, 200, removed.text)
            self.assertFalse(any(n['id'] == id for n in removed.json()['comments']))
        with TestClient(create_app(url)) as after_delete:
            after_delete.post('/api/auth/login', json={'username': 'demo_a', 'password': 'Wall2027!'})
            retried = after_delete.post('/api/comments', json={'request_id': id, 'content_html': '<p>延迟重试</p>', 'x': 330, 'y': 250})
            self.assertEqual(retried.status_code, 200)
            self.assertEqual(retried.json(), removed.json())
