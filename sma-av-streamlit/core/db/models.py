# --------------------------
id = Column(Integer, primary_key=True, autoincrement=True)
name = Column(String(255), nullable=False, unique=True, index=True)
description = Column(String(1024), nullable=True)
endpoint = Column(String(1024), nullable=True)
created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


__all__ = ["Base", "Agent", "Recipe", "Run", "ChatThread", "ChatMessage", "Tool"]
