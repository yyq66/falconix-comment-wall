"""Verify a deployed HTTPS app with two independent users and real WebSockets.

Creates one clearly marked acceptance comment and saves its expected state locally
so --verify-only can check persistence after a service restart or deployment.
"""
import argparse
import json
import os
import time
import uuid
from contextlib import ExitStack
from pathlib import Path

import httpx
from websockets.sync.client import connect


parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--verify-only", action="store_true")
parser.add_argument("--state", default="output/online-acceptance.json")
args = parser.parse_args()
base = args.url.rstrip("/")
proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
state_path = Path(args.state)


def checked(response):
    response.raise_for_status()
    return response.json()


def note(board, id):
    return next(n for n in board["comments"] if n["id"] == id)


def receive(ws, kind, revision=None):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        message = json.loads(ws.recv(timeout=max(.1, deadline-time.monotonic())))
        if message["type"] == kind and (revision is None or message["board"]["revision"] >= revision):
            return message
    raise AssertionError("Expected realtime event was not received")


with ExitStack() as stack:
    clients = [stack.enter_context(httpx.Client(base_url=base, proxy=proxy, timeout=40)) for _ in range(2)]
    a, b = clients
    assert checked(a.get("/api/health"))["status"] == "ok"
    assert a.get("/api/board").status_code == 401
    for client, username in zip(clients, ["demo_a", "demo_b"]):
        checked(client.post("/api/auth/login", json={"username": username, "password": "Wall2027!"}))

    if args.verify_only:
        expected = json.loads(state_path.read_text(encoding="utf-8"))
        for client in clients:
            saved = note(checked(client.get("/api/board")), expected["id"])
            for key, value in expected["fields"].items():
                assert saved[key] == value, f"Persisted {key} differs"
        print("PASS: deployed service retained content, coordinates, sentiment and likes")
    else:
        sockets = [stack.enter_context(connect(
            base.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws",
            origin=base, additional_headers={"Cookie": "; ".join(f"{k}={v}" for k, v in client.cookies.items())},
            proxy=proxy, open_timeout=40, close_timeout=5,
        )) for client in clients]
        for ws in sockets:
            receive(ws, "board")
            members = receive(ws, "presence")["members"]
        assert {u["id"] for u in members} >= {"user-a", "user-b"}
        id = str(uuid.uuid4())
        board = checked(a.post("/api/comments", json={"request_id": id, "content_html": "<p><strong>上线验收</strong>：感谢大家的建议，实时评论墙很好用。</p>", "x": 250, "y": 850}))
        for ws in sockets:
            assert note(receive(ws, "board", board["revision"])["board"], id)["text"].startswith("上线验收")
        edited = "<p><strong>上线验收已通过</strong>：发布、编辑、移动和点赞支持多人实时同步。</p>"
        board = checked(a.patch(f"/api/comments/{id}/content", json={"content_html": edited, "content_version": 1}))
        for ws in sockets:
            assert note(receive(ws, "board", board["revision"])["board"], id)["content_html"] == edited
        assert b.patch(f"/api/comments/{id}/content", json={"content_html": "<p>越权</p>", "content_version": 2}).status_code == 403
        assert b.patch(f"/api/comments/{id}/position", json={"x": 500, "y": 500, "position_version": 1}).status_code == 403
        board = checked(a.patch(f"/api/comments/{id}/position", json={"x": 300, "y": 850, "position_version": 1}))
        for ws in sockets:
            assert note(receive(ws, "board", board["revision"])["board"], id)["x"] == 300
        board = checked(b.put(f"/api/comments/{id}/like", json={"liked": True}))
        for ws in sockets:
            assert note(receive(ws, "board", board["revision"])["board"], id)["liked_by"] == ["user-b"]
        again = checked(b.put(f"/api/comments/{id}/like", json={"liked": True}))
        assert note(again, id)["liked_by"] == ["user-b"]
        final = note(again, id)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"url": base, "id": id, "fields": {k: final[k] for k in ["content_html", "text", "x", "y", "sentiment", "liked_by"]}}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("PASS: HTTPS login, two-user WebSockets, create/edit/move/likes, author permissions and idempotence")
    for client in clients:
        checked(client.post("/api/auth/logout"))
