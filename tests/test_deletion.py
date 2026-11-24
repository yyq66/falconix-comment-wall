import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.database import Comment, DeletedComment, Like
from backend.main import create_app


class DeletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.url = 'sqlite:///' + (Path(cls.temp.name) / 'deletion.db').as_posix()
        cls.app = create_app(cls.url, seed_demo=False)
        cls.client = TestClient(cls.app)
        cls.client.__enter__()
        cls.cookies = {}
        for name in ['demo_a', 'demo_b']:
            cls.client.cookies.clear()
            cls.client.post('/api/auth/login', json={'username': name, 'password': 'Wall2027!'})
            cls.cookies[name] = dict(cls.client.cookies)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    def as_user(self, name):
        self.client.cookies.clear()
        self.client.cookies.update(self.cookies[name])

    def setUp(self):
        self.as_user('demo_a')
        self.id = str(uuid.uuid4())
        self.body = {'request_id': self.id, 'content_html': '<p>删除测试</p>', 'x': 200, 'y': 200}
        self.client.post('/api/comments', json=self.body)

    def remove(self, **versions):
        return self.client.request('DELETE', f'/api/comments/{self.id}', json={'content_version': 1, 'position_version': 1, **versions})

    def test_requires_author_and_authentication(self):
        before = self.client.get('/api/board').json()
        self.as_user('demo_b')
        self.assertEqual(self.remove().status_code, 403)
        self.assertEqual(self.client.get('/api/board').json(), before)
        self.client.cookies.clear()
        self.assertEqual(self.remove().status_code, 401)
        self.as_user('demo_a')
        self.assertEqual(self.client.request('DELETE', '/api/comments/missing', json={'content_version': 1, 'position_version': 1}).status_code, 404)

    def test_removes_likes_and_is_idempotent(self):
        self.client.put(f'/api/comments/{self.id}/like', json={'liked': True})
        self.as_user('demo_b')
        self.client.put(f'/api/comments/{self.id}/like', json={'liked': True})
        self.as_user('demo_a')
        before = self.client.get('/api/board').json()
        removed = self.remove()
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()['revision'], before['revision'] + 1)
        self.assertFalse(any(n['id'] == self.id for n in removed.json()['comments']))
        with self.app.state.db() as db:
            self.assertIsNone(db.get(Comment, self.id))
            self.assertEqual(list(db.scalars(select(Like).where(Like.comment_id == self.id))), [])
            self.assertEqual(db.get(DeletedComment, self.id).user_id, 'user-a')
        self.assertEqual(self.remove().json(), removed.json())
        self.as_user('demo_b')
        self.assertEqual(self.remove().status_code, 403)
        self.assertEqual(self.client.put(f'/api/comments/{self.id}/like', json={'liked': True}).status_code, 404)

    def test_updated_content_or_position_requires_new_confirmation(self):
        self.client.patch(f'/api/comments/{self.id}/content', json={'content_html': '<p>其他窗口的新内容</p>', 'content_version': 1})
        self.assertEqual(self.remove().status_code, 409)
        self.client.patch(f'/api/comments/{self.id}/position', json={'x': 400, 'y': 300, 'position_version': 1})
        self.assertEqual(self.remove(content_version=2).status_code, 409)
        self.assertEqual(self.remove(content_version=2, position_version=2).status_code, 200)

    def test_restart_and_delayed_create_retry_cannot_restore_deleted_note(self):
        removed = self.remove().json()
        with TestClient(create_app(self.url, seed_demo=False)) as reopened:
            reopened.post('/api/auth/login', json={'username': 'demo_a', 'password': 'Wall2027!'})
            self.assertEqual(reopened.get('/api/board').json(), removed)
            self.assertEqual(reopened.post('/api/comments', json=self.body).json(), removed)
            self.assertEqual(reopened.patch(f'/api/comments/{self.id}/content', json={'content_html': '<p>旧窗口保存</p>', 'content_version': 1}).status_code, 404)
            self.assertEqual(reopened.patch(f'/api/comments/{self.id}/position', json={'x': 400, 'y': 300, 'position_version': 1}).status_code, 404)
            reopened.post('/api/auth/login', json={'username': 'demo_b', 'password': 'Wall2027!'})
            self.assertEqual(reopened.post('/api/comments', json=self.body).status_code, 409)
