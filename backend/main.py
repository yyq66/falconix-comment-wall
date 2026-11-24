import asyncio
import os
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import bcrypt
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .auth import router as auth_router, seed_users
from .database import Base, open_database
from .comments import initialize_wall, router as comments_router
from .realtime import Hub, router as realtime_router
from .sentiment import get_sentiment_service


def create_app(database_url: str | None = None, seed_demo: bool | None = None, *, sentiment_service=None):
    engine, factory = open_database(database_url)
    sentiment = sentiment_service or get_sentiment_service()

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        seed_users(factory)
        await asyncio.to_thread(initialize_wall, factory, demo=seed_demo if seed_demo is not None else os.getenv("SEED_DEMO", "1") == "1", sentiment_service=sentiment)
        yield
        engine.dispose()

    application = FastAPI(title="实时评论墙", version="0.1.0", lifespan=lifespan)
    application.state.db = factory
    application.state.sentiment = sentiment
    application.state.mutation_lock = asyncio.Lock()
    application.state.hub = Hub()
    application.state.login_attempts = defaultdict(deque)
    application.state.dummy_hash = bcrypt.hashpw(b"invalid-password", bcrypt.gensalt()).decode()

    @application.middleware("http")
    async def same_origin(request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and origin:
            if urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "不允许跨站操作"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.get("/api/health")
    def health():
        try:
            with factory() as db:
                db.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    application.include_router(auth_router)
    application.include_router(comments_router)
    application.include_router(realtime_router)
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return application


app = create_app()
