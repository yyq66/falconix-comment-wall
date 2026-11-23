import os
import time
from pathlib import Path

from sqlalchemy import BigInteger, ForeignKey, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    avatar: Mapped[str] = mapped_column(String(200), default="")


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires: Mapped[int] = mapped_column(default=lambda: int(time.time()) + 86400)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    content_html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    x: Mapped[float] = mapped_column(default=100.0)
    y: Mapped[float] = mapped_column(default=150.0)
    rotation: Mapped[float] = mapped_column(default=0.0)
    color: Mapped[str] = mapped_column(String(20), default="#ebe0ff")
    created_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger)
    content_version: Mapped[int] = mapped_column(default=1)
    position_version: Mapped[int] = mapped_column(default=1)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")


class WallState(Base):
    __tablename__ = "wall_state"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    revision: Mapped[int] = mapped_column(default=0)


class Like(Base):
    __tablename__ = "likes"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    comment_id: Mapped[str] = mapped_column(ForeignKey("comments.id"), primary_key=True)


def open_database(url: str | None = None):
    url = url or os.getenv("DATABASE_URL")
    if os.getenv("APP_ENV") == "production" and (not url or not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))):
        raise RuntimeError("生产部署必须设置持久化 PostgreSQL DATABASE_URL，避免临时磁盘丢失数据")
    if not url:
        directory = Path(__file__).resolve().parents[1] / "data"
        directory.mkdir(exist_ok=True)
        url = "sqlite:///" + (directory / "wall.db").as_posix()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    sqlite = url.startswith("sqlite")
    engine = create_engine(
        url, pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 20} if sqlite else {},
    )
    if sqlite:
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
    return engine, sessionmaker(engine, expire_on_commit=False)
