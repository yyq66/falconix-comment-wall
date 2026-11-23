import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.database import LoginSession, User
from backend.main import create_app


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.app = create_app("sqlite:///" + (Path(cls.temp.name) / "test.db").as_posix())
        cls.client = TestClient(cls.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    def setUp(self):
        self.client.cookies.clear()

    def login(self, **extra):
        return self.client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!", **extra})

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_bad_password_and_unknown_account(self):
        for username in ["demo_a", "nonexistent"]:
            response = self.client.post("/api/auth/login", json={"username": username, "password": "incorrect"})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "账号或密码错误")

    def test_login_cookie_and_logout_revocation(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn("Max-Age", cookie)
        token = self.client.cookies.get("wall_session")
        self.assertEqual(self.client.get("/api/auth/me").json()["name"], "赵欣")
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.client.cookies.set("wall_session", token)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_remember_me_persists_cookie(self):
        response = self.login(remember=True)
        self.assertIn("Max-Age=2592000", response.headers["set-cookie"])

    def test_password_and_token_not_stored_as_plaintext(self):
        self.login()
        with self.app.state.db() as db:
            user = db.scalar(select(User).where(User.username == "demo_a"))
            self.assertTrue(user.password_hash.startswith("$2"))
            tokens = db.scalars(select(LoginSession.token_hash)).all()
            self.assertNotIn(self.client.cookies.get("wall_session"), tokens)

    def test_demo_avatar_assets_exist(self):
        public = Path(__file__).resolve().parents[1] / "frontend" / "public"
        with self.app.state.db() as db:
            for user in db.scalars(select(User)):
                self.assertTrue((public / user.avatar.lstrip("/")).is_file(), user.avatar)

    def test_no_registration_route_and_cross_site_denied(self):
        self.assertNotEqual(self.client.post("/api/auth/register", json={}).status_code, 200)
        response = self.client.post("/api/auth/login", json={"username": "demo_a", "password": "Wall2027!"}, headers={"Origin": "https://other.example"})
        self.assertEqual(response.status_code, 403)

    def test_expired_and_forged_sessions_are_rejected(self):
        self.login()
        with self.app.state.db() as db:
            for session in db.scalars(select(LoginSession)):
                session.expires = 0
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.client.cookies.clear()
        self.client.cookies.set("wall_session", "forged-session-value")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
