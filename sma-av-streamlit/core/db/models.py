# core/db/models.py
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r}>"

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    # Support BOTH storage modes:
    # - yaml_path: filesystem path to the YAML file
    # - yaml: inline YAML text (what your importer is passing)
    yaml_path = Column(String(1024), nullable=True)
    yaml = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Recipe id={self.id} name={self.name!r} path={self.yaml_path!r} yaml_len={len(self.yaml) if self.yaml else 0}>"

class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="succeeded")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    agent = relationship("Agent", lazy="joined")
    recipe = relationship("Recipe", lazy="joined")

    def __repr__(self) -> str:
        return f"<Run id={self.id} agent_id={self.agent_id} recipe_id={self.recipe_id} status={self.status!r}>"

Index("ix_runs_status_created", Run.status, Run.created_at.desc())

class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    messages = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ChatThread id={self.id} title={self.title!r} archived={self.archived}>"

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    thread = relationship("ChatThread", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} thread_id={self.thread_id} role={self.role!r}>"

__all__ = ["Base","Agent","Recipe","Run","ChatThread","ChatMessage"]
