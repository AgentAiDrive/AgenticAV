from __future__ import annotations
import os
from sqlalchemy.orm import Session
from .session import engine, get_session
from .models import Base, Agent, Recipe, Tool
from .hotfix_migrations import ensure_recipes_yaml_column, ensure_agents_config_json_column

RECIPES_DIR = os.path.join(os.getcwd(), "recipes")

REGISTRY = {
    "slack-bot": {
        "description": "Slack bot MCP tool",
        "endpoint": "http://localhost:3001"
    },
    "zoom-admin": {
        "description": "Zoom admin MCP tool",
        "endpoint": "http://localhost:3002"
    },
    "servicenow": {
        "description": "ServiceNow MCP tool",
        "endpoint": "http://localhost:3003"
    },
}

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    ensure_recipes_yaml_column()
    ensure_agents_config_json_column()

def seed_demo():
    """Seed database with agents, recipes, and tools."""
    init_db()
    with get_session() as db:
        # Seed agents
        for name, domain in [
            ("Support", "support"),
            ("Events", "events"),
            ("Device Monitoring", "device-monitoring")
        ]:
            if not db.query(Agent).filter_by(name=name).first():
                db.add(Agent(name=name, domain=domain, config_json={}))

        # Seed recipes (from file names only)
        if os.path.isdir(RECIPES_DIR):
            for fn in os.listdir(RECIPES_DIR):
                if fn.endswith(".yaml"):
                    name = fn.replace(".yaml", "").replace("_", " ").title()
                    if not db.query(Recipe).filter_by(name=name).first():
                        db.add(Recipe(name=name, yaml_path=fn))

        # Seed tools
        for tool_name, cfg in REGISTRY.items():
            if not db.query(Tool).filter_by(name=tool_name).first():
                db.add(Tool(
                    name=tool_name,
                    description=cfg["description"],
                    endpoint=cfg["endpoint"]
                ))

        db.commit()
