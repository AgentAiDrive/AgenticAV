"""Utilities for one-off schema hotfix migrations.

These helpers run lightweight ALTER TABLE statements against the
application database so we can evolve the schema without requiring a
full migration framework.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

__all__ = [
    "ensure_recipes_yaml_column",
    "ensure_agent_config_json_column",
    "run_hotfix_migrations",
]


def ensure_recipes_yaml_column(engine: Engine) -> None:
    """Add recipes.yaml column if missing (backwards compatibility)."""
    insp = inspect(engine)
    if not insp.has_table("recipes"):
        return

    cols = {c["name"] for c in insp.get_columns("recipes")}
    if "yaml" in cols:
        return

    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE recipes ADD COLUMN yaml TEXT"))
    except SQLAlchemyError:
        # Some SQLite builds may not support ALTER ADD COLUMN in this context.
        # In that case, the operator must apply the change manually.
        pass


def ensure_agent_config_json_column(engine: Engine) -> None:
    """Ensure the agents table has the config_json column."""
    insp = inspect(engine)
    if not insp.has_table("agents"):
        return

    cols = {c["name"] for c in insp.get_columns("agents")}
    if "config_json" in cols:
        return

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE agents "
                    "ADD COLUMN config_json JSON NOT NULL DEFAULT '{}'"
                )
            )
            # Ensure any pre-existing rows have a JSON object value set.
            conn.execute(
                text(
                    "UPDATE agents SET config_json='{}' "
                    "WHERE config_json IS NULL"
                )
            )
    except SQLAlchemyError:
        # If the ALTER TABLE fails (older SQLite builds), leave the database
        # untouched; the operator will need to handle the migration manually.
        pass


def run_hotfix_migrations(engine: Engine) -> None:
    """Run all hotfix migrations against the provided engine."""
    ensure_recipes_yaml_column(engine)
    ensure_agent_config_json_column(engine)


if __name__ == "__main__":
    from core.db.session import engine

    run_hotfix_migrations(engine)
    print("Hotfix migrations completed.")
