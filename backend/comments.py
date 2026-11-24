import asyncio
import json
import math
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from .auth import public_user, require_user
from .content import clean_content
from .database import Comment, DeletedComment, Like, SentimentAnnotation, User, WallState
from .sentiment import get_sentiment_service

router = APIRouter(prefix="/api", tags=["comments"])
COLORS = ["#ebe0ff", "#dffce5", "#ffdee7", "#ffead2", "#cce9ff", "#fff7d1"]


class ContentBody(BaseModel):
    content_html: str = Field(min_length=1, max_length=20000)


class CreateBody(ContentBody):
    x: float = Field(ge=0, le=5000)
    y: float = Field(ge=80, le=5000)
    request_id: str = Field(min_length=16, max_length=40, pattern=r"^[a-zA-Z0-9-]+$")

    @field_validator("x", "y")
    @classmethod
    def finite_position(cls, value):
        if not math.isfinite(value):
            raise ValueError("无效的位置")
        return value


class EditBody(ContentBody):
    content_version: int = Field(ge=1)


class MoveBody(BaseModel):
    x: float = Field(ge=0, le=5000, allow_inf_nan=False)
    y: float = Field(ge=80, le=5000, allow_inf_nan=False)
    position_version: int = Field(ge=1)


class LikeBody(BaseModel):
    liked: bool


class DeleteBody(BaseModel):
    content_version: int = Field(ge=1)
    position_version: int = Field(ge=1)


def board_snapshot(app):
    with app.state.db() as db:
        authors = {user.id: public_user(user) for user in db.scalars(select(User))}
        comments = db.scalars(select(Comment).order_by(Comment.created_at, Comment.id)).all()
        annotations = {item.comment_id: item for item in db.scalars(select(SentimentAnnotation))}
        state = db.get(WallState, 1)
        likes = {}
        for like in db.scalars(select(Like)):
            likes.setdefault(like.comment_id, []).append(like.user_id)
        return {"revision": state.revision if state else 0, "comments": [
            {"id": c.id, "author": authors[c.user_id], "content_html": c.content_html, "text": c.text,
             "x": c.x, "y": c.y, "rotation": c.rotation, "color": c.color,
             "created_at": c.created_at, "updated_at": c.updated_at,
             "content_version": c.content_version, "position_version": c.position_version,
             "sentiment": c.sentiment,
             "sentiment_source": annotations[c.id].source if c.id in annotations else 'legacy',
             "sentiment_confidence": annotations[c.id].confidence if c.id in annotations else None,
             "liked_by": sorted(likes.get(c.id, []))} for c in comments
        ]}


def bump_revision(db):
    state = db.get(WallState, 1)
    state.revision += 1


def store_sentiment(db, comment, result, signature):
    comment.sentiment = result.label
    annotation = db.get(SentimentAnnotation, comment.id)
    if not annotation:
        annotation = SentimentAnnotation(comment_id=comment.id)
        db.add(annotation)
    annotation.content_version = comment.content_version or 1
    annotation.signature = signature
    annotation.source = result.source
    annotation.confidence = result.confidence


async def publish_board(request):
    snapshot = board_snapshot(request.app)
    await request.app.state.hub.broadcast({"type": "board", "board": snapshot})
    return snapshot


@router.get("/board")
async def get_board(request: Request):
    require_user(request)
    async with request.app.state.mutation_lock:
        return board_snapshot(request.app)


@router.post("/comments")
async def create_comment(body: CreateBody, request: Request):
    user = require_user(request)
    content_html, text = clean_content(body.content_html)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            previous = db.get(Comment, body.request_id) or db.get(DeletedComment, body.request_id)
            if previous:
                if previous.user_id != user.id:
                    raise HTTPException(409, "请求标识已被使用，请重试")
                return board_snapshot(request.app)
    sentiment = await asyncio.to_thread(request.app.state.sentiment.classify, text)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            deleted = db.get(DeletedComment, body.request_id)
            if deleted:
                if deleted.user_id != user.id:
                    raise HTTPException(409, "请求标识已被使用，请重试")
                return board_snapshot(request.app)
            existing = db.get(Comment, body.request_id)
            if existing:
                if existing.user_id != user.id:
                    raise HTTPException(409, "请求标识已被使用，请重试")
                return board_snapshot(request.app)
            if len(db.scalars(select(Comment.id)).all()) >= 1000:
                raise HTTPException(409, "评论墙已满，暂时无法新增")
            now = int(time.time() * 1000)
            seed = sum(body.request_id.encode())
            comment = Comment(id=body.request_id, user_id=user.id, content_html=content_html, text=text,
                           x=body.x, y=body.y, rotation=[-10, -6, 6, 10][seed % 4],
                           color=COLORS[seed % len(COLORS)], sentiment=sentiment.label, created_at=now, updated_at=now)
            db.add(comment)
            store_sentiment(db, comment, sentiment, request.app.state.sentiment.signature)
            bump_revision(db)
            db.commit()
        return await publish_board(request)


