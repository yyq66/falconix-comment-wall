import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.main import create_app


class RealtimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = create_app("sqlite:///" + (Path(cls.temp.name) / "realtime.db").as_posix(), seed_demo=False)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()
        cls.cookies = {}
        for username in ["demo_a", "demo_b"]:
            cls.client.cookies.clear()
            cls.client.post("/api/auth/login", json={"username": username, "password": "Wall2027!"})
            cls.cookies[username] = cls.client.cookies.get("wall_session")

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    def connect(self, username="demo_a"):
        return self.client.websocket_connect("/api/ws", headers={"cookie": f"wall_session={self.cookies[username]}"})

    def next_type(self, ws, type):
        for _ in range(10):
            message = ws.receive_json()
            if message["type"] == type:
                return message
        self.fail("Expected event was not delivered")

    def test_two_users_receive_created_edited_moved_liked_and_deleted_state(self):
        with self.connect("demo_a") as a, self.connect("demo_b") as b:
            self.next_type(a, "board")
            self.next_type(b, "board")
            self.client.cookies.clear()
            self.client.cookies.set("wall_session", self.cookies["demo_a"])
            id = str(uuid.uuid4())
            create = self.client.post("/api/comments", json={"request_id": id, "content_html": "<p>同步创建</p>", "x": 200, "y": 200})
            for ws in [a, b]:
                self.assertEqual(self.next_type(ws, "board")["board"]["revision"], create.json()["revision"])
            actions = [
                ("PATCH", f"/api/comments/{id}/content", {"content_html": "<p>同步编辑</p>", "content_version": 1}),
                ("PATCH", f"/api/comments/{id}/position", {"x": 600, "y": 400, "position_version": 1}),
                ("PUT", f"/api/comments/{id}/like", {"liked": True}),
            ]
            for method, url, data in actions:
                response = self.client.request(method, url, json=data)
                self.assertEqual(response.status_code, 200)
                for ws in [a, b]:
                    self.assertEqual(self.next_type(ws, "board")["board"], response.json())
            with self.connect("demo_b") as rejoined:
                state = self.next_type(rejoined, "board")["board"]
                note = next(n for n in state["comments"] if n["id"] == id)
                self.assertEqual((note["text"], note["x"], note["liked_by"]), ("同步编辑", 600, ["user-a"]))
            removed = self.client.request('DELETE', f'/api/comments/{id}', json={'content_version': 2, 'position_version': 2})
            self.assertEqual(removed.status_code, 200)
            for ws in [a, b]:
                snapshot = self.next_type(ws, 'board')['board']
                self.assertEqual(snapshot, removed.json())
                self.assertFalse(any(n['id'] == id for n in snapshot['comments']))
            with self.connect('demo_b') as rejoined:
                self.assertFalse(any(n['id'] == id for n in self.next_type(rejoined, 'board')['board']['comments']))

    def test_presence_deduplicates_tabs_and_keeps_user_until_last_tab_leaves(self):
        with self.connect() as a:
            self.next_type(a, "board")
            self.assertEqual(len(self.next_type(a, "presence")["members"]), 1)
            with self.connect() as tab:
                self.next_type(tab, "board")
                self.assertEqual(len(self.next_type(a, "presence")["members"]), 1)
                with self.connect("demo_b") as b:
                    self.next_type(b, "board")
                    self.assertEqual(len(self.next_type(a, "presence")["members"]), 2)
                self.assertEqual(len(self.next_type(a, "presence")["members"]), 1)
            self.assertEqual(len(self.next_type(a, "presence")["members"]), 1)
            a.send_text("ping")
            self.assertEqual(self.next_type(a, "pong"), {"type": "pong"})

    def test_unauthenticated_and_cross_origin_connections_rejected(self):
        self.client.cookies.clear()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/ws"):
                pass
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/ws", headers={"cookie": f'wall_session={self.cookies["demo_a"]}', "origin": "https://other.example"}):
                pass
