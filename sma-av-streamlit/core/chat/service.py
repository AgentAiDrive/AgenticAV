# core/chat/service.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, declarative_base
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, ForeignKey, DateTime
)

# --- Fallback ORM (used only if your core.db.models doesn't define ChatThread/ChatMessage)
Base = declarative_base()

class _FBChatThread(Base):  # fallback table
    __tablename__ = "chat_threads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class _FBChatMessage(Base):  # fallback table
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)       # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

__all__ = [
    "create_thread",
    "list_threads",
    "add_message",
    "get_messages",
    "archive_thread",
    "clear_thread",
]

# -------- internals -----------------------------------------------------------
def _have_attr(model, name: str) -> bool:
    try:
        return name in model.__table__.columns.keys()
    except Exception:
        return hasattr(model, name)

def _get_models(db: Session) -> Tuple[type, type, bool]:
    """
    Returns (ChatThreadModel, ChatMessageModel, used_fallback: bool).
    If your project defines core.db.models.ChatThread/ChatMessage, we use them.
    Otherwise we create minimal fallback tables on the bound engine.
    """
    try:
        from core.db.models import ChatThread as MThread, ChatMessage as MMessage  # type: ignore
        return MThread, MMessage, False
    except Exception:
        # Create fallback tables if missing
        bind = db.get_bind()
        Base.metadata.create_all(bind)
        return _FBChatThread, _FBChatMessage, True

# -------- public API ----------------------------------------------------------
def create_thread(db: Session, title: str):
    T, _, _ = _get_models(db)
    # Construct with only supported columns
    kwargs = {}
    if _have_attr(T, "title"): kwargs["title"] = title
    if _have_attr(T, "name") and "title" not in kwargs: kwargs["name"] = title  # alt naming
    obj = T(**kwargs)  # type: ignore[arg-type]
    # Defaults if attributes exist
    if hasattr(obj, "archived") and getattr(obj, "archived", None) is None:
        setattr(obj, "archived", False)
    if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
        setattr(obj, "created_at", datetime.utcnow())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_threads(db: Session):
    T, _, _ = _get_models(db)
    q = db.query(T)
    if _have_attr(T, "archived"):
        q = q.filter(getattr(T, "archived") == False)  # noqa: E712
    if _have_attr(T, "created_at"):
        q = q.order_by(getattr(T, "created_at").desc())
    return list(q.all())

def add_message(db: Session, thread_id: int, role: str, content: str):
    _, M, _ = _get_models(db)
    # Support alternate FK names if your model differs
    kwargs = {"role": role, "content": content}
    if _have_attr(M, "thread_id"):
        kwargs["thread_id"] = thread_id
    elif _have_attr(M, "chat_thread_id"):
        kwargs["chat_thread_id"] = thread_id
    obj = M(**kwargs)  # type: ignore[arg-type]
    if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
        setattr(obj, "created_at", datetime.utcnow())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_messages(db: Session, thread_id: int) -> List[dict]:
    _, M, _ = _get_models(db)
    # Build query by whichever FK column exists
    q = db.query(M)
    if _have_attr(M, "thread_id"):
        q = q.filter(getattr(M, "thread_id") == thread_id)
    elif _have_attr(M, "chat_thread_id"):
        q = q.filter(getattr(M, "chat_thread_id") == thread_id)
    if _have_attr(M, "created_at"):
        q = q.order_by(getattr(M, "created_at").asc())
    rows = q.all()
    out: List[dict] = []
    for r in rows:
        role = getattr(r, "role", "assistant")
        content = getattr(r, "content", "")
        out.append({"role": role, "content": content})
    return out

def archive_thread(db: Session, thread_id: int) -> None:
    T, _, _ = _get_models(db)
    obj = db.query(T).get(thread_id)  # type: ignore[arg-type]
    if not obj:
        return
    if hasattr(obj, "archived"):
        setattr(obj, "archived", True)
    db.commit()

def clear_thread(db: Session, thread_id: int) -> None:
    _, M, _ = _get_models(db)
    q = db.query(M)
    if _have_attr(M, "thread_id"):
        q = q.filter(getattr(M, "thread_id") == thread_id)
    elif _have_attr(M, "chat_thread_id"):
        q = q.filter(getattr(M, "chat_thread_id") == thread_id)
    for m in q.all():
        db.delete(m)
    db.commit()