@router.patch("/comments/{comment_id}/content")
async def edit_comment(comment_id: str, body: EditBody, request: Request):
    user = require_user(request)
    content_html, text = clean_content(body.content_html)
    with request.app.state.db() as db:
        comment = db.get(Comment, comment_id)
        if not comment:
            raise HTTPException(404, "贴纸不存在")
        if comment.user_id != user.id:
            raise HTTPException(403, "只能编辑自己的贴纸")
        if comment.content_version != body.content_version:
            raise HTTPException(409, "贴纸已在其他窗口修改，请重新打开后编辑")
    sentiment = await asyncio.to_thread(request.app.state.sentiment.classify, text)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            comment = db.get(Comment, comment_id)
            if not comment:
                raise HTTPException(404, "贴纸不存在")
            if comment.user_id != user.id:
                raise HTTPException(403, "只能编辑自己的贴纸")
            if comment.content_version != body.content_version:
                raise HTTPException(409, "贴纸已在其他窗口修改，请重新打开后编辑")
            comment.content_html = content_html
            comment.text = text
            comment.content_version += 1
            store_sentiment(db, comment, sentiment, request.app.state.sentiment.signature)
            comment.updated_at = int(time.time() * 1000)
            bump_revision(db)
            db.commit()
        return await publish_board(request)


def initialize_wall(factory, demo=True, sentiment_service=None):
    sentiment_service = sentiment_service or get_sentiment_service()
    with factory() as db:
        if db.get(WallState, 1):
            changed = False
            annotations = {item.comment_id: item for item in db.scalars(select(SentimentAnnotation))}
            for comment in db.scalars(select(Comment)):
                annotation = annotations.get(comment.id)
                if annotation and annotation.signature == sentiment_service.signature and annotation.content_version == comment.content_version and annotation.source != 'unavailable' and (not sentiment_service.api_enabled or annotation.source == 'api'):
                    continue
                result = sentiment_service.classify(comment.text)
                store_sentiment(db, comment, result, sentiment_service.signature)
                changed = True
            if changed:
                bump_revision(db)
                db.commit()
            return
        db.add(WallState(id=1, revision=0))
        if demo:
            source = Path(__file__).with_name("seed_comments.json")
            if source.is_file():
                for i, item in enumerate(json.loads(source.read_text(encoding="utf-8"))):
                    html, text = clean_content("<p>" + item["text"] + "</p>")
                    now = int(time.time() * 1000) - (8-i) * 180000
                    result = sentiment_service.classify(text)
                    comment = Comment(id=f"seed-comment-{i+1:04}", user_id=item["user_id"], content_html=html, text=text,
                                   x=item["x"], y=item["y"], rotation=item["rotation"], color=item["color"], sentiment=result.label, created_at=now, updated_at=now)
                    db.add(comment)
                    store_sentiment(db, comment, result, sentiment_service.signature)
        db.commit()


@router.patch("/comments/{comment_id}/position")
async def move_comment(comment_id: str, body: MoveBody, request: Request):
    user = require_user(request)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            comment = db.get(Comment, comment_id)
            if not comment:
                raise HTTPException(404, "贴纸不存在")
            if comment.user_id != user.id:
                raise HTTPException(403, "只能移动自己的贴纸")
            if comment.position_version != body.position_version:
                raise HTTPException(409, "位置已在其他窗口改变，已恢复最新位置")
            comment.x = body.x
            comment.y = body.y
            comment.position_version += 1
            comment.updated_at = int(time.time() * 1000)
            bump_revision(db)
            db.commit()
        return await publish_board(request)


@router.put("/comments/{comment_id}/like")
async def like_comment(comment_id: str, body: LikeBody, request: Request):
    user = require_user(request)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            if not db.get(Comment, comment_id):
                raise HTTPException(404, "贴纸不存在")
            like = db.get(Like, (user.id, comment_id))
            if body.liked and not like:
                db.add(Like(user_id=user.id, comment_id=comment_id))
                bump_revision(db)
            elif not body.liked and like:
                db.delete(like)
                bump_revision(db)
            db.commit()
        return await publish_board(request)


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, body: DeleteBody, request: Request):
    user = require_user(request)
    async with request.app.state.mutation_lock:
        with request.app.state.db() as db:
            deleted = db.get(DeletedComment, comment_id)
            if deleted:
                if deleted.user_id != user.id:
                    raise HTTPException(403, "只能删除自己的贴纸")
                return board_snapshot(request.app)
            comment = db.get(Comment, comment_id)
            if not comment:
                raise HTTPException(404, "贴纸不存在")
            if comment.user_id != user.id:
                raise HTTPException(403, "只能删除自己的贴纸")
            if (comment.content_version, comment.position_version) != (body.content_version, body.position_version):
                raise HTTPException(409, "贴纸已在其他窗口更新，请重新打开确认后删除")
            db.execute(delete(Like).where(Like.comment_id == comment_id))
            db.delete(comment)
            db.add(DeletedComment(id=comment_id, user_id=user.id, deleted_at=int(time.time() * 1000)))
            bump_revision(db)
            db.commit()
        return await publish_board(request)
