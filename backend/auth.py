import hashlib
import os
import secrets
import time
from collections import defaultdict, deque

import bcrypt
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from .database import LoginSession, User

COOKIE = "wall_session"
router = APIRouter(prefix="/api/auth", tags=["auth"])


def public_user(user: User):
    return {"id": user.id, "username": user.username, "name": user.name, "avatar": user.avatar}


def token_digest(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticated_user(app, token: str | None):
    if not token:
        return None
    with app.state.db() as db:
        session = db.get(LoginSession, token_digest(token))
        if session and session.expires > time.time():
            return db.get(User, session.user_id)
    return None


def require_user(request: Request):
    user = authenticated_user(request.app, request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(401, "请先登录")
    return user


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=72)
    remember: bool = False


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    attempts = request.app.state.login_attempts[ip]
    now = time.monotonic()
    while attempts and now - attempts[0] > 60:
        attempts.popleft()
    if len(attempts) >= 15:
        raise HTTPException(429, "尝试次数较多，请一分钟后重试")
    with request.app.state.db() as db:
        user = db.scalar(select(User).where(User.username == body.username.strip()))
        expected = user.password_hash if user else request.app.state.dummy_hash
        valid = bcrypt.checkpw(body.password.encode()[:72], expected.encode())
        if not user or not valid:
            attempts.append(now)
            raise HTTPException(401, "账号或密码错误")
        attempts.clear()
        old = request.cookies.get(COOKIE)
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(old)))
        db.execute(delete(LoginSession).where(LoginSession.expires < time.time()))
        token = secrets.token_urlsafe(32)
        lifetime = 30 * 86400 if body.remember else 86400
        db.add(LoginSession(token_hash=token_digest(token), user_id=user.id, expires=int(time.time()) + lifetime))
        db.commit()
        response.set_cookie(
            COOKIE, token, httponly=True, samesite="lax", path="/",
            secure=os.getenv("COOKIE_SECURE", "0") == "1",
            max_age=lifetime if body.remember else None,
        )
        return public_user(user)


@router.get("/me")
def me(request: Request):
    return public_user(require_user(request))


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with request.app.state.db() as db:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == token_digest(token)))
            db.commit()
        await request.app.state.hub.revoke(token_digest(token))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


def seed_users(db_factory):
    with db_factory() as db:
        if db.scalar(select(User.id).limit(1)):
            return
        password = os.getenv("DEMO_PASSWORD", "Wall2027!")
        password_hash = bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()
        for id, username, name, avatar in [
            ("user-a", "demo_a", "赵欣", "avatar-1.png"),
            ("user-b", "demo_b", "王美丽", "avatar-2.png"),
            ("user-c", "demo_c", "吴昌硕", "avatar-3.png"),
            ("user-d", "demo_d", "董其昌", "avatar-4.png"),
            ("user-e", "demo_e", "崔晓琳", "avatar-5.png"),
        ]:
            db.add(User(id=id, username=username, name=name, password_hash=password_hash, avatar="/assets/" + avatar))
        db.commit()
