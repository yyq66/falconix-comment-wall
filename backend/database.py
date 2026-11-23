import os
import time
from pathlib import Path

from sqlalchemy import ForeignKey, String, Text, create_engine, event
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


def open_database(url: str | None = None):
    url = url or os.getenv("DATABASE_URL")
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
